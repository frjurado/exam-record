from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services import openopus


def mock_http(json_data, status_code=200):
    """Patch openopus's httpx client so every GET returns the given JSON."""
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = json_data
    response.raise_for_status = lambda: None

    client = AsyncMock()
    client.get.return_value = response
    patcher = patch("app.services.openopus.httpx.AsyncClient")
    client_cls = patcher.start()
    client_cls.return_value.__aenter__.return_value = client
    return patcher, client


BEETHOVEN_WORKS = {
    "works": [
        {
            "title": 'Piano Sonata no. 14 in C sharp minor, op. 27 no. 2, "Moonlight"',
            "subtitle": "",
            "searchterms": "",
            "popular": "1",
            "id": "100",
        },
        {
            "title": "Symphony no. 5 in C minor, op. 67",
            "subtitle": "",
            "searchterms": "",
            "popular": "1",
            "id": "101",
        },
        {
            "title": "Bagatelle in A minor, WoO 59",
            "subtitle": "Für Elise",
            "searchterms": "",
            "popular": "0",
            "id": "102",
        },
    ]
}


@pytest.mark.asyncio
async def test_get_popular_composers():
    patcher, _ = mock_http(
        {"composers": [{"name": "Bach", "id": "87"}, {"name": "Mozart", "id": "140"}]}
    )
    try:
        results = await openopus.get_popular_composers()
    finally:
        patcher.stop()
    assert [c["name"] for c in results] == ["Bach", "Mozart"]


@pytest.mark.asyncio
async def test_search_composers_maps_fields():
    patcher, client = mock_http(
        {
            "composers": [
                {
                    "id": "216",
                    "name": "Albéniz",
                    "complete_name": "Isaac Albéniz",
                    "birth": "1860-01-01",
                    "death": "1909-01-01",
                    "epoch": "Late Romantic",
                }
            ]
        }
    )
    try:
        results = await openopus.search_composers("albéniz")
    finally:
        patcher.stop()

    assert results == [
        {"name": "Isaac Albéniz", "openopus_id": "216", "description": "Late Romantic, 1860–1909"}
    ]
    # The query is percent-encoded into the path.
    assert "alb%C3%A9niz.json" in client.get.call_args.args[0]


@pytest.mark.asyncio
async def test_search_composers_no_results():
    patcher, _ = mock_http({"status": {"success": "false"}})
    try:
        assert await openopus.search_composers("zzzz") == []
    finally:
        patcher.stop()


@pytest.mark.asyncio
async def test_find_composer_id_requires_exact_name():
    patcher, _ = mock_http(
        {
            "composers": [
                {"id": "1", "name": "Bach", "complete_name": "Carl Philipp Emanuel Bach"},
                {"id": "87", "name": "Bach", "complete_name": "Johann Sebastian Bach"},
            ]
        }
    )
    try:
        assert await openopus.find_composer_id("johann sebastian BACH") == "87"
        assert await openopus.find_composer_id("Johann Christian Bach") is None
    finally:
        patcher.stop()


@pytest.mark.asyncio
async def test_search_work_matches_spanish_and_english_words():
    patcher, client = mock_http(BEETHOVEN_WORKS)
    try:
        spanish = await openopus.search_work("sonata do sostenido", composer_id="145")
        english = await openopus.search_work("moonlight", composer_id="145")
        nickname = await openopus.search_work("claro de luna", composer_id="145")
        subtitle = await openopus.search_work("elise", composer_id="145")
        nothing = await openopus.search_work("cuarteto", composer_id="145")
    finally:
        patcher.stop()

    assert [w["openopus_id"] for w in spanish] == ["100"]
    assert spanish[0]["title"] == "Sonata para piano n.º 14 en do sostenido menor, op. 27 n.º 2"
    assert spanish[0]["nickname"] == "Claro de luna"
    assert [w["openopus_id"] for w in english] == ["100"]
    assert [w["openopus_id"] for w in nickname] == ["100"]
    assert [w["openopus_id"] for w in subtitle] == ["102"]
    assert nothing == []
    # Five searches, one download: the catalogue is cached per composer.
    assert client.get.call_count == 1


@pytest.mark.asyncio
async def test_search_work_empty_query_lists_popular_first():
    patcher, _ = mock_http(BEETHOVEN_WORKS)
    try:
        results = await openopus.search_work("", composer_id="145")
    finally:
        patcher.stop()
    assert [w["openopus_id"] for w in results] == ["101", "100", "102"]


@pytest.mark.asyncio
async def test_search_work_without_composer_returns_nothing():
    assert await openopus.search_work("sonata") == []


def test_name_search_terms_skip_words_openopus_rejects():
    # OpenOpus refuses searches under four letters, so "Sor" cannot be the search term.
    assert openopus.name_search_terms("Fernando Sor") == ["fernando"]
    assert openopus.name_search_terms("Carl Philipp Emanuel Bach") == [
        "bach",
        "philipp",
        "emanuel",
        "carl",
    ]
    assert openopus.name_search_terms("") == []


async def test_find_composer_id_with_a_short_surname():
    from unittest.mock import AsyncMock, patch

    found = [
        {"name": "Fernando Lopes-Graça", "openopus_id": "119", "description": ""},
        {"name": "Fernando Sor", "openopus_id": "212", "description": ""},
    ]
    search = AsyncMock(return_value=found)
    with patch("app.services.openopus.search_composers", search):
        assert await openopus.find_composer_id("Fernando Sor") == "212"
    search.assert_awaited_once_with("fernando")
