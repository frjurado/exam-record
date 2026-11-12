"""The statistics page and a region's coverage table."""

import pytest

from app.models import Composer, Discipline, ExamEvent, Region, Report, User, Vote, Work
from app.services.browse_service import BrowseService
from app.services.exam_service import ExamService


@pytest.fixture
async def world(db):
    """Counted: sonata in Piano (latest, verified), Piano (latest-1, single report) and
    Violín (latest, verified); fantasia in Piano (latest-2, single report).
    Disputed: Piano latest-3 (sonata vs bagatelle). Outvoted: bagatelle in Violín latest."""
    latest = ExamService.latest_exam_year()
    region = Region(name="Andalucía", slug="andalucia")
    piano = Discipline(name="Piano", slug="piano")
    violin = Discipline(name="Violín", slug="violin")
    tuba = Discipline(name="Tuba", slug="tuba")
    users = [User(email=f"u{i}@test.com") for i in range(4)]
    beethoven = Composer(name="Ludwig van Beethoven")
    mozart = Composer(name="Wolfgang Amadeus Mozart")
    db.add_all([region, piano, violin, tuba, beethoven, mozart, *users])
    await db.flush()
    sonata = Work(title="Sonata para piano n.º 14", composer_id=beethoven.id)
    bagatelle = Work(title="Bagatela en la menor", composer_id=beethoven.id)
    fantasia = Work(title="Fantasía en re menor", composer_id=mozart.id)
    db.add_all([sonata, bagatelle, fantasia])
    await db.flush()

    async def exam(discipline, year, *proposals):
        event = ExamEvent(year=year, region_id=region.id, discipline_id=discipline.id)
        db.add(event)
        await db.flush()
        voters = iter(users)
        for work, votes in proposals:
            report = Report(user_id=users[0].id, event_id=event.id, work_id=work.id)
            db.add(report)
            await db.flush()
            for _ in range(votes):
                db.add(Vote(user_id=next(voters).id, report_id=report.id, event_id=event.id))

    await exam(piano, latest, (sonata, 2))
    await exam(piano, latest - 1, (sonata, 1))
    await exam(piano, latest - 2, (fantasia, 1))
    await exam(piano, latest - 3, (sonata, 1), (bagatelle, 1))
    await exam(violin, latest, (sonata, 3), (bagatelle, 1))
    # An exam row nobody reported for must not count anywhere.
    db.add(ExamEvent(year=latest - 1, region_id=region.id, discipline_id=violin.id))
    await db.commit()
    return {"latest": latest, "sonata": sonata, "beethoven": beethoven, "mozart": mozart}


async def test_statistics_overall(db, world):
    stats = await BrowseService.statistics_context(db)
    assert stats["exams_counted"] == 4
    assert stats["exams_disputed"] == 1
    assert [(row["composer"].name, row["count"], row["works"]) for row in stats["composers"]] == [
        ("Ludwig van Beethoven", 3, 1),
        ("Wolfgang Amadeus Mozart", 1, 1),
    ]
    # Only works that fell at least twice are ranked; the same work in two disciplines
    # in the same year counts twice.
    assert [(row["work"].title, len(row["appearances"])) for row in stats["works"]] == [
        ("Sonata para piano n.º 14", 3)
    ]
    assert stats["single_works"] == 1
    assert [d.slug for d in stats["disciplines"]] == ["piano", "violin"]


async def test_statistics_for_one_discipline(db, world):
    stats = await BrowseService.statistics_context(db, "violin")
    assert stats["exams_counted"] == 1
    assert [(row["composer"].name, row["count"]) for row in stats["composers"]] == [
        ("Ludwig van Beethoven", 1)
    ]
    assert stats["works"] == []
    assert await BrowseService.statistics_context(db, "arpa") is None


async def test_statistics_page(client, world):
    response = await client.get("/estadisticas")
    assert response.status_code == 200
    page = response.text
    assert "4 convocatorias" in page
    assert "Otra está en disputa" in page
    assert f'href="{world["beethoven"].url_path}"' in page
    assert f'href="{world["sonata"].url_path}"' in page
    assert 'href="/estadisticas?especialidad=violin"' in page
    assert page.index("Ludwig van Beethoven") < page.index("Wolfgang Amadeus Mozart")

    page = (await client.get("/estadisticas?especialidad=violin")).text
    assert "1 convocatoria</b>" in page
    assert "Ninguna obra ha caído más de una vez" in page
    assert world["mozart"].url_path not in page

    assert (await client.get("/estadisticas?especialidad=arpa")).status_code == 404


async def test_statistics_page_with_no_data(client, db):
    page = (await client.get("/estadisticas")).text
    assert "Todavía no hay convocatorias registradas" in page
    assert "noindex" in page


async def test_coverage(db, world):
    latest = world["latest"]
    coverage = await BrowseService.coverage_context(db, "andalucia")
    assert coverage["years"][0] == latest
    assert len(coverage["years"]) == 6
    assert (coverage["filled"], coverage["total"]) == (5, 18)
    # Most complete discipline first; one with nothing is still listed.
    assert [row["discipline"].slug for row in coverage["rows"]] == ["piano", "violin", "tuba"]

    piano = {cell["year"]: cell for cell in coverage["rows"][0]["cells"]}
    assert piano[latest]["status"] == "verified"
    assert piano[latest - 1]["status"] == "neutral"
    assert piano[latest - 3]["status"] == "disputed"
    assert piano[latest - 4]["status"] == "empty"
    assert piano[latest]["url"] == f"/examenes/andalucia/piano/{latest}"
    assert piano[latest - 4]["url"] == f"/examenes/andalucia/piano/{latest - 4}/contribute"

    # The exam row without reports reads as empty.
    violin = {cell["year"]: cell for cell in coverage["rows"][1]["cells"]}
    assert violin[latest - 1]["status"] == "empty"
    assert await BrowseService.coverage_context(db, "atlantida") is None

    # Older exams are reachable too: the full range goes back to the first valid year.
    full = await BrowseService.coverage_context(db, "andalucia", all_years=True)
    assert full["years"][0] == latest
    assert full["years"][-1] == 2000
    assert full["filled"] == 5


async def test_region_page(client, world):
    latest = world["latest"]
    response = await client.get("/examenes/andalucia")
    assert response.status_code == 200
    page = response.text
    assert "<b>5</b> de las 18 convocatorias" in page
    assert "de los últimos 6 años" in page
    assert 'href="/examenes/andalucia?todos=1"' in page
    assert f'href="/examenes/andalucia/piano/{latest - 6}/contribute"' not in page

    full = (await client.get("/examenes/andalucia?todos=1")).text
    assert "desde 2000" in full
    assert 'href="/examenes/andalucia/piano/2000/contribute"' in full
    assert f'href="/examenes/andalucia/piano/{latest}"' in page
    assert f'href="/examenes/andalucia/tuba/{latest}/contribute"' in page
    assert 'href="/examenes/andalucia/piano"' in page
    assert (await client.get("/examenes/atlantida")).status_code == 404


async def test_ways_in(client, world):
    home = (await client.get("/")).text
    assert 'href="/examenes/andalucia"' in home
    assert 'href="/estadisticas"' in home
    # Breadcrumbs lead up to the region.
    assert 'href="/examenes/andalucia"' in (await client.get("/examenes/andalucia/piano")).text
    exam = (await client.get(f"/examenes/andalucia/piano/{world['latest']}")).text
    assert 'href="/examenes/andalucia"' in exam
    assert 'href="/examenes/andalucia/piano"' in exam
