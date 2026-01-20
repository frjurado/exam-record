import pytest
from app.models import ExamEvent, Region, Discipline

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
    return event, region, discipline

@pytest.mark.asyncio
async def test_wizard_page_load(client, db, event):
    event_obj, region, discipline = event
    response = await client.get(f"/exams/{region.slug}/{discipline.slug}/{event_obj.year}/contribute")
    assert response.status_code == 200
    assert "Exam Report Wizard" in response.text
    assert f"eventId: {event_obj.id}" in response.text

@pytest.mark.asyncio
async def test_wizard_page_404(client, db):
    response = await client.get("/exams/mars/theremin/3000/contribute")
    assert response.status_code == 404
    assert "Event not found" in response.text
