from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import RateLimit
from app.core.limiter import limiter
from app.db.session import get_db
from app.services.catalog_service import CatalogService

router = APIRouter()


@router.get(
    "/search",
    response_model=list[Any],
    summary="Search for composers by name",
    description=(
        "Search composers by name, ignoring case and accents. `source=local` searches the "
        "local database. `source=external` searches OpenOpus and Wikidata and returns only "
        "composers that are not already stored locally; if one catalogue is unavailable the "
        "other's results are still returned."
    ),
    responses={200: {"description": "List of matching composers"}},
)
@limiter.limit(RateLimit.CATALOG_SEARCH)
async def search_composers(
    request: Request,
    q: str = Query(..., min_length=2, max_length=100, description="Name to search for"),
    source: str = Query("local", pattern="^(local|external)$"),
    db: AsyncSession = Depends(get_db),
) -> list[Any]:
    """Search composers by name in the local DB or in the external catalogues."""
    if source == "external":
        return await CatalogService.search_external_composers(db, q)
    return await CatalogService.search_local_composers(db, q)
