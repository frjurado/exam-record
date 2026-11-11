"""Maintenance operations for the admin page: merging duplicates, removing bad entries.

Everything here changes or deletes data other people contributed, so each public method
is one transaction: it either commits the whole operation or raises `AdminError` having
changed nothing.
"""

import logging
from typing import Any

import httpx
from sqlalchemy import delete, func, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import joinedload, selectinload

from app.models import Composer, ExamEvent, Report, Vote, Work
from app.services import openopus, text

logger = logging.getLogger("uvicorn")


class AdminError(Exception):
    """An admin operation that cannot be carried out; the message is shown to the admin."""


class AdminService:
    # ------------------------------------------------------------------ overview

    @staticmethod
    async def get_overview(db: AsyncSession) -> dict[str, Any]:
        """Everything the admin page lists."""
        reports = (
            (
                await db.execute(
                    select(Report)
                    .options(
                        selectinload(Report.votes),
                        joinedload(Report.work).joinedload(Work.composer),
                        joinedload(Report.event).joinedload(ExamEvent.region),
                        joinedload(Report.event).joinedload(ExamEvent.discipline),
                    )
                    .order_by(Report.id.desc())
                )
            )
            .unique()
            .scalars()
            .all()
        )

        report_counts = dict(
            (await db.execute(select(Report.work_id, func.count()).group_by(Report.work_id)))
            .tuples()
            .all()
        )
        works = (await db.execute(select(Work).options(joinedload(Work.composer)))).scalars().all()
        works = sorted(works, key=lambda w: (w.composer.search_text or "", w.search_text or ""))
        work_rows = [
            {"work": work, "composer": work.composer, "reports": report_counts.get(work.id, 0)}
            for work in works
        ]

        work_counts = dict(
            (await db.execute(select(Work.composer_id, func.count()).group_by(Work.composer_id)))
            .tuples()
            .all()
        )
        composers = (
            (await db.execute(select(Composer).order_by(Composer.search_text))).scalars().all()
        )
        composer_rows = [
            {"composer": composer, "works": work_counts.get(composer.id, 0)}
            for composer in composers
        ]

        empty_events = (
            await db.execute(
                select(func.count()).select_from(ExamEvent).where(~ExamEvent.reports.any())
            )
        ).scalar_one()

        return {
            "reports": reports,
            "flagged": [r for r in reports if r.is_flagged],
            "works": work_rows,
            "composers": composer_rows,
            "empty_events": empty_events,
        }

    # ------------------------------------------------------------------- reports

    @staticmethod
    async def clear_flag(db: AsyncSession, report_id: int) -> None:
        report = await AdminService._get(db, Report, report_id, "Reporte")
        report.is_flagged = False
        await db.commit()
        logger.info("admin: cleared flag on report %s", report_id)

    @staticmethod
    async def delete_report(db: AsyncSession, report_id: int) -> None:
        """Delete a report and its votes; the exam itself goes too if nothing else is left."""
        report = await AdminService._get(db, Report, report_id, "Reporte")
        event_id = report.event_id
        await db.execute(delete(Vote).where(Vote.report_id == report_id))
        await db.execute(delete(Report).where(Report.id == report_id))
        remaining = (
            await db.execute(
                select(func.count()).select_from(Report).where(Report.event_id == event_id)
            )
        ).scalar_one()
        if not remaining:
            await db.execute(delete(ExamEvent).where(ExamEvent.id == event_id))
        await db.commit()
        logger.info("admin: deleted report %s (event %s)", report_id, event_id)

    @staticmethod
    async def delete_empty_events(db: AsyncSession) -> int:
        """Remove exams that have no reports (left over from before events were created
        on first report). Returns how many were removed."""
        result = await db.execute(delete(ExamEvent).where(~ExamEvent.reports.any()))
        await db.commit()
        removed = int(result.rowcount or 0)  # type: ignore[attr-defined]
        logger.info("admin: deleted %s empty events", removed)
        return removed

    # --------------------------------------------------------------------- works

    @staticmethod
    async def update_work(
        db: AsyncSession, work_id: int, title: str, nickname: str | None, imslp_url: str | None
    ) -> None:
        work = await AdminService._get(db, Work, work_id, "Obra")
        title = title.strip()
        if not title:
            raise AdminError("El título no puede quedar vacío.")
        imslp_url = (imslp_url or "").strip() or None
        if imslp_url and not imslp_url.startswith(("https://", "http://")):
            raise AdminError("La dirección de IMSLP debe empezar por https://")
        work.title = title
        work.nickname = (nickname or "").strip() or None
        work.imslp_url = imslp_url
        await db.commit()
        logger.info("admin: edited work %s", work_id)

    @staticmethod
    async def delete_work(db: AsyncSession, work_id: int) -> None:
        """Delete a work nobody has reported. Reported works must be merged or have
        their reports deleted first, so that no report is lost by accident."""
        await AdminService._get(db, Work, work_id, "Obra")
        reported = (
            await db.execute(
                select(func.count()).select_from(Report).where(Report.work_id == work_id)
            )
        ).scalar_one()
        if reported:
            raise AdminError("La obra tiene reportes: fusiónala con otra o elimina sus reportes.")
        await db.execute(delete(Work).where(Work.id == work_id))
        await db.commit()
        logger.info("admin: deleted work %s", work_id)

    @staticmethod
    async def merge_works(db: AsyncSession, source_id: int, target_id: int) -> None:
        """Fold `source` into `target`: its reports and votes move, then it is deleted."""
        if source_id == target_id:
            raise AdminError("Elige dos obras distintas.")
        source = await AdminService._get(db, Work, source_id, "Obra")
        target = await AdminService._get(db, Work, target_id, "Obra")
        await AdminService._merge_works(db, source, target)
        await db.commit()
        logger.info("admin: merged work %s into %s", source_id, target_id)

    @staticmethod
    async def _merge_works(db: AsyncSession, source: Work, target: Work) -> None:
        source_id, target_id = int(source.id), int(target.id)
        reports = (
            (await db.execute(select(Report).where(Report.work_id == source_id))).scalars().all()
        )
        for report in reports:
            twin = (
                await db.execute(
                    select(Report).where(
                        Report.event_id == report.event_id, Report.work_id == target_id
                    )
                )
            ).scalar_one_or_none()
            if twin is None:
                report.work_id = target_id
                continue
            # Both works were reported for the same exam: one report must absorb the
            # other. A user has at most one vote per exam, so the votes cannot collide.
            await db.execute(
                update(Vote).where(Vote.report_id == report.id).values(report_id=twin.id)
            )
            if not twin.movement_details:
                twin.movement_details = report.movement_details
            twin.is_flagged = bool(twin.is_flagged) or bool(report.is_flagged)
            await db.execute(delete(Report).where(Report.id == report.id))
        await db.flush()

        # Keep what the source knew and the target did not. The catalogue id is unique,
        # so it has to leave the source before the target can take it.
        openopus_id, title, nickname, imslp_url = (
            source.openopus_id,
            source.title,
            source.nickname,
            source.imslp_url,
        )
        await db.execute(delete(Work).where(Work.id == source_id))
        if openopus_id and not target.openopus_id:
            target.openopus_id = openopus_id
            target.title = title  # the catalogue's title is the canonical one
            target.is_verified = True
        if nickname and not target.nickname:
            target.nickname = nickname
        if imslp_url and not target.imslp_url:
            target.imslp_url = imslp_url
        await db.flush()

    @staticmethod
    async def catalogue_candidates(
        db: AsyncSession, work_id: int, query: str
    ) -> list[dict[str, Any]]:
        """OpenOpus works of this work's composer matching `query` (empty if not linked)."""
        work = await AdminService._get(db, Work, work_id, "Obra")
        composer = await AdminService._get(db, Composer, int(work.composer_id), "Compositor")
        if not composer.openopus_id or not query.strip():
            return []
        try:
            return await openopus.search_work(query, composer.openopus_id, limit=15)
        except httpx.HTTPError as e:
            raise AdminError("No se pudo consultar el catálogo de OpenOpus.") from e

    @staticmethod
    async def link_work_to_catalogue(db: AsyncSession, work_id: int, openopus_id: str) -> None:
        """Turn a hand-typed work into the catalogue work it stands for.

        If that catalogue work is already stored, the two are merged; otherwise this work
        takes the catalogue's title, nickname and id.
        """
        work = await AdminService._get(db, Work, work_id, "Obra")
        composer = await AdminService._get(db, Composer, int(work.composer_id), "Compositor")
        if not composer.openopus_id:
            raise AdminError("El compositor no está vinculado a OpenOpus.")
        try:
            catalogue = await openopus.get_composer_works(composer.openopus_id)
        except httpx.HTTPError as e:
            raise AdminError("No se pudo consultar el catálogo de OpenOpus.") from e
        entry = next((w for w in catalogue if w["openopus_id"] == openopus_id), None)
        if entry is None:
            raise AdminError("Esa obra no está en el catálogo del compositor.")

        stored = (
            await db.execute(select(Work).where(Work.openopus_id == openopus_id))
        ).scalar_one_or_none()
        if stored is not None and stored.id != work.id:
            await AdminService._merge_works(db, work, stored)
        elif stored is None:
            work.openopus_id = openopus_id
            work.title = entry["title"]
            work.nickname = entry["nickname"] or work.nickname
            work.is_verified = True
        await db.commit()
        logger.info("admin: linked work %s to OpenOpus %s", work_id, openopus_id)

    # ----------------------------------------------------------------- composers

    @staticmethod
    async def rename_composer(db: AsyncSession, composer_id: int, name: str) -> None:
        composer = await AdminService._get(db, Composer, composer_id, "Compositor")
        name = name.strip()
        if not name:
            raise AdminError("El nombre no puede quedar vacío.")
        composer.name = name
        await db.commit()
        logger.info("admin: renamed composer %s", composer_id)

    @staticmethod
    async def merge_composers(db: AsyncSession, source_id: int, target_id: int) -> None:
        """Fold `source` into `target`: its works move (same-titled ones are merged),
        then it is deleted. The target keeps its name."""
        if source_id == target_id:
            raise AdminError("Elige dos compositores distintos.")
        source = await AdminService._get(db, Composer, source_id, "Compositor")
        target = await AdminService._get(db, Composer, target_id, "Compositor")

        target_works = (
            (await db.execute(select(Work).where(Work.composer_id == target_id))).scalars().all()
        )
        by_title = {text.normalize(w.title): w for w in target_works}
        source_works = (
            (await db.execute(select(Work).where(Work.composer_id == source_id))).scalars().all()
        )
        for work in source_works:
            same = by_title.get(text.normalize(work.title))
            if same is not None:
                await AdminService._merge_works(db, work, same)
            else:
                work.composer_id = target_id
                by_title[text.normalize(work.title)] = work
        await db.flush()

        wikidata_id, openopus_id = source.wikidata_id, source.openopus_id
        await db.execute(delete(Composer).where(Composer.id == source_id))
        if wikidata_id and not target.wikidata_id:
            target.wikidata_id = wikidata_id
        if openopus_id and not target.openopus_id:
            target.openopus_id = openopus_id
        if wikidata_id or openopus_id:
            target.is_verified = True
        await db.commit()
        logger.info("admin: merged composer %s into %s", source_id, target_id)

    @staticmethod
    async def composer_candidates(query: str) -> list[dict[str, Any]]:
        """OpenOpus composers matching `query` (the API rejects very short ones)."""
        if len(query.strip()) < openopus.MIN_QUERY_LENGTH:
            return []
        try:
            return await openopus.search_composers(query.strip())
        except httpx.HTTPError as e:
            raise AdminError("No se pudo consultar OpenOpus.") from e

    @staticmethod
    async def link_composer_to_catalogue(
        db: AsyncSession, composer_id: int, openopus_id: str, query: str
    ) -> None:
        """Tie a hand-typed composer to an OpenOpus composer, so their catalogue can be
        searched. `query` is the search that listed the candidate: it is run again so the
        id is confirmed by OpenOpus rather than trusted from the form.

        If that OpenOpus composer is already stored, the two are merged; otherwise this
        composer takes the catalogue's id and name.
        """
        composer = await AdminService._get(db, Composer, composer_id, "Compositor")
        candidates = await AdminService.composer_candidates(query)
        entry = next((c for c in candidates if c["openopus_id"] == openopus_id), None)
        if entry is None:
            raise AdminError("Ese compositor no aparece en OpenOpus con esa búsqueda.")

        stored = (
            await db.execute(select(Composer).where(Composer.openopus_id == openopus_id))
        ).scalar_one_or_none()
        if stored is not None and stored.id != composer.id:
            await AdminService.merge_composers(db, composer_id, int(stored.id))
            return
        composer.openopus_id = openopus_id
        composer.name = entry["name"]
        composer.is_verified = True
        await db.commit()
        logger.info("admin: linked composer %s to OpenOpus %s", composer_id, openopus_id)

    @staticmethod
    async def get_composer(db: AsyncSession, composer_id: int) -> Composer:
        composer: Composer = await AdminService._get(db, Composer, composer_id, "Compositor")
        return composer

    # ------------------------------------------------------------------- helpers

    @staticmethod
    async def get_work(db: AsyncSession, work_id: int) -> Work:
        work = (
            await db.execute(
                select(Work).options(joinedload(Work.composer)).where(Work.id == work_id)
            )
        ).scalar_one_or_none()
        if work is None:
            raise AdminError("Obra no encontrada.")
        return work

    @staticmethod
    async def _get(db: AsyncSession, model: Any, row_id: int, label: str) -> Any:
        row = (await db.execute(select(model).where(model.id == row_id))).scalar_one_or_none()
        if row is None:
            raise AdminError(f"{label} no encontrado/a (id {row_id}).")
        return row
