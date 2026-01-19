import httpx
from typing import List, Dict, Optional

WIKIDATA_API_URL = "https://www.wikidata.org/w/api.php"

async def search_composer(query: str) -> List[Dict]:
    """
    Search for a composer on Wikidata.
    """
    params = {
        "action": "wbsearchentities",
        "search": query,
        "language": "en",
        "format": "json",
        "type": "item",
        # P106 is "occupation", Q36834 is "composer". 
        # Wikidata search is broad, filtering might be needed client-side or we rely on description.
        # For simple text search, we just pass the query.
        "limit": 10
    }
    
    headers = {
        "User-Agent": "ExamRecordbot/1.0 (exam-record-project; contact@example.com)"
    }
    
    async with httpx.AsyncClient(headers=headers) as client:
        response = await client.get(WIKIDATA_API_URL, params=params)
        response.raise_for_status()
        data = response.json()
        
    results = []
    for item in data.get("search", []):
        # We could filter by 'description' containing 'composer' if we wanted to be stricter,
        # but for now we follow the plan: return simplified objects.
        results.append({
            "name": item.get("label"),
            "wikidata_id": item.get("id"),
            "description": item.get("description"),
            # Wikidata API search doesn't always return birth/death directly in the search result.
            # We might need a secondary query or just return what we have for the search list.
            # The plan says "birth/death" but standard wbsearchentities checks text match.
            # Let's stick to what's available or simple.
            # If we strictly need birth/death in search key, we'd need SPARQL or EntityData.
            # For this MVP step, let's return what we can and maybe fetch details later.
        })
    return results

async def get_composer_by_id(wikidata_id: str) -> Dict:
    """
    Fetch details for a specific Wikidata ID.
    Using the entity data endpoint.
    """
    url = f"https://www.wikidata.org/wiki/Special:EntityData/{wikidata_id}.json"
    
    headers = {
        "User-Agent": "ExamRecordbot/1.0 (exam-record-project; contact@example.com)"
    }
    
    async with httpx.AsyncClient(headers=headers, follow_redirects=True) as client:
        response = await client.get(url)
        response.raise_for_status()
        data = response.json()
        
    entities = data.get("entities", {})
    entity = entities.get(wikidata_id, {})
    
    # Extract labels, claims etc.
    # This can get complex. For MVP, let's just return the raw entity or a slightly cleaned up version.
    return {
        "wikidata_id": wikidata_id,
        "name": entity.get("labels", {}).get("en", {}).get("value"),
        "claims": entity.get("claims", {}) # Contains structured data like dates
    }
