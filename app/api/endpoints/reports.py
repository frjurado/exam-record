from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.db.session import get_db
from app.api import deps
from app.models import User, Report, ExamEvent, Composer, Work
from app.schemas.report import ReportCreate, ReportResponse, ScopeEnum
from app.services import wikidata

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
        raise HTTPException(status_code=404, detail="Event not found")

    # 2. Process Composer
    composer = None
    if report_in.composer.id:
        # Local lookup
        result = await db.execute(select(Composer).filter(Composer.id == report_in.composer.id))
        composer = result.scalar_one_or_none()
        if not composer:
            raise HTTPException(status_code=404, detail="Composer not found")
    elif report_in.composer.wikidata_id:
        # Check if exists by wikidata_id
        result = await db.execute(select(Composer).filter(Composer.wikidata_id == report_in.composer.wikidata_id))
        composer = result.scalar_one_or_none()
        if not composer:
            # Import from Wikidata
            try:
                wd_data = await wikidata.get_composer_by_id(report_in.composer.wikidata_id)
                name = wd_data.get("name") or report_in.composer.name or "Unknown Composer"
                composer = Composer(
                    name=name,
                    wikidata_id=report_in.composer.wikidata_id,
                    is_verified=True
                )
                db.add(composer)
                await db.flush()
            except Exception as e:
                 raise HTTPException(status_code=400, detail=f"Failed to verify Wikidata ID: {str(e)}")
    elif report_in.composer.name:
        # Unverified creation
        composer = Composer(
            name=report_in.composer.name,
            is_verified=False
        )
        db.add(composer)
        await db.flush()
    else:
        raise HTTPException(status_code=400, detail="Composer identification required")

    # 3. Process Work
    work = None
    if report_in.work.id:
        # Local
        result = await db.execute(select(Work).filter(Work.id == report_in.work.id))
        work = result.scalar_one_or_none()
        if not work:
             raise HTTPException(status_code=404, detail="Work not found")
    elif report_in.work.openopus_id:
         # Check if exists
        result = await db.execute(select(Work).filter(Work.openopus_id == report_in.work.openopus_id))
        work = result.scalar_one_or_none()
        if not work:
            # Create verified work
            if not report_in.work.title:
                 raise HTTPException(status_code=400, detail="Work title required for new OpenOpus work")
            
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
         raise HTTPException(status_code=400, detail="Work identification required")

    # 4. Create Report
    full_details = report_in.movement_details
    if report_in.scope != ScopeEnum.WHOLE_WORK:
        prefix = f"[{report_in.scope.value}] "
        full_details = f"{prefix}{full_details}" if full_details else prefix

    report = Report(
        user_id=current_user.id,
        event_id=event.id,
        work_id=work.id,
        movement_details=full_details,
        is_flagged=False
    )

    db.add(report)
    await db.commit()
    await db.refresh(report)
    
    return report
