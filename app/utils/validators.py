import re

PHONE_REGEX = re.compile(r"^\+[1-9]\d{7,14}$")


def validate_password(value: str) -> str:
    if len(value) < 8:
        raise ValueError("Password must be at least 8 characters long")

    if not any(c.isupper() for c in value):
        raise ValueError("Password must contain an uppercase letter")

    if not any(c.islower() for c in value):
        raise ValueError("Password must contain a lowercase letter")

    if not any(c.isdigit() for c in value):
        raise ValueError("Password must contain a digit")

    if not any(c in "!@#$%^&*()-_=+[]{};:,<.>/?\\" for c in value):
        raise ValueError("Password must contain a special character")

    return value


def validate_phone_number(value: str) -> str:
    if not PHONE_REGEX.fullmatch(value):
        raise ValueError("Phone number must be in E.164 format (e.g. +919876543210)")
    return value


def get_email_domain(value: str) -> str:
    return value.split("@")[-1].strip().lower()


def validate_same_domain(company_email: str, owner_email: str) -> None:
    if get_email_domain(company_email) != get_email_domain(owner_email):
        raise ValueError("Company email and owner email must be from the same domain")
