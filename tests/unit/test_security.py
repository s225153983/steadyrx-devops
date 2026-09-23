"""Unit tests for password hashing and tokens."""

import jwt
import pytest

from app.security import create_token, decode_token, hash_password, verify_password

SECRET = "unit-test-secret-that-is-long-enough-1"


def test_password_round_trip():
    stored = hash_password("S3cure!pass")
    assert stored.startswith("pbkdf2$")
    assert verify_password("S3cure!pass", stored)
    assert not verify_password("wrong", stored)


def test_same_password_gets_different_salt():
    first = hash_password("x")
    second = hash_password("x")
    assert first != second
    assert verify_password("x", first) and verify_password("x", second)


def test_malformed_hash_is_rejected():
    assert verify_password("x", "not-a-hash") is False


def test_token_round_trip():
    claims = decode_token(create_token("daniel", "pharmacist", SECRET), SECRET)
    assert claims["sub"] == "daniel"
    assert claims["role"] == "pharmacist"


def test_token_signed_with_other_key_is_rejected():
    token = create_token("daniel", "pharmacist", SECRET)
    with pytest.raises(jwt.InvalidTokenError):
        decode_token(token, "another-secret-that-is-long-enough-22")


def test_expired_token_is_rejected():
    token = create_token("daniel", "pharmacist", SECRET, ttl_minutes=-1)
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_token(token, SECRET)
