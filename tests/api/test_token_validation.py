import pytest

from app.core import dependencies as deps
from app.utils import jwt
from tests.repository_fakes import repository_mocks


@pytest.mark.parametrize(
    "kind", ["malformed", "legacy", "expired", "refresh", "bad-signature"]
)
def test_me_rejects_invalid_access_before_storage(client, kind):
    repo = repository_mocks()
    client.app.dependency_overrides[deps.get_users] = lambda: repo.users
    client.app.dependency_overrides[deps.get_revocations] = lambda: repo.revocations
    if kind == "malformed":
        token = "not-a-token"
    elif kind == "refresh":
        token = jwt.create_token({"id": "user-1"}, "refresh")
    else:
        payload = {"id": "user-1", "type": "access"}
        if kind != "legacy":
            payload.update(iat=1, exp=2, jti="test-id")
        key = (
            "another-signing-secret-of-32-bytes"
            if kind == "bad-signature"
            else jwt.settings.jwt_secret_key
        )
        token = jwt.jwt.encode(payload, key, algorithm=jwt.settings.jwt_algorithm)
    client.cookies.set("access_token", token)
    assert client.get("/api/auth/me").status_code == 401
    repo.users.get_user_with_id.assert_not_awaited()
    repo.revocations.is_revoked.assert_not_awaited()


def test_missing_user_returns_unauthorized(client):
    client.cookies.set(
        "access_token", jwt.create_token({"id": "deleted-user"}, "access")
    )
    assert client.get("/api/auth/me").status_code == 401
