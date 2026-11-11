from typing import Any

import httpx

WIKIDATA_API_URL = "https://www.wikidata.org/w/api.php"
TIMEOUT_SECONDS = 10.0
# Wikimedia asks automated clients to identify themselves with a way to reach the operator.
HEADERS = {"User-Agent": "WikiAnalisisBot/1.0 (https://exam-record-beta.fly.dev)"}

# occupation (P106) = composer (Q36834)
_COMPOSER_FILTER = "haswbstatement:P106=Q36834"


def _pick(values: dict[str, Any], *languages: str) -> str | None:
    for language in languages:
        value = values.get(language, {}).get("value")
        if value:
            return str(value)
    return None


def _entity_summary(wikidata_id: str, entity: dict[str, Any]) -> dict[str, Any]:
    labels = entity.get("labels", {})
    return {
        "wikidata_id": wikidata_id,
        "name": _pick(labels, "es", "en"),
        "name_en": _pick(labels, "en", "es"),
        "description": _pick(entity.get("descriptions", {}), "es", "en"),
    }


async def _get_entities(client: httpx.AsyncClient, ids: list[str]) -> dict[str, Any]:
    response = await client.get(
        WIKIDATA_API_URL,
        params={
            "action": "wbgetentities",
            "ids": "|".join(ids),
            "props": "labels|descriptions",
            "languages": "es|en",
            "format": "json",
        },
    )
    response.raise_for_status()
    entities: dict[str, Any] = response.json().get("entities", {})
    return entities


async def search_composer(query: str, limit: int = 6) -> list[dict[str, Any]]:
    """Search Wikidata for people whose occupation is composer.

    The full-text search matches labels and aliases in every language, so "Chaikovski"
    and "Tchaikovsky" find the same person. Names come back in Spanish when Wikidata
    has a Spanish label, otherwise in English.
    """
    async with httpx.AsyncClient(headers=HEADERS, timeout=TIMEOUT_SECONDS) as client:
        response = await client.get(
            WIKIDATA_API_URL,
            params={
                "action": "query",
                "list": "search",
                "srsearch": f"{_COMPOSER_FILTER} {query}",
                "srlimit": str(limit),
                "format": "json",
            },
        )
        response.raise_for_status()
        ids = [hit["title"] for hit in response.json().get("query", {}).get("search", [])]
        if not ids:
            return []
        entities = await _get_entities(client, ids)

    results = [_entity_summary(qid, entities.get(qid, {})) for qid in ids]
    return [r for r in results if r["name"]]


async def get_composer_by_id(wikidata_id: str) -> dict[str, Any]:
    """Names and description for one Wikidata entity."""
    async with httpx.AsyncClient(headers=HEADERS, timeout=TIMEOUT_SECONDS) as client:
        entities = await _get_entities(client, [wikidata_id])
    return _entity_summary(wikidata_id, entities.get(wikidata_id, {}))
