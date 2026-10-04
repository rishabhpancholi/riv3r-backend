import json
from unittest.mock import AsyncMock

import pytest

from app.repositories.redis import RedisProjectCache


@pytest.mark.asyncio
async def test_project_detail_cache_round_trip():
    redis = AsyncMock()
    redis.get.side_effect = [b"2", json.dumps({"id": "project-a"})]
    cache = RedisProjectCache(redis, ttl=123)

    key, value = await cache.get_detail("project-a")
    assert key == "project:project-a:2"
    assert value == {"id": "project-a"}
    await cache.set_detail(key, {"id": "project-a"})

    assert [call.args[0] for call in redis.get.await_args_list] == [
        "project:version:project-a",
        "project:project-a:2",
    ]
    redis.setex.assert_awaited_once_with(
        "project:project-a:2", 123, json.dumps({"id": "project-a"})
    )


@pytest.mark.asyncio
async def test_project_list_cache_uses_scope_version_and_canonical_query():
    redis = AsyncMock()
    redis.get.side_effect = [b"4", json.dumps({"items": [], "total": 0})]
    cache = RedisProjectCache(redis, ttl=300)

    _, result = await cache.get_list(
        "org:org-a", {"page": 1, "status": "draft"}
    )

    assert result == {"items": [], "total": 0}
    list_key = redis.get.await_args_list[1].args[0]
    assert list_key.startswith("projects:list:org:org-a:4:")


@pytest.mark.asyncio
async def test_project_cache_invalidation_advances_org_and_global_versions():
    redis = AsyncMock()
    redis.get.return_value = b"3"
    cache = RedisProjectCache(redis, ttl=300)

    await cache.invalidate("project-a", "org-a")

    redis.delete.assert_awaited_once_with("project:project-a:3")
    assert [call.args[0] for call in redis.incr.await_args_list] == [
        "project:version:project-a",
        "projects:list:version:org:org-a",
        "projects:list:version:global",
    ]


@pytest.mark.asyncio
async def test_project_cache_failures_are_fail_open():
    redis = AsyncMock()
    redis.get.side_effect = RuntimeError("cache unavailable")
    redis.setex.side_effect = RuntimeError("cache unavailable")
    redis.incr.side_effect = RuntimeError("cache unavailable")
    cache = RedisProjectCache(redis, ttl=300)

    assert await cache.get_detail("project-a") == (None, None)
    assert await cache.get_list("global", {"page": 1}) == (None, None)
    await cache.set_detail("project:project-a:0", {"id": "project-a"})
    await cache.set_list("projects:list:global:0:key", {"items": []})
    await cache.invalidate(None, "org-a")
