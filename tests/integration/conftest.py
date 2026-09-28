"""Opt-in tests against dedicated Supabase and Redis test instances."""

import os
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from redis.asyncio import Redis

from app.api.auth.routes import auth_router
from app.api.auth import dependencies as auth_deps
from app.core import dependencies as deps
from app.core.exception_handlers import register_exception_handlers
from app.utils import password
from supabase import create_async_client


def required_test_setting(name):
    if os.getenv("RUN_INTEGRATION_TESTS") != "1":
        pytest.skip("Set RUN_INTEGRATION_TESTS=1 to use dedicated test services")
    value = os.getenv(name)
    if not value:
        pytest.fail(f"Integration tests enabled but {name} is missing")
    return value


@pytest_asyncio.fixture
async def live_redis():
    cache = Redis.from_url(required_test_setting("TEST_REDIS_URL"))
    keys = set()
    try:
        await cache.ping()
        yield SimpleNamespace(client=cache, keys=keys)
    finally:
        try:
            if keys:
                await cache.delete(*keys)
        finally:
            await cache.aclose()


@pytest_asyncio.fixture
async def live_auth(live_redis):
    url = required_test_setting("TEST_SUPABASE_URL")
    key = required_test_setting("TEST_SUPABASE_KEY")
    db = await create_async_client(url, key)
    user_id = str(uuid4())
    email = f"integration-{uuid4().hex}@example.com"
    plain_password = "IntegrationPass1!"
    try:
        await (
            db.table("users")
            .insert(
                {
                    "id": user_id,
                    "email": email,
                    "name": "Integration User",
                    "password": password.hash_password(plain_password),
                    "is_resource": True,
                }
            )
            .execute()
        )
        app = FastAPI()
        register_exception_handlers(app)
        app.include_router(auth_router)
        app.dependency_overrides[deps.get_db] = lambda: db
        app.dependency_overrides[deps.get_cache] = lambda: live_redis.client
        app.dependency_overrides[auth_deps.rate_limit_login] = lambda: None
        # HTTPS allows the real secure cookies in production-mode test configs.
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="https://integration.test"
        ) as client:
            yield SimpleNamespace(
                client=client,
                db=db,
                redis=live_redis,
                user_id=user_id,
                credentials={"email": email, "password": plain_password},
            )
    finally:
        try:
            # Only this fixture's UUID is removed; dependent tokens/logs cascade.
            await db.table("users").delete().eq("id", user_id).execute()
        finally:
            await db.postgrest.aclose()
