from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import joinedload

from app.api import deps
from app.api.api import api_router
from app.core.config import settings
from app.db.session import get_db
from app.models import Discipline, ExamEvent, Region, User
from app.services.exam_service import ExamService

app = FastAPI(
    title=settings.PROJECT_NAME,
    description=(
        "Community-driven database for crowdsourcing music conservatory entrance exam repertoire. "
        "Users submit and vote on the works performed in past exams, building consensus around "
        "what pieces appear most frequently."
    ),
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)
templates = Jinja2Templates(directory="app/templates")

app.include_router(api_router)
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/", response_class=HTMLResponse)
async def root(
    request: Request, current_user: User | None = Depends(deps.get_current_user_optional)
) -> HTMLResponse:
    return templates.TemplateResponse(request, "index.html", {"user": current_user})


@app.get("/logout")
async def logout() -> Response:
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
    sparse_mode: bool = True,
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(deps.get_current_user_optional),
) -> HTMLResponse:
    context = await ExamService.get_discipline_context(
        db, region_slug, discipline_slug, cursor, sparse_mode, current_user
    )
    if context is None:
        return HTMLResponse(content="<h1>Región o Especialidad no encontrada</h1>", status_code=404)
    if partial and not context["years"]:
        return HTMLResponse("")
    template = "partials/year_list.html" if partial else "discipline.html"
    return templates.TemplateResponse(request, template, context)


@app.get("/exams/{region_slug}/{discipline_slug}/{year}", response_class=HTMLResponse)
async def exam_page(
    request: Request,
    region_slug: str,
    discipline_slug: str,
    year: int,
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(deps.get_current_user_optional),
) -> HTMLResponse:
    context = await ExamService.get_exam_context(db, region_slug, discipline_slug, year, current_user)
    if context is None:
        return HTMLResponse(content="<h1>Convocatoria no encontrada</h1>", status_code=404)
    return templates.TemplateResponse(request, "event.html", context)


@app.get("/exams/{region_slug}/{discipline_slug}/{year}/contribute", response_class=HTMLResponse)
async def contribute_page(
    request: Request,
    region_slug: str,
    discipline_slug: str,
    year: int,
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(deps.get_current_user_optional),
) -> HTMLResponse:
    # 1. Check if event exists
    stmt = (
        select(ExamEvent)
        .join(Region)
        .join(Discipline)
        .filter(
            Region.slug == region_slug, Discipline.slug == discipline_slug, ExamEvent.year == year
        )
    )
    result = await db.execute(stmt)
    event = result.scalar_one_or_none()

    # 2. Lazy Creation Logic
    if not event:
        # Validate year (Optional: limit to reasonable range?)
        # For now, trust the user or the upstream link.

        # We need Region and Discipline objects to create the event
        region = (
            await db.execute(select(Region).filter(Region.slug == region_slug))
        ).scalar_one_or_none()
        discipline = (
            await db.execute(select(Discipline).filter(Discipline.slug == discipline_slug))
        ).scalar_one_or_none()

        if not region or not discipline:
            return HTMLResponse(
                content="<h1>Región o Especialidad no encontrada</h1>", status_code=404
            )

        # Create the missing event
        event = ExamEvent(region_id=region.id, discipline_id=discipline.id, year=year)
        db.add(event)
        await db.commit()
        await db.refresh(event)

    return templates.TemplateResponse(
        request,
        "wizard.html",
        {
            "event_id": event.id,
            "region_slug": region_slug,
            "discipline_slug": discipline_slug,
            "year": year,
            "turnstile_site_key": settings.TURNSTILE_SITE_KEY,
            "user": current_user,
        },
    )


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok", "app": settings.PROJECT_NAME, "environment": settings.ENVIRONMENT}


@app.get("/robots.txt", response_class=HTMLResponse)
async def robots_txt() -> Response:
    content = """User-agent: *
Allow: /
Sitemap: https://exam-record.com/sitemap.xml
"""
    return Response(content=content, media_type="text/plain")


@app.get("/sitemap.xml", response_class=HTMLResponse)
async def sitemap_xml(request: Request, db: AsyncSession = Depends(get_db)) -> Response:
    stmt = select(ExamEvent).options(joinedload(ExamEvent.region), joinedload(ExamEvent.discipline))
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

    xml_content.append("</urlset>")

    return Response(content="".join(xml_content), media_type="application/xml")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
