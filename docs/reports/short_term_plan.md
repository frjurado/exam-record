# Short-Term Improvement Plan — Exam Record

**Phase Goal:** Move from C+ to B+ quality by tackling code consistency, architecture, testing, tooling, and documentation.

**Estimated Duration:** 4–6 weeks

**Status: ✅ COMPLETED (verified 2026-07-04)**

All of Steps 0–8 are implemented and green in the current codebase:
`ruff check .` passes, `mypy app` reports 0 errors, and `pytest` passes 68 tests at 84.5% coverage (threshold 70%). Service layer (`ReportService`, `ExamService`, `WorkService`), constants module, dedup (`build_item_dict`, auth helper, `check_user_event_participation`), pre-commit config, CI workflow, and OpenAPI docs are all present and match the plan's prompts. This also covers the "Immediate" and "Short Term" items from `2026_02_14_code_quality_analysis.md` § 11 (dependency pinning, bare-except fix, conditional SQL echo, and everything else in those two buckets).

Next phase: see [2026_07_04_medium_term_plan.md](2026_07_04_medium_term_plan.md) for the "Medium Term" batch (§ 11) — SQLAlchemy 2.0 style migration, rate limiting, caching, coding standards doc, monitoring.

---

## How to Read This Plan

Each **Step** is designed as one Claude Code session (or a small cluster of closely related sessions). Steps are ordered by dependency — later steps assume earlier ones are done. Within each step you'll find:

- **What & why** — scope and rationale.
- **Prompt** — a ready-to-paste Claude Code prompt.
- **Mode** — whether to start in *plan mode* (`--plan`) or go straight to execution.
- **Review notes** — what to check before moving on.

### Claude Code Tips Used in This Plan

| Feature | When it appears | What it does |
|---|---|---|
| `--plan` flag | Steps that touch many files | Claude Code shows you a plan and waits for approval before writing code. Useful when the blast radius is large. |
| `@file` mentions | Most prompts | Tells Claude Code to read specific files for context before acting. |
| `/init` command | Step 0 | Generates a `CLAUDE.md` project summary that gives Claude Code persistent context about your repo. |

---

## Step 0 — Bootstrap Project Context

Before any refactoring, give Claude Code a map of your project.

**Prompt:**

```
/init
```

Review the generated `CLAUDE.md`. Edit it to mention the tech stack (FastAPI, SQLAlchemy async, SQLite, Jinja2, HTMX), the test command (`pytest`), and any env vars needed. This file will be read automatically in every future session, saving you from repeating context.

**Mode:** Interactive (this is a one-off setup command).

---

## Step 1 — Finish Mypy Fixes + Add Ruff Formatter & Linter

Consistent tooling first — everything that follows will be auto-formatted on save.

### 1a. Add Ruff, configure it, format the whole codebase

**Prompt:**

```
Add ruff as a dev dependency. Create a pyproject.toml (or extend the existing one) with the following ruff config:
- line-length = 100
- target-version = "py312"
- lint rules: E, W, F, I, B, C4, UP
- ignore E501
- Use double quotes as the string convention
- Configure isort to put "app" as a first-party package

Then run `ruff format .` and `ruff check --fix .` across the whole project. Show me the summary of what changed.

Refer to @code_quality_analysis.md sections 2.4 (Import Organization) and 3.2 (String Quotation) for context on the problems being fixed.
```

**Mode:** `--plan` — the formatter will touch every file; review the plan first.

**Review:** Run `ruff check .` yourself and confirm zero errors. Skim a few files to confirm imports are reordered and quotes are consistent.

### 1b. Fix remaining mypy errors

**Prompt:**

```
Run `mypy app` and fix all remaining errors. Key issues to watch for:
- Mixed Optional[X] vs X | None syntax — standardize on X | None (Python 3.12)
- Missing return type annotations
- Any untyped function arguments in the public API

Don't change runtime behavior — only type annotations and narrow fixes like adding `assert` or `cast` where needed. See @code_quality_analysis.md section 3.1 for the specific inconsistencies.
```

**Mode:** `--plan` — mypy fixes can cascade; approve the plan.

**Review:** `mypy app` should return 0 errors (or only intentional `type: ignore` comments with explanations).

---

## Step 2 — Extract Constants & Fix Magic Numbers

A small, self-contained cleanup that makes the next refactoring steps easier to read.

**Prompt:**

```
Create a file `app/core/constants.py`. Extract all magic numbers and string literals used as configuration into named constants, organized by domain. Key locations from @code_quality_analysis.md section 2.3:

- app/main.py lines 63-64: batch_size = 10, min_year_limit = 2000
- app/services/consensus.py lines 14-16: votes threshold (2), consensus rate (0.75)

Also look for any other hardcoded thresholds, limits, or config values I may have missed. Replace all usages across the codebase to reference the new constants.
```

