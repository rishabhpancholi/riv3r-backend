import time
from datetime import datetime

import pytest

from app.utils import jwt

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def test_login_refresh_logout_with_real_storage(live_auth):
    client = live_auth.client
    login = await client.post("/api/auth/login", json=live_auth.credentials)
    assert login.status_code == 200
    access = client.cookies["access_token"]
    refresh = client.cookies["refresh_token"]
    live_auth.redis.keys.add(jwt.hash_token(access))
    assert (await client.get("/api/auth/me")).status_code == 200

    stored = (
        await live_auth.db.table("refresh_tokens")
        .select("expires_at")
        .eq("refresh_token", jwt.hash_token(refresh))
        .execute()
    )
    assert (
        datetime.fromisoformat(stored.data[0]["expires_at"]).timestamp()
        == jwt.decode_token(refresh)["exp"]
    )

    assert (await client.post("/api/auth/refresh")).status_code == 204
    fresh = client.cookies["access_token"]
    live_auth.redis.keys.add(jwt.hash_token(fresh))
    assert fresh != access
    assert (await client.get("/api/auth/me")).status_code == 200
    ttl = await live_auth.redis.client.ttl(jwt.hash_token(access))
    remaining = jwt.decode_token(access)["exp"] - time.time()
    assert 0 < ttl <= remaining + 1
    assert ttl >= remaining - 1

    client.cookies.clear()
    client.cookies.set("access_token", access)
    assert (await client.get("/api/auth/me")).status_code == 401

    client.cookies.clear()
    client.cookies.set("access_token", fresh)
    client.cookies.set("refresh_token", refresh)
    assert (await client.post("/api/auth/logout")).status_code == 204
    client.cookies.set("access_token", fresh)
    client.cookies.set("refresh_token", refresh)
    assert (await client.get("/api/auth/me")).status_code == 401
    assert (await client.post("/api/auth/refresh")).status_code == 401
    logs = (
        await live_auth.db.table("audit_logs")
        .select("task_type")
        .eq("user_id", live_auth.user_id)
        .execute()
    )
    assert {row["task_type"] for row in logs.data} >= {"login", "refresh", "logout"}


async def test_refresh_after_access_expiry_with_real_storage(live_auth):
    client = live_auth.client
    assert (
        await client.post("/api/auth/login", json=live_auth.credentials)
    ).status_code == 200
    refresh = client.cookies["refresh_token"]
    expired = jwt.jwt.encode(
        {
            "id": live_auth.user_id,
            "type": "access",
            "iat": 1,
            "exp": 2,
            "jti": "expired-test-access",
        },
        jwt.settings.jwt_secret_key,
        algorithm=jwt.settings.jwt_algorithm,
    )
    client.cookies.clear()
    client.cookies.set("access_token", expired)
    client.cookies.set("refresh_token", refresh)
    assert (await client.get("/api/auth/me")).status_code == 401
    assert (await client.post("/api/auth/refresh")).status_code == 204
    fresh = client.cookies["access_token"]
    assert jwt.decode_token(fresh)["exp"] > time.time()
    assert (await client.get("/api/auth/me")).status_code == 200
