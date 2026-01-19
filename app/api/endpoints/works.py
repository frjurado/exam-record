from typing import List, Any
from fastapi import APIRouter, HTTPException, Query

from app.services import openopus

router = APIRouter()

@router.get("/search", response_model=List[Any])
async def search_works(
    q: str = Query(..., min_length=2, description="Title of the work to search for"),
    composer_id: str = Query(..., description="OpenOpus Composer ID to filter by")
):
    """
    Search for works by title for a specific composer using OpenOpus.
    Requires 'composer_id' because global search is unstable.
    """
    try:
        results = await openopus.search_work(q, composer_id=composer_id)
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
