"""Unit tests for ExamService."""
import pytest

from app.models import Composer, Discipline, ExamEvent, Region, Report, User, Vote, Work
from app.services.exam_service import ExamService


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def region(db):
    r = Region(name="ES Region", slug="es-region")
    db.add(r)
    await db.commit()
    await db.refresh(r)
    return r


@pytest.fixture
async def discipline(db):
    d = Discipline(name="ES Discipline", slug="es-discipline")
    db.add(d)
    await db.commit()
    await db.refresh(d)
    return d


@pytest.fixture
async def event(db, region, discipline):
    ev = ExamEvent(year=2024, region_id=region.id, discipline_id=discipline.id)
    db.add(ev)
    await db.commit()
    await db.refresh(ev)
    return ev


@pytest.fixture
async def user(db):
    u = User(email="exam-svc@test.com")
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u


@pytest.fixture
async def composer_and_work(db, event):
    """Creates a Composer, Work, and Report for the given event (no votes)."""
    c = Composer(name="ES Composer", is_verified=True)
    db.add(c)
    await db.commit()
    await db.refresh(c)

    w = Work(title="ES Work", composer_id=c.id, is_verified=True)
    db.add(w)
    await db.commit()
    await db.refresh(w)

    return c, w


# ---------------------------------------------------------------------------
# get_exam_context
# ---------------------------------------------------------------------------


async def test_get_exam_context_not_found(db):
    result = await ExamService.get_exam_context(
        db,
        region_slug="no-such-region",
        discipline_slug="no-such-discipline",
        year=2024,
        current_user=None,
    )
    assert result is None


async def test_get_exam_context_no_user(db, region, discipline, event):
    ctx = await ExamService.get_exam_context(
        db,
        region_slug=region.slug,
        discipline_slug=discipline.slug,
        year=event.year,
        current_user=None,
    )
    assert ctx is not None
    assert ctx["event"].id == event.id
    assert "works" in ctx
    assert "total_votes" in ctx
    assert "event_status" in ctx
    assert ctx["user_has_participated"] is False
    assert ctx["user_participation_report_id"] is None


async def test_get_exam_context_empty_event(db, region, discipline, event):
    ctx = await ExamService.get_exam_context(
        db,
        region_slug=region.slug,
        discipline_slug=discipline.slug,
        year=event.year,
        current_user=None,
    )
    assert ctx is not None
    assert ctx["total_votes"] == 0
    assert ctx["event_status"] == "empty"


async def test_get_exam_context_with_votes(db, region, discipline, event, user, composer_and_work):
    _, work = composer_and_work
    other = User(email="other-exam@test.com")
    db.add(other)
    await db.commit()
    await db.refresh(other)

    report = Report(user_id=other.id, event_id=event.id, work_id=work.id, is_flagged=False)
    db.add(report)
    await db.commit()
    await db.refresh(report)

    vote1 = Vote(user_id=other.id, report_id=report.id)
    vote2 = Vote(user_id=user.id, report_id=report.id)
    db.add(vote1)
    db.add(vote2)
    await db.commit()

    ctx = await ExamService.get_exam_context(
        db,
        region_slug=region.slug,
        discipline_slug=discipline.slug,
        year=event.year,
        current_user=user,
    )
    assert ctx is not None
    assert ctx["total_votes"] == 2
    # user voted → participated
    assert ctx["user_has_participated"] is True


async def test_get_exam_context_user_participated_via_report(
    db, region, discipline, event, user, composer_and_work
):
    _, work = composer_and_work
    report = Report(user_id=user.id, event_id=event.id, work_id=work.id, is_flagged=False)
    db.add(report)
    await db.commit()
    await db.refresh(report)

    ctx = await ExamService.get_exam_context(
        db,
        region_slug=region.slug,
        discipline_slug=discipline.slug,
        year=event.year,
        current_user=user,
    )
    assert ctx is not None
    assert ctx["user_has_participated"] is True
    assert ctx["user_participation_report_id"] == report.id


# ---------------------------------------------------------------------------
# get_discipline_context
# ---------------------------------------------------------------------------


async def test_get_discipline_context_not_found(db):
    result = await ExamService.get_discipline_context(
        db,
        region_slug="no-region",
        discipline_slug="no-discipline",
        cursor=None,
        sparse_mode=False,
        current_user=None,
    )
    assert result is None


async def test_get_discipline_context_all_empty(db, region, discipline):
    ctx = await ExamService.get_discipline_context(
        db,
        region_slug=region.slug,
        discipline_slug=discipline.slug,
        cursor=None,
        sparse_mode=True,
        current_user=None,
    )
    assert ctx is not None
    assert ctx["all_empty"] is True
    assert ctx["region"].slug == region.slug
    assert ctx["discipline"].slug == discipline.slug


