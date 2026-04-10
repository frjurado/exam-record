from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.session import get_db
from app.models import Work
from app.services import openopus

router = APIRouter()


@router.get(
    "/search",
    response_model=list[Any],
    summary="Search for musical works by title",
    description=(
        "Search works by title (and optionally nickname) against the local database or the OpenOpus API. "
        "Local results match any substring of title or nickname and are capped at 20. "
        "OpenOpus results require `composer_id` (the OpenOpus composer ID) and are fetched live."
    ),
    responses={
        200: {"description": "List of matching works"},
        400: {"description": "`composer_id` is required when `source=openopus`"},
        500: {"description": "Upstream search error (e.g. OpenOpus unavailable)"},
    },
)
async def search_works(
    q: str = Query(..., min_length=2, description="Title of the work to search for"),
    source: str = Query("local", description="Source to search: 'local' or 'openopus'"),
    composer_id: str | None = Query(
        None, description="Composer ID (local integer ID for local search, OpenOpus ID for remote)"
    ),
    db: AsyncSession = Depends(get_db),
) -> list[Any]:
    """Search musical works by title in the local DB or via the OpenOpus API."""
    try:
        if source == "openopus":
            if not composer_id:
                # We allow search without composer_id if source is openopus but openopus service demands it
                # For now, we propagate the requirement
                raise HTTPException(
                    status_code=400, detail="composer_id is required for OpenOpus search"
                )
            results = await openopus.search_work(q, composer_id=composer_id)
            # Map OpenOpus results to unified format if needed, but service now returns consistent dict
            return results
        else:
            # Local search
            stmt = select(Work).filter(
                (Work.title.ilike(f"%{q}%")) | (Work.nickname.ilike(f"%{q}%"))
            )

            if composer_id:
                # Ensure composer_id is integer for local
                try:
                    c_id = int(composer_id)
                    stmt = stmt.filter(Work.composer_id == c_id)
                except ValueError:
                    pass  # Ignore invalid ID format for local search

            stmt = stmt.limit(20)
            result = await db.execute(stmt)
            works = result.scalars().all()
            return [
                {
                    "id": w.id,
                    "title": w.title,
                    "nickname": w.nickname,
                    "openopus_id": w.openopus_id,
                    "composer_id": w.composer_id,
                    "is_verified": w.is_verified,
                }
                for w in works
            ]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
