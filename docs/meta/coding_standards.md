# Coding Standards

A short reference for conventions already in use across this codebase. This documents what
the code actually does today, not aspirational rules — if you find a mismatch, either the
code or this doc is wrong; fix whichever is easier to align.

For commit/branch conventions, see [version_control.md](version_control.md) — not duplicated here.

## Tooling does the enforcing

Formatting, import order, and lint rules are mechanical and enforced by `ruff` — see
`[tool.ruff]` in `pyproject.toml` for the exact rule set. Don't hand-format code to match a
style described here; run `ruff format .` and `ruff check --fix .` instead. `pre-commit`
runs both on every commit.

## Types

- Use `X | None`, never `Optional[X]` (Python 3.12+, enforced by `mypy`/`ruff` UP rules).
- Every function has a return type annotation, including `-> None`.
- Public service methods return concrete types (`Report`, `RegionRef`) or `dict[str, Any]`
  for template-context payloads — avoid `Any` for anything else.
- `mypy app` must report 0 errors. A `# type: ignore[code]` is acceptable only for a genuine
  third-party stub gap (see `app/main.py`'s slowapi handler for an example) — always scope it
  to the specific error code, never a bare `# type: ignore`.

## Where business logic lives

- **Route handlers** (`app/main.py`, `app/api/endpoints/*.py`) should parse the request, call
  a service, and return a response — no aggregation logic, no business rules. This is fully
  true for `discipline_page`/`exam_page` (delegate to `ExamService`) and the `reports.py`
  endpoints (delegate to `ReportService`). It is *not* yet true for `main.py`'s `root()`,
  `contribute_page`, and `sitemap_xml` — they still run queries directly. That's a known gap,
  not the target shape; don't copy their pattern for new routes, and feel free to extract
  them to a service (or `ExamService`) if you're touching that code anyway.
- **Services** (`app/services/*.py`) hold the logic, structured as a class of `@staticmethod`s
  (see `ReportService`, `ExamService`, `WorkService`) — there's no instance state, so there's
  no reason to instantiate them.
- **Models** (`app/models.py`) are data only: columns and relationships. No properties that
  compute derived values or call out to other logic — that belongs in a service
  (`WorkService.get_score_url`, not a `Work.best_score_url` property).
- Cross-cutting reads used from multiple call sites (e.g. `check_user_event_participation`)
  live in `app/api/deps.py` alongside the auth dependencies, since both are "things every
  endpoint needs," not endpoint-specific logic.

## Constants

Named constants live in `app/core/constants.py`, grouped into small classes by domain
(`Pagination`, `Consensus`, `RateLimit`, `Cache`, ...). A bare number or string literal used
as a threshold, limit, or config value anywhere else is a sign it should move there. A
one-line comment explaining *why* the value is what it is beats a long docstring.

## Docstrings

- Route handlers and service methods get a one-line docstring stating what they do — only
  when the name and signature don't already make it obvious.
- Multi-line docstrings are rare and reserved for genuinely non-obvious behavior (e.g.
  `check_user_event_participation`'s explanation of what "participation" checks). Don't
  write a multi-paragraph docstring restating the function's own code.
- Models, dataclasses, and simple helpers usually have none.

## Tests

- Use the `db`/`client` fixtures from `tests/conftest.py`; build test data with small,
  local `@pytest.fixture` functions (see `tests/services/test_exam_service.py`) rather than
  constructing objects inline across many tests — but a couple of inline `User`/`Region`
  rows in a single test is fine when nothing else in the file needs them.
- Mock external services (Wikidata, OpenOpus, Turnstile, Resend) with
  `unittest.mock.AsyncMock`/`patch` — tests never make real network calls (see
  `tests/services/test_wikidata.py` for the pattern of patching the module's `httpx.AsyncClient`).
- `asyncio_mode = "auto"` (see `pyproject.toml`) — no `@pytest.mark.asyncio` needed on new
  tests, though plenty of existing ones still carry it from before that was set; either is fine.
- Any new process-global state (a cache, a rate limiter, anything held in a module-level
  variable) needs an autouse fixture in `conftest.py` resetting it between tests — see
  `_reset_rate_limiter` and `_reset_reference_data_cache` for why this matters: tests reuse
  the same fake client IP and the same slugs/emails across functions, so global state silently
  leaks across tests without a reset.
- Coverage floor is 70% (`--cov-fail-under=70` in `pyproject.toml`); current actual coverage
  is noticeably higher — treat the floor as a backstop, not a target.

## What not to do

- Don't add a new abstraction (base class, interface, config flag) for a single use case.
- Don't add error handling for inputs that can't reach a given code path — validate at the
  boundary (request schemas, path params) and trust internal callers.
- Don't introduce a new external dependency (cache backend, queue, etc.) without checking
  whether the existing in-process/SQLite-based approach is really insufficient at this
  app's scale first.