**Mode:** Direct execution — small scope, low risk.

**Review:** Grep for the old literal values to confirm none remain outside of `constants.py`.

---

## Step 3 — Eliminate Code Duplication

Remove the duplicates identified in the analysis before extracting services (Step 4 will move logic; this step deduplicates it first).

**Prompt:**

```
Fix the code duplication issues listed in @code_quality_analysis.md section 2.2:

1. **Duplicate `build_item_dict`** in app/api/endpoints/reports.py (appears at ~line 206 and ~line 323). Keep one, delete the other.

2. **Duplicate auth logic** in app/api/deps.py: `get_current_user` and `get_current_user_optional` share ~80% of their code. Refactor into a shared private helper like `_authenticate(request, db, required=True)` that both functions call.

3. **Duplicate participation checks** appearing in create_report, vote_report, and exam_page. Extract a single reusable async function — something like `check_user_event_participation(db, user_id, event_id) -> tuple[bool, int | None]` — and call it from all three locations.

Make sure existing tests still pass after each change.
```

**Mode:** `--plan` — three distinct refactors; review the approach before execution.

**Review:** Run `pytest`. Grep for the old duplicated function signatures to confirm they're gone.

---

## Step 4 — Extract Business Logic to Service Layer

The biggest refactoring step. This restructures the architecture without changing behavior.

### 4a. Create the service layer (reports)

**Prompt:**

```
Refactor app/api/endpoints/reports.py following the recommendations in @code_quality_analysis.md sections 2.1 and 4.1–4.2.

The `create_report` function is ~156 lines with mixed concerns. Extract a `ReportService` class in `app/services/report_service.py` with methods like:
- verify_turnstile(token) -> bool
- get_or_create_composer(db, data) -> Composer
- get_or_create_work(db, data, composer_id) -> Work
- create_report_with_vote(db, ...) -> Report

Similarly, the duplicated logic in `vote_report` and `flag_report` should use shared service methods.

The route handlers in reports.py should become thin: parse request, call service, return response. Keep all existing behavior and HTTP status codes identical. Run pytest after.
```

**Mode:** `--plan` — this is the highest-impact refactor. Read the plan carefully.

### 4b. Create the service layer (exam pages)

**Prompt:**

```
Refactor the exam-related route handlers in app/main.py following @code_quality_analysis.md sections 4.1 and 4.2.

`discipline_page` (~125 lines) and `exam_page` (~123 lines) have database queries, aggregation, and status calculations mixed into the route handler.

Create `app/services/exam_service.py` with an `ExamService` class. Move the query-building, consensus aggregation, and status logic there. The route handlers should become ~15-20 lines: get params, call service, render template.

Don't change template variable names or HTTP behavior. Run pytest after.
```

**Mode:** `--plan`.

### 4c. Fix mixed concerns in models

**Prompt:**

```
In app/models.py, the `Work.best_score_url` property contains business logic and an inline import (urllib.parse). Following @code_quality_analysis.md section 4.3:

1. Move the URL-building logic to a static method in the new WorkService (or a utility function in app/services/work_service.py).
2. Remove the property from the model.
3. Update all call sites (templates, other code) to use the service method instead.
4. Move the `import urllib.parse` to the top of the new file.

Run pytest after.
```

**Mode:** Direct execution — small, contained change.

**Review for all of Step 4:** Run `pytest`. Verify route behavior manually by starting the server and checking a few pages. Confirm that `app/api/endpoints/reports.py` and `app/main.py` are now significantly shorter.

---

## Step 5 — Fix Failing Tests & Increase Coverage

Now that the architecture is cleaner, fix the test suite and expand it.

### 5a. Fix currently failing tests

**Prompt:**

```
Run `pytest -v` and fix all failing tests. These failures likely stem from the refactoring in previous steps (changed imports, moved functions). Don't change test intent — only update imports, fixtures, and call signatures to match the new code structure.
```

**Mode:** Direct execution.

### 5b. Add unit tests for new services

**Prompt:**

```
Add unit tests for the service layer we just created. Target files:
- app/services/report_service.py
- app/services/exam_service.py
- app/services/work_service.py (if created)
- app/core/security.py (verify_token — test expired, invalid signature, malformed, and valid tokens separately)

Use pytest fixtures (not hardcoded test data) as recommended in @code_quality_analysis.md section 6.2. Mock external services (Wikidata, OpenOpus, Turnstile) with unittest.mock.AsyncMock so tests don't depend on network.

Also add the participation-check utility to the test suite.

Target: at least 70% coverage on the `app/` directory. Run `pytest --cov=app --cov-report=term-missing` and show results.
```

