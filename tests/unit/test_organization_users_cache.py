import json
from unittest.mock import AsyncMock

import pytest

from app.repositories.redis import RedisOrganizationUsersCache


@pytest.mark.asyncio
async def test_organization_users_cache_reads_json():
    redis = AsyncMock()
    redis.get.return_value = json.dumps([{"id": "user-a"}]).encode()
    cache = RedisOrganizationUsersCache(redis, ttl=300)

    assert await cache.get("org-a") == [{"id": "user-a"}]
    redis.get.assert_awaited_once_with("org_users:org-a")


@pytest.mark.asyncio
@pytest.mark.parametrize("cached", [None, b"not-json", b"{}"])
async def test_organization_users_cache_treats_invalid_values_as_misses(cached):
    redis = AsyncMock()
    redis.get.return_value = cached

    assert await RedisOrganizationUsersCache(redis, ttl=300).get("org-a") is None


@pytest.mark.asyncio
async def test_organization_users_cache_writes_with_configured_ttl():
    redis = AsyncMock()
    cache = RedisOrganizationUsersCache(redis, ttl=123)

    await cache.set("org-a", [{"id": "user-a"}])

    redis.setex.assert_awaited_once_with(
        "org_users:org-a", 123, '[{"id": "user-a"}]'
    )


@pytest.mark.asyncio
async def test_organization_users_cache_fails_open():
    redis = AsyncMock()
    redis.get.side_effect = RuntimeError("redis unavailable")
    redis.setex.side_effect = RuntimeError("redis unavailable")
    cache = RedisOrganizationUsersCache(redis, ttl=300)

    assert await cache.get("org-a") is None
    await cache.set("org-a", [])
