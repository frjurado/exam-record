"""Pages that look across exams: one work, one composer (and, later, the statistics).

Everything is computed at query time from reports and votes, like the consensus itself.
An "appearance" is one report of a work for one exam, together with how that report
stands in its exam (see ConsensusService.report_standing). Only verified and unconfirmed
appearances are counted; a disputed exam counts for nobody until it is resolved.
"""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import joinedload, selectinload

from app.models import Composer, ExamEvent, Report, Work
from app.services.consensus import ConsensusService
from app.services.work_service import WorkService

COUNTED = ("verified", "unconfirmed")


class BrowseService:
    @staticmethod
    async def appearances(
        db: AsyncSession, *, work_id: int | None = None, composer_id: int | None = None
    ) -> list[dict[str, Any]]:
        """Every report of the given work (or of any work by the given composer), newest
        exam first, with its standing in that exam."""
        wanted = (
            Report.work_id == work_id if work_id is not None else Work.composer_id == composer_id
        )
        stmt = (
            select(ExamEvent)
            .where(ExamEvent.reports.any(Report.work.has(wanted) if work_id is None else wanted))
            .options(
                selectinload(ExamEvent.reports).joinedload(Report.work).joinedload(Work.composer),
                selectinload(ExamEvent.reports).selectinload(Report.votes),
                joinedload(ExamEvent.region),
                joinedload(ExamEvent.discipline),
            )
        )
        events = (await db.execute(stmt)).unique().scalars().all()

        found: list[dict[str, Any]] = []
        for event in events:
            outcome = ConsensusService.event_outcome(event.reports)
            for report in event.reports:
                if work_id is not None and report.work_id != work_id:
                    continue
                if work_id is None and report.work.composer_id != composer_id:
                    continue
                standing = ConsensusService.report_standing(report, outcome)
                found.append(
                    {
                        "work": report.work,
                        "year": event.year,
                        "region": event.region,
                        "discipline": event.discipline,
                        "url": f"/examenes/{event.region.slug}/{event.discipline.slug}/{event.year}",
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
        appearances = await BrowseService.appearances(db, work_id=work_id)
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
        appearances = await BrowseService.appearances(db, composer_id=composer_id)

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
