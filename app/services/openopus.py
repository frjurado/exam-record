import httpx
from typing import List, Dict, Optional

OPENOPUS_API_URL = "https://api.openopus.org"

async def get_popular_composers() -> List[Dict]:
    """
    Fetch popular composers from OpenOpus to seed the database.
    POST /composer/list/pop.json
    """
    url = f"{OPENOPUS_API_URL}/composer/list/pop.json"
    
    async with httpx.AsyncClient() as client:
        # OpenOpus sometimes requires a User-Agent or acts quirky, but usually standard GET works.
        # Wait, the docs say GET is fine.
        response = await client.get(url)
        response.raise_for_status()
        data = response.json()
        
    # OpenOpus structure: { "status": ..., "composers": [ ... ] }
    return data.get("composers", [])

async def search_work(query: str, composer_id: str = None) -> List[Dict]:
    """
    Search for works in OpenOpus.
    Since the global search endpoint seems deprecated/broken, we use the strategy:
    If composer_id is provided, fetch ALL works for that composer and filter locally.
    """
    if not composer_id:
        # Global search is not reliably available via simple API.
        # We require a composer_id to scope the search.
        return []

    # Fetch all works for the composer
    url = f"{OPENOPUS_API_URL}/work/list/composer/{composer_id}/genre/all.json"

    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        # OpenOpus might return 404 if composer not found or invalid
        if response.status_code == 404:
            return []
        response.raise_for_status()
        data = response.json()
        
    all_works = data.get("works", [])
    
    # Filter works by query (case-insensitive)
    query_lower = query.lower()
    return [
        work for work in all_works 
        if query_lower in work.get("title", "").lower() 
        or query_lower in work.get("nickname", "").lower()
    ]
