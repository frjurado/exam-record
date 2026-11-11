import pytest
from sqlalchemy import func, select

from app.api import deps
from app.main import app as fastapi_app
from app.models import Composer, Discipline, ExamEvent, Region, Report, User, Vote, Work


@pytest.fixture
async def data(db):
    region = Region(name="Andalucía", slug="andalucia")
    discipline = Discipline(name="Piano", slug="piano")
    admin = User(email="admin@test.com", role="Admin")
    visitor = User(email="visitor@test.com")
    composer = Composer(name="Bach")
    db.add_all([region, discipline, admin, visitor, composer])
    await db.flush()
    event = ExamEvent(year=2019, region_id=region.id, discipline_id=discipline.id)
    empty = ExamEvent(year=2018, region_id=region.id, discipline_id=discipline.id)
    work_a = Work(title="Fuga en do menor", composer_id=composer.id)
    work_b = Work(title="Fuga do menor BWV 847", composer_id=composer.id)
    db.add_all([event, empty, work_a, work_b])
    await db.flush()
    report = Report(user_id=visitor.id, event_id=event.id, work_id=work_a.id, is_flagged=True)
    db.add(report)
    await db.flush()
    db.add(Vote(user_id=visitor.id, report_id=report.id, event_id=event.id))
    await db.commit()
    return {
        "admin": admin,
        "visitor": visitor,
        "work_a": work_a.id,
        "work_b": work_b.id,
        "report": report.id,
        "composer": composer.id,
    }


def _sign_in(user):
    fastapi_app.dependency_overrides[deps.get_current_user_optional] = lambda: user


async def test_admin_is_hidden_from_everyone_else(client, data):
    assert (await client.get("/admin")).status_code == 404
    assert (await client.post(f"/admin/reports/{data['report']}/delete")).status_code == 404

    _sign_in(data["visitor"])
    assert (await client.get("/admin")).status_code == 404
    assert (await client.post(f"/admin/reports/{data['report']}/delete")).status_code == 404
    assert (await client.post("/admin/events/delete-empty")).status_code == 404
    assert (await client.get(f"/admin/works/{data['work_a']}")).status_code == 404


async def test_admin_page_lists_everything(client, data):
    _sign_in(data["admin"])
    response = await client.get("/admin")
    assert response.status_code == 200
    assert "Reportes marcados (1)" in response.text
    assert "Fuga do menor BWV 847" in response.text
    assert "Convocatorias vacías (1)" in response.text
    # The header offers the page to admins only.
    assert 'href="/admin"' in response.text

    _sign_in(data["visitor"])
    assert 'href="/admin"' not in (await client.get("/")).text


async def test_actions_redirect_back_with_the_outcome(client, db, data):
    _sign_in(data["admin"])

    response = await client.post(f"/admin/reports/{data['report']}/clear-flag")
    assert response.status_code == 303
    assert response.headers["location"].startswith("/admin?msg=")
    assert "Reportes marcados (0)" in (await client.get("/admin")).text

    response = await client.post(
        "/admin/works/merge",
        content=f"source_id={data['work_a']}&target_id={data['work_b']}",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert response.headers["location"].startswith("/admin?msg=")
    report = (await db.execute(select(Report))).scalar_one()
    assert report.work_id == data["work_b"]

    response = await client.post("/admin/events/delete-empty")
    assert response.headers["location"].startswith("/admin?msg=")
    assert (await db.execute(select(func.count()).select_from(ExamEvent))).scalar_one() == 1

    response = await client.post(f"/admin/reports/{data['report']}/delete")
    assert response.headers["location"].startswith("/admin?msg=")
    assert (await db.execute(select(func.count()).select_from(Vote))).scalar_one() == 0


async def test_failed_action_reports_the_error_and_changes_nothing(client, db, data):
    _sign_in(data["admin"])
    for body in (f"source_id={data['work_a']}&target_id={data['work_a']}", "source_id=&target_id="):
        response = await client.post(
            "/admin/works/merge",
            content=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert response.status_code == 303
        assert response.headers["location"].startswith("/admin?error=")
    assert (await db.execute(select(func.count()).select_from(Work))).scalar_one() == 2

    # A reported work cannot be deleted outright.
    response = await client.post(f"/admin/works/{data['work_a']}/delete")
    assert response.headers["location"].startswith("/admin?error=")


async def test_edit_work_page(client, db, data):
    _sign_in(data["admin"])
    page = await client.get(f"/admin/works/{data['work_a']}")
    assert page.status_code == 200
    assert "Fuga en do menor" in page.text
    assert "no está vinculado a OpenOpus" in page.text
    assert (await client.get("/admin/works/99999")).status_code == 404

    response = await client.post(
        f"/admin/works/{data['work_a']}",
        content="title=Fuga+n.%C2%BA+2&nickname=&imslp_url=https%3A%2F%2Fimslp.org%2Fwiki%2FX",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert response.headers["location"].startswith(f"/admin/works/{data['work_a']}?msg=")
    work = (await db.execute(select(Work).where(Work.id == data["work_a"]))).scalar_one()
    await db.refresh(work)
    assert (work.title, work.imslp_url) == ("Fuga n.º 2", "https://imslp.org/wiki/X")


async def test_rename_composer(client, db, data):
    _sign_in(data["admin"])
    response = await client.post(
        "/admin/composers/rename",
        content=f"composer_id={data['composer']}&name=Johann+Sebastian+Bach",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert response.headers["location"].startswith("/admin?msg=")
    composer = (await db.execute(select(Composer))).scalar_one()
    await db.refresh(composer)
    assert composer.name == "Johann Sebastian Bach"


async def test_link_composer_page_and_action(client, db, data):
    from unittest.mock import AsyncMock, patch

    _sign_in(data["admin"])
    found = [{"openopus_id": "87", "name": "Johann Sebastian Bach", "description": "Baroque"}]
    with patch(
        "app.services.admin_service.openopus.search_composers", AsyncMock(return_value=found)
    ):
        page = await client.get(f"/admin/composers/{data['composer']}?q=bach")
        assert page.status_code == 200
        assert "Johann Sebastian Bach" in page.text
        response = await client.post(
            f"/admin/composers/{data['composer']}/link",
            content="openopus_id=87&q=bach",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
    assert response.headers["location"].startswith("/admin?msg=")
    composer = (await db.execute(select(Composer))).scalar_one()
    await db.refresh(composer)
    assert composer.openopus_id == "87"

    assert (await client.get("/admin/composers/99999")).status_code == 404
    _sign_in(data["visitor"])
    assert (await client.get(f"/admin/composers/{data['composer']}")).status_code == 404
