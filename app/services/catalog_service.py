import asyncio
import logging
from collections.abc import Awaitable
from typing import Any

import httpx
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.constants import Suggestions
from app.models import Composer, ExamEvent, Report, Work
from app.services import openopus, text, wikidata

logger = logging.getLogger("uvicorn")

LOCAL_COMPOSER_LIMIT = 10
EXTERNAL_COMPOSER_LIMIT = 12


def composer_dict(composer: Composer) -> dict[str, Any]:
    return {
        "id": composer.id,
        "name": composer.name,
        "wikidata_id": composer.wikidata_id,
        "openopus_id": composer.openopus_id,
        "is_verified": bool(composer.is_verified),
    }


def work_dict(work: Work) -> dict[str, Any]:
    return {
        "id": work.id,
        "title": work.title,
        "nickname": work.nickname,
        "openopus_id": work.openopus_id,
        "is_verified": bool(work.is_verified),
    }


async def _or_empty(source: str, lookup: Awaitable[list[dict[str, Any]]]) -> list[dict[str, Any]]:
    """Await an external lookup, treating an unavailable catalogue as "no results"."""
    try:
        return await lookup
    except httpx.HTTPError as e:
        logger.warning("%s composer search failed: %r", source, e)
        return []


class CatalogService:
    """Composer and work lookups for the contribute form: local database first, then the
    external catalogues, merged so the same composer or work is offered only once."""

    @staticmethod
    async def search_local_composers(db: AsyncSession, query: str) -> list[dict[str, Any]]:
        query_tokens = text.tokens(query)
        if not query_tokens:
            return []
        stmt = select(Composer)
        for token in query_tokens:
            stmt = stmt.filter(Composer.search_text.contains(token, autoescape=True))
        stmt = stmt.order_by(Composer.is_verified.desc(), Composer.name).limit(LOCAL_COMPOSER_LIMIT)
        result = await db.execute(stmt)
        return [composer_dict(c) for c in result.scalars().all()]

    @staticmethod
    async def search_external_composers(db: AsyncSession, query: str) -> list[dict[str, Any]]:
        """OpenOpus and Wikidata results for a query, merged so each person appears once.

        Either catalogue may be down; the other one's results are still returned.
        """
        openopus_results, wikidata_results = await asyncio.gather(
            _or_empty("OpenOpus", openopus.search_composers(query)),
            _or_empty("Wikidata", wikidata.search_composer(query)),
        )

        local = (await db.execute(select(Composer))).scalars().all()
        by_name = {c.search_text: c for c in local if c.search_text}
        by_openopus = {c.openopus_id: c for c in local if c.openopus_id}
        by_wikidata = {c.wikidata_id: c for c in local if c.wikidata_id}

        merged: list[dict[str, Any]] = []
        seen_names: set[str] = set()
        seen_local: set[int] = set()

        def add_local(composer: Composer) -> None:
            # A catalogue hit for someone we already store (typically found under another
            # spelling, e.g. "Chaikovski" for a composer stored as "Tchaikovsky") is
            # offered as the stored composer, so picking it cannot create a duplicate.
            if composer.id not in seen_local:
                seen_local.add(composer.id)
                merged.append(composer_dict(composer))

        # OpenOpus first: only its composers have a searchable catalogue of works.
        for item in openopus_results:
            name = text.normalize(item["name"])
            known = by_openopus.get(item["openopus_id"]) or by_name.get(name)
            if known:
                add_local(known)
            elif name not in seen_names:
                seen_names.add(name)
                merged.append({**item, "source": "OpenOpus"})

        for item in wikidata_results:
            names = {text.normalize(item["name"]), text.normalize(item.get("name_en"))} - {""}
            known = by_wikidata.get(item["wikidata_id"]) or next(
                (by_name[n] for n in names if n in by_name), None
            )
            if known:
                add_local(known)
            elif not names & seen_names:
                seen_names |= names
                merged.append(
                    {
                        "name": item["name"],
                        "wikidata_id": item["wikidata_id"],
                        "description": item.get("description"),
                        "source": "Wikidata",
                    }
                )

        return merged[:EXTERNAL_COMPOSER_LIMIT]

    @staticmethod
    async def search_works(
        db: AsyncSession,
        query: str,
        composer_id: int | None,
        openopus_composer_id: str | None,
    ) -> list[dict[str, Any]]:
        """Works by one composer matching every word of the query: local works first,
        then the OpenOpus catalogue without the entries already stored locally."""
        query_tokens = text.tokens(query)
        local: list[dict[str, Any]] = []

        if composer_id is not None:
            composer = (
                await db.execute(select(Composer).filter(Composer.id == composer_id))
            ).scalar_one_or_none()
            if composer is None:
                return []
            openopus_composer_id = composer.openopus_id or openopus_composer_id

            # Most reported first, so with an empty query the likeliest works lead.
            stmt = (
                select(Work, func.count(Report.id).label("reports"))
                .outerjoin(Report, Report.work_id == Work.id)
                .filter(Work.composer_id == composer_id)
                .group_by(Work.id)
                .order_by(func.count(Report.id).desc(), Work.title)
            )
            for token in query_tokens:
                stmt = stmt.filter(Work.search_text.contains(token, autoescape=True))
            local = [work_dict(work) for work, _ in (await db.execute(stmt)).all()]

        remote: list[dict[str, Any]] = []
        if openopus_composer_id:
            try:
                remote = await openopus.search_work(query, composer_id=openopus_composer_id)
            except httpx.HTTPError as e:
                logger.warning("OpenOpus work search failed: %r", e)

        local_openopus = {w["openopus_id"] for w in local if w["openopus_id"]}
        local_titles = {text.normalize(w["title"]) for w in local}
        remote = [
            w
            for w in remote
            if w["openopus_id"] not in local_openopus
            and text.normalize(w["title"]) not in local_titles
        ]
        return (local + remote)[: Suggestions.MAX_WORKS]

    @staticmethod
    async def suggested_composers(db: AsyncSession, discipline_id: int) -> list[dict[str, Any]]:
        """Composers offered before the user types anything: the most reported in this
        discipline, topped up with the most reported overall."""

        def most_reported(*filters: Any) -> Any:
            return (
                select(Composer)
                .join(Work, Work.composer_id == Composer.id)
                .join(Report, Report.work_id == Work.id)
                .join(ExamEvent, ExamEvent.id == Report.event_id)
                .filter(*filters)
                .group_by(Composer.id)
                .order_by(func.count(Report.id).desc(), Composer.name)
                .limit(Suggestions.MAX_COMPOSERS)
            )

        in_discipline = (
            (await db.execute(most_reported(ExamEvent.discipline_id == discipline_id)))
            .scalars()
            .all()
        )
        composers = list(in_discipline)
        if len(composers) < Suggestions.MAX_COMPOSERS:
            known = {c.id for c in composers}
            overall = (await db.execute(most_reported())).scalars().all()
            composers += [c for c in overall if c.id not in known]
        return [composer_dict(c) for c in composers[: Suggestions.MAX_COMPOSERS]]
