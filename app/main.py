from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import joinedload

from app.api import deps
from app.api.api import api_router
from app.core.config import settings
from app.core.limiter import limiter
from app.core.monitoring import init_sentry
from app.core.urls import canonical_redirect, public_base_url
from app.db.session import get_db
from app.models import Discipline, ExamEvent, Region, Report, User
from app.services.browse_service import BrowseService
from app.services.exam_service import ExamService

init_sentry()

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

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]


@app.middleware("http")
async def one_address(request: Request, call_next):  # type: ignore[no-untyped-def]
    """Send visitors of the site's other addresses to the canonical one, so links,
    search engines and the session cookie all use a single host."""
    # Fly terminates TLS and forwards plain HTTP. Restore the visitor's scheme so that
    # every address built from the request (canonical tags, links in emails) is https.
    if request.headers.get("x-forwarded-proto") == "https":
        request.scope["scheme"] = "https"
    target = canonical_redirect(request)
    if target:
        # 301 for page views; 308 keeps the method and body of anything else.
        status = 301 if request.method in ("GET", "HEAD") else 308
        return RedirectResponse(url=target, status_code=status)
    return await call_next(request)


app.include_router(api_router)
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/", response_class=HTMLResponse)
async def root(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(deps.get_current_user_optional),
) -> HTMLResponse:
    result = await db.execute(
        select(Region.slug, Discipline.slug)
        .join(ExamEvent, ExamEvent.region_id == Region.id)
        .join(Discipline, Discipline.id == ExamEvent.discipline_id)
        .join(Report, Report.event_id == ExamEvent.id)
        .distinct()
    )
    slugs_with_data = {f"{r}/{d}" for r, d in result.all()}
    return templates.TemplateResponse(
        request, "index.html", {"user": current_user, "slugs_with_data": slugs_with_data}
    )


@app.get("/auth/modal", response_class=HTMLResponse)
async def signin_modal(request: Request) -> Response:
    """The email form behind the header's "Entrar" link. HTMX drops it into the page;
    opened directly (no JavaScript, or a new tab) there is nothing to show, so go home."""
    if request.headers.get("HX-Request") != "true":
        return RedirectResponse(url="/")
    return templates.TemplateResponse(
        request, "partials/auth_modal.html", {"signin": True, "next_url": ""}
    )


@app.get("/logout")
async def logout() -> Response:
    response = Response(status_code=307, headers={"Location": "/"})
    response.delete_cookie(key="access_token")
    return response


@app.get("/examenes/{region_slug}/{discipline_slug}", response_class=HTMLResponse)
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


@app.get("/examenes/{region_slug}/{discipline_slug}/{year}", response_class=HTMLResponse)
async def exam_page(
    request: Request,
    region_slug: str,
    discipline_slug: str,
    year: int,
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(deps.get_current_user_optional),
) -> HTMLResponse:
    context = await ExamService.get_exam_context(
        db, region_slug, discipline_slug, year, current_user
    )
    if context is None:
        return HTMLResponse(content="<h1>Convocatoria no encontrada</h1>", status_code=404)
    return templates.TemplateResponse(request, "event.html", context)


@app.get("/examenes/{region_slug}/{discipline_slug}/{year}/contribute", response_class=HTMLResponse)
async def contribute_page(
    request: Request,
    region_slug: str,
    discipline_slug: str,
    year: int,
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(deps.get_current_user_optional),
) -> Response:
    # The ExamEvent itself is only created when a report is actually submitted
    # (ReportService.get_or_create_event), so opening this page never writes to the DB.
    context = await ExamService.get_contribute_context(
        db, region_slug, discipline_slug, year, current_user
    )
    if context is None:
        return HTMLResponse(content="<h1>Convocatoria no encontrada</h1>", status_code=404)
    if context["has_participated"]:
        # One participation per exam: send them to the page that shows their choice
        # instead of letting them fill in a form that would be rejected at the end.
        return RedirectResponse(
            url=f"/examenes/{region_slug}/{discipline_slug}/{year}", status_code=303
        )

    context["turnstile_site_key"] = settings.TURNSTILE_SITE_KEY or ""
    return templates.TemplateResponse(request, "wizard.html", context)


@app.get("/exams/{rest:path}", include_in_schema=False)
async def old_exam_addresses(request: Request, rest: str) -> RedirectResponse:
    """Exam pages lived under /exams until November 2026; links to them still work."""
    target = f"/examenes/{rest}"
    if request.url.query:
        target += "?" + request.url.query
    return RedirectResponse(url=target, status_code=301)


def _page_id(ref: str) -> int | None:
    """The id at the start of "42-sonata-para-piano" (the slug after it is decoration)."""
    head = ref.split("-", 1)[0]
    return int(head) if head.isdigit() else None


@app.get("/obras/{ref}", response_class=HTMLResponse)
async def work_page(
    request: Request,
    ref: str,
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(deps.get_current_user_optional),
) -> Response:
    work_id = _page_id(ref)
    context = await BrowseService.work_context(db, work_id) if work_id is not None else None
    if context is None:
        return HTMLResponse(content="<h1>Obra no encontrada</h1>", status_code=404)
    if request.url.path != context["work"].url_path:
        # An old or mistyped slug: the id found the work, send them to its real address.
        return RedirectResponse(url=context["work"].url_path, status_code=301)
    return templates.TemplateResponse(request, "work.html", {**context, "user": current_user})


@app.get("/compositores/{ref}", response_class=HTMLResponse)
async def composer_page(
    request: Request,
    ref: str,
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(deps.get_current_user_optional),
) -> Response:
    composer_id = _page_id(ref)
    context = (
        await BrowseService.composer_context(db, composer_id) if composer_id is not None else None
    )
    if context is None:
        return HTMLResponse(content="<h1>Compositor no encontrado</h1>", status_code=404)
    if request.url.path != context["composer"].url_path:
        return RedirectResponse(url=context["composer"].url_path, status_code=301)
    return templates.TemplateResponse(request, "composer.html", {**context, "user": current_user})


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok", "app": settings.PROJECT_NAME, "environment": settings.ENVIRONMENT}


@app.get("/robots.txt", response_class=HTMLResponse)
async def robots_txt(request: Request) -> Response:
    content = f"""User-agent: *
Allow: /
Sitemap: {public_base_url(request)}/sitemap.xml
"""
    return Response(content=content, media_type="text/plain")


@app.get("/sitemap.xml", response_class=HTMLResponse)
async def sitemap_xml(request: Request, db: AsyncSession = Depends(get_db)) -> Response:
    # Only events that have at least one report: empty events have nothing to index.
    stmt = (
        select(ExamEvent)
        .where(ExamEvent.reports.any())
        .options(joinedload(ExamEvent.region), joinedload(ExamEvent.discipline))
    )
    result = await db.execute(stmt)
    events = result.scalars().all()

    base_url = public_base_url(request)

    xml_content = ['<?xml version="1.0" encoding="UTF-8"?>']
    xml_content.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')
    xml_content.append(f"<url><loc>{base_url}/</loc></url>")

    for event in events:
        loc = f"{base_url}/examenes/{event.region.slug}/{event.discipline.slug}/{event.year}"
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
