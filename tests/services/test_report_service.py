"""Unit tests for ReportService."""

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
    with (
        patch(
            "app.services.report_service.wikidata.get_composer_by_id",
            new=AsyncMock(return_value={"name": "Johann Bach", "name_en": "Johann Bach"}),
        ),
        patch(
            "app.services.report_service.openopus.find_composer_id",
            new=AsyncMock(return_value="87"),
        ),
    ):
        data = ComposerInput(wikidata_id="Q999")
        result = await ReportService.get_or_create_composer(db, data)
        assert result.name == "Johann Bach"
        assert result.wikidata_id == "Q999"
        assert result.is_verified is True
        # Linked to OpenOpus so its works can be searched.
        assert result.openopus_id == "87"


async def test_get_or_create_composer_wikidata_reuses_same_person_under_english_name(db):
    # Stored from OpenOpus under the English form; picked from Wikidata under the Spanish one.
    existing = Composer(name="Pyotr Ilyich Tchaikovsky", openopus_id="150", is_verified=True)
    db.add(existing)
    await db.commit()

    with patch(
        "app.services.report_service.wikidata.get_composer_by_id",
        new=AsyncMock(
            return_value={"name": "Piotr Ilich Chaikovski", "name_en": "Pyotr Ilyich Tchaikovsky"}
        ),
    ):
        result = await ReportService.get_or_create_composer(db, ComposerInput(wikidata_id="Q7315"))

    assert result.id == existing.id
    assert result.wikidata_id == "Q7315"
    assert len((await db.execute(select(Composer))).scalars().all()) == 1


async def test_get_or_create_composer_wikidata_down_falls_back_to_name(db):
    import httpx

    with patch(
        "app.services.report_service.wikidata.get_composer_by_id",
        new=AsyncMock(side_effect=httpx.ConnectError("down")),
    ):
        data = ComposerInput(wikidata_id="Q5", name="Typed Name")
        result = await ReportService.get_or_create_composer(db, data)
    assert result.name == "Typed Name"
    assert result.wikidata_id is None
    assert result.is_verified is False


async def test_get_or_create_composer_by_openopus_id_confirmed_by_catalogue(db):
    with patch(
        "app.services.report_service.openopus.search_composers",
        new=AsyncMock(return_value=[{"name": "Isaac Albéniz", "openopus_id": "216"}]),
    ):
        data = ComposerInput(openopus_id="216", name="isaac albeniz")
        result = await ReportService.get_or_create_composer(db, data)
    # The catalogue's spelling is stored, not the client's.
    assert result.name == "Isaac Albéniz"
    assert result.openopus_id == "216"
    assert result.is_verified is True


async def test_get_or_create_composer_unconfirmed_openopus_id_is_ignored(db):
    with patch(
        "app.services.report_service.openopus.search_composers",
        new=AsyncMock(return_value=[{"name": "Someone Else", "openopus_id": "1"}]),
    ):
        data = ComposerInput(openopus_id="216", name="Made Up")
        result = await ReportService.get_or_create_composer(db, data)
    assert result.name == "Made Up"
    assert result.openopus_id is None
    assert result.is_verified is False


async def test_get_or_create_composer_by_name(db):
    data = ComposerInput(name="Brand New Composer")
    result = await ReportService.get_or_create_composer(db, data)
    assert result.name == "Brand New Composer"
    assert result.is_verified is False


@pytest.mark.parametrize("typed", ["isaac albeniz", "ISAAC ALBÉNIZ", "  Isaac  Albéniz "])
async def test_get_or_create_composer_by_name_reuses_existing(db, typed):
    existing = Composer(name="Isaac Albéniz", is_verified=True)
    db.add(existing)
    await db.commit()

    result = await ReportService.get_or_create_composer(db, ComposerInput(name=typed))
    assert result.id == existing.id
    assert len((await db.execute(select(Composer))).scalars().all()) == 1


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
    result = await ReportService.get_or_create_work(db, data, composer)
    assert result.id == work.id


async def test_get_or_create_work_by_id_not_found(db, composer):
    data = WorkInput(id=99999)
    with pytest.raises(HTTPException) as exc_info:
        await ReportService.get_or_create_work(db, data, composer)
    assert exc_info.value.status_code == 404


async def test_get_or_create_work_by_openopus_id_existing(db, composer):
    existing = Work(title="Existing OO Work", openopus_id="oo-42", composer_id=composer.id)
    db.add(existing)
    await db.commit()
    await db.refresh(existing)

    data = WorkInput(openopus_id="oo-42")
    result = await ReportService.get_or_create_work(db, data, composer)
    assert result.id == existing.id


async def test_get_or_create_work_by_openopus_id_no_title_raises(db, composer):
    data = WorkInput(openopus_id="oo-new")
    with pytest.raises(HTTPException) as exc_info:
        await ReportService.get_or_create_work(db, data, composer)
    assert exc_info.value.status_code == 400


