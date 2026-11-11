from typing import Any, cast
from urllib.parse import quote

import httpx
from cachetools import TTLCache

from app.core.constants import Cache
from app.services import text, titles

OPENOPUS_API_URL = "https://api.openopus.org"
TIMEOUT_SECONDS = 10.0
# OpenOpus answers "Too short search term" to anything under four letters.
MIN_QUERY_LENGTH = 4

# A composer's catalogue is a single large download (Bach has ~1000 works) and changes
# essentially never, so it is fetched once and filtered in memory on every keystroke.
_works_cache: TTLCache[str, list[dict[str, Any]]] = TTLCache(
    maxsize=Cache.OPENOPUS_MAX_COMPOSERS, ttl=Cache.OPENOPUS_TTL_SECONDS
)


def reset_cache() -> None:
    """Clear cached catalogues. Used by tests."""
    _works_cache.clear()


async def get_popular_composers() -> list[dict]:
    """Fetch OpenOpus's "popular" composers, used to seed the local database."""
    url = f"{OPENOPUS_API_URL}/composer/list/pop.json"
    async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
        response = await client.get(url)
        response.raise_for_status()
        data = response.json()
    return cast(list[dict], data.get("composers", []))


async def search_composers(query: str) -> list[dict[str, Any]]:
    """Search OpenOpus composers by name (the API itself ignores accents and case)."""
    url = f"{OPENOPUS_API_URL}/composer/list/search/{quote(query, safe='')}.json"
    async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
        response = await client.get(url)
        if response.status_code == 404:
            return []
        response.raise_for_status()
        data = response.json()

    results = []
    for composer in data.get("composers") or []:
        years = "–".join(
            part[:4] for part in (composer.get("birth"), composer.get("death")) if part
        )
        results.append(
            {
                "name": composer.get("complete_name") or composer.get("name"),
                "openopus_id": str(composer.get("id")),
                "description": ", ".join(p for p in (composer.get("epoch"), years) if p),
            }
        )
    return results


def name_search_terms(name: str) -> list[str]:
    """Words of a composer's name worth sending to OpenOpus: the surname first, then the
    rest from longest to shortest, leaving out those the API rejects as too short
    ("Sor" in "Fernando Sor" is, so that composer is found through "fernando")."""
    name_tokens = text.tokens(name)
    if not name_tokens:
        return []
    ordered = [name_tokens[-1], *sorted(name_tokens[:-1], key=len, reverse=True)]
    return [token for token in ordered if len(token) >= MIN_QUERY_LENGTH]


async def search_composers_by_name(name: str) -> list[dict[str, Any]]:
    """Candidates for a full name: the first of its words that OpenOpus finds anything for."""
    for term in name_search_terms(name):
        results = await search_composers(term)
        if results:
            return results
    return []


async def find_composer_id(name: str) -> str | None:
    """Best-effort OpenOpus id for a composer known only by name (e.g. picked from Wikidata).

    Accepts only an exact match on the full name, so a wrong composer's catalogue is
    never attached.
    """
    name_tokens = text.tokens(name)
    if not name_tokens:
        return None
    wanted = " ".join(name_tokens)
    for candidate in await search_composers_by_name(name):
        if text.normalize(candidate["name"]) == wanted:
            return cast(str, candidate["openopus_id"])
    return None


async def get_composer_works(composer_id: str) -> list[dict[str, Any]]:
    """All works of a composer, with Spanish titles and a normalized search string."""
    cached = _works_cache.get(composer_id)
    if cached is not None:
        return cached

    url = f"{OPENOPUS_API_URL}/work/list/composer/{quote(composer_id, safe='')}/genre/all.json"
    async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
        response = await client.get(url)
        if response.status_code == 404:
            return []
        response.raise_for_status()
        data = response.json()

    works = []
    for raw in data.get("works") or []:
        raw_title = raw.get("title") or ""
        title, nickname = titles.localize_openopus_title(raw_title)
        works.append(
            {
                "title": title,
                "nickname": nickname,
                "subtitle": raw.get("subtitle") or None,
                "openopus_id": str(raw.get("id")),
                "is_verified": True,
                "popular": raw.get("popular") == "1",
                # Both languages are searchable: "moonlight", "sonata piano", "piano sonata".
                "search_text": text.normalize(
                    f"{title} {nickname or ''} {raw_title} {raw.get('subtitle') or ''} {raw.get('searchterms') or ''}"
                ),
            }
        )
    works.sort(key=lambda w: (not w["popular"], w["title"]))

    _works_cache[composer_id] = works
    return works


async def search_work(
    query: str, composer_id: str | None = None, limit: int = 40
) -> list[dict[str, Any]]:
    """Works of one composer whose title contains every word of the query.

    OpenOpus has no usable global work search, so a composer id is required. An empty
    query returns the composer's most popular works first.
    """
    if not composer_id:
        return []

    query_tokens = text.tokens(query)
    public_keys = ("title", "nickname", "subtitle", "openopus_id", "is_verified")
    return [
        {key: work[key] for key in public_keys}
        for work in await get_composer_works(composer_id)
        if text.matches(query_tokens, work["search_text"])
    ][:limit]
