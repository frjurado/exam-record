from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import func, select

from app.models import Composer, Discipline, ExamEvent, Region, Report, User, Vote, Work
from app.services.admin_service import AdminError, AdminService


async def _count(db, model) -> int:
    return (await db.execute(select(func.count()).select_from(model))).scalar_one()


@pytest.fixture
async def world(db):
    """Two exams, three users, a composer stored twice and a work stored twice."""
    region = Region(name="Andalucía", slug="andalucia")
    discipline = Discipline(name="Piano", slug="piano")
    users = [User(email=f"u{i}@test.com") for i in range(3)]
    beethoven = Composer(name="Ludwig van Beethoven", openopus_id="145", is_verified=True)
    typed = Composer(name="Betoven")
    db.add_all([region, discipline, beethoven, typed, *users])
    await db.flush()

    e2019 = ExamEvent(year=2019, region_id=region.id, discipline_id=discipline.id)
    e2020 = ExamEvent(year=2020, region_id=region.id, discipline_id=discipline.id)
    catalogue = Work(
        title="Sonata para piano n.º 14",
        openopus_id="900",
        composer_id=beethoven.id,
        is_verified=True,
    )
    by_hand = Work(title="Sonata Claro de Luna", composer_id=beethoven.id)
    db.add_all([e2019, e2020, catalogue, by_hand])
    await db.flush()

    # 2019: both spellings were reported (one vote each). 2020: only the hand-typed one.
    r_cat_2019 = Report(user_id=users[0].id, event_id=e2019.id, work_id=catalogue.id)
    r_hand_2019 = Report(
        user_id=users[1].id, event_id=e2019.id, work_id=by_hand.id, movement_details="Mov. 1"
    )
    r_hand_2020 = Report(user_id=users[2].id, event_id=e2020.id, work_id=by_hand.id)
    db.add_all([r_cat_2019, r_hand_2019, r_hand_2020])
    await db.flush()
    db.add_all(
        [
            Vote(user_id=users[0].id, report_id=r_cat_2019.id, event_id=e2019.id),
            Vote(user_id=users[1].id, report_id=r_hand_2019.id, event_id=e2019.id),
            Vote(user_id=users[2].id, report_id=r_hand_2020.id, event_id=e2020.id),
        ]
    )
    await db.commit()
    return {
        "beethoven": beethoven.id,
        "typed": typed.id,
        "catalogue": catalogue.id,
        "by_hand": by_hand.id,
        "e2019": e2019.id,
        "e2020": e2020.id,
        "r_cat_2019": r_cat_2019.id,
        "r_hand_2020": r_hand_2020.id,
    }


async def test_merge_works_moves_reports_and_combines_same_exam(db, world):
    await AdminService.merge_works(db, world["by_hand"], world["catalogue"])

    assert await _count(db, Work) == 1
    assert await _count(db, Vote) == 3  # no vote is lost
    reports = (await db.execute(select(Report).order_by(Report.event_id))).scalars().all()
    assert [(r.event_id, r.work_id) for r in reports] == [
        (world["e2019"], world["catalogue"]),
        (world["e2020"], world["catalogue"]),
    ]
    # 2019 had a report for each spelling: the surviving one holds both votes and
    # inherits the details it lacked.
    votes_2019 = (
        await db.execute(
            select(func.count()).select_from(Vote).where(Vote.report_id == world["r_cat_2019"])
        )
    ).scalar_one()
    assert votes_2019 == 2
    assert reports[0].movement_details == "Mov. 1"


async def test_merge_works_into_hand_typed_keeps_catalogue_identity(db, world):
    await AdminService.merge_works(db, world["catalogue"], world["by_hand"])

    work = (await db.execute(select(Work))).scalar_one()
    assert work.id == world["by_hand"]
    assert work.openopus_id == "900"
    assert work.title == "Sonata para piano n.º 14"
    assert work.is_verified
    assert await _count(db, Vote) == 3
    assert await _count(db, Report) == 2


async def test_merge_works_rejects_same_or_missing(db, world):
    with pytest.raises(AdminError):
        await AdminService.merge_works(db, world["catalogue"], world["catalogue"])
    with pytest.raises(AdminError):
        await AdminService.merge_works(db, 99999, world["catalogue"])
    assert await _count(db, Work) == 2


async def test_merge_composers_moves_and_merges_works(db, world):
    same_title = Work(title="sonata para piano nº 14", composer_id=world["typed"])
    other = Work(title="Bagatela", composer_id=world["typed"])
    db.add_all([same_title, other])
    await db.commit()

    await AdminService.merge_composers(db, world["typed"], world["beethoven"])

    assert await _count(db, Composer) == 1
    works = (await db.execute(select(Work).order_by(Work.title))).scalars().all()
    assert {w.composer_id for w in works} == {world["beethoven"]}
    # The same-titled work was folded into the existing one instead of being duplicated.
    assert sorted(w.title for w in works) == [
        "Bagatela",
        "Sonata Claro de Luna",
        "Sonata para piano n.º 14",
    ]


