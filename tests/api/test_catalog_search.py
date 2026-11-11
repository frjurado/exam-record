"""Composer and work search endpoints, backed by CatalogService."""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.models import Composer, Discipline, ExamEvent, Region, Report, User, Work
from app.services.catalog_service import CatalogService


@pytest.fixture
async def albeniz(db):
    composer = Composer(name="Isaac Albéniz", openopus_id="216", is_verified=True)
    db.add(composer)
    await db.commit()
    await db.refresh(composer)
    return composer


# ---------------------------------------------------------------------------
# Composers
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("query", ["albeniz", "ALBÉNIZ", "isaac alb", "Albéniz Isaac"])
async def test_local_composer_search_ignores_accents_case_and_order(client, albeniz, query):
    response = await client.get("/api/composers/search", params={"q": query})
    assert response.status_code == 200
    assert [c["id"] for c in response.json()] == [albeniz.id]


@pytest.mark.asyncio
async def test_local_composer_search_no_match(client, albeniz):
    response = await client.get("/api/composers/search", params={"q": "granados"})
    assert response.json() == []


@pytest.mark.asyncio
@pytest.mark.parametrize("url", ["/api/composers/search", "/api/composers/search?q=a"])
async def test_composer_search_validates_query(client, url):
    assert (await client.get(url)).status_code == 422


@pytest.mark.asyncio
async def test_composer_search_rejects_unknown_source(client):
    response = await client.get("/api/composers/search?q=bach&source=elsewhere")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_external_search_merges_catalogues_and_maps_known_composers(client, albeniz):
    openopus_results = [
        {"name": "Isaac Albéniz", "openopus_id": "216", "description": "Late Romantic"},  # local
        {"name": "Mateo Albéniz", "openopus_id": "900", "description": "Classical"},
    ]
    wikidata_results = [
        # Same person as the OpenOpus entry above: offered once.
        {
            "name": "Mateo Albéniz",
            "name_en": "Mateo Albéniz",
            "wikidata_id": "Q1",
            "description": "x",
        },
        # Same person as the local composer, under its English name.
        {
            "name": "Isaac Albéniz y Pascual",
            "name_en": "Isaac Albeniz",
            "wikidata_id": "Q2",
            "description": "x",
        },
        {
            "name": "Pedro Albéniz",
            "name_en": "Pedro Albéniz",
            "wikidata_id": "Q3",
            "description": "pianista",
        },
    ]
    with (
        patch(
            "app.services.openopus.search_composers", new=AsyncMock(return_value=openopus_results)
        ),
        patch(
            "app.services.wikidata.search_composer", new=AsyncMock(return_value=wikidata_results)
        ),
    ):
        response = await client.get("/api/composers/search?q=albeniz&source=external")

    assert response.status_code == 200
    results = response.json()
    assert [(c["name"], c.get("source")) for c in results] == [
        # Already stored: offered once, as the stored composer (it has a local id).
        ("Isaac Albéniz", None),
        ("Mateo Albéniz", "OpenOpus"),
        ("Pedro Albéniz", "Wikidata"),
    ]
    assert results[0]["id"] == albeniz.id
    assert results[2]["wikidata_id"] == "Q3"


@pytest.mark.asyncio
async def test_external_search_survives_one_catalogue_being_down(client):
    with (
        patch(
            "app.services.openopus.search_composers",
            new=AsyncMock(side_effect=httpx.ConnectError("down")),
        ),
        patch(
            "app.services.wikidata.search_composer",
            new=AsyncMock(
                return_value=[{"name": "Kuhnau", "name_en": "Kuhnau", "wikidata_id": "Q9"}]
            ),
        ),
    ):
        response = await client.get("/api/composers/search?q=kuhnau&source=external")

    assert response.status_code == 200
    assert [c["name"] for c in response.json()] == ["Kuhnau"]


# ---------------------------------------------------------------------------
# Works
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_work_search_requires_a_composer(client):
    assert (await client.get("/api/works/search?q=sonata")).status_code == 400


