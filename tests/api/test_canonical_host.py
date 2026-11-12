import pytest

from app.core.config import settings


@pytest.fixture
def canonical(monkeypatch):
    monkeypatch.setattr(settings, "CANONICAL_HOST", "wikianalisis.org")


@pytest.mark.parametrize(
    "host", ["www.wikianalisis.org", "exam-record-beta.fly.dev", "WWW.wikianalisis.org:443"]
)
async def test_other_addresses_redirect_to_the_canonical_one(client, canonical, host):
    response = await client.get("/exams/andalucia/piano?x=1", headers={"host": host})
    assert response.status_code == 301
    assert response.headers["location"] == "https://wikianalisis.org/exams/andalucia/piano?x=1"

    # Anything that is not a page view keeps its method.
    response = await client.post("/api/auth/magic-link", headers={"host": host}, json={})
    assert response.status_code == 308
    assert response.headers["location"] == "https://wikianalisis.org/api/auth/magic-link"


@pytest.mark.parametrize(
    "host", ["wikianalisis.org", "172.19.0.2:8080", "localhost:8000", "evil.example"]
)
async def test_canonical_and_internal_hosts_are_served(client, canonical, host):
    assert (await client.get("/health", headers={"host": host})).status_code == 200


async def test_no_redirect_when_unset(client):
    response = await client.get("/health", headers={"host": "exam-record-beta.fly.dev"})
    assert response.status_code == 200
