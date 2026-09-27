from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.auth.routes import auth_router
from app.api.onboarding.routes import onboarding_router
from app.core import dependencies as deps
from app.core.config import load_settings
from app.core.exception_handlers import register_exception_handlers
from tests.repository_fakes import repository_mocks


def _health() -> dict:
    settings = load_settings()
    return {
        "status": "healthy",
        "name": settings.app_name,
        "version": settings.app_version,
    }


@pytest.fixture
def client():
    test_app = FastAPI(title="riv3r-tests")
    register_exception_handlers(test_app)

    test_app.include_router(onboarding_router)
    test_app.include_router(auth_router)
    test_app.get("/api/health", tags=["Health"])(_health)

    test_app.dependency_overrides[deps.get_db] = lambda: AsyncMock()
    test_app.dependency_overrides[deps.get_cache] = lambda: AsyncMock()
    test_app.dependency_overrides[deps.rate_limit_login] = lambda: None
    test_app.dependency_overrides[deps.rate_limit_onboarding] = lambda: None

    repo = repository_mocks()
    repo.revocations.is_revoked.return_value = False
    test_app.dependency_overrides[deps.get_users] = lambda: repo.users
    test_app.dependency_overrides[deps.get_organizations] = lambda: repo.organizations
    test_app.dependency_overrides[deps.get_memberships] = lambda: repo.memberships
    test_app.dependency_overrides[deps.get_resources] = lambda: repo.resources
    test_app.dependency_overrides[deps.get_refresh_tokens] = lambda: repo.refresh_tokens
    test_app.dependency_overrides[deps.get_audit_logs] = lambda: repo.audit_logs
    test_app.dependency_overrides[deps.get_revocations] = lambda: repo.revocations
    test_app.dependency_overrides[deps.get_duplicates] = lambda: repo.duplicates

    with TestClient(test_app) as client:
        yield client

    test_app.dependency_overrides.clear()
