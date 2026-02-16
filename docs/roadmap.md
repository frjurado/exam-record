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
*   **4.4 Beta Launch:** [Done] Deploy to a VPS/Cloud (Constraint: Andalucía + Piano only).

## Phase 5: Refinement & Localization (v0.2.0)
**Goal:** Transform the raw Beta into a user-friendly, Spanish-language product with reliable systems.
*   **5.1 Localization (Spanish):**
    *   Translate all UI text to Spanish.
    *   Update static data (Regions/Disciplines are already Spanish, ensuring matching UI).
*   **5.2 Critical Infrastructure:**
    *   **Real Email System:** Replace console logging with a real provider (e.g., SMTP/SendGrid/SES) for Magic Links.
    *   **Form Hardening:** Fix usability issues in the Contribution Wizard, improve validation, and ensuring state persistence.
*   **5.3 Rebranding & Polish:**
    *   **Appearance:** New Favicon, potential Name Change ("Exam Record" -> ?).
    *   **SEO:** Verify meta tags and sitemap generation.
*   **5.4 Wizard Improvement:**
    *   **Works from OpenOpus:** Fetch works from OpenOpus for verified composers.

## Phase 6: Structure & Navigation (v0.3.0)
**Goal:** robust navigation and architectural integrity.
*   **6.1 Navigation Overhaul:**
    *   Implement "Year" navigation (past/future exams).
    *   Review and fix all redirect/breadcrumb paths.
*   **6.2 Codebase Health:**
    *   **Testing:** Implement specific unit tests (Pytest) for critical paths (voting, submission).
    *   **Cleanup:** Review directory structure and remove unused artifacts.

## Phase 7: Expansion (v0.4.0+)
**Goal:** Grow the dataset and scope.
*   **7.1 New Disciplines:** Add some more disciplines (e.g., Violin, Clarinet, Guitar).
*   **7.2 PDF link:** Research (& implement, if feasible) a way to link to the PDF of the exam.

## Phase 8: Tweaks & Fixes (v0.5.0+)
**Goal:** Fix issues and improve the project.
*   **8.1 Infrastructure:** 
    *   Set proper domain at wikianalisis.org.
    *   Magic link from any email address?
    *   Two machines on Fly.io? (load is too slow).
    *   Change the DB to PostgreSQL? (necesary if more than one machine).
*   **8.2 UI improvements & more disciplines:** 
    *   Group links under "Andalucía" to avoid text clutter.
    *   Discipline page: event boxes could show status badge/work if validated.
    *   Consider opening more disciplines (see meta/08_tweaks_&_fixes.md).
*   **8.3 Text revision:** 
    *   Revise the whole text of the site.
    *   Add a small "About" note at the bottom of index page.
*   **8.4 Bugs & issues:** 
    *   Revise wizard_buglist.md and fix the most important issues.
