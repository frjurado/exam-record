from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import RateLimit
from app.core.limiter import limiter
from app.db.session import get_db
from app.services.catalog_service import CatalogService

router = APIRouter()


@router.get(
    "/search",
    response_model=list[Any],
    summary="Search one composer's works",
    description=(
        "Works by a single composer whose title or nickname contains every word of `q`, "
        "ignoring case and accents. Local works come first, followed by the composer's "
        "OpenOpus catalogue (titles rendered in Spanish) without the entries already stored "
        "locally. An empty `q` lists the composer's most reported and most popular works. "
        "Identify the composer with `composer_id` (local) or `openopus_composer_id`."
    ),
    responses={
        200: {"description": "List of matching works"},
        400: {"description": "No composer was identified"},
    },
)
@limiter.limit(RateLimit.CATALOG_SEARCH)
async def search_works(
    request: Request,
    q: str = Query("", max_length=100, description="Words of the title to search for"),
    composer_id: int | None = Query(None, description="Local composer ID"),
    openopus_composer_id: str | None = Query(
        None, max_length=32, description="OpenOpus composer ID, for composers not stored locally"
    ),
    db: AsyncSession = Depends(get_db),
) -> list[Any]:
    """Search a composer's works in the local DB and the OpenOpus catalogue."""
    if composer_id is None and not openopus_composer_id:
        raise HTTPException(status_code=400, detail="Falta identificar al compositor")
    return await CatalogService.search_works(db, q, composer_id, openopus_composer_id)
