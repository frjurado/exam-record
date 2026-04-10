from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import joinedload

from app.api import deps
from app.core.constants import Calendar, Consensus, Pagination
from app.models import Discipline, ExamEvent, Region, Report, User, Work
from app.services.consensus import ConsensusService
from app.services.work_service import WorkService


class ExamService:
    @staticmethod
    async def get_exam_context(
        db: AsyncSession,
        region_slug: str,
        discipline_slug: str,
        year: int,
        current_user: User | None,
    ) -> dict[str, Any] | None:
        """Return template context for the exam page, or None if the event doesn't exist."""
        stmt = (
            select(ExamEvent)
            .options(
                joinedload(ExamEvent.reports).joinedload(Report.work).joinedload(Work.composer),
                joinedload(ExamEvent.reports).selectinload(Report.votes),
                joinedload(ExamEvent.region),
                joinedload(ExamEvent.discipline),
            )
            .join(Region)
            .join(Discipline)
            .filter(
                Region.slug == region_slug,
                Discipline.slug == discipline_slug,
                ExamEvent.year == year,
            )
        )
        result = await db.execute(stmt)
        event = result.unique().scalar_one_or_none()
        if not event:
            return None

        aggregated = ConsensusService.aggregate_event_reports(event.reports)

        user_has_participated = False
        user_participation_report_id = None
        if current_user:
            (
                user_has_participated,
                user_participation_report_id,
            ) = await deps.check_user_event_participation(db, int(current_user.id), int(event.id))

        return {
            "event": event,
            "region_slug": region_slug,
            "discipline_slug": discipline_slug,
            "year": year,
            "works": aggregated["works"],
            "total_votes": aggregated["total_votes"],
            "event_status": aggregated["event_status"],
            "user": current_user,
            "user_has_participated": user_has_participated,
            "user_participation_report_id": user_participation_report_id,
        }

    @staticmethod
    async def get_discipline_context(
        db: AsyncSession,
        region_slug: str,
        discipline_slug: str,
        cursor: int | None,
        sparse_mode: bool,
        current_user: User | None,
    ) -> dict[str, Any] | None:
        """Return template context for the discipline page, or None if region/discipline not found."""
        region = (
            await db.execute(select(Region).filter(Region.slug == region_slug))
        ).scalar_one_or_none()
        discipline = (
            await db.execute(select(Discipline).filter(Discipline.slug == discipline_slug))
        ).scalar_one_or_none()

        if not region or not discipline:
            return None

        # Determine anchor year using academic year logic
        now = datetime.now()
        base_anchor_year = (
            now.year if now.month >= Calendar.ACADEMIC_YEAR_CUTOFF_MONTH else now.year - 1
        )

        batch_size = Pagination.DEFAULT_BATCH_SIZE

        # Years that have data in the DB
        result_years = await db.execute(
            select(ExamEvent.year)
            .join(ExamEvent.reports)
            .filter(ExamEvent.region_id == region.id, ExamEvent.discipline_id == discipline.id)
        )
        db_years = set(result_years.scalars().all())

        # Build the full sorted year list for this view
        if sparse_mode:
            mandatory_years = set(
                range(base_anchor_year, base_anchor_year - Calendar.MANDATORY_YEARS_WINDOW, -1)
            )
            all_relevant_years = sorted(mandatory_years.union(db_years), reverse=True)
        else:
            min_db_year = min(db_years) if db_years else base_anchor_year
            real_end = min(Calendar.MIN_YEAR, min_db_year)
            all_relevant_years = sorted(range(base_anchor_year, real_end - 1, -1), reverse=True)

        # Cap at anchor year to exclude future years
        all_relevant_years = [y for y in all_relevant_years if y <= base_anchor_year]

        # Apply cursor (descending: show years before the cursor value)
        filtered_years = (
            [y for y in all_relevant_years if y < cursor] if cursor else all_relevant_years
        )
        batch_years = filtered_years[:batch_size]
        show_more = len(filtered_years) > batch_size

        # Fetch events for the batch with enough data for badge display
        stmt = (
            select(ExamEvent)
            .options(
                joinedload(ExamEvent.reports).joinedload(Report.work).joinedload(Work.composer),
                joinedload(ExamEvent.reports).selectinload(Report.votes),
            )
            .filter(
                ExamEvent.region_id == region.id,
                ExamEvent.discipline_id == discipline.id,
                ExamEvent.year.in_(batch_years),
            )
        )
        result = await db.execute(stmt)
        events_map = {e.year: e for e in result.unique().scalars().all()}

        # Build per-year display data
        years_data = []
        for year in batch_years:
            event = events_map.get(year)  # type: ignore[call-overload]
            item: dict[str, Any] = {
                "year": year,
                "has_event": False,
                "status": "Sin datos",
                "report_count": 0,
                "region": region,
                "discipline": discipline,
                "best_work": None,
                "badge_status": "empty",
            }

            if event and len(event.reports) > 0:
                item["has_event"] = True
                report_count = len(event.reports)
                item["report_count"] = report_count
                item["status"] = (
                    f"{report_count} Aportación"
                    if report_count == 1
                    else f"{report_count} Aportaciones"
                )

                total_event_votes = sum(len(r.votes) for r in event.reports)
                has_verified = False
                work_stats = []

                for report in event.reports:
                    vote_count = len(report.votes)
                    consensus_rate = vote_count / total_event_votes if total_event_votes > 0 else 0
                    is_verified = (
                        vote_count >= Consensus.MIN_VOTES_FOR_VERIFICATION
                        and consensus_rate >= Consensus.VERIFICATION_THRESHOLD
                    )
                    if is_verified:
                        has_verified = True
                    work_stats.append(
                        {"report": report, "votes": vote_count, "is_verified": is_verified}
                    )

                work_stats.sort(key=lambda x: x["votes"], reverse=True)

                if work_stats:
                    top = work_stats[0]
                    item["best_work"] = {
                        "title": top["report"].work.title,
                        "composer": top["report"].work.composer.name,
                        "imslp_url": WorkService.get_score_url(top["report"].work),
                        "is_verified": top["is_verified"],
                    }

                if has_verified:
                    item["badge_status"] = "verified"
                elif total_event_votes > 0:
                    item["badge_status"] = "disputed"
                else:
                    item["badge_status"] = "neutral"

            years_data.append(item)

        return {
            "region": region,
            "discipline": discipline,
            "years": years_data,
            "show_more": show_more,
            "user": current_user,
            "sparse_mode": sparse_mode,
            "all_empty": len(db_years) == 0,
        }
