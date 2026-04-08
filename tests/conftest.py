import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.base import Base  # Ensure this import is correct based on checking file
from app.db.session import get_db
from app.main import app as fastapi_app

# Use in-memory SQLite for tests
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestingSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


@pytest.fixture(scope="session")
async def prepare_database():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def db_session(prepare_database):
    async with TestingSessionLocal() as session:
        yield session
        # Rollback is automatic if not committed?
        # But we commit in endpoints.
        # For isolation, we might want to drop/create tables or use nested transactions (unsupported in aiosqlite easily?)
        # For now, let's keep it simple. State persists across tests in session.
        # We might need to cleanup data manually or scope to function.
        # Changing scope of prepare_database to function is safer but slower.
        # Let's try function scope for safety.


@pytest.fixture(scope="function")
async def db(prepare_database):  # Renamed to db for clarity
    async with TestingSessionLocal() as session:
        yield session
        # Clean up tables (votes first — references reports and users)
        await session.execute(text("DELETE FROM votes"))
        await session.execute(text("DELETE FROM reports"))
        await session.execute(text("DELETE FROM works"))
        await session.execute(text("DELETE FROM composers"))
        await session.execute(text("DELETE FROM exam_events"))
        await session.execute(text("DELETE FROM regions"))
        await session.execute(text("DELETE FROM disciplines"))
        await session.execute(text("DELETE FROM users"))
        await session.commit()


@pytest.fixture
async def client(db):
    async def override_get_db():
        yield db

    fastapi_app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=fastapi_app), base_url="http://test") as ac:
        yield ac
    fastapi_app.dependency_overrides.clear()
