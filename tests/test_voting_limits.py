import pytest
from app.models import User, ExamEvent, Region, Discipline, Report, Work, Vote, Composer
from sqlalchemy.future import select
from app.main import app # For dependency overrides

@pytest.fixture
async def setup_data(db):
    # Ensure raw data exists
    # Create Region/Discipline/Event
    region = Region(name="TestRegion", slug="test-region")
    discipline = Discipline(name="TestDiscipline", slug="test-discipline")
    db.add(region)
    db.add(discipline)
    await db.flush()
    
    event = ExamEvent(year=2030, region_id=region.id, discipline_id=discipline.id)
    db.add(event)
    await db.commit()
    return event

@pytest.fixture
async def test_user(db):
    user = User(email="tester@example.com", role="Visitor")
    db.add(user)
    await db.commit()
    return user

@pytest.mark.asyncio
async def test_strict_voting_limits(client, db, setup_data, test_user):
    event = setup_data
    user = test_user
    
    # 1. Create a Work to vote on
    # We need a work and composer
    from app.models import Composer
    composer = Composer(name="Test Composer", is_verified=True)
    db.add(composer)
    await db.flush()
    
    work1 = Work(title="Test Work 1", composer_id=composer.id, is_verified=True)
    work2 = Work(title="Test Work 2", composer_id=composer.id, is_verified=True)
    db.add_all([work1, work2])
    await db.commit()
    
    # Create a Report for Work 1 by another user so we can vote on it
    other_user = User(email="other@example.com")
    db.add(other_user)
    await db.commit()
    
    report1 = Report(user_id=other_user.id, event_id=event.id, work_id=work1.id)
    db.add(report1)
    await db.commit()
    
    # Authenticate as test_user
    # Authenticate as test_user
    from app.api.deps import get_current_user, get_current_user_optional
    
    from types import SimpleNamespace
    
    # Capture IDs and data while objects are fresh
    user_id = user.id
    user_email = user.email
    user_role = user.role
    
    event_id = event.id
    composer_id = composer.id
    composer_name = composer.name
    work2_id = work2.id
    work2_title = work2.title

    # Use a non-ORM object to avoid SQLAlchemy session expiry issues during test 
    # when the endpoint calls db.expire_all()
    async def override_get_current_user():
        return SimpleNamespace(id=user_id, email=user_email, role=user_role)

    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_current_user_optional] = override_get_current_user
    
    try:
        # A. Vote on Report 1 -> Should Succeed
        response = await client.post(f"/api/reports/{report1.id}/vote")
        print(f"Response Status: {response.status_code}")
        print(f"Response Text: {response.text}")
        assert response.status_code == 200
        
        # Verify vote exists
        votes_result = await db.execute(select(Vote).filter(Vote.user_id == user_id))
        votes = votes_result.scalars().all()
        print(f"Votes found: {len(votes)}")
        for v in votes:
            print(f"Vote: {v.id}, User: {v.user_id}, Report: {v.report_id}")
            
        assert len(votes) == 1
        
        # Expunge user to force clean reload and avoid expiry issues
        db.expunge(user)

        # B. Try to Vote on Report 1 AGAIN -> Should Fail
        response = await client.post(f"/api/reports/{report1.id}/vote")
        assert response.status_code == 400
        assert "Ya has votado" in response.text or "participado" in response.text
        
        # C. Try to Contribute (Create new Report) for Work 2 -> Should Fail
        # Prepare payload
        payload = {
            "event_id": event_id,
            "composer": {"id": composer_id, "name": composer_name},
            "work": {"id": work2_id, "title": work2_title},
            "scope": "Whole Work",
            "turnstile_token": "dummy" # Mocked if needed
        }
        
        # Override turnstile check?
        from app.core.config import settings
        original_secret = settings.TURNSTILE_SECRET_KEY
        settings.TURNSTILE_SECRET_KEY = None # Disable for test
        
        try:
            response = await client.post("/api/reports/", json=payload)
            assert response.status_code == 400
            err_msg = response.json()["detail"]
            assert "Ya has participado" in err_msg or "Ya has votado" in err_msg
        finally:
            settings.TURNSTILE_SECRET_KEY = original_secret
            
    finally:
        app.dependency_overrides.clear()
