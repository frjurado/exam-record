# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Exam Record** is a community-driven database for crowdsourcing music conservatory entrance exam repertoire. Users submit and vote on the works performed in past exams, building consensus around what pieces appear most frequently.

## Commands

### Development

```bash
# Create and activate virtual environment
python -m venv .venv
source .venv/Scripts/activate  # Windows (bash)

# Install dependencies
pip install -r requirements.txt

# Run dev server (reload on change)
uvicorn app.main:app --reload --port 8000

# Apply database migrations
alembic upgrade head

# Create a new migration
alembic revision --autogenerate -m "description"

# Seed initial data (regions, disciplines)
python scripts/seed.py
```

### Testing

```bash
pytest                        # All tests
pytest tests/api/             # API tests only
pytest tests/test_consensus.py  # Single file
pytest -v                     # Verbose output
```

### Deployment

The app deploys automatically to Fly.io (`exam-record-beta`) on push to `main`. Manual deploy:

```bash
fly deploy
```

## Architecture

### Request Flow

1. **HTML pages** (SSR): Routes defined directly in `app/main.py` return Jinja2 templates. The frontend uses HTMX for partial updates and Alpine.js for client-side wizard state.
2. **API endpoints**: Registered under `/api` prefix via `app/api/api.py`, implemented in `app/api/endpoints/`.
3. **Auth**: Stateless JWT stored in an HTTP-only cookie. Magic link flow — user requests email → clicks link → token verified → cookie set. Dependency injection in `app/api/deps.py` provides `get_current_user` (required) and `get_current_user_optional`.

### Data Model

The core data flow is: a user submits a **Report** linking a **Work** (by a **Composer**) to an **ExamEvent** (year × region × discipline). Other users cast **Votes** on reports. The **ConsensusService** (`app/services/consensus.py`) aggregates votes at query time — nothing is stored.

Key constraint: `(event_id, work_id)` is unique on `Report`, so each work can appear at most once per exam event.

### External Integrations

- **Wikidata SPARQL** (`app/services/wikidata.py`): Composer search/lookup
- **OpenOpus API** (`app/services/openopus.py`): Work search by composer
- **Resend** (`app/services/email.py`): Magic link emails — falls back to console logging if `RESEND_API_KEY` is unset (dev mode)
- **Cloudflare Turnstile**: CAPTCHA on report submission

### Database

SQLite via SQLAlchemy 2.0 async (`aiosqlite`). Sessions are created per-request via `app/db/session.py:get_db()`. Migrations live in `alembic/versions/`. Production DB is mounted as a Fly.io volume at `/data/exam_record.db`.

### Environment Variables

Required:
- `DATABASE_URL` — e.g. `sqlite+aiosqlite:///./exam_record.db`
- `SECRET_KEY` — JWT signing key

Optional (have dev defaults):
- `RESEND_API_KEY` — omit to log emails to console
- `TURNSTILE_SITE_KEY` / `TURNSTILE_SECRET_KEY` — omit to skip CAPTCHA
- `FROM_EMAIL` — defaults to `noreply@wikianalisis.org`
- `ENVIRONMENT` — `development` or `production`

### Tests

Tests use an in-memory SQLite DB. Fixtures in `tests/conftest.py` provide:
- `db` — async session, auto-cleaned between tests
- `client` — `AsyncClient` with `get_db` dependency overridden

`pytest.ini` sets `asyncio_mode = auto`, so all async test functions work without additional decoration.

## Git Workflow

See `docs/meta/version_control.md` for commit standards. The project uses conventional commits (`feat:`, `fix:`, `docs:`, etc.).
