from typing import List, Any, Optional
from fastapi import APIRouter, HTTPException, Query, Depends
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.models import Composer

from app.services import wikidata

router = APIRouter()

@router.get("/search", response_model=List[Any])
async def search_composers(
    q: str = Query(..., min_length=2, description="Name of the composer to search for"),
    source: str = Query("local", description="Source to search: 'local' or 'wikidata'"),
    db: AsyncSession = Depends(get_db)
):
    """
    Search for a composer by name.
    Default: Local DB.
    Optional: Wikidata (source='wikidata').
    """
    try:
        if source == "wikidata":
            results = await wikidata.search_composer(q)
            return results
        else:
            # Local search
            stmt = select(Composer).filter(Composer.name.ilike(f"%{q}%")).limit(10)
            result = await db.execute(stmt)
            composers = result.scalars().all()
            return [
                {
                    "id": c.id,
                    "name": c.name,
                    "wikidata_id": c.wikidata_id,
                    "openopus_id": c.openopus_id,
                    "is_verified": c.is_verified
                }
                for c in composers
            ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
