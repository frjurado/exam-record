from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import func, select
from starlette.requests import Request

from app.core import security
from app.core.config import settings
from app.core.urls import safe_next_path
from app.models import User


def _request(host: str = "test") -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "query_string": b"",
            "scheme": "http",
            "server": (host, 80),
            "headers": [(b"host", host.encode())],
        }
    )


@pytest.mark.parametrize(
    ("target", "expected"),
    [
        (None, "/"),
        ("", "/"),
        ("/exams/andalucia/piano/2024?action=vote&report_id=3", None),
        ("http://test/exams/andalucia/piano", "/exams/andalucia/piano"),
        ("http://test", "/"),
        ("https://evil.example/login", "/"),
        ("//evil.example/login", "/"),
        ("/\\evil.example", "/"),
        ("javascript:alert(1)", "/"),
        ("exams/relative", "/"),
    ],
)
def test_safe_next_path(target, expected):
    # expected None: the target is already a path on this site and comes back unchanged.
    assert safe_next_path(target, _request()) == (target if expected is None else expected)


async def test_verify_never_redirects_off_site(client):
    token = security.create_token("a@test.com", security.LINK)
    response = await client.get(
        "/api/auth/verify", params={"token": token, "next": "https://evil.example/x"}
    )
    assert response.status_code == 307
    assert response.headers["location"] == "/"


async def test_link_token_opens_a_long_session(client, db):
    token = security.create_token("new@test.com", security.LINK)
    response = await client.get("/api/auth/verify", params={"token": token})
    assert response.status_code == 307
    assert response.headers["location"] == "/"

    cookie_header = response.headers["set-cookie"]
    assert "HttpOnly" in cookie_header
    assert f"Max-Age={30 * 24 * 3600}" in cookie_header
    assert "Secure" not in cookie_header  # development; see the production test below

    # The cookie holds a session token, not the link token.
    session = response.cookies["access_token"]
    assert session != token
    payload = security.verify_token(session, security.SESSION)
    assert payload is not None and payload["sub"] == "new@test.com"

    client.cookies.set("access_token", session)
    me = await client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == "new@test.com"

    # Opening the same link again signs the same account in; no second row.
    await client.get("/api/auth/verify", params={"token": token})
    assert (await db.execute(select(func.count()).select_from(User))).scalar_one() == 1


async def test_cookie_is_secure_in_production(client, monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    token = security.create_token("a@test.com", security.LINK)
    response = await client.get("/api/auth/verify", params={"token": token})
    assert "Secure" in response.headers["set-cookie"]


async def test_link_token_is_not_a_session_and_vice_versa(client, db):
    db.add(User(email="a@test.com"))
    await db.commit()

    client.cookies.set("access_token", security.create_token("a@test.com", security.LINK))
    assert (await client.get("/api/auth/me")).status_code == 401
    client.cookies.clear()

    session = security.create_token("a@test.com", security.SESSION)
    response = await client.get("/api/auth/verify", params={"token": session})
    assert response.status_code == 400
    assert "caducado" in response.text
    assert "set-cookie" not in response.headers


async def test_expired_or_garbage_link_gets_an_explanation(client, db):
    response = await client.get("/api/auth/verify", params={"token": "garbage"})
    assert response.status_code == 400
    assert "pide uno nuevo" in response.text
    assert (await db.execute(select(func.count()).select_from(User))).scalar_one() == 0


async def test_requesting_a_link_stores_nothing_and_links_to_this_site(client, db, monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    with patch(
        "app.api.endpoints.auth.email_service.send_magic_link", new_callable=AsyncMock
    ) as send:
        response = await client.post(
            "/api/auth/magic-link",
            json={"email": "a@test.com", "next_url": "https://evil.example/x"},
        )
    assert response.status_code == 200
    link = send.call_args.args[1]
    assert link.startswith("https://test/api/auth/verify?token=")
    assert "evil" not in link
    assert (await db.execute(select(func.count()).select_from(User))).scalar_one() == 0
