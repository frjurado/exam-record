"""Unit tests for app.core.security — no DB required."""

from datetime import timedelta

import jwt

from app.core.config import settings
from app.core.security import LINK, SESSION, create_token, verify_token


def test_verify_valid_token():
    payload = verify_token(create_token("user@test.com", SESSION), SESSION)
    assert payload is not None
    assert payload["sub"] == "user@test.com"
    assert "exp" in payload


def test_verify_expired_token():
    token = create_token("expired@test.com", SESSION, expires_delta=timedelta(seconds=-1))
    assert verify_token(token, SESSION) is None


def test_verify_invalid_signature():
    token = jwt.encode({"sub": "x", "purpose": SESSION}, "wrong-secret", algorithm="HS256")
    assert verify_token(token, SESSION) is None


def test_verify_malformed_token():
    assert verify_token("not.a.jwt", SESSION) is None
    assert verify_token("", SESSION) is None


def test_a_token_is_only_good_for_its_purpose():
    assert verify_token(create_token("a@b.com", LINK), SESSION) is None
    assert verify_token(create_token("a@b.com", SESSION), LINK) is None
    assert verify_token(create_token("a@b.com", LINK), LINK) is not None


def test_tokens_from_before_purposes_existed_are_refused():
    old = jwt.encode({"sub": "a@b.com", "role": "Visitor"}, settings.SECRET_KEY, algorithm="HS256")
    assert verify_token(old, SESSION) is None
    assert verify_token(old, LINK) is None


def test_lifetimes():
    link = verify_token(create_token("a@b.com", LINK), LINK)
    session = verify_token(create_token("a@b.com", SESSION), SESSION)
    assert link is not None and session is not None
    assert session["exp"] - link["exp"] > 29 * 24 * 3600
