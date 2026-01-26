from fastapi import FastAPI, Request, Depends
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import joinedload, selectinload
from app.db.session import get_db
from app.models import ExamEvent, Region, Discipline, Report, Work, Composer
from app.core.config import settings
from app.api.api import api_router

app = FastAPI(title=settings.PROJECT_NAME)
templates = Jinja2Templates(directory="app/templates")

app.include_router(api_router)

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/exams/{region_slug}/{discipline_slug}", response_class=HTMLResponse)
async def discipline_page(
    request: Request,
    region_slug: str,
    discipline_slug: str,
    db: AsyncSession = Depends(get_db)
):
    # Verify Region and Discipline exist
    region = (await db.execute(select(Region).filter(Region.slug == region_slug))).scalar_one_or_none()
    discipline = (await db.execute(select(Discipline).filter(Discipline.slug == discipline_slug))).scalar_one_or_none()

    if not region or not discipline:
        return HTMLResponse(content="<h1>Region or Discipline not found</h1>", status_code=404)

    # Fetch events for this pair
    stmt = (
        select(ExamEvent)
        .options(joinedload(ExamEvent.reports))
        .filter(
            ExamEvent.region_id == region.id,
            ExamEvent.discipline_id == discipline.id
        )
        .order_by(ExamEvent.year.desc())
    )
    result = await db.execute(stmt)
    events = result.scalars().unique().all()

    # Process events to get status for display
    events_data = []
    for event in events:
        report_count = len(event.reports)
        status = "empty"
        if report_count > 0:
            status = f"{report_count} Reports" # enhanced logic can be added later
        
        events_data.append({
            "year": event.year,
            "status": status,
            "report_count": report_count
        })

    return templates.TemplateResponse("discipline.html", {
        "request": request,
        "region": region,
        "discipline": discipline,
        "events": events_data
    })

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
            joinedload(ExamEvent.reports).selectinload(Report.votes),
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
    total_votes = 0
    works_list = []
    
    # First pass: Count total votes
    for report in event.reports:
        total_votes += len(report.votes)

    # Second pass: Build list
    for report in event.reports:
        votes_count = len(report.votes)
        
        # Calculate percentage based on TOTAL votes for the EVENT
        consensus_rate = votes_count / total_votes if total_votes > 0 else 0
        percentage = int(consensus_rate * 100)

        # Trust State Logic (Per Work)
        status = "neutral"
        if votes_count >= 2:
            if consensus_rate >= 0.75:
                status = "verified"
            else:
                status = "disputed"
        elif votes_count == 1:
            status = "neutral"
        
        works_list.append({
            "report_id": report.id,
            "work": report.work,
            "composer": report.work.composer,
            "votes": votes_count,
            "percentage": percentage,
            "status": status,
            "is_flagged": report.is_flagged
        })

    # Sort by votes descending
    works_list.sort(key=lambda x: x["votes"], reverse=True)

    # Event Level Consensus
    has_verified_work = any(item["status"] == "verified" for item in works_list)
    event_status = "neutral"
    if total_votes == 0:
        event_status = "empty"
    elif total_votes == 1:
        event_status = "neutral"
    elif has_verified_work:
        event_status = "resolved"
    else:
        event_status = "disputed"

    return templates.TemplateResponse("event.html", {
        "request": request,
        "event": event,
        "region_slug": region_slug,
        "discipline_slug": discipline_slug,
        "year": year,
        "works": works_list,
        "total_votes": total_votes,
        "event_status": event_status
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

@app.get("/robots.txt", response_class=HTMLResponse)
async def robots_txt():
    content = """User-agent: *
Allow: /
Sitemap: https://exam-record.com/sitemap.xml
"""
    return Response(content=content, media_type="text/plain")

@app.get("/sitemap.xml", response_class=HTMLResponse)
async def sitemap_xml(request: Request, db: AsyncSession = Depends(get_db)):
    stmt = (
        select(ExamEvent)
        .options(
            joinedload(ExamEvent.region),
            joinedload(ExamEvent.discipline)
        )
    )
    result = await db.execute(stmt)
    events = result.scalars().all()
    
    base_url = str(request.base_url).rstrip("/")
    
    xml_content = ['<?xml version="1.0" encoding="UTF-8"?>']
    xml_content.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')
    
    # Home Page (?) - We don't have one exposed yet, maybe just the base
    # xml_content.append(f'<url><loc>{base_url}/</loc></url>')
    
    for event in events:
        loc = f"{base_url}/exams/{event.region.slug}/{event.discipline.slug}/{event.year}"
        xml_content.append(f"""
            <url>
                <loc>{loc}</loc>
                <changefreq>weekly</changefreq>
                <priority>0.8</priority>
            </url>
        """)
        
    xml_content.append('</urlset>')
    
    return Response(content="".join(xml_content), media_type="application/xml")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
