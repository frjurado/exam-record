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

# Install dependencies (includes pre-commit)
pip install -r requirements.txt

# Install pre-commit hooks (once per clone)
pre-commit install

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
3. **Admin page**: `/admin`, routes in `app/api/endpoints/admin.py`, logic in `app/services/admin_service.py`. Plain form posts that redirect back with a message. Requires `User.role == "Admin"` (404 otherwise); grant it with `python scripts/set_role.py <email> Admin`.
4. **Auth**: Stateless JWT stored in an HTTP-only cookie. Magic link flow — user requests email → clicks link → token verified → cookie set. Dependency injection in `app/api/deps.py` provides `get_current_user` (required) and `get_current_user_optional`.

### Data Model

The core data flow is: a user submits a **Report** linking a **Work** (by a **Composer**) to an **ExamEvent** (year × region × discipline). Other users cast **Votes** on reports. The **ConsensusService** (`app/services/consensus.py`) aggregates votes at query time — nothing is stored.

Key constraints:
- `(event_id, work_id)` is unique on `Report`, so each work can appear at most once per exam event.
- `(user_id, event_id)` is unique on `Vote` (`event_id` is denormalised from the report), so a user participates at most once per exam event. The migration skips this index if existing data violates it — check the boot log for `SKIPPED unique index`.

`Composer.search_text` and `Work.search_text` hold `app.services.text.normalize()` of the name/title (no accents, case or punctuation). They are set by listeners at the bottom of `app/models.py`; all name matching and searching goes through them. Free-text composers and works are matched against existing rows before a new one is created (`ReportService.get_or_create_composer` / `get_or_create_work`).

A report's `movement_details` is plain Spanish text shown to users. It belongs to the report: later voters do not change it.

An `ExamEvent` is created by `ReportService.get_or_create_event` when the first report for that region/discipline/year is submitted. Page views never create events, and years outside `Calendar.MIN_YEAR`..latest exam year are rejected.

### External Integrations

- **Wikidata API** (`app/services/wikidata.py`): Composer search restricted to occupation = composer; Spanish labels preferred
- **OpenOpus API** (`app/services/openopus.py`): Composer search, and each composer's catalogue (cached in memory for a day); titles are rendered in Spanish by `app/services/titles.py`
- `app/services/catalog_service.py` merges local and external results for the contribute form
- **Resend** (`app/services/email.py`): Magic link emails — falls back to console logging if `RESEND_API_KEY` is unset (dev mode)
- **Cloudflare Turnstile**: CAPTCHA on report submission
- **Sentry** (`app/core/monitoring.py`): Production error tracking — no-ops unless `ENVIRONMENT=production` and `SENTRY_DSN` is set

### Database

SQLite via SQLAlchemy 2.0 async (`aiosqlite`). Sessions are created per-request via `app/db/session.py:get_db()`. Migrations live in `alembic/versions/`. Production DB is mounted as a Fly.io volume at `/data/exam_record.db`.

### Environment Variables

Required:
- `DATABASE_URL` — e.g. `sqlite+aiosqlite:///./exam_record.db`
- `SECRET_KEY` — JWT signing key

Optional (have dev defaults):
- `RESEND_API_KEY` — omit to log emails to console
- `TURNSTILE_SITE_KEY` / `TURNSTILE_SECRET_KEY` — omit to skip CAPTCHA
- `FROM_EMAIL` — code default is `onboarding@resend.dev`; production sets `noreply@wikianalisis.org` in `fly.toml`
- `ENVIRONMENT` — `development` or `production`
- `SENTRY_DSN` — omit to disable error tracking; only takes effect when `ENVIRONMENT=production` (see `app/core/monitoring.py`)

### Tests

Tests use an in-memory SQLite DB. Fixtures in `tests/conftest.py` provide:
- `db` — async session, auto-cleaned between tests
- `client` — `AsyncClient` with `get_db` dependency overridden

An autouse fixture blocks real outbound HTTP, so anything that calls OpenOpus, Wikidata or Turnstile must be mocked.

`pytest.ini` sets `asyncio_mode = auto`, so all async test functions work without additional decoration.

## Git Workflow

See `docs/meta/version_control.md` for commit standards. The project uses conventional commits (`feat:`, `fix:`, `docs:`, etc.).
