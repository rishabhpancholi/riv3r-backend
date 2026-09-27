import hashlib
import time
from unittest.mock import AsyncMock

import pytest

from app.core.dependencies import get_duplicates
from app.repositories.redis import RedisAccessTokenRevocationStore
from app.services.duplicates import DuplicateChecker
from tests.repository_fakes import repository_mocks


class MemoryRedis:
    def __init__(self):
        self.values = {}
        self.writes = []

    async def setex(self, key, ttl, value):
        self.writes.append((key, ttl, value))
        self.values[key] = value.encode()

    async def exists(self, *keys):
        return sum(key in self.values for key in keys)


@pytest.mark.asyncio
async def test_revoke_and_read_same_raw_token_until_expiry(monkeypatch):
    monkeypatch.setattr("app.repositories.redis.time.time", lambda: 1000.25)
    cache = MemoryRedis()
    store = RedisAccessTokenRevocationStore(cache)
    assert not await store.is_revoked("token")
    await store.revoke("token", expires_at=1123)
    assert await store.is_revoked("token")
    assert not await store.is_revoked("another-token")
    digest = hashlib.sha256(b"token").hexdigest()
    assert cache.writes == [(digest, 123, "blacklisted")]
    assert "token" not in cache.values


@pytest.mark.asyncio
@pytest.mark.parametrize("hashed", [False, True])
@pytest.mark.parametrize("value", [b"blacklisted", "blacklisted"])
async def test_legacy_keys_do_not_depend_on_value_decoding(hashed, value):
    cache = MemoryRedis()
    key = hashlib.sha256(b"token").hexdigest() if hashed else "token"
    cache.values[key] = value
    assert await RedisAccessTokenRevocationStore(cache).is_revoked("token")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "method,redis_method", [("revoke", "setex"), ("is_revoked", "exists")]
)
async def test_redis_failures_propagate(method, redis_method):
    cache = AsyncMock()
    getattr(cache, redis_method).side_effect = RuntimeError("redis unavailable")
    store = RedisAccessTokenRevocationStore(cache)
    with pytest.raises(RuntimeError, match="redis unavailable"):
        if method == "revoke":
            await store.revoke("token", expires_at=int(time.time()) + 300)
        else:
            await store.is_revoked("token")


@pytest.mark.asyncio
@pytest.mark.parametrize("expiry", [999, 1000])
async def test_expired_access_does_not_create_blacklist_entry(monkeypatch, expiry):
    monkeypatch.setattr("app.repositories.redis.time.time", lambda: 1000)
    cache = MemoryRedis()
    await RedisAccessTokenRevocationStore(cache).revoke("token", expires_at=expiry)
    assert not cache.writes


@pytest.mark.asyncio
@pytest.mark.parametrize("matching_source", range(5))
async def test_wired_duplicate_sources(matching_source):
    repo = repository_mocks()
    sources = [
        repo.organizations.email_exists,
        repo.users.email_exists,
        repo.organizations.website_exists,
        repo.resources.portfolio_exists,
        repo.resources.linkedin_exists,
    ]
    for source in sources:
        source.return_value = False
    sources[matching_source].return_value = True
    checker = get_duplicates(repo.users, repo.organizations, repo.resources)
    assert await checker.check_email_in_db("email") is (matching_source < 2)
    assert await checker.check_website_url_in_db("url") is (matching_source >= 2)
    for index, source in enumerate(sources):
        source.assert_awaited_once_with("email" if index < 2 else "url")


@pytest.mark.asyncio
async def test_add_source_without_changing_checker():
    existing = AsyncMock(return_value=False)
    added = AsyncMock(return_value=True)
    original = DuplicateChecker(email_checks=[existing], url_checks=[])
    extended = DuplicateChecker(email_checks=[existing, added], url_checks=[])
    assert not await original.check_email_in_db("email")
    assert await extended.check_email_in_db("email")
    assert not await extended.check_website_url_in_db("url")
    added.assert_awaited_once_with("email")


@pytest.mark.asyncio
async def test_duplicate_source_failures_propagate():
    checker = DuplicateChecker(
        email_checks=[AsyncMock(side_effect=RuntimeError("db down"))], url_checks=[]
    )
    with pytest.raises(RuntimeError, match="db down"):
        await checker.check_email_in_db("email")
