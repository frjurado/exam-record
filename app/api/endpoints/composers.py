from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.session import get_db
from app.models import Composer
from app.services import wikidata

router = APIRouter()


@router.get(
    "/search",
    response_model=list[Any],
    summary="Search for composers by name",
    description=(
        "Search composers by name against the local database or Wikidata. "
        "Local results are limited to 10 entries and match any substring. "
        "Wikidata results are fetched live via SPARQL and include the Wikidata entity ID."
    ),
    responses={
        200: {"description": "List of matching composers"},
        500: {"description": "Upstream search error (e.g. Wikidata unavailable)"},
    },
)
async def search_composers(
    q: str = Query(..., min_length=2, description="Name of the composer to search for"),
    source: str = Query("local", description="Source to search: 'local' or 'wikidata'"),
    db: AsyncSession = Depends(get_db),
) -> list[Any]:
    """Search composers by name in the local DB or via the Wikidata SPARQL endpoint."""
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
                    "is_verified": c.is_verified,
                }
                for c in composers
            ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
