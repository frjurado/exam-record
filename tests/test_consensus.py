
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.db.base import Base
from app.db.session import get_db
from app.models import Region, Discipline, ExamEvent, User, Composer, Work, Report

# Test DB Setup
SQLALCHEMY_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, class_=AsyncSession, expire_on_commit=False)

async def override_get_db():
    async with TestingSessionLocal() as session:
        yield session

app.dependency_overrides[get_db] = override_get_db

@pytest.mark.asyncio
async def test_consensus_logic():
    # 1. Setup DB
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestingSessionLocal() as db:
        # 2. Seed Data
        region = Region(name="Andalucia", slug="andalucia")
        discipline = Discipline(name="Piano", slug="piano")
        db.add_all([region, discipline])
        await db.commit()
        
        event = ExamEvent(year=2026, region_id=region.id, discipline_id=discipline.id)
        db.add(event)
        await db.commit()
        await db.refresh(event)

        user1 = User(email="u1@test.com")
        user2 = User(email="u2@test.com")
        user3 = User(email="u3@test.com")
        db.add_all([user1, user2, user3])
        await db.commit()

        composer = Composer(name="Bach", wikidata_id="Q1")
        db.add(composer)
        await db.commit()

        # Work A: Verified (2 votes)
        work_a = Work(title="Prelude A", composer_id=composer.id)
        # Work B: Neutral (1 vote)
        work_b = Work(title="Prelude B", composer_id=composer.id)
        # Work C: Disputed (part of a split vote event)
        # To test disputed, we need a separate event or ensure the total votes cause < 75%
        # Let's use the SAME event for all works to test the aggregate logic.
        # If we have Work A (2 votes) and Work B (1 vote). Total = 3.
        # Work A: 2/3 = 66% -> Disputed (< 75%)
        # Work B: 1/3 = 33% -> Neutral? No, logic says "Votes >= 2" is condition for Verified/Disputed.
        # If votes = 1, it's Neutral. Confirmed by plan snippet.
        
        db.add_all([work_a, work_b])
        await db.commit()
        await db.refresh(work_a)
        await db.refresh(work_b)

        # Submit Reports
        # 2 Votes for Work A
        r1 = Report(user_id=user1.id, event_id=event.id, work_id=work_a.id)
        r2 = Report(user_id=user2.id, event_id=event.id, work_id=work_a.id)
        # 1 Vote for Work B
        r3 = Report(user_id=user3.id, event_id=event.id, work_id=work_b.id)
        
        db.add_all([r1, r2, r3])
        await db.commit()

    # 3. Request
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/exams/andalucia/piano/2026")

    assert response.status_code == 200
    html = response.text
    
    # 4. Assertions
    # Work A: 2/3 votes = 66%. Should be DISPUTED (Orange).
    assert "Prelude A" in html
    # Event Level: Disputed (because no verified winner, total votes >= 2)
    assert "Conflicting reports" in html
    assert "Disputed" in html
    assert "66%" in html
    
    # Work B: 1/3 votes. Should be listed but not Verified.
    assert "Prelude B" in html

    # Case 2: Clean Verified
    # Let's add a NEW event for verified test
    async with TestingSessionLocal() as db:
        event2 = ExamEvent(year=2027, region_id=region.id, discipline_id=discipline.id)
        db.add(event2)
        await db.commit()
        await db.refresh(event2)
        
        # 2 Votes for Work A only
        r4 = Report(user_id=user1.id, event_id=event2.id, work_id=work_a.id)
        r5 = Report(user_id=user2.id, event_id=event2.id, work_id=work_a.id)
        db.add_all([r4, r5])
        await db.commit()

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/exams/andalucia/piano/2027")
        
    html2 = response.text
    assert "Prelude A" in html2
    # Event Level: Resolved/Verified
    assert "Verified by students" in html2
    
    # Case 3: Neutral (Single Source)
    async with TestingSessionLocal() as db:
        event3 = ExamEvent(year=2028, region_id=region.id, discipline_id=discipline.id)
        db.add(event3)
        await db.commit()
        
        # 1 Vote for Work B
        r6 = Report(user_id=user3.id, event_id=event3.id, work_id=work_b.id)
        db.add(r6)
        await db.commit()

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/exams/andalucia/piano/2028")
        
    html3 = response.text
    assert "Prelude B" in html3
    # Event Level: Neutral
    assert "Single source for this exam" in html3
