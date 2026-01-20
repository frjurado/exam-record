import pytest
from app.models import User, ExamEvent, Region, Discipline, Composer, Work, Report
from app.api import deps
from app.main import app as fastapi_app
from sqlalchemy.future import select

@pytest.fixture
async def user(db):
    user = User(email="test@example.com", role="Contributor")
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user

@pytest.fixture
async def event(db):
    region = Region(name="Andalucia", slug="andalucia")
    discipline = Discipline(name="Piano", slug="piano")
    db.add(region)
    db.add(discipline)
    await db.commit()
    await db.refresh(region)
    await db.refresh(discipline)
    
    event = ExamEvent(year=2026, region_id=region.id, discipline_id=discipline.id)
    db.add(event)
    await db.commit()
    await db.refresh(event)
    return event

@pytest.mark.asyncio
async def test_create_report_simple(client, db, user, event):
    # Create local composer/work
    composer = Composer(name="Bach", is_verified=True)
    db.add(composer)
    await db.commit()
    await db.refresh(composer)
    
    work = Work(title="Prelude", composer_id=composer.id, is_verified=True)
    db.add(work)
    await db.commit()
    await db.refresh(work)
    
    # Override auth
    fastapi_app.dependency_overrides[deps.get_current_user] = lambda: user
    
    payload = {
        "event_id": event.id,
        "composer": {"id": composer.id},
        "work": {"id": work.id},
        "scope": "Whole Work",
        "movement_details": "Played perfectly"
    }
    
    try:
        response = await client.post("/api/reports/", json=payload)
    finally:
        fastapi_app.dependency_overrides.pop(deps.get_current_user, None)
    
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["status"] == "created"
    
    # Check DB
    result = await db.execute(select(Report).filter(Report.id == data["id"]))
    report = result.scalar_one()
    assert report.work_id == work.id
    assert report.movement_details == "Played perfectly"

@pytest.mark.asyncio
async def test_create_report_unverified_composer_and_work(client, db, user, event):
    fastapi_app.dependency_overrides[deps.get_current_user] = lambda: user
    
    payload = {
        "event_id": event.id,
        "composer": {"name": "New Composer"},
        "work": {"title": "New Song"},
        "scope": "Whole Work"
    }
    
    try:
        response = await client.post("/api/reports/", json=payload)
    finally:
        fastapi_app.dependency_overrides.pop(deps.get_current_user, None)
        
    assert response.status_code == 200, response.text
    
    # Verify created
    result = await db.execute(select(Composer).filter(Composer.name == "New Composer"))
    composer = result.scalar_one()
    assert not composer.is_verified
    
    result = await db.execute(select(Work).filter(Work.title == "New Song"))
    work = result.scalar_one()
    assert not work.is_verified
    assert work.composer_id == composer.id
