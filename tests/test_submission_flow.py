import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models import Discipline, ExamEvent, Region, Report


@pytest.mark.asyncio
async def test_submission_flow_unauthenticated(client: AsyncClient, db):
    # 1. Setup Data
    region = Region(name="Test Region", slug="test-region")
    discipline = Discipline(name="Test Discipline", slug="test-discipline")
    db.add(region)
    db.add(discipline)
    await db.commit()

    event = ExamEvent(region_id=region.id, discipline_id=discipline.id, year=2026)
    db.add(event)
    await db.commit()
    await db.refresh(event)

    # 2. Attempt Submission (Unauthenticated) -> Should Fail / Redirect to Auth (or return 401 if API)
    # The wizard uses /api/reports/ which returns 401 if not authenticated (or rather 403/401 depends on deps)
    # Actually deps.get_current_user raises HTTPException(status_code=403, detail="Not authenticated") usually or returns None if optional.
    # In reports.py: current_user: User = Depends(deps.get_current_user) -> REQUIRED.

    payload = {
        "region_slug": "test-region",
        "discipline_slug": "test-discipline",
        "year": 2026,
        "composer": {"name": "Test Composer"},
        "work": {"title": "Test Work"},
        "scope": "Whole Work",
        "turnstile_token": "dummy_token",
    }

    response = await client.post("/api/reports/", json=payload)
    assert response.status_code in [401, 403]


@pytest.mark.asyncio
async def test_submission_flow_full(client: AsyncClient, db):
    # 1. Setup Data
    region = Region(name="Test Region 2", slug="test-region-2")
    discipline = Discipline(name="Test Discipline 2", slug="test-discipline-2")
    db.add(region)
    db.add(discipline)
    await db.commit()

    event = ExamEvent(region_id=region.id, discipline_id=discipline.id, year=2026)
    db.add(event)
    await db.commit()
    await db.refresh(event)

    # 2. Request the magic link and read it from what would have been emailed
    email = "test@example.com"

    from unittest.mock import AsyncMock, patch

    from app.models import User

    with patch("app.services.email.email_service.send_magic_link", new_callable=AsyncMock) as send:
        response = await client.post(
            "/api/auth/magic-link", json={"email": email, "next_url": "http://test/wizard?x=1"}
        )
        assert response.status_code == 200
    magic_link = send.call_args.args[1]

    # Asking for a link does not create an account; opening it does.
    assert (await db.execute(select(User))).scalars().all() == []

    # 3. Open the link: it sets the session cookie and returns to the page
    response = await client.get(magic_link, follow_redirects=False)
    assert response.status_code == 307  # Redirect
    assert response.headers["location"] == "/wizard?x=1"
    assert "access_token" in response.cookies
    assert (await db.execute(select(User))).scalar_one().email == email

    # 4. Submit Report (Authenticated)
    # We need to manually set the cookie in the client for subsequent requests if follow_redirects=False lost it,
    # but AsyncClient should keep it if we reuse it?
    # Let's set it explicitly to be sure or use the cookie jar.
    client.cookies = response.cookies

    payload = {
        "region_slug": "test-region-2",
        "discipline_slug": "test-discipline-2",
        "year": 2026,
        "composer": {"name": "Test Composer"},
        "work": {"title": "Test Work"},
        "scope": "Whole Work",
        "turnstile_token": "mock-token",  # We need to mock Turnstile validation
    }

    # Mock Turnstile
    from unittest.mock import AsyncMock, patch

    # We also need to set TURNSTILE_SECRET_KEY in settings if it's not set, to trigger the check
    from app.core.config import settings

    original_secret = settings.TURNSTILE_SECRET_KEY
    settings.TURNSTILE_SECRET_KEY = "mock_secret"

    try:
        # Patch httpx.AsyncClient to return a mock that handles the post request
        with patch("httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            MockClient.return_value = mock_instance
            mock_instance.__aenter__.return_value = mock_instance

            # Setup response mock
            from unittest.mock import MagicMock

            mock_response = MagicMock()
            mock_response.json.return_value = {"success": True}
            mock_response.status_code = 200

            mock_instance.post.return_value = mock_response

            response = await client.post("/api/reports/", json=payload, cookies=response.cookies)

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "created"

            # Verify DB
            # We must use eager loading for async relationships to avoid MissingGreenlet
            from sqlalchemy.orm import selectinload

            stmt = select(Report).options(selectinload(Report.work)).filter(Report.id == data["id"])
            result = await db.execute(stmt)
            report = result.scalar_one_or_none()
            assert report is not None
            assert report.work.title == "Test Work"
            assert report.event_id == event.id

    finally:
        settings.TURNSTILE_SECRET_KEY = original_secret