async def test_merge_composers_passes_on_catalogue_ids(db, world):
    await AdminService.merge_composers(db, world["beethoven"], world["typed"])

    composer = (await db.execute(select(Composer))).scalar_one()
    assert composer.name == "Betoven"  # the target keeps its name
    assert composer.openopus_id == "145"
    assert composer.is_verified
    assert await _count(db, Work) == 2


async def test_delete_report_removes_votes_and_empty_exam(db, world):
    await AdminService.delete_report(db, world["r_hand_2020"])

    assert await _count(db, Report) == 2
    assert await _count(db, Vote) == 2
    # 2020 had only that report, so the exam goes; 2019 still has two.
    years = (await db.execute(select(ExamEvent.year))).scalars().all()
    assert years == [2019]

    await AdminService.delete_report(db, world["r_cat_2019"])
    assert (await db.execute(select(ExamEvent.year))).scalars().all() == [2019]


async def test_clear_flag(db, world):
    report = (await db.execute(select(Report).where(Report.id == world["r_cat_2019"]))).scalar_one()
    report.is_flagged = True
    await db.commit()

    await AdminService.clear_flag(db, world["r_cat_2019"])

    await db.refresh(report)
    assert report.is_flagged is False


async def test_delete_empty_events_leaves_reported_ones(db, world):
    region_id = (await db.execute(select(Region.id))).scalar_one()
    discipline_id = (await db.execute(select(Discipline.id))).scalar_one()
    db.add_all(
        [
            ExamEvent(year=year, region_id=region_id, discipline_id=discipline_id)
            for year in (2010, 2011)
        ]
    )
    await db.commit()

    assert (await AdminService.get_overview(db))["empty_events"] == 2
    assert await AdminService.delete_empty_events(db) == 2
    assert sorted((await db.execute(select(ExamEvent.year))).scalars().all()) == [2019, 2020]


async def test_delete_work_only_when_unreported(db, world):
    with pytest.raises(AdminError):
        await AdminService.delete_work(db, world["by_hand"])
    orphan = Work(title="Nadie la reportó", composer_id=world["beethoven"])
    db.add(orphan)
    await db.commit()

    await AdminService.delete_work(db, orphan.id)
    assert await _count(db, Work) == 2


async def test_update_work_and_search_text(db, world):
    await AdminService.update_work(
        db, world["by_hand"], " Sonata n.º 14 ", "Claro de luna", "https://imslp.org/wiki/X"
    )
    work = await AdminService.get_work(db, world["by_hand"])
    assert (work.title, work.nickname, work.imslp_url) == (
        "Sonata n.º 14",
        "Claro de luna",
        "https://imslp.org/wiki/X",
    )
    assert work.search_text == "sonata n 14 claro de luna"

    with pytest.raises(AdminError):
        await AdminService.update_work(db, world["by_hand"], "  ", None, None)
    with pytest.raises(AdminError):
        await AdminService.update_work(db, world["by_hand"], "T", None, "javascript:alert(1)")


async def test_rename_composer(db, world):
    await AdminService.rename_composer(db, world["typed"], "Beethoven (copia)")
    composer = (
        await db.execute(select(Composer).where(Composer.id == world["typed"]))
    ).scalar_one()
    assert composer.name == "Beethoven (copia)"
    assert composer.search_text == "beethoven copia"


CATALOGUE = [
    {"openopus_id": "900", "title": "Sonata para piano n.º 14", "nickname": "Claro de luna"},
    {"openopus_id": "901", "title": "Sonata para piano n.º 8", "nickname": "Patética"},
]


async def test_link_to_catalogue_work_already_stored_merges(db, world):
    with patch(
        "app.services.admin_service.openopus.get_composer_works", AsyncMock(return_value=CATALOGUE)
    ):
        await AdminService.link_work_to_catalogue(db, world["by_hand"], "900")

    work = (await db.execute(select(Work))).scalar_one()
    assert work.id == world["catalogue"]
    assert await _count(db, Vote) == 3


async def test_link_to_catalogue_work_not_stored_adopts_its_identity(db, world):
    with patch(
        "app.services.admin_service.openopus.get_composer_works", AsyncMock(return_value=CATALOGUE)
    ):
        await AdminService.link_work_to_catalogue(db, world["by_hand"], "901")
        with pytest.raises(AdminError):
            await AdminService.link_work_to_catalogue(db, world["by_hand"], "does-not-exist")

    work = await AdminService.get_work(db, world["by_hand"])
    assert (work.title, work.nickname, work.openopus_id) == (
        "Sonata para piano n.º 8",
        "Patética",
        "901",
    )
    assert work.is_verified
    assert await _count(db, Work) == 2


async def test_link_requires_a_catalogue_composer(db, world):
    orphan = Work(title="Algo", composer_id=world["typed"])
    db.add(orphan)
    await db.commit()
    with pytest.raises(AdminError):
        await AdminService.link_work_to_catalogue(db, orphan.id, "900")
