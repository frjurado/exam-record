from unittest.mock import AsyncMock, patch

from starlette.requests import Request

from app.core import security
from app.core.constants import RateLimit
from app.core.limiter import user_or_address


def _limit_count(limit_string: str) -> int:
    return int(limit_string.split("/")[0])


def _send():
    return patch("app.api.endpoints.auth.email_service.send_magic_link", new_callable=AsyncMock)


async def test_magic_link_limit_per_address(client):
    # A different target email each time, so only the per-IP limit is in play.
    limit = _limit_count(RateLimit.MAGIC_LINK_REQUEST)
    with _send():
        for i in range(limit):
            response = await client.post("/api/auth/magic-link", json={"email": f"u{i}@test.com"})
            assert response.status_code == 200
        response = await client.post("/api/auth/magic-link", json={"email": "last@test.com"})
    assert response.status_code == 429


async def test_magic_link_limit_per_target_email(client):
    limit = _limit_count(RateLimit.MAGIC_LINK_PER_EMAIL)
    with _send() as send:
        for _ in range(limit):
            response = await client.post("/api/auth/magic-link", json={"email": "same@test.com"})
            assert response.status_code == 200
        # Case does not get around it, and nothing more is sent.
        response = await client.post("/api/auth/magic-link", json={"email": "Same@test.com"})
        assert response.status_code == 429
        assert send.call_count == limit
        # Someone else on the same connection is unaffected.
        response = await client.post("/api/auth/magic-link", json={"email": "other@test.com"})
        assert response.status_code == 200


def _request(cookie: str | None = None, ip: str = "203.0.113.7") -> Request:
    headers = [(b"fly-client-ip", ip.encode())]
    if cookie:
        headers.append((b"cookie", f"access_token={cookie}".encode()))
    return Request({"type": "http", "method": "POST", "path": "/", "headers": headers})


def test_votes_are_counted_per_user_when_signed_in():
    # Two pupils on the school's one address get separate buckets...
    a = user_or_address(_request(security.create_token("a@test.com", security.SESSION)))
    b = user_or_address(_request(security.create_token("b@test.com", security.SESSION)))
    assert a == "user:a@test.com"
    assert b == "user:b@test.com"
    # ...while anonymous or badly signed requests fall back to the address.
    assert user_or_address(_request()) == "203.0.113.7"
    assert user_or_address(_request("garbage")) == "203.0.113.7"
    link_token = security.create_token("a@test.com", security.LINK)
    assert user_or_address(_request(link_token)) == "203.0.113.7"
