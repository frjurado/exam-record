from fastapi import FastAPI, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import joinedload
from app.db.session import get_db
from app.models import ExamEvent, Region, Discipline, Report, Work, Composer
from app.core.config import settings
from app.api.api import api_router

app = FastAPI(title=settings.PROJECT_NAME)
templates = Jinja2Templates(directory="app/templates")

app.include_router(api_router)

@app.get("/exams/{region_slug}/{discipline_slug}/{year}", response_class=HTMLResponse)
async def exam_page(
    request: Request,
    region_slug: str,
    discipline_slug: str,
    year: int,
    db: AsyncSession = Depends(get_db)
):
    stmt = (
        select(ExamEvent)
        .options(
            joinedload(ExamEvent.reports)
            .joinedload(Report.work)
            .joinedload(Work.composer),
            joinedload(ExamEvent.region),
            joinedload(ExamEvent.discipline)
        )
        .join(Region)
        .join(Discipline)
        .filter(
            Region.slug == region_slug,
            Discipline.slug == discipline_slug,
            ExamEvent.year == year
        )
    )
    result = await db.execute(stmt)
    event = result.unique().scalar_one_or_none()

    if not event:
        return HTMLResponse(content="<h1>Event not found</h1>", status_code=404)

    # Aggregation Logic
    total_votes = len(event.reports)
    works_map = {}

    for report in event.reports:
        work_id = report.work.id
        if work_id not in works_map:
            works_map[work_id] = {
                "work": report.work,
                "composer": report.work.composer,
                "votes": 0
            }
        works_map[work_id]["votes"] += 1

    # Calculate Consensus & Sort
    works_list = []
    for wid, data in works_map.items():
        votes = data["votes"]
        consensus_rate = votes / total_votes if total_votes > 0 else 0
        percentage = int(consensus_rate * 100)

        # Trust State Logic
        status = "neutral"  # Default
        if votes == 1:
            status = "neutral"
        elif votes >= 2:
            if consensus_rate >= 0.75:
                status = "verified"
            else:
                status = "disputed"
        
        data["percentage"] = percentage
        data["status"] = status
        works_list.append(data)

    # Sort by votes descending
    works_list.sort(key=lambda x: x["votes"], reverse=True)

    return templates.TemplateResponse("event.html", {
        "request": request,
        "event": event,
        "region_slug": region_slug,
        "discipline_slug": discipline_slug,
        "year": year,
        "works": works_list,
        "total_votes": total_votes
    })

@app.get("/exams/{region_slug}/{discipline_slug}/{year}/contribute", response_class=HTMLResponse)
async def contribute_page(
    request: Request,
    region_slug: str,
    discipline_slug: str,
    year: int,
    db: AsyncSession = Depends(get_db)
):
    stmt = select(ExamEvent).join(Region).join(Discipline).filter(
        Region.slug == region_slug,
        Discipline.slug == discipline_slug,
        ExamEvent.year == year
    )
    result = await db.execute(stmt)
    event = result.scalar_one_or_none()
    
    if not event:
        return HTMLResponse(content="<h1>Event not found</h1>", status_code=404)

    return templates.TemplateResponse("wizard.html", {
        "request": request,
        "event_id": event.id,
        "region_slug": region_slug,
        "discipline_slug": discipline_slug,
        "year": year
    })

@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "app": settings.PROJECT_NAME,
        "environment": settings.ENVIRONMENT
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