async def test_get_discipline_context_has_data(db, region, discipline, event, composer_and_work):
    _, work = composer_and_work
    user = User(email="disc-ctx@test.com")
    db.add(user)
    await db.commit()
    await db.refresh(user)

    report = Report(user_id=user.id, event_id=event.id, work_id=work.id, is_flagged=False)
    db.add(report)
    await db.commit()
    await db.refresh(report)

    vote = Vote(user_id=user.id, report_id=report.id)
    db.add(vote)
    await db.commit()

    ctx = await ExamService.get_discipline_context(
        db,
        region_slug=region.slug,
        discipline_slug=discipline.slug,
        cursor=None,
        sparse_mode=True,
        current_user=None,
    )
    assert ctx is not None
    assert ctx["all_empty"] is False

    year_entry = next((y for y in ctx["years"] if y["year"] == event.year), None)
    assert year_entry is not None
    assert year_entry["has_event"] is True
    assert year_entry["report_count"] == 1


async def test_get_discipline_context_badge_disputed(
    db, region, discipline, event, composer_and_work
):
    """One vote but below verification threshold → disputed."""
    _, work = composer_and_work

    # Add a second work/report so consensus_rate < 0.75
    c2 = Composer(name="Composer 2", is_verified=True)
    db.add(c2)
    await db.commit()
    await db.refresh(c2)
    w2 = Work(title="Work 2", composer_id=c2.id, is_verified=True)
    db.add(w2)
    await db.commit()
    await db.refresh(w2)

    user1 = User(email="badge1@test.com")
    user2 = User(email="badge2@test.com")
    db.add(user1)
    db.add(user2)
    await db.commit()
    await db.refresh(user1)
    await db.refresh(user2)

    report1 = Report(user_id=user1.id, event_id=event.id, work_id=work.id, is_flagged=False)
    report2 = Report(user_id=user2.id, event_id=event.id, work_id=w2.id, is_flagged=False)
    db.add(report1)
    db.add(report2)
    await db.commit()
    await db.refresh(report1)
    await db.refresh(report2)

    # 1 vote each → 50% each → disputed (neither reaches 75%)
    db.add(Vote(user_id=user1.id, report_id=report1.id))
    db.add(Vote(user_id=user2.id, report_id=report2.id))
    await db.commit()

    ctx = await ExamService.get_discipline_context(
        db,
        region_slug=region.slug,
        discipline_slug=discipline.slug,
        cursor=None,
        sparse_mode=True,
        current_user=None,
    )
    assert ctx is not None
    year_entry = next((y for y in ctx["years"] if y["year"] == event.year), None)
    assert year_entry is not None
    assert year_entry["badge_status"] == "disputed"


async def test_get_discipline_context_badge_verified(
    db, region, discipline, event, composer_and_work
):
    """Two votes on one work, one on another → first is verified."""
    _, work = composer_and_work

    c2 = Composer(name="Minor Composer", is_verified=True)
    db.add(c2)
    await db.commit()
    await db.refresh(c2)
    w2 = Work(title="Minor Work", composer_id=c2.id, is_verified=True)
    db.add(w2)
    await db.commit()
    await db.refresh(w2)

    users = []
    for i in range(3):
        u = User(email=f"verif{i}@test.com")
        db.add(u)
    await db.commit()
    result = await db.execute(__import__("sqlalchemy.future", fromlist=["select"]).select(User).filter(User.email.like("verif%@test.com")))
    users = result.scalars().all()

    report1 = Report(user_id=users[0].id, event_id=event.id, work_id=work.id, is_flagged=False)
    report2 = Report(user_id=users[1].id, event_id=event.id, work_id=w2.id, is_flagged=False)
    db.add(report1)
    db.add(report2)
    await db.commit()
    await db.refresh(report1)
    await db.refresh(report2)

    # 2 votes on report1 (66%), 1 vote on report2 (33%) — total 3
    # report1: votes=2, rate=0.667 → not verified (needs ≥0.75)
    # Let's give 3 votes to report1 and 1 to report2: 3/4 = 75% → verified
    db.add(Vote(user_id=users[0].id, report_id=report1.id))
    db.add(Vote(user_id=users[1].id, report_id=report1.id))
    db.add(Vote(user_id=users[2].id, report_id=report1.id))
    db.add(Vote(user_id=users[2].id, report_id=report2.id))
    await db.commit()

    ctx = await ExamService.get_discipline_context(
        db,
        region_slug=region.slug,
        discipline_slug=discipline.slug,
        cursor=None,
        sparse_mode=True,
        current_user=None,
    )
    assert ctx is not None
    year_entry = next((y for y in ctx["years"] if y["year"] == event.year), None)
    assert year_entry is not None
    assert year_entry["badge_status"] == "verified"


async def test_get_discipline_context_cursor_pagination(
    db, region, discipline
):
    """cursor filters out years >= cursor value."""
    # Create two events
    ev1 = ExamEvent(year=2020, region_id=region.id, discipline_id=discipline.id)
    ev2 = ExamEvent(year=2021, region_id=region.id, discipline_id=discipline.id)
    db.add(ev1)
    db.add(ev2)
    await db.commit()

    ctx = await ExamService.get_discipline_context(
        db,
        region_slug=region.slug,
        discipline_slug=discipline.slug,
        cursor=2021,  # only years < 2021 should be in batch
        sparse_mode=False,
        current_user=None,
    )
    assert ctx is not None
    years_in_batch = [y["year"] for y in ctx["years"]]
    assert 2021 not in years_in_batch
    assert 2020 in years_in_batch
