"""Unit tests for app.core.security — no DB required."""
from datetime import timedelta

import jwt
import pytest

from app.core.security import create_access_token, verify_token


def test_verify_valid_token():
    token = create_access_token({"sub": "user@test.com"})
    payload = verify_token(token)
    assert payload is not None
    assert payload["sub"] == "user@test.com"


def test_verify_expired_token():
    token = create_access_token({"sub": "expired@test.com"}, expires_delta=timedelta(seconds=-1))
    assert verify_token(token) is None


def test_verify_invalid_signature():
    token = jwt.encode({"sub": "x"}, "wrong-secret", algorithm="HS256")
    assert verify_token(token) is None


def test_verify_malformed_token():
    assert verify_token("not.a.jwt") is None


def test_verify_empty_string():
    assert verify_token("") is None


def test_create_token_contains_sub():
    token = create_access_token({"sub": "a@b.com", "role": "Contributor"})
    payload = verify_token(token)
    assert payload is not None
    assert payload["role"] == "Contributor"
    assert "exp" in payload
