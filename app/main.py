from fastapi import FastAPI, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.db.session import get_db
from app.models import ExamEvent, Region, Discipline
from app.core.config import settings
from app.api.api import api_router

app = FastAPI(title=settings.PROJECT_NAME)
templates = Jinja2Templates(directory="app/templates")

app.include_router(api_router)

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
