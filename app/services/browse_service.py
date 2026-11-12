"""Pages that look across exams: one work, one composer, the statistics, a region's coverage.

Everything is computed at query time from reports and votes, like the consensus itself.
An "appearance" is one report of a work for one exam, together with how that report
stands in its exam (see ConsensusService.report_standing). Only verified and unconfirmed
appearances are counted; a disputed exam counts for nobody until it is resolved. The same
work set for two disciplines in one year counts twice: those choices are made separately.
"""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import joinedload, selectinload

from app.core.constants import Coverage, Statistics
from app.models import Composer, Discipline, ExamEvent, Report, Work
from app.services.consensus import ConsensusService
from app.services.exam_service import ExamService
from app.services.reference_data_service import ReferenceDataService
from app.services.work_service import WorkService

COUNTED = ("verified", "unconfirmed")


def exam_url(region_slug: str, discipline_slug: str, year: int) -> str:
    return f"/examenes/{region_slug}/{discipline_slug}/{year}"


class BrowseService:
    @staticmethod
    async def _events(db: AsyncSession, *conditions: Any) -> list[ExamEvent]:
        """Exams that have reports and meet the conditions, loaded for consensus."""
        stmt = (
            select(ExamEvent)
            .where(ExamEvent.reports.any(), *conditions)
            .options(
                selectinload(ExamEvent.reports).joinedload(Report.work).joinedload(Work.composer),
                selectinload(ExamEvent.reports).selectinload(Report.votes),
                joinedload(ExamEvent.region),
                joinedload(ExamEvent.discipline),
            )
        )
        return list((await db.execute(stmt)).unique().scalars().all())

    @staticmethod
    def _appearances(events: list[ExamEvent]) -> list[dict[str, Any]]:
        """Every report of the given exams, newest exam first, with its standing."""
        found: list[dict[str, Any]] = []
        for event in events:
            outcome = ConsensusService.event_outcome(event.reports)
            for report in event.reports:
                standing = ConsensusService.report_standing(report, outcome)
                found.append(
                    {
                        "work": report.work,
                        "year": event.year,
                        "region": event.region,
                        "discipline": event.discipline,
                        "url": exam_url(event.region.slug, event.discipline.slug, event.year),
                        "standing": standing,
                        "counted": standing in COUNTED,
                        "details": report.movement_details,
                    }
                )
        found.sort(key=lambda a: (-a["year"], a["discipline"].name, a["region"].name))
        return found

    @staticmethod
    async def work_context(db: AsyncSession, work_id: int) -> dict[str, Any] | None:
        stmt = select(Work).where(Work.id == work_id).options(joinedload(Work.composer))
        work = (await db.execute(stmt)).scalar_one_or_none()
        if work is None:
            return None
        events = await BrowseService._events(db, ExamEvent.reports.any(Report.work_id == work_id))
        appearances = [a for a in BrowseService._appearances(events) if a["work"].id == work_id]
        return {
            "work": work,
            "composer": work.composer,
            "score_url": WorkService.get_score_url(work),
            "appearances": [a for a in appearances if a["counted"]],
            "mentions": [a for a in appearances if not a["counted"]],
        }

    @staticmethod
    async def composer_context(db: AsyncSession, composer_id: int) -> dict[str, Any] | None:
        composer = (
            await db.execute(select(Composer).where(Composer.id == composer_id))
        ).scalar_one_or_none()
        if composer is None:
            return None
        events = await BrowseService._events(
            db, ExamEvent.reports.any(Report.work.has(Work.composer_id == composer_id))
        )
        appearances = [
            a for a in BrowseService._appearances(events) if a["work"].composer_id == composer_id
        ]

        by_work: dict[int, dict[str, Any]] = {}
        for appearance in appearances:
            row = by_work.setdefault(
                appearance["work"].id,
                {"work": appearance["work"], "appearances": [], "mentions": []},
            )
            row["appearances" if appearance["counted"] else "mentions"].append(appearance)

        # Most frequent first; works only ever mentioned in unresolved exams go last.
        works = sorted(
            by_work.values(),
            key=lambda row: (-len(row["appearances"]), row["work"].title),
        )
        return {
            "composer": composer,
            "works": [row for row in works if row["appearances"]],
            "only_mentioned": [row for row in works if not row["appearances"]],
            "total": sum(len(row["appearances"]) for row in works),
        }

    @staticmethod
    async def statistics_context(
        db: AsyncSession, discipline_slug: str | None = None
    ) -> dict[str, Any] | None:
        """Most frequent composers and works, overall or for one discipline. None if the
        discipline does not exist."""
        discipline = None
        conditions: list[Any] = []
        if discipline_slug:
            discipline = await ReferenceDataService.get_discipline_by_slug(db, discipline_slug)
            if discipline is None:
                return None
            conditions.append(ExamEvent.discipline_id == discipline.id)

        events = await BrowseService._events(db, *conditions)
        counted = [a for a in BrowseService._appearances(events) if a["counted"]]

        composers: dict[int, dict[str, Any]] = {}
        works: dict[int, dict[str, Any]] = {}
        for appearance in counted:
            work = appearance["work"]
            c = composers.setdefault(
                work.composer_id, {"composer": work.composer, "count": 0, "works": set()}
            )
            c["count"] += 1
            c["works"].add(work.id)
            w = works.setdefault(work.id, {"work": work, "appearances": []})
            w["appearances"].append(appearance)

        composer_rows = sorted(
            composers.values(), key=lambda row: (-row["count"], row["composer"].name)
        )
        for row in composer_rows:
            row["works"] = len(row["works"])
        # A work that fell once is not a pattern; the list starts at two.
        work_rows = sorted(
            (
                row
                for row in works.values()
                if len(row["appearances"]) >= Statistics.MIN_WORK_APPEARANCES
            ),
            key=lambda row: (-len(row["appearances"]), row["work"].title),
        )

        # Disciplines offered in the filter: those with at least one exam on record.
        with_data = (
            (
                await db.execute(
                    select(Discipline)
                    .where(Discipline.events.any(ExamEvent.reports.any()))
                    .order_by(Discipline.name)
                )
            )
            .scalars()
            .all()
        )
        return {
            "discipline": discipline,
            "disciplines": with_data,
            "composers": composer_rows[: Statistics.MAX_ROWS],
            "works": work_rows[: Statistics.MAX_ROWS],
            "exams_counted": len(counted),
            "exams_disputed": len(events) - len(counted),
            "single_works": len(works) - len(work_rows),
        }

    @staticmethod
    async def coverage_context(db: AsyncSession, region_slug: str) -> dict[str, Any] | None:
        """Disciplines × recent years for one region: what is on record and what is missing."""
        region = await ReferenceDataService.get_region_by_slug(db, region_slug)
        if region is None:
            return None
        latest = ExamService.latest_exam_year()
        years = list(range(latest, latest - Coverage.YEARS, -1))
        events = await BrowseService._events(
            db, ExamEvent.region_id == region.id, ExamEvent.year.in_(years)
        )
        status = {
            (e.discipline_id, e.year): ConsensusService.event_outcome(e.reports)["status"]
            for e in events
        }
        disciplines = (
            (await db.execute(select(Discipline).order_by(Discipline.name))).scalars().all()
        )
        rows: list[dict[str, Any]] = []
        for discipline in disciplines:
            cells = []
            for year in years:
                state = status.get((discipline.id, year), "empty")
                url = exam_url(region.slug, discipline.slug, year)
                cells.append(
                    {
                        "year": year,
                        "status": state,
                        "url": url if state != "empty" else f"{url}/contribute",
                    }
                )
            rows.append(
                {
                    "discipline": discipline,
                    "cells": cells,
                    "filled": sum(1 for c in cells if c["status"] != "empty"),
                }
            )
        # Disciplines with most on record first, so the table starts with content.
        rows.sort(key=lambda row: (-row["filled"], row["discipline"].name))
        return {
            "region": region,
            "years": years,
            "rows": rows,
            "filled": sum(row["filled"] for row in rows),
            "total": len(rows) * len(years),
        }
