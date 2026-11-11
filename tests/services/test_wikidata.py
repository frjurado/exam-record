from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services import wikidata

SEARCH_RESPONSE = {"query": {"search": [{"title": "Q7315"}, {"title": "Q999"}]}}
ENTITIES_RESPONSE = {
    "entities": {
        "Q7315": {
            "labels": {
                "en": {"value": "Pyotr Ilyich Tchaikovsky"},
                "es": {"value": "Piotr Ilich Chaikovski"},
            },
            "descriptions": {
                "en": {"value": "Russian composer"},
                "es": {"value": "compositor ruso"},
            },
        },
        # Only an English label: used as the fallback.
        "Q999": {"labels": {"en": {"value": "Some Composer"}}, "descriptions": {}},
    }
}


def mock_http(*json_responses):
    responses = []
    for data in json_responses:
        response = MagicMock()
        response.json.return_value = data
        response.raise_for_status = lambda: None
        responses.append(response)

    client = AsyncMock()
    client.get.side_effect = responses
    patcher = patch("app.services.wikidata.httpx.AsyncClient")
    client_cls = patcher.start()
    client_cls.return_value.__aenter__.return_value = client
    return patcher, client


@pytest.mark.asyncio
async def test_search_composer_filters_by_occupation_and_prefers_spanish():
    patcher, client = mock_http(SEARCH_RESPONSE, ENTITIES_RESPONSE)
    try:
        results = await wikidata.search_composer("chaikovski")
    finally:
        patcher.stop()

    assert results == [
        {
            "wikidata_id": "Q7315",
            "name": "Piotr Ilich Chaikovski",
            "name_en": "Pyotr Ilyich Tchaikovsky",
            "description": "compositor ruso",
        },
        {
            "wikidata_id": "Q999",
            "name": "Some Composer",
            "name_en": "Some Composer",
            "description": None,
        },
    ]
    search_params = client.get.call_args_list[0].kwargs["params"]
    assert search_params["srsearch"] == "haswbstatement:P106=Q36834 chaikovski"


@pytest.mark.asyncio
async def test_search_composer_no_hits_skips_entity_lookup():
    patcher, client = mock_http({"query": {"search": []}})
    try:
        assert await wikidata.search_composer("zzzz") == []
    finally:
        patcher.stop()
    assert client.get.call_count == 1


@pytest.mark.asyncio
async def test_get_composer_by_id():
    patcher, _ = mock_http(ENTITIES_RESPONSE)
    try:
        result = await wikidata.get_composer_by_id("Q7315")
    finally:
        patcher.stop()
    assert result["name"] == "Piotr Ilich Chaikovski"
    assert result["name_en"] == "Pyotr Ilyich Tchaikovsky"
    assert result["wikidata_id"] == "Q7315"
