from datetime import UTC, datetime

import pytest

from app.core import exceptions
from app.utils import jwt


def test_create_and_decode_access_token():
    token = jwt.create_token({"id": "user-1", "email": "owner@example.com"}, "access")

    decoded = jwt.decode_token(token)
    assert decoded["id"] == "user-1"
    assert decoded["email"] == "owner@example.com"
    assert decoded["type"] == "access"


def test_create_and_decode_refresh_token():
    token = jwt.create_token({"id": "user-1"}, "refresh")

    assert jwt.decode_token(token)["type"] == "refresh"


def test_hash_token_is_deterministic_sha256():
    assert jwt.hash_token("token-abc") == jwt.hash_token("token-abc")
    assert len(jwt.hash_token("token-abc")) == 64


def signed_claims(**overrides):
    now = int(datetime.now(UTC).timestamp())
    payload = {
        "id": "user-1",
        "type": "access",
        "iat": now,
        "exp": now + 300,
        "jti": "test-id",
    }
    payload.update(overrides)
    return jwt.jwt.encode(
        payload, jwt.settings.jwt_secret_key, algorithm=jwt.settings.jwt_algorithm
    )


@pytest.mark.parametrize("token_type,seconds", [("access", 180), ("refresh", 172800)])
def test_configured_lifetimes_and_input_is_not_mutated(
    monkeypatch, token_type, seconds
):
    monkeypatch.setattr(jwt.settings, "jwt_access_token_expire_minutes", 3)
    monkeypatch.setattr(jwt.settings, "jwt_refresh_token_expire_days", 2)
    data = {"id": "user-1", "name": "User"}
    token = jwt.create_token(data, token_type)
    claims = jwt.decode_token(token, expected_type=token_type)
    assert claims["exp"] - claims["iat"] == seconds
    assert claims["jti"]
    assert data == {"id": "user-1", "name": "User"}


def test_identical_payloads_get_distinct_tokens_and_ids():
    first = jwt.create_token({"id": "user-1"}, "access")
    second = jwt.create_token({"id": "user-1"}, "access")
    assert first != second
    assert jwt.decode_token(first)["jti"] != jwt.decode_token(second)["jti"]


def test_new_access_token_replaces_refresh_lifetime_and_identity():
    refresh = jwt.decode_token(jwt.create_token({"id": "user-1"}, "refresh"))
    access = jwt.decode_token(jwt.create_token(refresh, "access"))
    assert access["jti"] != refresh["jti"]
    assert (
        access["exp"] - access["iat"]
        == jwt.settings.jwt_access_token_expire_minutes * 60
    )
    assert refresh["type"] == "refresh"


def test_expired_token_rejected_but_signature_can_be_verified_for_cleanup():
    token = signed_claims(iat=1, exp=2)
    with pytest.raises(exceptions.AuthorizationError):
        jwt.decode_token(token, expected_type="access")
    assert (
        jwt.decode_token(token, expected_type="access", allow_expired=True)["exp"] == 2
    )


def test_legacy_tokens_require_sign_in_again():
    token = jwt.jwt.encode(
        {"id": "user-1", "type": "access"},
        jwt.settings.jwt_secret_key,
        algorithm=jwt.settings.jwt_algorithm,
    )
    with pytest.raises(exceptions.AuthorizationError):
        jwt.decode_token(token)


@pytest.mark.parametrize(
    "claims",
    [
        {"jti": ""},
        {"id": ""},
        {"id": 123},
        {"type": "invalid"},
        {"exp": "not-a-time"},
        {"exp": []},
        {"exp": True},
        {"iat": True},
        {"iat": 9999999999},
        {"iat": 2, "exp": 1},
    ],
)
def test_invalid_claims_rejected(claims):
    with pytest.raises(exceptions.AuthorizationError):
        jwt.decode_token(signed_claims(**claims))


def test_token_types_cannot_be_interchanged():
    for token_type, expected in [("access", "refresh"), ("refresh", "access")]:
        token = jwt.create_token({"id": "user-1"}, token_type)
        with pytest.raises(exceptions.AuthorizationError):
            jwt.decode_token(token, expected_type=expected)


def test_invalid_signature_rejected_even_for_cleanup():
    token = jwt.jwt.encode(
        {"id": "user-1"},
        "different-signing-secret-at-least-32-bytes",
        algorithm="HS256",
    )
    with pytest.raises(exceptions.AuthorizationError):
        jwt.decode_token(token, allow_expired=True)