@pytest.mark.asyncio
async def test_work_search_merges_local_and_catalogue(client, db, albeniz):
    db.add_all(
        [
            Work(title="Suite española n.º 1, op. 47", openopus_id="500", composer_id=albeniz.id),
            Work(title="Pavana-capricho, op. 12", nickname="Pavana", composer_id=albeniz.id),
        ]
    )
    await db.commit()

    catalogue = [
        {
            "title": "Suite española n.º 1, op. 47",
            "nickname": None,
            "openopus_id": "500",
        },  # local by id
        {
            "title": "Pavana capricho, op. 12",
            "nickname": None,
            "openopus_id": "501",
        },  # local by title
        {"title": "Suite Iberia, libro 1", "nickname": None, "openopus_id": "502"},
    ]
    with patch(
        "app.services.openopus.search_work", new=AsyncMock(return_value=catalogue)
    ) as search:
        response = await client.get(
            "/api/works/search", params={"q": "", "composer_id": albeniz.id}
        )

    assert response.status_code == 200
    titles = [w["title"] for w in response.json()]
    assert titles == [
        "Pavana-capricho, op. 12",
        "Suite española n.º 1, op. 47",
        "Suite Iberia, libro 1",
    ]
    # The local composer's OpenOpus id is what the catalogue is asked for.
    search.assert_awaited_once_with("", composer_id="216")


@pytest.mark.asyncio
async def test_work_search_matches_local_nickname_without_accents(client, db, albeniz):
    db.add(Work(title="Sonata n.º 5", nickname="Española", composer_id=albeniz.id))
    await db.commit()

    with patch("app.services.openopus.search_work", new=AsyncMock(return_value=[])):
        response = await client.get(
            "/api/works/search", params={"q": "espanola sonata", "composer_id": albeniz.id}
        )
    assert [w["title"] for w in response.json()] == ["Sonata n.º 5"]


@pytest.mark.asyncio
async def test_work_search_returns_local_works_when_catalogue_is_down(client, db, albeniz):
    db.add(Work(title="Mallorca, op. 202", composer_id=albeniz.id))
    await db.commit()

    with patch(
        "app.services.openopus.search_work", new=AsyncMock(side_effect=httpx.ConnectError("down"))
    ):
        response = await client.get("/api/works/search", params={"composer_id": albeniz.id})
    assert response.status_code == 200
    assert [w["title"] for w in response.json()] == ["Mallorca, op. 202"]


@pytest.mark.asyncio
async def test_work_search_by_openopus_composer_not_yet_stored(client):
    catalogue = [{"title": "Goyescas", "nickname": None, "openopus_id": "700"}]
    with patch(
        "app.services.openopus.search_work", new=AsyncMock(return_value=catalogue)
    ) as search:
        response = await client.get("/api/works/search?q=goy&openopus_composer_id=33")
    assert response.json() == catalogue
    search.assert_awaited_once_with("goy", composer_id="33")


# ---------------------------------------------------------------------------
# Suggestions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_suggested_composers_prefer_the_discipline(db):
    region = Region(name="R", slug="r")
    piano = Discipline(name="Piano", slug="piano")
    violin = Discipline(name="Violín", slug="violin")
    user = User(email="suggest@test.com")
    chopin = Composer(name="Chopin")
    bach = Composer(name="Bach")
    paganini = Composer(name="Paganini")
    unreported = Composer(name="Nobody")
    db.add_all([region, piano, violin, user, chopin, bach, paganini, unreported])
    await db.flush()

    def report(discipline, year, composer, title):
        event = ExamEvent(year=year, region_id=region.id, discipline_id=discipline.id)
        work = Work(title=title, composer_id=composer.id)
        db.add_all([event, work])
        return event, work

    rows = [
        report(piano, 2020, chopin, "Balada 1"),
        report(piano, 2021, chopin, "Balada 2"),
        report(piano, 2022, bach, "Preludio"),
        report(violin, 2020, paganini, "Capricho 1"),
        report(violin, 2021, paganini, "Capricho 2"),
        report(violin, 2022, paganini, "Capricho 3"),
    ]
    await db.flush()
    db.add_all(Report(user_id=user.id, event_id=e.id, work_id=w.id) for e, w in rows)
    await db.commit()

    names = [c["name"] for c in await CatalogService.suggested_composers(db, piano.id)]
    # Piano's own composers first (most reported first), then the rest by overall count.
    assert names == ["Chopin", "Bach", "Paganini"]