async def test_get_or_create_work_by_openopus_id_takes_title_from_catalogue(db):
    composer = Composer(name="OO Composer", openopus_id="145", is_verified=True)
    db.add(composer)
    await db.commit()
    catalogue = [
        {"openopus_id": "16", "title": "Sonata para piano n.º 8", "nickname": "Pathétique"}
    ]

    with patch(
        "app.services.report_service.openopus.get_composer_works",
        new=AsyncMock(return_value=catalogue),
    ):
        data = WorkInput(openopus_id="16", title="whatever the client sent")
        result = await ReportService.get_or_create_work(db, data, composer)

    assert result.title == "Sonata para piano n.º 8"
    assert result.nickname == "Pathétique"
    assert result.openopus_id == "16"
    assert result.is_verified is True


async def test_get_or_create_work_unknown_openopus_id_falls_back_to_title(db, composer):
    # The composer has no OpenOpus id, so the work id cannot be confirmed.
    data = WorkInput(openopus_id="oo-unknown", title="Typed Title")
    result = await ReportService.get_or_create_work(db, data, composer)
    assert result.title == "Typed Title"
    assert result.openopus_id is None
    assert result.is_verified is False


async def test_get_or_create_work_by_title_only(db, composer):
    data = WorkInput(title="Unverified Work Title")
    result = await ReportService.get_or_create_work(db, data, composer)
    assert result.title == "Unverified Work Title"
    assert result.is_verified is False


async def test_get_or_create_work_by_title_reuses_existing_and_keeps_nickname(db, composer):
    first = await ReportService.get_or_create_work(
        db, WorkInput(title="Sonata n.º 3 en do mayor, op. 2"), composer
    )
    second = await ReportService.get_or_create_work(
        db, WorkInput(title="sonata nº 3 en Do Mayor op 2", nickname="La grande"), composer
    )
    assert second.id == first.id
    assert second.nickname == "La grande"
    await db.commit()


async def test_get_or_create_work_same_title_other_composer_is_a_new_work(db, composer):
    other = Composer(name="Another Composer")
    db.add(other)
    await db.commit()
    first = await ReportService.get_or_create_work(db, WorkInput(title="Preludio"), composer)
    second = await ReportService.get_or_create_work(db, WorkInput(title="Preludio"), other)
    assert second.id != first.id


async def test_get_or_create_work_no_data_raises(db, composer):
    data = WorkInput()
    with pytest.raises(HTTPException) as exc_info:
        await ReportService.get_or_create_work(db, data, composer)
    assert exc_info.value.status_code == 400


# ---------------------------------------------------------------------------
# submit_report
# ---------------------------------------------------------------------------


