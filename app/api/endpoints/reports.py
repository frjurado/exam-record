from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.db.session import get_db
from app.models import User
from app.schemas.report import ReportCreate, ReportResponse
from app.services.consensus import ConsensusService
from app.services.report_service import ReportService

templates = Jinja2Templates(directory="app/templates")

router = APIRouter()


@router.post("/", response_model=ReportResponse)
async def create_report(
    report_in: ReportCreate,
    current_user: User = Depends(deps.get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    return await ReportService.submit_report(db, current_user, report_in)


@router.post("/{report_id}/vote", response_class=HTMLResponse)
async def vote_report(
    request: Request,
    report_id: int,
    current_user: User | None = Depends(deps.get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    report = await ReportService.fetch_report_with_context(db, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Reporte no encontrado")

    total_votes = sum(len(r.votes) for r in report.event.reports)

    if not current_user:
        item = ReportService.build_item_dict(report, total_votes)
        next_url = request.headers.get("referer", "/")
        if "?" in next_url:
            next_url += f"&action=vote&report_id={report_id}"
        else:
            next_url += f"?action=vote&report_id={report_id}"
        return templates.TemplateResponse(
            "partials/vote_updates.html",
            {
                "request": request,
                "item": item,
                "show_auth_modal": True,
                "next_url": next_url,
            },
        )

    has_participated, _ = await deps.check_user_event_participation(
        db, current_user.id, report.event_id
    )
    if has_participated:
        raise HTTPException(status_code=400, detail="Ya has participado en esta convocatoria.")

    await ReportService.cast_vote(db, current_user.id, report)

    db.expire_all()
    report = await ReportService.fetch_report_with_context(db, report_id)
    assert report is not None

    total_votes = sum(len(r.votes) for r in report.event.reports)
    target_item = ReportService.build_item_dict(report, total_votes)
    other_items = [
        ReportService.build_item_dict(r, total_votes)
        for r in report.event.reports
        if r.id != report.id
    ]
    event_status = ConsensusService.aggregate_event_reports(report.event.reports)["event_status"]

    return templates.TemplateResponse(
        "partials/vote_updates.html",
        {
            "request": request,
            "item": target_item,
            "other_items": other_items,
            "event_status": event_status,
            "user_has_participated": True,
            "user_participation_report_id": report.id,
        },
    )


@router.post("/{report_id}/flag", response_class=HTMLResponse)
async def flag_report(
    request: Request,
    report_id: int,
    current_user: User | None = Depends(deps.get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    report = await ReportService.fetch_report_with_context(db, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Reporte no encontrado")

    total_votes = sum(len(r.votes) for r in report.event.reports)

    if not current_user:
        item = ReportService.build_item_dict(report, total_votes)
        return templates.TemplateResponse(
            "partials/vote_updates.html",
            {
                "request": request,
                "item": item,
                "show_auth_modal": True,
                "next_url": request.headers.get("referer", "/"),
            },
        )

    await ReportService.set_flagged(db, report)

    db.expire_all()
    report = await ReportService.fetch_report_with_context(db, report_id)
    assert report is not None

    total_votes = sum(len(r.votes) for r in report.event.reports)
    target_item = ReportService.build_item_dict(report, total_votes)
    target_item["is_flagged"] = True
    other_items = [
        ReportService.build_item_dict(r, total_votes)
        for r in report.event.reports
        if r.id != report.id
    ]
    event_status = ConsensusService.aggregate_event_reports(report.event.reports)["event_status"]

    user_has_participated, user_participation_report_id = (
        await deps.check_user_event_participation(db, current_user.id, report.event_id)
    )

    return templates.TemplateResponse(
        "partials/vote_updates.html",
        {
            "request": request,
            "item": target_item,
            "other_items": other_items,
            "event_status": event_status,
            "user_has_participated": user_has_participated,
            "user_participation_report_id": user_participation_report_id,
        },
    )
