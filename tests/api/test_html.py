from unittest.mock import patch

import pytest
from sqlalchemy import func, select

from app.core.config import settings
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
    with patch.object(settings, "TURNSTILE_SITE_KEY", None):
        response = await client.get(
            f"/exams/{region.slug}/{discipline.slug}/{event_obj.year}/contribute"
        )
    assert response.status_code == 200
    assert "Aportar obra · Piano 2026" in response.text
    assert "Andalucia — Piano" in response.text  # breadcrumb uses the real names
    assert '"regionSlug": "andalucia"' in response.text
    assert '"year": 2026' in response.text
    # No Turnstile key configured: no widget, and the form must not wait for a token.
    assert "cf-turnstile" not in response.text
    assert '"turnstileKey": ""' in response.text


@pytest.mark.asyncio
async def test_wizard_page_404(client, db):
    response = await client.get("/exams/mars/theremin/3000/contribute")
    assert response.status_code == 404
    assert "Convocatoria no encontrada" in response.text


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


@pytest.mark.asyncio
async def test_wizard_page_offers_existing_reports_and_frequent_composers(client, db, event):
    event_obj, region, discipline = event
    user = User(email="prepop@test.com")
    composer = Composer(name="Enrique Granados")
    db.add_all([user, composer])
    await db.flush()
    work = Work(title="Goyescas", nickname="Los majos enamorados", composer_id=composer.id)
    db.add(work)
    await db.flush()
    db.add(
        Report(
            user_id=user.id,
            event_id=event_obj.id,
            work_id=work.id,
            movement_details="Mov. 4 (Quejas)",
        )
    )
    await db.commit()

    response = await client.get(f"/exams/{region.slug}/{discipline.slug}/2026/contribute")
    assert response.status_code == 200
    # Both lists are embedded as JSON for the form.
    assert '"title": "Goyescas"' in response.text
    assert '"details": "Mov. 4 (Quejas)"' in response.text
    assert '"suggested": [{"id": ' in response.text
    assert "Enrique Granados" in response.text


@pytest.mark.asyncio
async def test_wizard_page_redirects_users_who_already_participated(client, db, event):
    from app.api import deps
    from app.main import app
    from app.models import Vote

    event_obj, region, discipline = event
    user = User(email="voted@test.com")
    composer = Composer(name="Voted Composer")
    db.add_all([user, composer])
    await db.flush()
    work = Work(title="Voted Work", composer_id=composer.id)
    db.add(work)
    await db.flush()
    report = Report(user_id=user.id, event_id=event_obj.id, work_id=work.id)
    db.add(report)
    await db.flush()
    db.add(Vote(user_id=user.id, report_id=report.id, event_id=event_obj.id))
    await db.commit()

    app.dependency_overrides[deps.get_current_user_optional] = lambda: user
    try:
        response = await client.get(
            f"/exams/{region.slug}/{discipline.slug}/2026/contribute", follow_redirects=False
        )
    finally:
        app.dependency_overrides.pop(deps.get_current_user_optional, None)

    assert response.status_code == 303
    assert response.headers["location"] == "/exams/andalucia/piano/2026"


@pytest.mark.asyncio
async def test_event_page_shows_what_was_analysed(client, db, event):
    event_obj, region, discipline = event
    user = User(email="details@test.com")
    composer = Composer(name="Details Composer")
    db.add_all([user, composer])
    await db.flush()
    work = Work(title="Details Work", composer_id=composer.id)
    db.add(work)
    await db.flush()
    db.add(
        Report(
            user_id=user.id,
            event_id=event_obj.id,
            work_id=work.id,
            movement_details="Mov. 2 (Adagio) · fragmento: cc. 1-40",
        )
    )
    await db.commit()

    response = await client.get(f"/exams/{region.slug}/{discipline.slug}/2026")
    assert response.status_code == 200
    assert "Mov. 2 (Adagio) · fragmento: cc. 1-40" in response.text


@pytest.mark.asyncio
async def test_year_list_links_score_for_a_single_unverified_report(client, db, event):
    event_obj, region, discipline = event
    user = User(email="score@test.com")
    composer = Composer(name="Score Composer")
    db.add_all([user, composer])
    await db.flush()
    work = Work(title="Score Work", composer_id=composer.id)
    db.add(work)
    await db.flush()
    db.add(Report(user_id=user.id, event_id=event_obj.id, work_id=work.id))
    await db.commit()

    response = await client.get(f"/exams/{region.slug}/{discipline.slug}")
    assert response.status_code == 200
    assert "Score Work" in response.text
    # One report is not "verified", but the work is named, so its score link is offered.
    assert "IMSLP ↗" in response.text
