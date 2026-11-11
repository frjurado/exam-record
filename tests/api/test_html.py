import pytest
from sqlalchemy import func, select

from app.models import Composer, Discipline, ExamEvent, Region, Report, User, Work


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
    response = await client.get(
        f"/exams/{region.slug}/{discipline.slug}/{event_obj.year}/contribute"
    )
    assert response.status_code == 200
    assert "Contribute - Exam Record" in response.text
    assert "wizard('andalucia', 'piano', 2026)" in response.text


@pytest.mark.asyncio
async def test_wizard_page_404(client, db):
    response = await client.get("/exams/mars/theremin/3000/contribute")
    assert response.status_code == 404
    assert "Región o Especialidad no encontrada" in response.text


@pytest.mark.asyncio
async def test_wizard_page_does_not_create_event(client, db, event):
    _, region, discipline = event
    response = await client.get(f"/exams/{region.slug}/{discipline.slug}/2020/contribute")
    assert response.status_code == 200
    count = (await db.execute(select(func.count()).select_from(ExamEvent))).scalar_one()
    assert count == 1  # only the fixture's event


@pytest.mark.asyncio
@pytest.mark.parametrize("year", [1999, 3000])
async def test_wizard_page_rejects_out_of_range_year(client, db, event, year):
    _, region, discipline = event
    response = await client.get(f"/exams/{region.slug}/{discipline.slug}/{year}/contribute")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_sitemap_lists_only_events_with_reports(client, db, event):
    event_obj, region, discipline = event
    empty_event = ExamEvent(year=2020, region_id=region.id, discipline_id=discipline.id)
    user = User(email="sitemap@test.com")
    composer = Composer(name="Sitemap Composer")
    db.add_all([empty_event, user, composer])
    await db.flush()
    work = Work(title="Sitemap Work", composer_id=composer.id)
    db.add(work)
    await db.flush()
    db.add(Report(user_id=user.id, event_id=event_obj.id, work_id=work.id))
    await db.commit()

    response = await client.get("/sitemap.xml")
    assert response.status_code == 200
    assert "/exams/andalucia/piano/2026</loc>" in response.text
    assert "/exams/andalucia/piano/2020" not in response.text


@pytest.mark.asyncio
async def test_robots_txt_points_to_own_sitemap(client):
    response = await client.get("/robots.txt")
    assert "Sitemap: http://test/sitemap.xml" in response.text
