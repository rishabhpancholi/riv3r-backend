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
