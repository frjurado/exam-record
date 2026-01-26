# Project Roadmap: Exam Record to MVP

This roadmap defines the critical path to launch the "Constrained Beta" (Andalucía + Piano).

## Phase 1: Foundation & Setup (Week 1)
**Goal:** A running server with schema and basic input capability.
*   **1.1 Project Init:** Repo setup, FastAPI skeleton, Environment config.
*   **1.2 Database:** Implement `models.py` (SQLAlchemy), Alembic init, and SQLite DB creation.
*   **1.3 Seeding Script:** Create a Python script (`scripts/seed.py`) to inject the static "Fixed Lists" (Regions, Disciplines).
*   **1.4 Auth (Magic Link):** Implement the `POST /auth/magic-link` flow and Session management (Cookies).

## Phase 2: The Core Data Loop (Week 2)
**Goal:** We can identify Composers and Works reliably.
*   **2.1 Importer Service:**
    *   Build `services/wikidata.py`: Fetch/Cache Composer data.
    *   Build `services/openopus.py`: Fetch/Cache Work data.
*   **2.2 Internal API:** Endpoints to proxy these services to the frontend (`/api/composers/search`, `/api/works/search`).
*   **2.3 Shell Importer:** A CLI command to "Seed" the database with the initial "Teacher's List" (Golden Data) CSVs.

## Phase 3: The User Experience (Week 3)
**Goal:** Verified users can submit data via the UI.
*   **3.1 The "Wizard":** [Done] Build the Data Input Form (Alpine.js) utilizing the Search APIs.
    *   Step 1: Composer (Select/Verify).
    *   Step 2: Work (Select/Alias/Create).
    *   Step 3: Details (Movement/Excerpt).
*   **3.2 Read-Only Views:**
    *   `GET /exams/{region}/{discipline}/{year}`: Render the list of reported works.
    *   Implement "Consensus Badges" (Green/Traffic Light logic) in Jinja templates.

## Phase 4: Validation & MVP Polish (Week 4)
**Goal:** Data integrity and production readiness.
*   **4.1 Voting & Flagging:**
    *   Implement "Me Too" button (Quick Vote).
    *   Implement "Flag/Report" button.
*   **4.2 SEO Basics:** Meta tags, readable URLs.
*   **4.3 Launch Prep:** Root Page, Region/Discipline Navigation, Routing.
*   **4.4 Beta Launch:** Deploy to a VPS/Cloud (Constraint: Andalucía + Piano only).
