"""Unit tests for ReportService."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from sqlalchemy.future import select

from app.core import config as app_config
from app.models import Composer, Discipline, ExamEvent, Region, Report, User, Vote, Work
from app.schemas.report import ComposerInput, ReportCreate, ScopeEnum, WorkInput
from app.services.report_service import ReportService


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def user(db):
    u = User(email="report-svc@test.com")
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u


@pytest.fixture
async def event(db):
    region = Region(name="RS Region", slug="rs-region")
    discipline = Discipline(name="RS Discipline", slug="rs-discipline")
    db.add(region)
    db.add(discipline)
    await db.commit()
    await db.refresh(region)
    await db.refresh(discipline)
    ev = ExamEvent(year=2025, region_id=region.id, discipline_id=discipline.id)
    db.add(ev)
    await db.commit()
    await db.refresh(ev)
    return ev


@pytest.fixture
async def composer(db):
    c = Composer(name="RS Composer", is_verified=True)
    db.add(c)
    await db.commit()
    await db.refresh(c)
    return c


@pytest.fixture
async def work(db, composer):
    w = Work(title="RS Work", composer_id=composer.id, is_verified=True)
    db.add(w)
    await db.commit()
    await db.refresh(w)
    return w


# ---------------------------------------------------------------------------
# verify_turnstile
# ---------------------------------------------------------------------------


async def test_verify_turnstile_missing_token_raises():
    with pytest.raises(HTTPException) as exc_info:
        await ReportService.verify_turnstile("")
    assert exc_info.value.status_code == 400


async def test_verify_turnstile_failure_raises():
    mock_response = MagicMock()
    mock_response.json.return_value = {"success": False}

    with patch("httpx.AsyncClient") as MockClient:
        mock_instance = AsyncMock()
        MockClient.return_value.__aenter__.return_value = mock_instance
        mock_instance.post.return_value = mock_response

        with pytest.raises(HTTPException) as exc_info:
            await ReportService.verify_turnstile("invalid-token")
        assert exc_info.value.status_code == 400


async def test_verify_turnstile_success():
    mock_response = MagicMock()
    mock_response.json.return_value = {"success": True}

    with patch("httpx.AsyncClient") as MockClient:
        mock_instance = AsyncMock()
        MockClient.return_value.__aenter__.return_value = mock_instance
        mock_instance.post.return_value = mock_response

        # Should not raise
        await ReportService.verify_turnstile("valid-token")


# ---------------------------------------------------------------------------
# get_or_create_composer
# ---------------------------------------------------------------------------


async def test_get_or_create_composer_by_id_found(db, composer):
    data = ComposerInput(id=composer.id)
    result = await ReportService.get_or_create_composer(db, data)
    assert result.id == composer.id


async def test_get_or_create_composer_by_id_not_found(db):
    data = ComposerInput(id=99999)
    with pytest.raises(HTTPException) as exc_info:
        await ReportService.get_or_create_composer(db, data)
    assert exc_info.value.status_code == 404


async def test_get_or_create_composer_by_wikidata_id_existing(db):
    existing = Composer(name="WikiComposer", wikidata_id="Q123", is_verified=True)
    db.add(existing)
    await db.commit()
    await db.refresh(existing)

    data = ComposerInput(wikidata_id="Q123")
    result = await ReportService.get_or_create_composer(db, data)
    assert result.id == existing.id
    assert result.wikidata_id == "Q123"


async def test_get_or_create_composer_by_wikidata_id_new(db):
    with patch(
        "app.services.report_service.wikidata.get_composer_by_id",
        new=AsyncMock(return_value={"name": "Johann Bach"}),
    ):
        data = ComposerInput(wikidata_id="Q999")
        result = await ReportService.get_or_create_composer(db, data)
        assert result.name == "Johann Bach"
        assert result.wikidata_id == "Q999"
        assert result.is_verified is True


async def test_get_or_create_composer_by_name(db):
    data = ComposerInput(name="Brand New Composer")
    result = await ReportService.get_or_create_composer(db, data)
    assert result.name == "Brand New Composer"
    assert result.is_verified is False


async def test_get_or_create_composer_no_data_raises(db):
    data = ComposerInput()
    with pytest.raises(HTTPException) as exc_info:
        await ReportService.get_or_create_composer(db, data)
    assert exc_info.value.status_code == 400


# ---------------------------------------------------------------------------
# get_or_create_work
# ---------------------------------------------------------------------------


async def test_get_or_create_work_by_id_found(db, work, composer):
    data = WorkInput(id=work.id)
    result = await ReportService.get_or_create_work(db, data, composer.id)
    assert result.id == work.id


async def test_get_or_create_work_by_id_not_found(db, composer):
    data = WorkInput(id=99999)
    with pytest.raises(HTTPException) as exc_info:
        await ReportService.get_or_create_work(db, data, composer.id)
    assert exc_info.value.status_code == 404


async def test_get_or_create_work_by_openopus_id_existing(db, composer):
    existing = Work(title="Existing OO Work", openopus_id="oo-42", composer_id=composer.id)
    db.add(existing)
    await db.commit()
    await db.refresh(existing)

    data = WorkInput(openopus_id="oo-42")
    result = await ReportService.get_or_create_work(db, data, composer.id)
    assert result.id == existing.id


async def test_get_or_create_work_by_openopus_id_no_title_raises(db, composer):
    data = WorkInput(openopus_id="oo-new")
    with pytest.raises(HTTPException) as exc_info:
        await ReportService.get_or_create_work(db, data, composer.id)
    assert exc_info.value.status_code == 400


async def test_get_or_create_work_by_openopus_id_with_title(db, composer):
    data = WorkInput(openopus_id="oo-brand-new", title="New OO Work")
    result = await ReportService.get_or_create_work(db, data, composer.id)
    assert result.title == "New OO Work"
    assert result.openopus_id == "oo-brand-new"
    assert result.is_verified is True


async def test_get_or_create_work_by_title_only(db, composer):
    data = WorkInput(title="Unverified Work Title")
    result = await ReportService.get_or_create_work(db, data, composer.id)
    assert result.title == "Unverified Work Title"
    assert result.is_verified is False


async def test_get_or_create_work_no_data_raises(db, composer):
    data = WorkInput()
    with pytest.raises(HTTPException) as exc_info:
        await ReportService.get_or_create_work(db, data, composer.id)
    assert exc_info.value.status_code == 400


# ---------------------------------------------------------------------------
# submit_report
# ---------------------------------------------------------------------------


async def test_submit_report_happy_path(db, user, event, composer, work):
    report_in = ReportCreate(
        event_id=event.id,
        composer=ComposerInput(id=composer.id),
        work=WorkInput(id=work.id),
        scope=ScopeEnum.WHOLE_WORK,
    )

    with patch.object(app_config.settings, "TURNSTILE_SECRET_KEY", None):
        report = await ReportService.submit_report(db, user, report_in)

    assert report.event_id == event.id
    assert report.work_id == work.id

    # Vote must exist
    result = await db.execute(select(Vote).filter(Vote.report_id == report.id))
    vote = result.scalar_one_or_none()
    assert vote is not None
    assert vote.user_id == user.id


async def test_submit_report_event_not_found(db, user, composer, work):
    report_in = ReportCreate(
        event_id=99999,
        composer=ComposerInput(id=composer.id),
        work=WorkInput(id=work.id),
        scope=ScopeEnum.WHOLE_WORK,
    )

    with patch.object(app_config.settings, "TURNSTILE_SECRET_KEY", None):
        with pytest.raises(HTTPException) as exc_info:
            await ReportService.submit_report(db, user, report_in)
    assert exc_info.value.status_code == 404


async def test_submit_report_blocks_double_participation(db, user, event, composer, work):
    report_in = ReportCreate(
        event_id=event.id,
        composer=ComposerInput(id=composer.id),
        work=WorkInput(id=work.id),
        scope=ScopeEnum.WHOLE_WORK,
    )

    with patch.object(app_config.settings, "TURNSTILE_SECRET_KEY", None):
        await ReportService.submit_report(db, user, report_in)

        with pytest.raises(HTTPException) as exc_info:
            await ReportService.submit_report(db, user, report_in)
    assert exc_info.value.status_code == 400


async def test_submit_report_scope_prefix_stored(db, user, event, composer, work):
    report_in = ReportCreate(
        event_id=event.id,
        composer=ComposerInput(id=composer.id),
        work=WorkInput(id=work.id),
        scope=ScopeEnum.MOVEMENT,
        movement_details="Allegro vivace",
    )

    with patch.object(app_config.settings, "TURNSTILE_SECRET_KEY", None):
        report = await ReportService.submit_report(db, user, report_in)

    assert report.movement_details is not None
    assert ScopeEnum.MOVEMENT.value in report.movement_details
    assert "Allegro vivace" in report.movement_details


async def test_submit_report_scope_prefix_no_details(db, user, event, composer, work):
    report_in = ReportCreate(
        event_id=event.id,
        composer=ComposerInput(id=composer.id),
        work=WorkInput(id=work.id),
        scope=ScopeEnum.MOVEMENT,
        movement_details=None,
    )

    with patch.object(app_config.settings, "TURNSTILE_SECRET_KEY", None):
        report = await ReportService.submit_report(db, user, report_in)

    assert report.movement_details is not None
    assert ScopeEnum.MOVEMENT.value in report.movement_details


# ---------------------------------------------------------------------------
# cast_vote
# ---------------------------------------------------------------------------


async def test_cast_vote_creates_vote_record(db, user, event, composer, work):
    # Create a report (submitted by another user so we don't trigger participation block)
    other = User(email="other-voter@test.com")
    db.add(other)
    await db.commit()
    await db.refresh(other)

    report = Report(user_id=other.id, event_id=event.id, work_id=work.id, is_flagged=False)
    db.add(report)
    await db.commit()
    await db.refresh(report)

    await ReportService.cast_vote(db, user.id, report)

    result = await db.execute(select(Vote).filter(Vote.report_id == report.id, Vote.user_id == user.id))
    vote = result.scalar_one_or_none()
    assert vote is not None


# ---------------------------------------------------------------------------
# set_flagged
# ---------------------------------------------------------------------------


async def test_set_flagged_marks_report(db, user, event, composer, work):
    report = Report(user_id=user.id, event_id=event.id, work_id=work.id, is_flagged=False)
    db.add(report)
    await db.commit()
    await db.refresh(report)

    await ReportService.set_flagged(db, report)

    await db.refresh(report)
    assert report.is_flagged is True


# ---------------------------------------------------------------------------
# build_item_dict (pure logic via ReportService after DB setup)
# ---------------------------------------------------------------------------


async def test_build_item_dict_structure(db, user, event, composer, work):
    from sqlalchemy.orm import joinedload, selectinload

    report = Report(user_id=user.id, event_id=event.id, work_id=work.id, is_flagged=False)
    db.add(report)
    await db.commit()
    await db.refresh(report)

    vote = Vote(user_id=user.id, report_id=report.id)
    db.add(vote)
    await db.commit()

    result = await db.execute(
        select(Report)
        .options(
            selectinload(Report.votes),
            joinedload(Report.work).joinedload(Work.composer),
        )
        .filter(Report.id == report.id)
    )
    loaded_report = result.unique().scalar_one()

    item = ReportService.build_item_dict(loaded_report, total_vs=1)
    assert "report_id" in item
    assert "work" in item
    assert "composer" in item
    assert "votes" in item
    assert "percentage" in item
    assert "status" in item
    assert "is_flagged" in item
    assert "score_url" in item
    assert item["votes"] == 1
    assert item["percentage"] == 100
