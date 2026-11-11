import logging
from typing import Any

import httpx
from fastapi import HTTPException
from sqlalchemy import Select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import joinedload, selectinload

from app.api import deps
from app.core.config import settings
from app.models import Composer, ExamEvent, Report, User, Vote, Work
from app.schemas.report import ComposerInput, ReportCreate, ScopeEnum, WorkInput
from app.services import openopus, text, wikidata
from app.services.consensus import ConsensusService
from app.services.exam_service import ExamService
from app.services.reference_data_service import ReferenceDataService
from app.services.work_service import WorkService

logger = logging.getLogger("uvicorn")

ALREADY_PARTICIPATED = "Ya has participado en esta convocatoria."
# Shown when the contributor marks a movement or excerpt but gives no further detail.
SCOPE_LABELS = {ScopeEnum.MOVEMENT: "Un movimiento", ScopeEnum.EXCERPT: "Un fragmento"}


class ReportService:
    @staticmethod
    async def verify_turnstile(token: str) -> None:
        """Raises HTTPException(400) if the Turnstile token is missing or invalid."""
        if not token:
            raise HTTPException(status_code=400, detail="Falta validación Anti-Spam (Turnstile)")

        async with httpx.AsyncClient(timeout=10.0) as client:
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
    async def _find_composer_by_name(db: AsyncSession, *names: str | None) -> Composer | None:
        """An existing composer whose name matches any of the given ones, ignoring case and accents."""
        wanted = {text.normalize(name) for name in names if name} - {""}
        if not wanted:
            return None
        result = await db.execute(
            select(Composer).filter(Composer.search_text.in_(wanted)).order_by(Composer.id)
        )
        return result.scalars().first()

    @staticmethod
    async def get_or_create_composer(db: AsyncSession, data: ComposerInput) -> Composer:
        """Resolve a Composer by local id, OpenOpus id, Wikidata id, or name.

        Every path looks for an existing composer with the same name before creating one,
        so the same person picked from two catalogues (or typed by hand) is stored once.
        External ids are confirmed against their catalogue; an id that cannot be
        confirmed is ignored and the composer is handled by name only.
        """
        if data.id:
            result = await db.execute(select(Composer).filter(Composer.id == data.id))
            composer = result.scalar_one_or_none()
            if not composer:
                raise HTTPException(status_code=404, detail="Compositor no encontrado")
            return composer

        name = (data.name or "").strip()

        if data.openopus_id:
            result = await db.execute(
                select(Composer).filter(Composer.openopus_id == data.openopus_id)
            )
            composer = result.scalar_one_or_none()
            if composer:
                return composer
            confirmed_name = await ReportService._confirm_openopus_composer(data.openopus_id, name)
            if confirmed_name:
                composer = await ReportService._find_composer_by_name(db, confirmed_name)
                if composer and not composer.openopus_id:
                    composer.openopus_id = data.openopus_id
                    composer.is_verified = True
                    return composer
                if not composer:
                    composer = Composer(
                        name=confirmed_name, openopus_id=data.openopus_id, is_verified=True
                    )
                    db.add(composer)
                    await db.flush()
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
            except httpx.HTTPError:
                logger.warning("Wikidata lookup failed for %s", data.wikidata_id)
                wd_data = {}
            if wd_data.get("name"):
                composer = await ReportService._find_composer_by_name(
                    db, wd_data["name"], wd_data.get("name_en")
                )
                if composer and not composer.wikidata_id:
                    composer.wikidata_id = data.wikidata_id
                    return composer
                if not composer:
                    composer = Composer(
                        name=wd_data["name"], wikidata_id=data.wikidata_id, is_verified=True
                    )
                    # Works can only be searched for composers linked to OpenOpus.
                    composer.openopus_id = await ReportService._find_free_openopus_id(
                        db, wd_data.get("name_en") or wd_data["name"]
                    )
                    db.add(composer)
                    await db.flush()
                    return composer

        if name:
            composer = await ReportService._find_composer_by_name(db, name)
            if composer:
                return composer
            composer = Composer(name=name, is_verified=False)
            db.add(composer)
            await db.flush()
            return composer

        raise HTTPException(status_code=400, detail="Identificación de compositor requerida")

    @staticmethod
    async def _confirm_openopus_composer(openopus_id: str, name: str) -> str | None:
        """The catalogue's own name for this OpenOpus composer id, or None if unconfirmed."""
        name_tokens = text.tokens(name)
        if not name_tokens:
            return None
        try:
            candidates = await openopus.search_composers(name_tokens[-1])
        except httpx.HTTPError:
            logger.warning("OpenOpus lookup failed for composer %s", openopus_id)
            return None
        for candidate in candidates:
            if candidate["openopus_id"] == openopus_id:
                return str(candidate["name"])
        return None

    @staticmethod
    async def _find_free_openopus_id(db: AsyncSession, name: str) -> str | None:
        """OpenOpus id for a composer name, unless another local composer already holds it."""
        try:
            openopus_id = await openopus.find_composer_id(name)
        except httpx.HTTPError:
            return None
        if not openopus_id:
            return None
        taken = await db.execute(select(Composer.id).filter(Composer.openopus_id == openopus_id))
        return None if taken.first() else openopus_id

    @staticmethod
    async def get_or_create_work(db: AsyncSession, data: WorkInput, composer: Composer) -> Work:
        """Resolve a Work by local id, OpenOpus id, or title.

        A title typed by hand is matched against the composer's existing works (ignoring
        case, accents and punctuation) before a new one is created. An OpenOpus id is
        looked up in the composer's catalogue, which supplies the stored title.
        """
        if data.id:
            result = await db.execute(select(Work).filter(Work.id == data.id))
            work = result.scalar_one_or_none()
            if not work:
                raise HTTPException(status_code=404, detail="Obra no encontrada")
            return work

        title = (data.title or "").strip()
        nickname = (data.nickname or "").strip() or None

        if data.openopus_id:
            result = await db.execute(select(Work).filter(Work.openopus_id == data.openopus_id))
            work = result.scalar_one_or_none()
            if work:
                return work
            entry = await ReportService._find_catalogue_work(composer, data.openopus_id)
            if entry:
                work = Work(
                    title=entry["title"],
                    nickname=entry["nickname"],
                    openopus_id=data.openopus_id,
                    composer_id=composer.id,
                    is_verified=True,
                )
                db.add(work)
                await db.flush()
                return work
            if not title:
                raise HTTPException(status_code=400, detail="Obra no encontrada en el catálogo")

        if title:
            wanted = text.normalize(title)
            result = await db.execute(
                select(Work).filter(Work.composer_id == composer.id).order_by(Work.id)
            )
            for existing in result.scalars().all():
                if text.normalize(existing.title) == wanted:
                    if nickname and not existing.nickname:
                        existing.nickname = nickname
                    return existing
            work = Work(title=title, nickname=nickname, composer_id=composer.id, is_verified=False)
            db.add(work)
            await db.flush()
            return work

        raise HTTPException(status_code=400, detail="Identificación de obra requerida")

    @staticmethod
    async def _find_catalogue_work(composer: Composer, openopus_id: str) -> dict[str, Any] | None:
        if not composer.openopus_id:
            return None
        try:
            works = await openopus.get_composer_works(composer.openopus_id)
        except httpx.HTTPError:
            logger.warning("OpenOpus catalogue unavailable for composer %s", composer.id)
            return None
        return next((w for w in works if w["openopus_id"] == openopus_id), None)

    @staticmethod
    async def get_or_create_event(
        db: AsyncSession, region_slug: str, discipline_slug: str, year: int
    ) -> ExamEvent:
        """Resolve the ExamEvent for a region/discipline/year, creating it on first report.

        Events are created here (on an authenticated submission) rather than when the
        contribute page is opened, so anonymous page views never write to the database.
        """
        region = await ReferenceDataService.get_region_by_slug(db, region_slug)
        discipline = await ReferenceDataService.get_discipline_by_slug(db, discipline_slug)
        if not region or not discipline or not ExamService.is_valid_exam_year(year):
            raise HTTPException(status_code=404, detail="Convocatoria no encontrada")

        result = await db.execute(
            select(ExamEvent).filter(
                ExamEvent.region_id == region.id,
                ExamEvent.discipline_id == discipline.id,
                ExamEvent.year == year,
            )
        )
        event = result.scalar_one_or_none()
        if not event:
            event = ExamEvent(region_id=region.id, discipline_id=discipline.id, year=year)
            db.add(event)
            await db.flush()
        return event

    @staticmethod
    async def submit_report(
        db: AsyncSession, current_user: User, report_in: ReportCreate
    ) -> Report:
        """Full report submission: verify Turnstile, resolve entities, check participation,
        get/create report candidate, add vote, commit."""
        # 0. Verify Turnstile
        if settings.TURNSTILE_SECRET_KEY:
            await ReportService.verify_turnstile(report_in.turnstile_token or "")

        # 1. Resolve Event
        event = await ReportService.get_or_create_event(
            db, report_in.region_slug, report_in.discipline_slug, report_in.year
        )

        # 2. Resolve Composer
        composer = await ReportService.get_or_create_composer(db, report_in.composer)

        # 3. Resolve Work
        work = await ReportService.get_or_create_work(db, report_in.work, composer)

        # 4. Strict Participation Check
        has_participated, _ = await deps.check_user_event_participation(
            db, int(current_user.id), int(event.id)
        )
        if has_participated:
            raise HTTPException(status_code=400, detail=ALREADY_PARTICIPATED)

        # 5. Details of what was set. They belong to the report, so they only apply when
        # this submission creates it; later voters back the report as it stands.
        details = (report_in.movement_details or "").strip() or None
        if report_in.scope == ScopeEnum.WHOLE_WORK:
            details = None
        elif not details:
            details = SCOPE_LABELS[report_in.scope]

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
                movement_details=details,
                is_flagged=False,
            )
            db.add(report)
            await db.flush()

        # 7. Add Vote
        vote = Vote(user_id=current_user.id, report_id=report.id, event_id=event.id)
        db.add(vote)

        try:
            await db.commit()
        except IntegrityError as e:
            # A concurrent request got there first (same user voting twice, or the same
            # work being reported twice); the unique constraints are the last line of defence.
            await db.rollback()
            raise HTTPException(status_code=400, detail=ALREADY_PARTICIPATED) from e
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
            "details": report.movement_details,
            "score_url": WorkService.get_score_url(report.work),
        }

    @staticmethod
    def _report_context_query(report_id: int) -> Select[tuple[Report]]:
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
    async def fetch_report_with_context(db: AsyncSession, report_id: int) -> Report | None:
        """Fetch a report with all relations required for rendering vote/flag responses."""
        result = await db.execute(ReportService._report_context_query(report_id))
        return result.unique().scalar_one_or_none()

    @staticmethod
    async def cast_vote(db: AsyncSession, user_id: int, report: Report) -> None:
        """Insert a Vote for the given report and commit."""
        vote = Vote(user_id=user_id, report_id=report.id, event_id=report.event_id)
        db.add(vote)
        try:
            await db.commit()
        except IntegrityError as e:
            await db.rollback()
            raise HTTPException(status_code=400, detail=ALREADY_PARTICIPATED) from e

    @staticmethod
    async def set_flagged(db: AsyncSession, report: Report) -> None:
        """Mark a report as flagged and commit."""
        report.is_flagged = True  # type: ignore[assignment]
        await db.commit()
