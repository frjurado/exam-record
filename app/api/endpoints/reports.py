from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.db.session import get_db
from app.api import deps
from fastapi.responses import HTMLResponse
from app.models import User, Report, ExamEvent, Composer, Work, Vote
from app.schemas.report import ReportCreate, ReportResponse, ScopeEnum
from app.services import wikidata
from app.services.consensus import ConsensusService
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import selectinload, joinedload

templates = Jinja2Templates(directory="app/templates")

router = APIRouter()

@router.post("/", response_model=ReportResponse)
async def create_report(
    report_in: ReportCreate,
    current_user: User = Depends(deps.get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # 1. Check Event
    result = await db.execute(select(ExamEvent).filter(ExamEvent.id == report_in.event_id))
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Convocatoria no encontrada")

    # 2. Process Composer
    composer = None
    if report_in.composer.id:
        # Local lookup
        result = await db.execute(select(Composer).filter(Composer.id == report_in.composer.id))
        composer = result.scalar_one_or_none()
        if not composer:
            raise HTTPException(status_code=404, detail="Compositor no encontrado")
    elif report_in.composer.wikidata_id:
        # Check if exists by wikidata_id
        result = await db.execute(select(Composer).filter(Composer.wikidata_id == report_in.composer.wikidata_id))
        composer = result.scalar_one_or_none()
        if not composer:
            # Import from Wikidata
            try:
                wd_data = await wikidata.get_composer_by_id(report_in.composer.wikidata_id)
                name = wd_data.get("name") or report_in.composer.name or "Compositor Desconocido"
                composer = Composer(
                    name=name,
                    wikidata_id=report_in.composer.wikidata_id,
                    is_verified=True
                )
                db.add(composer)
                await db.flush()
            except Exception as e:
                 raise HTTPException(status_code=400, detail=f"Error verificando ID de Wikidata: {str(e)}")
    elif report_in.composer.name:
        # Unverified creation
        composer = Composer(
            name=report_in.composer.name,
            is_verified=False
        )
        db.add(composer)
        await db.flush()
    else:
        raise HTTPException(status_code=400, detail="Identificación de compositor requerida")

    # 3. Process Work
    work = None
    if report_in.work.id:
        # Local
        result = await db.execute(select(Work).filter(Work.id == report_in.work.id))
        work = result.scalar_one_or_none()
        if not work:
             raise HTTPException(status_code=404, detail="Obra no encontrada")
    elif report_in.work.openopus_id:
         # Check if exists
        result = await db.execute(select(Work).filter(Work.openopus_id == report_in.work.openopus_id))
        work = result.scalar_one_or_none()
        if not work:
            # Create verified work
            if not report_in.work.title:
                 raise HTTPException(status_code=400, detail="Título de obra requerido para nueva obra OpenOpus")
            
            work = Work(
                title=report_in.work.title,
                openopus_id=report_in.work.openopus_id,
                composer_id=composer.id,
                is_verified=True
            )
            db.add(work)
            await db.flush()
    elif report_in.work.title: 
         # Lazy Builder or raw title - Unverified
         work = Work(
             title=report_in.work.title,
             composer_id=composer.id,
             is_verified=False
         )
         db.add(work)
         await db.flush()
    else:
         raise HTTPException(status_code=400, detail="Identificación de obra requerida")

    # 4. Get or Create Report (Candidate)
    full_details = report_in.movement_details
    if report_in.scope != ScopeEnum.WHOLE_WORK:
        prefix = f"[{report_in.scope.value}] "
        full_details = f"{prefix}{full_details}" if full_details else prefix

    # Check for existing candidate
    query = select(Report).filter(Report.event_id == event.id, Report.work_id == work.id)
    existing_report = (await db.execute(query)).scalar_one_or_none()

    if existing_report:
        report = existing_report
    else:
        report = Report(
            user_id=current_user.id,
            event_id=event.id,
            work_id=work.id,
            movement_details=full_details,
            is_flagged=False
        )
        db.add(report)
        await db.flush() # Get ID

    # 5. Create Vote
    vote = Vote(
        user_id=current_user.id,
        report_id=report.id
    )
    db.add(vote)
    
    await db.commit()
    await db.refresh(report)
    
    return report

@router.post("/{report_id}/vote", response_class=HTMLResponse)
async def vote_report(
    request: Request,
    report_id: int,
    current_user: User | None = Depends(deps.get_current_user_optional),
    db: AsyncSession = Depends(get_db)
):
    # Fetch report with event relation to count totals
    query = (
        select(Report)
        .options(
             selectinload(Report.votes),
             joinedload(Report.work).joinedload(Work.composer),
             # Deep load for aggregation: Event -> Reports -> (Votes, Work -> Composer)
             joinedload(Report.event).selectinload(ExamEvent.reports).options(
                 selectinload(Report.votes),
                 joinedload(Report.work).joinedload(Work.composer)
             )
        )
        .filter(Report.id == report_id)
    )
    result = await db.execute(query)
    report = result.unique().scalar_one_or_none()
    
    if not report:
        raise HTTPException(status_code=404, detail="Reporte no encontrado")
        
    # Helper to build item dict
    def build_item_dict(r, total_vs):
        vs_count = len(r.votes)
        m = ConsensusService.calculate_work_status(vs_count, total_vs)
        return {
            "report_id": r.id,
            "work": r.work,
            "composer": r.work.composer,
            "votes": vs_count,
            "percentage": m["percentage"],
            "status": m["status"],
            "is_flagged": r.is_flagged,
        }

    # 1. Unauthenticated Case
    if not current_user:
        # Calculate context just to re-render the card exactly as is
        total_votes = sum(len(r.votes) for r in report.event.reports)
        item = build_item_dict(report, total_votes)
        
        return templates.TemplateResponse("partials/vote_updates.html", {
            "request": request,
            "item": item, # Restore the card
            "show_auth_modal": True, # Show modal OOB
            "next_url": request.headers.get("referer", "/")
        })

    # 2. Authenticated Case
    # Add vote
    # Check if user already voted? Unique constraint usually handles this or we ignore.
    # Assuming simple insert for now.
    # 2. Authenticated Case
    # Add vote
    # Unlimited voting allowed for now
    vote = Vote(user_id=current_user.id, report_id=report.id)
    db.add(vote)
    await db.commit()

    # Refresh data
    db.expire_all() 
    result = await db.execute(query)
    report = result.unique().scalar_one_or_none()
    
    # Recalculate context for ALL items
    total_votes = sum(len(r.votes) for r in report.event.reports)
    
    # Target Item
    target_item = build_item_dict(report, total_votes)
    
    # Other Items
    other_items = []
    for r in report.event.reports:
        if r.id != report.id:
            other_items.append(build_item_dict(r, total_votes))
    
    event_status = ConsensusService.aggregate_event_reports(report.event.reports)["event_status"]
    
    return templates.TemplateResponse("partials/vote_updates.html", {
        "request": request,
        "item": target_item,
        "other_items": other_items,
        "event_status": event_status
    })

@router.post("/{report_id}/flag", response_class=HTMLResponse)
async def flag_report(
    request: Request,
    report_id: int,
    current_user: User | None = Depends(deps.get_current_user_optional),
    db: AsyncSession = Depends(get_db)
):
    # Fetch report with event relation
    query = (
        select(Report)
        .options(
             selectinload(Report.votes),
             joinedload(Report.work).joinedload(Work.composer),
             # Deep load for aggregation
             joinedload(Report.event).selectinload(ExamEvent.reports).options(
                 selectinload(Report.votes),
                 joinedload(Report.work).joinedload(Work.composer)
             )
        )
        .filter(Report.id == report_id)
    )
    result = await db.execute(query)
    report = result.unique().scalar_one_or_none()
    
    if not report:
        raise HTTPException(status_code=404, detail="Reporte no encontrado")

    # Helper (duplicated but safe)
    def build_item_dict(r, total_vs):
        vs_count = len(r.votes)
        m = ConsensusService.calculate_work_status(vs_count, total_vs)
        return {
            "report_id": r.id,
            "work": r.work,
            "composer": r.work.composer,
            "votes": vs_count,
            "percentage": m["percentage"],
            "status": m["status"],
            "is_flagged": r.is_flagged,
        }

    # 1. Unauthenticated Case
    if not current_user:
        total_votes = sum(len(r.votes) for r in report.event.reports)
        item = build_item_dict(report, total_votes)
        
        return templates.TemplateResponse("partials/vote_updates.html", {
            "request": request,
            "item": item, 
            "show_auth_modal": True, 
            "next_url": request.headers.get("referer", "/")
        })
        
    # 2. Authenticated Case
    report.is_flagged = True
    await db.commit()
    # Refresh logic similar to vote
    db.expire_all()
    result = await db.execute(query)
    report = result.unique().scalar_one_or_none()
    
    # Recalculate context for ALL items
    total_votes = sum(len(r.votes) for r in report.event.reports)
    
    target_item = build_item_dict(report, total_votes)
    # Ensure flag status is True locally just in case db commit didn't propagate fast enough (it should have)
    target_item["is_flagged"] = True 
    
    other_items = []
    for r in report.event.reports:
        if r.id != report.id:
            other_items.append(build_item_dict(r, total_votes))
    
    event_status = ConsensusService.aggregate_event_reports(report.event.reports)["event_status"]
    
    return templates.TemplateResponse("partials/vote_updates.html", {
        "request": request,
        "item": target_item,
        "other_items": other_items,
        "event_status": event_status
    })
