from fastapi import Request
from redis.asyncio import Redis

_FIXED_WINDOW_SCRIPT = """
local current = redis.call('INCR', KEYS[1])
if current == 1 then
  redis.call('EXPIRE', KEYS[1], ARGV[1])
end
return current
"""


def client_ip(request: Request, trust_forwarded_headers: bool = False) -> str:
    """Best-effort real client IP.

    X-Forwarded-For / X-Real-IP are only trusted when the deployment
    guarantees clients cannot spoof them (i.e. a reverse proxy strips
    incoming values before forwarding). Blindly trusting them lets an
    attacker rotate the header and bypass the rate limit, so they are
    ignored unless trust_forwarded_headers is enabled.
    """
    if trust_forwarded_headers:
        xff = request.headers.get("x-forwarded-for")
        if xff:
            first = xff.split(",")[0].strip()
            if first:
                return first
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip.strip()
    return request.client.host if request.client else "unknown"


async def check_rate_limit(
    cache: Redis, key: str, max_requests: int, window_seconds: int
) -> bool:
    """Returns True if request is allowed, False if rate limited.

    Increment and TTL are applied atomically in a single Lua script. The
    TTL is set only when the counter is created, so this is a fixed window
    that starts from the first request instead of a sliding window that is
    extended by every request.
    """
    current = await cache.eval(
        _FIXED_WINDOW_SCRIPT, 1, f"ratelimit:{key}", window_seconds
    )
    return current <= max_requests
