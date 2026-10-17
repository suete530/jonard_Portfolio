"""Tests para sa security.py (walang DB na kailangan)."""

from security import clean, is_valid_email, hash_password, verify_password


def test_clean_trims_whitespace():
    assert clean("  hello  ") == "hello"


def test_clean_limits_length():
    assert clean("abcdef", 3) == "abc"


def test_clean_handles_none():
    assert clean(None) == ""


def test_valid_email():
    assert is_valid_email("user@example.com")
    assert is_valid_email("a.b+c@sub.domain.ph")


def test_invalid_email():
    assert not is_valid_email("not-an-email")
    assert not is_valid_email("user@nodot")
    assert not is_valid_email("")
    assert not is_valid_email(None)


def test_password_hash_roundtrip():
    hashed = hash_password("s3cret-password")
    assert hashed != "s3cret-password"
    assert verify_password(hashed, "s3cret-password")
    assert not verify_password(hashed, "wrong-password")


def test_verify_password_bad_hash_is_false():
    assert verify_password("not-a-real-hash", "anything") is False
