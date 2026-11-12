"""Work and composer pages, the exam outcome they rest on, and the address changes."""

import pytest

from app.models import Composer, Discipline, ExamEvent, Region, Report, User, Vote, Work, page_ref
from app.services.browse_service import BrowseService
from app.services.consensus import ConsensusService


@pytest.fixture
async def world(db):
    """Beethoven's sonata: verified in Piano 2021, the only report in Piano 2019, one of two
    proposals in Piano 2018, outvoted in Violín 2021. His bagatelle: only ever disputed."""
    region = Region(name="Andalucía", slug="andalucia")
    piano = Discipline(name="Piano", slug="piano")
    violin = Discipline(name="Violín", slug="violin")
    users = [User(email=f"u{i}@test.com") for i in range(4)]
    beethoven = Composer(name="Ludwig van Beethoven", wikidata_id="Q255")
    mozart = Composer(name="Wolfgang Amadeus Mozart")
    db.add_all([region, piano, violin, beethoven, mozart, *users])
    await db.flush()
    sonata = Work(
        title="Sonata para piano n.º 14 en do sostenido menor, op. 27 n.º 2",
        nickname="Claro de luna",
        composer_id=beethoven.id,
    )
    bagatelle = Work(title="Bagatela en la menor", composer_id=beethoven.id)
    fantasia = Work(title="Fantasía en re menor, K. 397", composer_id=mozart.id)
    db.add_all([sonata, bagatelle, fantasia])
    await db.flush()

    async def exam(discipline, year, *proposals):
        event = ExamEvent(year=year, region_id=region.id, discipline_id=discipline.id)
        db.add(event)
        await db.flush()
        voters = iter(users)
        for work, votes, details in proposals:
            report = Report(
                user_id=users[0].id, event_id=event.id, work_id=work.id, movement_details=details
            )
            db.add(report)
            await db.flush()
            for _ in range(votes):
                db.add(Vote(user_id=next(voters).id, report_id=report.id, event_id=event.id))

    await exam(piano, 2021, (sonata, 3, "Mov. 1 (Adagio sostenuto)"), (fantasia, 1, None))
    await exam(piano, 2019, (sonata, 1, None))
    await exam(piano, 2018, (sonata, 1, None), (bagatelle, 1, None))
    await exam(violin, 2021, (fantasia, 3, None), (sonata, 1, None))
    await db.commit()
    return {"sonata": sonata, "bagatelle": bagatelle, "fantasia": fantasia, "beethoven": beethoven}


class _Report:
    def __init__(self, votes):
        self.votes = [object()] * votes


@pytest.mark.parametrize(
    ("votes", "status", "counted", "standings"),
    [
        ([], "empty", None, []),
        ([1], "neutral", 0, ["unconfirmed"]),
        ([2], "verified", 0, ["verified"]),
        ([3, 1], "verified", 0, ["verified", "outvoted"]),
        ([1, 1], "disputed", None, ["disputed", "disputed"]),
        ([2, 1], "disputed", None, ["disputed", "disputed"]),
    ],
)
def test_event_outcome(votes, status, counted, standings):
    reports = [_Report(n) for n in votes]
    outcome = ConsensusService.event_outcome(reports)
    assert outcome["status"] == status
    assert outcome["counted"] is (reports[counted] if counted is not None else None)
    assert [ConsensusService.report_standing(r, outcome) for r in reports] == standings


def test_page_ref():
    assert page_ref(42, "Sonata para piano n.º 14, op. 27") == "42-sonata-para-piano-n-14-op-27"
    assert page_ref(7, "Albéniz") == "7-albeniz"
    assert page_ref(7, "¿?") == "7"
    assert len(page_ref(1, "palabra " * 40)) <= 82


async def test_appearances_count_only_settled_exams(db, world):
    context = await BrowseService.work_context(db, world["sonata"].id)
    assert [(a["year"], a["discipline"].slug, a["standing"]) for a in context["appearances"]] == [
        (2021, "piano", "verified"),
        (2019, "piano", "unconfirmed"),
    ]
    assert [(a["year"], a["discipline"].slug, a["standing"]) for a in context["mentions"]] == [
        (2021, "violin", "outvoted"),
        (2018, "piano", "disputed"),
    ]
    assert await BrowseService.work_context(db, 99999) is None


async def test_work_page(client, world):
    sonata = world["sonata"]
    response = await client.get(sonata.url_path)
    assert response.status_code == 200
    page = response.text
    assert "Claro de luna" in page
    assert "2 convocatorias" in page
    assert 'href="/examenes/andalucia/piano/2021"' in page
    assert "Mov. 1 (Adagio sostenuto)" in page
    assert "Menciones sin confirmar" in page
    assert f'href="{world["beethoven"].url_path}"' in page
    assert "noindex" not in page

    # A work nobody has settled on yet is shown, but kept out of search engines.
    page = (await client.get(world["bagatelle"].url_path)).text
    assert "Todavía no hay ninguna convocatoria confirmada" in page
    assert "noindex" in page


async def test_work_address_follows_the_id(client, world):
    sonata = world["sonata"]
    for ref in (str(sonata.id), f"{sonata.id}-titulo-antiguo"):
        response = await client.get(f"/obras/{ref}")
        assert response.status_code == 301
        assert response.headers["location"] == sonata.url_path
    for ref in ("99999-nada", "sin-numero", "-3"):
        assert (await client.get(f"/obras/{ref}")).status_code == 404


async def test_composer_page(client, world):
    beethoven = world["beethoven"]
    response = await client.get(beethoven.url_path)
    assert response.status_code == 200
    page = response.text
    assert "2 convocatorias" in page
    assert f'href="{world["sonata"].url_path}"' in page
    assert "wikidata.org/wiki/Q255" in page
    # The bagatelle was only ever proposed for a disputed exam.
    assert page.index("Menciones sin confirmar") < page.index("Bagatela en la menor")
    # Mozart's works are not his.
    assert "Fantasía" not in page

    assert (await client.get(f"/compositores/{beethoven.id}")).status_code == 301
    assert (await client.get("/compositores/99999-nadie")).status_code == 404


async def test_exam_page_links_to_work_and_composer(client, world):
    page = (await client.get("/examenes/andalucia/piano/2021")).text
    assert f'href="{world["sonata"].url_path}"' in page
    assert f'href="{world["beethoven"].url_path}"' in page


async def test_old_exam_addresses_redirect(client, world):
    response = await client.get("/exams/andalucia/piano/2021?x=1")
    assert response.status_code == 301
    assert response.headers["location"] == "/examenes/andalucia/piano/2021?x=1"
    response = await client.get("/exams/andalucia/piano")
    assert response.headers["location"] == "/examenes/andalucia/piano"


async def test_canonical_address_is_https_behind_the_proxy(client, world):
    page = (await client.get(world["sonata"].url_path, headers={"x-forwarded-proto": "https"})).text
    assert f'<link rel="canonical" href="https://test{world["sonata"].url_path}">' in page
