from typing import Any

import httpx
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import joinedload, selectinload

from app.api import deps
from app.core.config import settings
from app.services.work_service import WorkService
from app.models import Composer, ExamEvent, Report, User, Vote, Work
from app.schemas.report import ComposerInput, ReportCreate, ScopeEnum, WorkInput
from app.services import wikidata
from app.services.consensus import ConsensusService


class ReportService:
    @staticmethod
    async def verify_turnstile(token: str) -> None:
        """Raises HTTPException(400) if the Turnstile token is missing or invalid."""
        if not token:
            raise HTTPException(status_code=400, detail="Falta validación Anti-Spam (Turnstile)")

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://challenges.cloudflare.com/turnstile/v0/siteverify",
                data={
                    "secret": settings.TURNSTILE_SECRET_KEY,
                    "response": token,
                },
            )
            data = resp.json()
            if not data.get("success"):
                raise HTTPException(status_code=400, detail="Token Anti-Spam inválido")

    @staticmethod
    async def get_or_create_composer(db: AsyncSession, data: ComposerInput) -> Composer:
        """Resolve a Composer by local id, Wikidata id, or name. Raises HTTPException on error."""
        if data.id:
            result = await db.execute(select(Composer).filter(Composer.id == data.id))
            composer = result.scalar_one_or_none()
            if not composer:
                raise HTTPException(status_code=404, detail="Compositor no encontrado")
            return composer

        if data.wikidata_id:
            result = await db.execute(
                select(Composer).filter(Composer.wikidata_id == data.wikidata_id)
            )
            composer = result.scalar_one_or_none()
            if composer:
                return composer
            try:
                wd_data = await wikidata.get_composer_by_id(data.wikidata_id)
                name = wd_data.get("name") or data.name or "Compositor Desconocido"
                composer = Composer(name=name, wikidata_id=data.wikidata_id, is_verified=True)
                db.add(composer)
                await db.flush()
                return composer
            except Exception as e:
                raise HTTPException(
                    status_code=400, detail=f"Error verificando ID de Wikidata: {str(e)}"
                ) from e

        if data.name:
            composer = Composer(name=data.name, is_verified=False)
            db.add(composer)
            await db.flush()
            return composer

        raise HTTPException(status_code=400, detail="Identificación de compositor requerida")

    @staticmethod
    async def get_or_create_work(
        db: AsyncSession, data: WorkInput, composer_id: int
    ) -> Work:
        """Resolve a Work by local id, OpenOpus id, or title. Raises HTTPException on error."""
        if data.id:
            result = await db.execute(select(Work).filter(Work.id == data.id))
            work = result.scalar_one_or_none()
            if not work:
                raise HTTPException(status_code=404, detail="Obra no encontrada")
            return work

        if data.openopus_id:
            result = await db.execute(
                select(Work).filter(Work.openopus_id == data.openopus_id)
            )
            work = result.scalar_one_or_none()
            if work:
                return work
            if not data.title:
                raise HTTPException(
                    status_code=400, detail="Título de obra requerido para nueva obra OpenOpus"
                )
            work = Work(
                title=data.title,
                openopus_id=data.openopus_id,
                composer_id=composer_id,
                is_verified=True,
            )
            db.add(work)
            await db.flush()
            return work

        if data.title:
            work = Work(title=data.title, composer_id=composer_id, is_verified=False)
            db.add(work)
            await db.flush()
            return work

        raise HTTPException(status_code=400, detail="Identificación de obra requerida")

    @staticmethod
    async def submit_report(
        db: AsyncSession, current_user: User, report_in: ReportCreate
    ) -> Report:
        """Full report submission: verify Turnstile, resolve entities, check participation,
        get/create report candidate, add vote, commit."""
        # 0. Verify Turnstile
        if settings.TURNSTILE_SECRET_KEY:
            await ReportService.verify_turnstile(report_in.turnstile_token or "")

        # 1. Check Event
        result = await db.execute(select(ExamEvent).filter(ExamEvent.id == report_in.event_id))
        event = result.scalar_one_or_none()
        if not event:
            raise HTTPException(status_code=404, detail="Convocatoria no encontrada")

        # 2. Resolve Composer
        composer = await ReportService.get_or_create_composer(db, report_in.composer)

        # 3. Resolve Work
        work = await ReportService.get_or_create_work(db, report_in.work, composer.id)

        # 4. Strict Participation Check
        has_participated, _ = await deps.check_user_event_participation(
            db, current_user.id, event.id
        )
        if has_participated:
            raise HTTPException(status_code=400, detail="Ya has participado en esta convocatoria.")

        # 5. Build movement details string
        full_details = report_in.movement_details
        if report_in.scope != ScopeEnum.WHOLE_WORK:
            prefix = f"[{report_in.scope.value}] "
            full_details = f"{prefix}{full_details}" if full_details else prefix

        # 6. Get or create Report candidate
        existing = (
            await db.execute(
                select(Report).filter(Report.event_id == event.id, Report.work_id == work.id)
            )
        ).scalar_one_or_none()

        if existing:
            report = existing
        else:
            report = Report(
                user_id=current_user.id,
                event_id=event.id,
                work_id=work.id,
                movement_details=full_details,
                is_flagged=False,
            )
            db.add(report)
            await db.flush()

        # 7. Add Vote
        vote = Vote(user_id=current_user.id, report_id=report.id)
        db.add(vote)

        await db.commit()
        await db.refresh(report)
        return report

    @staticmethod
    def build_item_dict(report: Report, total_vs: int) -> dict[str, Any]:
        """Compute consensus metrics dict for a single report."""
        vs_count = len(report.votes)
        m = ConsensusService.calculate_work_status(vs_count, total_vs)
        return {
            "report_id": report.id,
            "work": report.work,
            "composer": report.work.composer,
            "votes": vs_count,
            "percentage": m["percentage"],
            "status": m["status"],
            "is_flagged": report.is_flagged,
            "score_url": WorkService.get_score_url(report.work),
        }

    @staticmethod
    def _report_context_query(report_id: int):
        """Eager-load Select for a report with all relations needed to render vote_updates.html."""
        return (
            select(Report)
            .options(
                selectinload(Report.votes),
                joinedload(Report.work).joinedload(Work.composer),
                joinedload(Report.event)
                .selectinload(ExamEvent.reports)
                .options(
                    selectinload(Report.votes),
                    joinedload(Report.work).joinedload(Work.composer),
                ),
            )
            .filter(Report.id == report_id)
        )

    @staticmethod
    async def fetch_report_with_context(
        db: AsyncSession, report_id: int
    ) -> Report | None:
        """Fetch a report with all relations required for rendering vote/flag responses."""
        result = await db.execute(ReportService._report_context_query(report_id))
        return result.unique().scalar_one_or_none()

    @staticmethod
    async def cast_vote(db: AsyncSession, user_id: int, report: Report) -> None:
        """Insert a Vote for the given report and commit."""
        vote = Vote(user_id=user_id, report_id=report.id)
        db.add(vote)
        await db.commit()

    @staticmethod
    async def set_flagged(db: AsyncSession, report: Report) -> None:
        """Mark a report as flagged and commit."""
        report.is_flagged = True  # type: ignore[assignment]
        await db.commit()
