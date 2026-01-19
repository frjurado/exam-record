from typing import List, Any
from fastapi import APIRouter, HTTPException, Query

from app.services import wikidata

router = APIRouter()

@router.get("/search", response_model=List[Any])
async def search_composers(
    q: str = Query(..., min_length=2, description="Name of the composer to search for")
):
    """
    Search for a composer by name using Wikidata.
    """
    try:
        results = await wikidata.search_composer(q)
        return results
    except Exception as e:
        # In a real app, we might log this and return 500 or specific error
        raise HTTPException(status_code=500, detail=str(e))
