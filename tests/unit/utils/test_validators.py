import pytest

from app.utils import validators


def test_validate_password_accepts_valid():
    assert validators.validate_password("StrongPass1!") == "StrongPass1!"


@pytest.mark.parametrize(
    "weak_password",
    [
        "short1!",
        "nouppercase1!",
        "NOLOWERCASE1!",
        "NoSpecialChars1",
        "NoDigitsA!",
    ],
)
def test_validate_password_rejects_invalid(weak_password):
    with pytest.raises(ValueError):
        validators.validate_password(weak_password)


def test_validate_phone_number_accepts_e164():
    assert validators.validate_phone_number("+14155552671") == "+14155552671"


@pytest.mark.parametrize(
    "bad_phone",
    ["14155552671", "+1", "abc", ""],
)
def test_validate_phone_number_rejects_invalid(bad_phone):
    with pytest.raises(ValueError):
        validators.validate_phone_number(bad_phone)


def test_get_email_domain_lowercases_and_strips():
    assert validators.get_email_domain("Owner@Example.COM") == "example.com"


def test_validate_same_domain_accepts():
    validators.validate_same_domain("acme@example.com", "owner@example.com")


def test_validate_same_domain_rejects_different_domains():
    with pytest.raises(ValueError):
        validators.validate_same_domain("acme@example.com", "owner@other.com")