async def test_submit_report_happy_path(db, user, event, composer, work):
    report_in = ReportCreate(
        region_slug="rs-region",
        discipline_slug="rs-discipline",
        year=2025,
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
    assert vote.event_id == event.id


async def test_submit_report_creates_event_on_first_report(db, user, event, composer, work):
    report_in = ReportCreate(
        region_slug="rs-region",
        discipline_slug="rs-discipline",
        year=2024,
        composer=ComposerInput(id=composer.id),
        work=WorkInput(id=work.id),
        scope=ScopeEnum.WHOLE_WORK,
    )

    with patch.object(app_config.settings, "TURNSTILE_SECRET_KEY", None):
        report = await ReportService.submit_report(db, user, report_in)

    created = (
        await db.execute(select(ExamEvent).filter(ExamEvent.id == report.event_id))
    ).scalar_one()
    assert created.year == 2024
    assert created.id != event.id


@pytest.mark.parametrize("year", [1999, 3000])
async def test_submit_report_rejects_out_of_range_year(db, user, event, composer, work, year):
    report_in = ReportCreate(
        region_slug="rs-region",
        discipline_slug="rs-discipline",
        year=year,
        composer=ComposerInput(id=composer.id),
        work=WorkInput(id=work.id),
        scope=ScopeEnum.WHOLE_WORK,
    )

    with patch.object(app_config.settings, "TURNSTILE_SECRET_KEY", None):
        with pytest.raises(HTTPException) as exc_info:
            await ReportService.submit_report(db, user, report_in)
    assert exc_info.value.status_code == 404
    assert (await db.execute(select(ExamEvent).filter(ExamEvent.year == year))).first() is None


async def test_submit_report_unknown_discipline(db, user, event, composer, work):
    report_in = ReportCreate(
        region_slug="rs-region",
        discipline_slug="no-such-discipline",
        year=2025,
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
        region_slug="rs-region",
        discipline_slug="rs-discipline",
        year=2025,
        composer=ComposerInput(id=composer.id),
        work=WorkInput(id=work.id),
        scope=ScopeEnum.WHOLE_WORK,
    )

    with patch.object(app_config.settings, "TURNSTILE_SECRET_KEY", None):
        await ReportService.submit_report(db, user, report_in)

        with pytest.raises(HTTPException) as exc_info:
            await ReportService.submit_report(db, user, report_in)
    assert exc_info.value.status_code == 400


async def test_submit_report_details_stored_as_plain_text(db, user, event, composer, work):
    report_in = ReportCreate(
        region_slug="rs-region",
        discipline_slug="rs-discipline",
        year=2025,
        composer=ComposerInput(id=composer.id),
        work=WorkInput(id=work.id),
        scope=ScopeEnum.MOVEMENT,
        movement_details="Allegro vivace",
    )

    with patch.object(app_config.settings, "TURNSTILE_SECRET_KEY", None):
        report = await ReportService.submit_report(db, user, report_in)

    # Stored as the contributor's text, with no machine prefix.
    assert report.movement_details == "Allegro vivace"


async def test_submit_report_scope_without_details_gets_a_label(db, user, event, composer, work):
    report_in = ReportCreate(
        region_slug="rs-region",
        discipline_slug="rs-discipline",
        year=2025,
        composer=ComposerInput(id=composer.id),
        work=WorkInput(id=work.id),
        scope=ScopeEnum.MOVEMENT,
        movement_details=None,
    )

    with patch.object(app_config.settings, "TURNSTILE_SECRET_KEY", None):
        report = await ReportService.submit_report(db, user, report_in)

    assert report.movement_details == "Un movimiento"


async def test_submit_report_whole_work_has_no_details(db, user, event, composer, work):
    report_in = ReportCreate(
        region_slug="rs-region",
        discipline_slug="rs-discipline",
        year=2025,
        composer=ComposerInput(id=composer.id),
        work=WorkInput(id=work.id),
        scope=ScopeEnum.WHOLE_WORK,
        movement_details="ignored",
    )
    with patch.object(app_config.settings, "TURNSTILE_SECRET_KEY", None):
        report = await ReportService.submit_report(db, user, report_in)
    assert report.movement_details is None


async def test_submit_report_second_voter_does_not_change_details(db, user, event, composer, work):
    other = User(email="second-voter@test.com")
    db.add(other)
    await db.commit()

    def report_in(details):
        return ReportCreate(
            region_slug="rs-region",
            discipline_slug="rs-discipline",
            year=2025,
            composer=ComposerInput(id=composer.id),
            work=WorkInput(id=work.id),
            scope=ScopeEnum.MOVEMENT,
            movement_details=details,
        )

    with patch.object(app_config.settings, "TURNSTILE_SECRET_KEY", None):
        first = await ReportService.submit_report(db, user, report_in("Mov. 1"))
        second = await ReportService.submit_report(db, other, report_in("Mov. 3"))

    assert second.id == first.id
    assert second.movement_details == "Mov. 1"
    votes = (await db.execute(select(Vote).filter(Vote.report_id == first.id))).scalars().all()
    assert len(votes) == 2


async def test_two_users_typing_the_same_unlisted_work_agree(db, user, event):
    """The headline bug of the old wizard: free text always created a new composer and
    work, so two people reporting the same piece produced a dispute instead of consensus."""
    other = User(email="same-work@test.com")
    db.add(other)
    await db.commit()

    def report_in(composer_name, title):
        return ReportCreate(
            region_slug="rs-region",
            discipline_slug="rs-discipline",
            year=2025,
            composer=ComposerInput(name=composer_name),
            work=WorkInput(title=title),
            scope=ScopeEnum.WHOLE_WORK,
        )

    with patch.object(app_config.settings, "TURNSTILE_SECRET_KEY", None):
        first = await ReportService.submit_report(
            db, user, report_in("Joaquín Turina", "Sonata n.º 1, op. 3")
        )
        second = await ReportService.submit_report(
            db, other, report_in("joaquin turina", "sonata nº 1 op. 3")
        )

    assert second.id == first.id
    assert len((await db.execute(select(Composer))).scalars().all()) == 1
    assert len((await db.execute(select(Work))).scalars().all()) == 1


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

    result = await db.execute(
        select(Vote).filter(Vote.report_id == report.id, Vote.user_id == user.id)
    )
    vote = result.scalar_one_or_none()
    assert vote is not None
    assert vote.event_id == event.id


async def test_cast_vote_twice_is_rejected_by_constraint(db, user, event, composer, work):
    # Bypasses the application-level participation check on purpose: this is the race
    # (e.g. a double click) that only the unique (user_id, event_id) index can stop.
    report = Report(user_id=user.id, event_id=event.id, work_id=work.id, is_flagged=False)
    db.add(report)
    await db.commit()
    await db.refresh(report)
    user_id = user.id

    await ReportService.cast_vote(db, user_id, report)
    with pytest.raises(HTTPException) as exc_info:
        await ReportService.cast_vote(db, user_id, report)
    assert exc_info.value.status_code == 400

    votes = (await db.execute(select(Vote).filter(Vote.user_id == user_id))).scalars().all()
    assert len(votes) == 1


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
