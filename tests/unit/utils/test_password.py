from app.utils import password


def test_hash_and_verify_round_trip():
    hashed = password.hash_password("StrongPass1!")

    assert hashed != "StrongPass1!"
    assert password.verify_password("StrongPass1!", hashed)


def test_verify_rejects_wrong_password():
    hashed = password.hash_password("StrongPass1!")

    assert not password.verify_password("WrongPass1!", hashed)
