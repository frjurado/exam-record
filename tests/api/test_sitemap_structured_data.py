"""What search engines are told: the sitemap, robots.txt and structured data."""

import json
import re

import pytest

from app.models import Composer, Discipline, ExamEvent, Region, Report, User, Vote, Work


@pytest.fixture
async def world(db):
    """Piano 2021: sonata verified. Piano 2020: bagatelle vs fantasia, disputed.
    Violín 2019: an exam row with no reports."""
    region = Region(name="Andalucía", slug="andalucia")
    piano = Discipline(name="Piano", slug="piano")
    violin = Discipline(name="Violín", slug="violin")
    users = [User(email=f"u{i}@test.com") for i in range(3)]
    beethoven = Composer(name="Ludwig van Beethoven", wikidata_id="Q255")
    mozart = Composer(name="Wolfgang Amadeus Mozart")
    db.add_all([region, piano, violin, beethoven, mozart, *users])
    await db.flush()
    sonata = Work(
        title='Sonata "Claro" & </script>',
        nickname="Claro de luna",
        imslp_url="https://imslp.org/wiki/X",
        composer_id=beethoven.id,
    )
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

    await exam(piano, 2021, (sonata, 2))
    await exam(piano, 2020, (bagatelle, 1), (fantasia, 1))
    db.add(ExamEvent(year=2019, region_id=region.id, discipline_id=violin.id))
    await db.commit()
    return {
        "sonata": sonata,
        "bagatelle": bagatelle,
        "fantasia": fantasia,
        "beethoven": beethoven,
        "mozart": mozart,
    }


async def test_sitemap_lists_pages_with_something_to_show(client, world):
    response = await client.get("/sitemap.xml")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/xml")
    locs = re.findall(r"<loc>http://test([^<]*)</loc>", response.text)
    assert locs == [
        "/",
        "/estadisticas",
        "/examenes/andalucia",
        "/examenes/andalucia/piano",
        "/examenes/andalucia/piano/2021",
        "/examenes/andalucia/piano/2020",
        world["beethoven"].url_path,
        world["sonata"].url_path,
    ]
    # Left out: the discipline and exam without reports, and the works and composer that
    # only appear in a disputed exam (their pages ask not to be indexed).
    assert "violin" not in response.text
    assert world["mozart"].url_path not in response.text


async def test_empty_site_sitemap(client, db):
    locs = re.findall(r"<loc>([^<]*)</loc>", (await client.get("/sitemap.xml")).text)
    assert locs == ["http://test/"]


async def test_robots_keeps_crawlers_out_of_the_machinery(client):
    text = (await client.get("/robots.txt")).text
    assert "Allow: /" in text
    for line in ("Disallow: /api/", "Disallow: /admin", "Disallow: /auth/"):
        assert line in text


def _structured_data(page: str) -> dict:
    block = re.search(r'<script type="application/ld\+json">(.*?)</script>', page, re.S)
    assert block is not None
    return json.loads(block.group(1))


async def test_work_page_structured_data(client, world):
    sonata = world["sonata"]
    page = (await client.get(sonata.url_path)).text
    assert _structured_data(page) == {
        "@context": "https://schema.org",
        "@type": "MusicComposition",
        "name": 'Sonata "Claro" & </script>',
        "alternateName": "Claro de luna",
        "url": f"http://test{sonata.url_path}",
        "sameAs": "https://imslp.org/wiki/X",
        "composer": {
            "@type": "Person",
            "name": "Ludwig van Beethoven",
            "url": f"http://test{world['beethoven'].url_path}",
            "sameAs": "https://www.wikidata.org/wiki/Q255",
        },
    }
    # A title cannot break out of the script block.
    assert page.count("</script>") == page.count("<script")


async def test_composer_page_structured_data(client, world):
    mozart = world["mozart"]
    data = _structured_data((await client.get(mozart.url_path)).text)
    assert data == {
        "@context": "https://schema.org",
        "@type": "Person",
        "name": "Wolfgang Amadeus Mozart",
        "url": f"http://test{mozart.url_path}",
    }


async def test_all_years_view_is_the_same_page_to_search_engines(client, world):
    page = (await client.get("/examenes/andalucia?todos=1")).text
    assert '<link rel="canonical" href="http://test/examenes/andalucia">' in page
