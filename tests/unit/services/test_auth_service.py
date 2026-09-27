import asyncio
from unittest.mock import AsyncMock

import pytest

from app.api.auth.schemas import LoginUser
from app.core import exceptions
from app.services import auth
from app.utils import jwt, password
from tests.repository_fakes import repository_mocks


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
    repo = repository_mocks()
    svc = auth.AuthService(
        users=repo.users,
        refresh_tokens=repo.refresh_tokens,
        revocations=repo.revocations,
    )
    return svc


def test_login_success(service):
    service.users.get_user_with_email = AsyncMock(return_value=user_row())
    service.refresh_tokens.store_refresh_token = AsyncMock()

    result = asyncio.run(
        service.login_user(
            LoginUser(email="owner@example.com", password="StrongPass1!")
        )
    )

    assert result["access_token"]
    assert result["refresh_token"]
    assert result["user"]["email"] == "owner@example.com"
    assert "password" not in result["user"]

    service.refresh_tokens.store_refresh_token.assert_awaited_once_with(
        "user-1",
        jwt.hash_token(result["refresh_token"]),
        expires_at=jwt.decode_token(result["refresh_token"])["exp"],
    )
    assert not {"type", "iat", "exp", "jti"} & result["user"].keys()


def test_login_user_not_found(service):
    service.users.get_user_with_email = AsyncMock(return_value=None)

    with pytest.raises(exceptions.AuthorizationError):
        asyncio.run(
            service.login_user(
                LoginUser(email="nobody@example.com", password="StrongPass1!")
            )
        )


def test_login_wrong_password(service):
    service.users.get_user_with_email = AsyncMock(return_value=user_row())

    with pytest.raises(exceptions.AuthorizationError):
        asyncio.run(
            service.login_user(
                LoginUser(email="owner@example.com", password="WrongPass1!")
            )
        )


def test_logout_user(service):
    service.refresh_tokens.blacklist_refresh_token = AsyncMock()
    service.revocations.revoke = AsyncMock()

    access_token = jwt.create_token({"id": "user-1"}, "access")
    refresh_token = jwt.create_token({"id": "user-1"}, "refresh")
    asyncio.run(service.logout_user(access_token, refresh_token))

    service.refresh_tokens.blacklist_refresh_token.assert_awaited_once_with(
        jwt.hash_token(refresh_token)
    )
    service.revocations.revoke.assert_awaited_once_with(
        access_token, expires_at=jwt.decode_token(access_token)["exp"]
    )


def test_refresh_success(service):
    service.refresh_tokens.check_refresh_token_valid = AsyncMock(return_value=True)
    service.revocations.revoke = AsyncMock()

    refresh_token = jwt.create_token(
        {"id": "user-1", "email": "owner@example.com"}, "refresh"
    )
    access_token = jwt.create_token(
        {"id": "user-1", "email": "owner@example.com"}, "access"
    )

    result = asyncio.run(service.refresh(refresh_token, access_token))

    assert result["fresh_access_token"]
    assert result["fresh_access_token"] != access_token
    service.revocations.revoke.assert_awaited_once_with(
        access_token, expires_at=jwt.decode_token(access_token)["exp"]
    )


def test_refresh_invalid_token(service):
    service.refresh_tokens.check_refresh_token_valid = AsyncMock(return_value=False)

    with pytest.raises(exceptions.AuthorizationError):
        asyncio.run(service.refresh("invalid-refresh", "invalid-access"))


def test_refresh_rejects_blacklisted_record_without_revoking_access(service):
    service.refresh_tokens.check_refresh_token_valid.return_value = False
    refresh = jwt.create_token({"id": "user-1"}, "refresh")
    access = jwt.create_token({"id": "user-1"}, "access")
    with pytest.raises(exceptions.AuthorizationError):
        asyncio.run(service.refresh(refresh, access))
    service.revocations.revoke.assert_not_awaited()


@pytest.mark.parametrize("operation", ["refresh", "logout_user"])
def test_mismatched_token_users_cannot_revoke_other_users_tokens(service, operation):
    refresh = jwt.create_token({"id": "user-1"}, "refresh")
    access = jwt.create_token({"id": "user-2"}, "access")
    args = (refresh, access) if operation == "refresh" else (access, refresh)
    with pytest.raises(exceptions.AuthorizationError):
        asyncio.run(getattr(service, operation)(*args))
    service.revocations.revoke.assert_not_awaited()
    service.refresh_tokens.blacklist_refresh_token.assert_not_awaited()


def test_refresh_accepts_expired_access_but_not_expired_refresh(service):
    service.refresh_tokens.check_refresh_token_valid.return_value = True
    access = jwt.jwt.encode(
        {"id": "user-1", "type": "access", "iat": 1, "exp": 2, "jti": "expired-access"},
        jwt.settings.jwt_secret_key,
        algorithm=jwt.settings.jwt_algorithm,
    )
    refresh = jwt.create_token({"id": "user-1"}, "refresh")
    result = asyncio.run(service.refresh(refresh, access))
    assert (
        jwt.decode_token(result["fresh_access_token"], expected_type="access")["id"]
        == "user-1"
    )
    service.revocations.revoke.assert_awaited_once_with(access, expires_at=2)
    service.revocations.revoke.reset_mock()
    expired_refresh = jwt.jwt.encode(
        {
            "id": "user-1",
            "type": "refresh",
            "iat": 1,
            "exp": 2,
            "jti": "expired-refresh",
        },
        jwt.settings.jwt_secret_key,
        algorithm=jwt.settings.jwt_algorithm,
    )
    with pytest.raises(exceptions.AuthorizationError):
        asyncio.run(service.refresh(expired_refresh, access))
    service.revocations.revoke.assert_not_awaited()
