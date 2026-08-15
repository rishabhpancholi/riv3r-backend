import pytest
from pydantic import ValidationError

from app.api.auth.schemas import LoginUser


def test_login_user_valid():
    login = LoginUser(email="owner@example.com", password="StrongPass1!")

    assert login.email == "owner@example.com"


def test_login_user_rejects_invalid_email():
    with pytest.raises(ValidationError):
        LoginUser(email="not-an-email", password="StrongPass1!")