**Mode:** `--plan` — there's a lot of test code to write; review which tests Claude Code proposes.

### 5c. Improve pytest configuration

**Prompt:**

```
Update the pytest config (pytest.ini or pyproject.toml [tool.pytest.ini_options]) following @code_quality_analysis.md section 6.3:

- Keep asyncio_mode = auto
- Set testpaths = tests
- Add coverage options: --cov=app, --cov-report=html, --cov-report=term-missing, --cov-fail-under=70
- Change filterwarnings to error on DeprecationWarning but ignore from third-party packages (httpx, sqlalchemy if needed)

Run pytest once to confirm it still passes with the new config.
```

**Mode:** Direct execution.

**Review:** `pytest` should pass, show a coverage report, and fail if coverage drops below 70%.

---

## Step 6 — Add API Documentation (OpenAPI)

**Prompt:**

```
Improve the API documentation using FastAPI's built-in OpenAPI support. Following @code_quality_analysis.md section 7:

1. In app/main.py, configure the FastAPI app with title, description, version, docs_url="/api/docs", and redoc_url="/api/redoc".

2. For each endpoint in app/api/endpoints/, add:
   - A summary and description parameter to the decorator
   - A responses dict covering the main status codes
   - Docstrings on the handler functions

3. Make sure all Pydantic schemas used as request/response models have Field descriptions and example values (using model_config or Field(example=...)).

Don't change any runtime behavior — only metadata and documentation.
```

**Mode:** Direct execution — this is additive, not destructive.

**Review:** Start the server and visit `/api/docs`. Confirm all endpoints appear with descriptions, request/response examples, and status codes.

---

## Step 7 — Add Pre-commit Hooks

**Prompt:**

```
Create a .pre-commit-config.yaml with the following hooks:

1. ruff (lint + format) — use the same config already in pyproject.toml
2. trailing-whitespace, end-of-file-fixer, check-yaml, check-added-large-files from pre-commit-hooks

Don't add mypy as a pre-commit hook yet (it's slow and we'll run it in CI instead).

Also add instructions to CLAUDE.md and/or the README for running `pre-commit install` after cloning.
```

**Mode:** Direct execution.

**Review:** Run `pre-commit run --all-files` and confirm everything passes.

---

## Step 8 — Set Up CI/CD with GitHub Actions

**Prompt:**

```
Create .github/workflows/ci.yml following @code_quality_analysis.md section 8.2. The workflow should:

1. Trigger on push and pull_request
2. Use Python 3.12
3. Install dependencies from requirements.txt
4. Run `ruff check app tests`
5. Run `ruff format --check app tests`
6. Run `mypy app`
7. Run `pytest --cov=app --cov-report=xml`

Keep it simple — single job, no matrix, no caching for now. We can optimize later.
```

**Mode:** Direct execution.

**Review:** Push to a branch and confirm the workflow runs green.

---

## Summary & Sequencing

```
Week 1          Week 2            Week 3          Week 4
──────          ──────            ──────          ──────
Step 0 (init)   Step 4a (svc:     Step 5b (new    Step 7 (pre-commit)
Step 1 (ruff      reports)          tests)        Step 8 (CI/CD)
  + mypy)       Step 4b (svc:     Step 5c (pytest
Step 2            exam pages)       config)
  (constants)   Step 4c (models)  Step 6 (API
Step 3          Step 5a (fix        docs)
  (dedup)         broken tests)
```

Each step is a single Claude Code session. After each, run `pytest` and `ruff check .` before moving on. If a step produces unexpected breakage, fix it before proceeding — later steps assume a green test suite.

### When to Use Plan Mode — Quick Reference

| Step | Plan mode? | Why |
|---|---|---|
| 0 (init) | No | One command |
| 1a (ruff) | Yes | Touches every file |
| 1b (mypy) | Yes | Type fixes can cascade |
| 2 (constants) | No | Small scope |
| 3 (dedup) | Yes | Multiple refactors |
| 4a–4b (services) | Yes | Major architecture change |
| 4c (model fix) | No | One small move |
| 5a (fix tests) | No | Reactive fixes |
| 5b (new tests) | Yes | Lots of new code to review |
| 5c (pytest config) | No | Config-only |
| 6 (API docs) | No | Additive, no behavior change |
| 7 (pre-commit) | No | Config-only |
| 8 (CI) | No | Single new file |
