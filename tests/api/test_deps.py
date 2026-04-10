"""Unit tests for check_user_event_participation in app.api.deps."""

import pytest

from app.api.deps import check_user_event_participation
from app.models import Composer, Discipline, ExamEvent, Region, Report, User, Vote, Work


@pytest.fixture
async def user(db):
    u = User(email="user@deps-test.com")
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u


@pytest.fixture
async def other_user(db):
    u = User(email="other@deps-test.com")
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u


@pytest.fixture
async def event(db):
    region = Region(name="Deps Region", slug="deps-region")
    discipline = Discipline(name="Deps Discipline", slug="deps-discipline")
    db.add(region)
    db.add(discipline)
    await db.commit()
    await db.refresh(region)
    await db.refresh(discipline)
    ev = ExamEvent(year=2024, region_id=region.id, discipline_id=discipline.id)
    db.add(ev)
    await db.commit()
    await db.refresh(ev)
    return ev


@pytest.fixture
async def composer_and_work(db):
    composer = Composer(name="Deps Composer", is_verified=True)
    db.add(composer)
    await db.commit()
    await db.refresh(composer)
    work = Work(title="Deps Work", composer_id=composer.id, is_verified=True)
    db.add(work)
    await db.commit()
    await db.refresh(work)
    return composer, work


async def test_no_participation(db, user, event):
    has_participated, report_id = await check_user_event_participation(db, user.id, event.id)
    assert has_participated is False
    assert report_id is None


async def test_user_has_report(db, user, event, composer_and_work):
    _, work = composer_and_work
    report = Report(user_id=user.id, event_id=event.id, work_id=work.id, is_flagged=False)
    db.add(report)
    await db.commit()
    await db.refresh(report)

    has_participated, report_id = await check_user_event_participation(db, user.id, event.id)
    assert has_participated is True
    assert report_id == report.id


async def test_user_has_vote_on_others_report(db, user, other_user, event, composer_and_work):
    _, work = composer_and_work
    # other_user submits the report
    report = Report(user_id=other_user.id, event_id=event.id, work_id=work.id, is_flagged=False)
    db.add(report)
    await db.commit()
    await db.refresh(report)

    # user votes on it
    vote = Vote(user_id=user.id, report_id=report.id)
    db.add(vote)
    await db.commit()

    has_participated, report_id = await check_user_event_participation(db, user.id, event.id)
    assert has_participated is True
    assert report_id == report.id


async def test_other_user_report_does_not_affect_unrelated_user(
    db, user, other_user, event, composer_and_work
):
    _, work = composer_and_work
    report = Report(user_id=other_user.id, event_id=event.id, work_id=work.id, is_flagged=False)
    db.add(report)
    await db.commit()

    # user has neither report nor vote
    has_participated, report_id = await check_user_event_participation(db, user.id, event.id)
    assert has_participated is False
    assert report_id is None
