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
         # To filter by occupation, we often need a secondary check because standard search doesn't return claims.
         # Ideally, we would use a SPARQL query or WBGETENTITIES, but for search box speed, we might have to accept some noise.
         # However, we can check the description for "composer".
         description = item.get("description", "").lower()
         if "composer" in description:
            results.append({
                "name": item.get("label"),
                "wikidata_id": item.get("id"),
                "description": item.get("description"),
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
