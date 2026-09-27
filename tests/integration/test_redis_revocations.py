import asyncio
import time
from uuid import uuid4

import pytest

from app.repositories.redis import RedisAccessTokenRevocationStore
from app.utils.jwt import hash_token

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def test_revocation_lives_until_expiry_then_disappears(live_redis):
    token = f"integration-token-{uuid4()}"
    digest = hash_token(token)
    live_redis.keys.add(digest)
    store = RedisAccessTokenRevocationStore(live_redis.client)
    expiry = int(time.time()) + 2
    await store.revoke(token, expires_at=expiry)
    assert await store.is_revoked(token)
    assert 0 < await live_redis.client.ttl(digest) <= 2
    assert await live_redis.client.get(digest) == b"blacklisted"
    await asyncio.sleep(2.1)
    assert not await store.is_revoked(token)


async def test_legacy_raw_keys_are_still_recognized(live_redis):
    token = f"integration-legacy-{uuid4()}"
    live_redis.keys.add(token)
    await live_redis.client.setex(token, 30, "blacklisted")
    assert await RedisAccessTokenRevocationStore(live_redis.client).is_revoked(token)
