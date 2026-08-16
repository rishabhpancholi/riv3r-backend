import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.api.auth.schemas import LoginUser
from app.core import exceptions
from app.services import auth
from app.utils import jwt, password


def user_row():
    return {
        "id": "user-1",
        "email": "owner@example.com",
        "name": "John Doe",
        "password": password.hash_password("StrongPass1!"),
        "phone_number": "+14155552671",
        "verification_status": "in_progress",
        "is_resource": False,
    }


@pytest.fixture
def service():
    svc = auth.AuthService(AsyncMock(), AsyncMock())
    svc.db_service = MagicMock()
    svc.cache_service = MagicMock()
    return svc


def test_login_success(service):
    service.db_service.get_user_with_email = AsyncMock(return_value=user_row())
    service.db_service.store_refresh_token = AsyncMock()

    result = asyncio.run(
        service.login_user(LoginUser(email="owner@example.com", password="StrongPass1!"))
    )

    assert result["access_token"]
    assert result["refresh_token"]
    assert result["user"]["email"] == "owner@example.com"
    assert "password" not in result["user"]

    service.db_service.store_refresh_token.assert_awaited_once()


def test_login_user_not_found(service):
    service.db_service.get_user_with_email = AsyncMock(return_value=None)

    with pytest.raises(exceptions.AuthorizationError):
        asyncio.run(
            service.login_user(
                LoginUser(email="nobody@example.com", password="StrongPass1!")
            )
        )


def test_login_wrong_password(service):
    service.db_service.get_user_with_email = AsyncMock(return_value=user_row())

    with pytest.raises(exceptions.AuthorizationError):
        asyncio.run(
            service.login_user(
                LoginUser(email="owner@example.com", password="WrongPass1!")
            )
        )


def test_logout_user(service):
    service.db_service.blacklist_refresh_token = AsyncMock()
    service.cache_service.blacklist_access_token = AsyncMock()

    asyncio.run(service.logout_user("access-token", "refresh-token"))

    service.db_service.blacklist_refresh_token.assert_awaited_once()
    service.cache_service.blacklist_access_token.assert_awaited_once()


def test_refresh_success(service):
    service.db_service.check_refresh_token_valid = AsyncMock(return_value=True)
    service.cache_service.blacklist_access_token = AsyncMock()

    refresh_token = jwt.create_token({"id": "user-1", "email": "owner@example.com"}, "refresh")
    access_token = jwt.create_token({"id": "user-1", "email": "owner@example.com"}, "access")

    result = asyncio.run(service.refresh(refresh_token, access_token))

    assert result["fresh_access_token"]
    service.cache_service.blacklist_access_token.assert_awaited_once()


def test_refresh_invalid_token(service):
    service.db_service.check_refresh_token_valid = AsyncMock(return_value=False)

    with pytest.raises(exceptions.AuthorizationError):
        asyncio.run(service.refresh("invalid-refresh", "invalid-access"))
