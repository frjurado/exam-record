from fastapi import FastAPI, Request, Depends
from datetime import datetime
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import joinedload, selectinload
from app.db.session import get_db
from app.models import ExamEvent, Region, Discipline, Report, Work, Composer, User, Vote
from app.core.config import settings
from app.api.api import api_router
from app.api import deps

app = FastAPI(title=settings.PROJECT_NAME)
templates = Jinja2Templates(directory="app/templates")

app.include_router(api_router)

from fastapi.staticfiles import StaticFiles
app.mount("/static", StaticFiles(directory="app/static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def root(
    request: Request,
    current_user: User | None = Depends(deps.get_current_user_optional)
):
    return templates.TemplateResponse("index.html", {
        "request": request,
        "user": current_user
    })

@app.get("/logout")
async def logout():
    response = Response(status_code=307, headers={"Location": "/"})
    response.delete_cookie(key="access_token")
    return response

@app.get("/exams/{region_slug}/{discipline_slug}", response_class=HTMLResponse)
async def discipline_page(
    request: Request,
    region_slug: str,
    discipline_slug: str,
    cursor: int | None = None,
    partial: bool = False,
    sparse_mode: bool = True, # Default to True (Sparse Mode)
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(deps.get_current_user_optional)
):
    # Verify Region and Discipline exist
    region = (await db.execute(select(Region).filter(Region.slug == region_slug))).scalar_one_or_none()
    discipline = (await db.execute(select(Discipline).filter(Discipline.slug == discipline_slug))).scalar_one_or_none()

    if not region or not discipline:
        return HTMLResponse(content="<h1>Región o Especialidad no encontrada</h1>", status_code=404)

    # Determine Anchor Year (Academic Year Logic)
    now = datetime.now()
    if now.month >= 6:
        base_anchor_year = now.year
    else:
        base_anchor_year = now.year - 1
    
    # Pagination Logic
    batch_size = 10
    min_year_limit = 2000 # Hard limit for now

    # --- Sparse Mode Logic ---
    # 1. Mandatory Years: The last 5 academic years (always shown)
    mandatory_years = set(range(base_anchor_year, base_anchor_year - 5, -1))

    # 2. Available Years: Years that actually have data (Reports) in the DB
    # We join with Report to ensure we only get years that resulted in contributions
    stmt_years = (
        select(ExamEvent.year)
        .join(ExamEvent.reports) # Inner join ensures only events with reports are selected
        .filter(
            ExamEvent.region_id == region.id,
            ExamEvent.discipline_id == discipline.id
        )
    )
    result_years = await db.execute(stmt_years)
    db_years = set(result_years.scalars().all())

    # 3. Combine
    if sparse_mode:
        all_relevant_years = sorted(list(mandatory_years.union(db_years)), reverse=True)
    else:
        # Full Mode: All years from base_anchor until end of DB data or 2000
        min_db_year = min(db_years) if db_years else base_anchor_year
        real_end = min(min_year_limit, min_db_year)
        all_relevant_years = sorted(list(range(base_anchor_year, real_end - 1, -1)), reverse=True)

    # Filter out future years (e.g. 2026 ghost event from seed)
    # This acts as a global ceiling for safety
    all_relevant_years = [y for y in all_relevant_years if y <= base_anchor_year]

    # 4. Apply Cursor/Pagination
    # If cursor is provided, we want years < cursor
    if cursor:
        filtered_years = [y for y in all_relevant_years if y < cursor]
    else:
        filtered_years = all_relevant_years

    # Slice for batch
    batch_years = filtered_years[:batch_size]
    
    # If empty batch and partial, return empty
    if not batch_years:
        if partial:
            return HTMLResponse("")
        # If not partial, we still render the page (empty list) with headers

    # Fetch events for the batch
    # We need rich data now for the badges/preview
    stmt = (
        select(ExamEvent)
        .options(
            joinedload(ExamEvent.reports).joinedload(Report.work).joinedload(Work.composer),
            joinedload(ExamEvent.reports).selectinload(Report.votes),
             # We might need to eager load more if we want to be super efficient, 
             # but this should cover the "Best Work" logic
        )
        .filter(
            ExamEvent.region_id == region.id,
            ExamEvent.discipline_id == discipline.id,
            ExamEvent.year.in_(batch_years)
        )
    )
    result = await db.execute(stmt)
    events_map = {e.year: e for e in result.unique().scalars().all()}

    # Process events to get status for display
    years_data = []
    for year in batch_years:
        event = events_map.get(year)
        
        item = {
            "year": year,
            "has_event": False,
            "status": "Sin datos",
            "report_count": 0,
            "region": region,
            "discipline": discipline,
            "best_work": None,
            "badge_status": "empty" # empty, verified, disputed, neutral
        }

        if event and len(event.reports) > 0:
            item["has_event"] = True
            report_count = len(event.reports)
            item["report_count"] = report_count
            
            if report_count == 1:
                item["status"] = f"{report_count} Aportación"
            else:
                item["status"] = f"{report_count} Aportaciones"

            # logic to find "Best Work" for preview
            # Reusing the logic from exam_page basically
            best_work_candidate = None
            max_votes = -1
            
            # We want to know if there is AT LEAST ONE verified work
            has_verified = False
            
            # Temporary list to sort
            work_stats = []

            total_event_votes = 0

            for report in event.reports:
                vote_count = len(report.votes)
                total_event_votes += vote_count

            for report in event.reports:
                vote_count = len(report.votes)
                # Consensus Check
                consensus_rate = vote_count / total_event_votes if total_event_votes > 0 else 0
                
                is_verified = False
                if vote_count >= 2 and consensus_rate >= 0.75:
                    is_verified = True
                    has_verified = True
                
                work_stats.append({
                    "report": report,
                    "votes": vote_count,
                    "is_verified": is_verified
                })
            
            # Sort by votes desc
            work_stats.sort(key=lambda x: x["votes"], reverse=True)
            
            if work_stats:
                top_item = work_stats[0]
                item["best_work"] = {
                    "title": top_item["report"].work.title,
                    "composer": top_item["report"].work.composer.name,
                    "imslp_url": top_item["report"].work.imslp_url or top_item["report"].work.best_score_url, # Fallback to ducky?
                    "is_verified": top_item["is_verified"]
                }
            
            # Badge Status
            if has_verified:
                item["badge_status"] = "verified"
            elif total_event_votes > 0: # Has votes but no consensus
                 item["badge_status"] = "disputed"
            else:
                 item["badge_status"] = "neutral" # Just reports, no votes

        years_data.append(item)

    # Determine next cursor logic
    if len(filtered_years) > batch_size:
        next_cursor = batch_years[-1] # The last displayed year
        show_more = True
    else:
        next_cursor = None
        show_more = False

    # IMPORTANT: The loadMore JS expects the last item's ID to parse the year.
    # Our logic uses `cursor` which is treated as "Start AFTER this year" (descending).
    # so `loadMore` passing the last year displayed is correct for `cursor`.

    context = {
        "request": request,
        "region": region,
        "discipline": discipline,
        "years": years_data,
        "show_more": show_more,
        "user": current_user,
        "sparse_mode": sparse_mode,
        "all_empty": len(db_years) == 0 # Flag to show "No Data At All" encouragement
    }

    if partial:
        return templates.TemplateResponse("partials/year_list.html", context)

    return templates.TemplateResponse("discipline.html", context)

@app.get("/exams/{region_slug}/{discipline_slug}/{year}", response_class=HTMLResponse)
async def exam_page(
    request: Request,
    region_slug: str,
    discipline_slug: str,
    year: int,
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(deps.get_current_user_optional)
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
        # Check if year is valid? For now, just 404. 
        # But maybe we should redirect to contribute if it's a valid past year?
        # User requirement says: "if a year doesn't have any data, just say so, and give a button directly to contribute".
        # This page logic handles EXISTING events. If event doesn't exist, it 404s.
        # We should probably handle non-existent event here too?
        # Let's keep 404 for now, relying on discipline list to guide users.
        return HTMLResponse(content="<h1>Convocatoria no encontrada</h1>", status_code=404)

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

    # Check User Participation
    user_has_participated = False
    user_participation_report_id = None
    
    if current_user:
        # Check Report
        existing_report = await db.execute(
            select(Report).filter(Report.event_id == event.id, Report.user_id == current_user.id)
        )
        if existing_event_report := existing_report.scalars().first():
            user_has_participated = True
            user_participation_report_id = existing_event_report.id
        else:
            # Check Vote
            existing_vote_result = await db.execute(
                select(Vote).join(Report).filter(Report.event_id == event.id, Vote.user_id == current_user.id)
            )
            if existing_vote := existing_vote_result.scalars().first():
                user_has_participated = True
                user_participation_report_id = existing_vote.report_id

    return templates.TemplateResponse("event.html", {
        "request": request,
        "event": event,
        "region_slug": region_slug,
        "discipline_slug": discipline_slug,
        "year": year,
        "works": works_list,
        "total_votes": total_votes,
        "event_status": event_status,
        "user": current_user,
        "user_has_participated": user_has_participated,
        "user_participation_report_id": user_participation_report_id
    })

@app.get("/exams/{region_slug}/{discipline_slug}/{year}/contribute", response_class=HTMLResponse)
async def contribute_page(
    request: Request,
    region_slug: str,
    discipline_slug: str,
    year: int,
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(deps.get_current_user_optional)
):
    # 1. Check if event exists
    stmt = select(ExamEvent).join(Region).join(Discipline).filter(
        Region.slug == region_slug,
        Discipline.slug == discipline_slug,
        ExamEvent.year == year
    )
    result = await db.execute(stmt)
    event = result.scalar_one_or_none()
    
    # 2. Lazy Creation Logic
    if not event:
        # Validate year (Optional: limit to reasonable range?)
        # For now, trust the user or the upstream link.
        
        # We need Region and Discipline objects to create the event
        region = (await db.execute(select(Region).filter(Region.slug == region_slug))).scalar_one_or_none()
        discipline = (await db.execute(select(Discipline).filter(Discipline.slug == discipline_slug))).scalar_one_or_none()
        
        if not region or not discipline:
             return HTMLResponse(content="<h1>Región o Especialidad no encontrada</h1>", status_code=404)

        # Create the missing event
        event = ExamEvent(
            region_id=region.id,
            discipline_id=discipline.id,
            year=year
        )
        db.add(event)
        await db.commit()
        await db.refresh(event)

    return templates.TemplateResponse("wizard.html", {
        "request": request,
        "event_id": event.id,
        "region_slug": region_slug,
        "discipline_slug": discipline_slug,
        "year": year,
        "turnstile_site_key": settings.TURNSTILE_SITE_KEY,
        "user": current_user
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
