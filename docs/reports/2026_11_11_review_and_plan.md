# Project Review & Plan — November 2026

A full read of the app, templates, docs and scripts, done on 2026-11-11, and the plan that
came out of it. Phase 1 (hygiene) was carried out the same day and is recorded at the end.

**Summary.** The backend is in decent shape (tests pass, coverage ~88%, clean lint and types).
The contribution wizard is the weak point: it loses data, creates duplicates and has dead
ends. The design docs describe a much bigger product (roles, incentives, catalogue mirror)
than the one that exists.

**Context that shapes the plan.**
- Traffic is very low. Almost all data so far was collected from teachers by the project
  owner and entered by hand through the wizard.
- That hand-entered data gets **no special "verified" status**. Even among teachers there
  were a few contradictory reports, so the normal consensus rule applies to everyone.
- Exams happen around June, so anything aimed at candidates should be ready by spring 2027.

---

## 1. Findings: robustness

Ordered by importance. Items marked ✅ were fixed in Phase 1.

| # | Finding | Where |
|---|---|---|
| 1 | Free-text composers and works are always inserted as new rows, never matched to an existing one. Two people typing the same unlisted work produce two works, two reports and a "disputed" event. | `ReportService.get_or_create_composer` / `get_or_create_work` |
| 2 | ✅ Opening `/contribute` created an `ExamEvent` for any integer year (9999, -3), for anonymous visitors and crawlers. The sitemap then listed every empty event. | `app/main.py` |
| 3 | ✅ "One participation per user and event" was only a check-then-insert in application code; a double click could vote twice. | `app/models.py`, `ReportService` |
| 4 | Rate limits key on the remote address. Behind Fly's proxy this is probably the proxy's address, not the visitor's — **not verified in production**. Even when correct, 20 votes/hour per IP would block a class voting from school wifi. | `app/core/limiter.py`, `app/core/constants.py` |
| 5 | Auth is loose: the magic-link token is the session JWT itself; sessions last 2 hours; the cookie lacks `secure`; `next` is an open redirect; a `User` row is created before the email is verified; `role` is always "Visitor" and never checked. | `app/api/endpoints/auth.py` |
| 6 | Flagging has no consequence. One click by any logged-in user, permanent, not attributed, not rate-limited, and nobody can review or clear it. | `flag_report` |
| 7 | Failures are silent. HTMX does not swap 4xx responses, so "Ya has participado" and 429s show nothing. A failed magic-link request in the wizard shows nothing either. | `work_card.html`, `wizard.html` |
| 8 | ✅ `robots.txt` pointed to `https://exam-record.com/sitemap.xml`, a domain that is not ours. | `app/main.py` |
| 9 | Cold starts are heavy: with `min_machines_running = 0`, every wake runs migrations, seeding (up to 30 s) and 4 gunicorn workers on 1 CPU. Probably the "load is too slow" note in the roadmap. | `fly.toml`, `start.sh` |
| 10 | No backup of the SQLite volume beyond Fly's own snapshots. The data is the project's only real asset. | — |
| 11 | Search endpoints return raw exception text in 500 responses and proxy to Wikidata/OpenOpus with no rate limit or cache. | `composers.py`, `works.py` |

## 2. Findings: accumulated mess

- ✅ Tracked junk (`error.log`, `coverage.xml`) and one-off scripts with hardcoded
  `f:/Antigravity/...` paths, one of which (`scripts/cleanup_duplicates.py`) dropped the
  `votes` table.
- `wizard.html` is an 800-line standalone page that does not extend `base.html`: English
  title, a breadcrumb that literally reads "Región - Especialidad", no user header, and its
  own copy of the auth modal. It also contains dead code (`isVerifying` is never set; a
  `querySelector` that can never match).
- Consensus logic exists twice: `ConsensusService` and the badge code in
  `ExamService.get_discipline_context`.
- `work_card.html` is two near-identical halves.
- The discipline list lives in two places: `scripts/seed.py` and 17 hand-copied lines in
  `index.html`.
- `WorkInput` has `genre`, `key`, `opus`, `number` fields that nothing sends or reads.
- Unpinned: Alpine (`3.x.x` from a CDN), `gunicorn`, `ruff`, `pre-commit`. Dev and
  production requirements are not split.
- Madrid and Valencia are seeded as regions but not linked from the UI.

## 3. Findings: docs versus code

- ✅ Broken links in `README.md` and `docs/README.md`.
- ✅ `technical_specs.md` had no `Vote` table, said a vote creates a new Report, and used
  the wrong API paths.
- ✅ `roadmap.md` still described "Andalucía + Piano" with almost nothing marked done.
- ✅ `april_fixes_todo.md` said tests were failing.
- ✅ The medium-term plan did not mark steps 1–2 complete.
- ✅ `CLAUDE.md` said Wikidata SPARQL and gave the wrong `FROM_EMAIL` default.
- Still true: the design docs (`docs/design/`) promise things never built — a top-500
  composer cache, a local OpenOpus mirror, an "Ambiguous" data-quality tag, Steward and
  Admin roles, alerts, PDF export. They are kept as the original vision; `docs/README.md`
  now says so.

## 4. Findings: the contribution wizard

**Search and selection**
- A composer picked from Wikidata has no OpenOpus id, so work search returns nothing and
  the user is pushed into free text. `openopus.search_composer_by_name` exists and is
  unused.
- Wikidata search takes 10 generic hits and keeps those whose *English* description
  contains "composer". This explains the missing Palestrina and the "Johann" behaviour in
  `wizard_buglist.md`.
- Local search is accent-sensitive (SQLite `ilike` only folds ASCII): "Albeniz" does not
  find "Albéniz". No typo tolerance.
- For composers with an OpenOpus id, local works are never searched, so works created by
  hand earlier are invisible and get recreated.
- Every keystroke downloads the composer's whole OpenOpus catalogue, uncached.
- Queries are not URL-encoded, and a slow response can overwrite a newer one.

**Prepopulation and defaults**
- Nothing is shown before typing — not the works already reported for this event, not the
  usual composers for the discipline.
- The lazy builder's "live match" cannot work: it builds Spanish strings ("Sonata en Do
  Mayor Op. 57") and substring-matches them against English OpenOpus titles.
- A user who already participated can fill in all three steps and is only rejected at
  submit.

**Data loss and register**
- The nickname typed in the lazy builder is dropped (`WorkInput` has no such field).
- Movement and excerpt details are stored but never displayed. They are also discarded
  when the work was already reported.
- Languages are mixed: OpenOpus titles and Wikidata names in English, hand-made works in
  Spanish, scope stored as "[Movement] Mov. ?". The magic-link email and some error
  messages are in English.

**Submission**
- Without Turnstile keys the form cannot be submitted: the missing key renders as "None"
  and the button stays disabled. The backend skips CAPTCHA in dev; the frontend does not.
- A Turnstile token is single-use and expires, but is never reset after a failed submit,
  so a retry fails with "Token Anti-Spam inválido".
- Wizard state lives in `localStorage`; opening the magic link on another device loses it.

---

## 5. Triage of features pending in the docs

| When | Feature | Why |
|---|---|---|
| Now | Wizard fixes (section 4, most of `wizard_buglist.md`) | Every contribution passes through it |
| Now | Minimal admin tools: merge works/composers, delete a report, clear a flag | Today these need raw SQL over SSH |
| Now | Finish Sentry (needs an account and DSN), wikianalisis.org domain, Spanish email | Small, already half-done |
| Spring 2027 | Light "avísame" email capture, one mailing after the June exams | The only incentive feature that matches the seasonal traffic |
| Later | Global search, opening Madrid/Valencia, link to the exam PDF | Needs denser data first |
| Premature | Dispute resolution UI, Steward role and badges, gated PDF export, user banning, PostgreSQL, a second machine, Redis | No traffic to justify them |
| Dropped | Trusted status for teacher-supplied data | Teachers' reports contradict each other too; consensus applies to all |

## 6. Not planned before, worth doing

- **Statistics view:** most frequent works and composers, per discipline and overall, with
  the years each appeared. Cheap to compute at query time. Only meaningful once duplicate
  works are under control (Phase 2 and 3).
- **Work and composer pages** ("this work fell in Piano 2021, Violín 2019"). Same queries,
  and the pages people would find through search engines.
- **Year × discipline table** per region, as a one-glance view of coverage.
- **Privacy-friendly analytics.** There is currently no way to tell whether the wizard
  loses people or nobody arrives at all.
- **Longer sessions** (about 30 days) with a separate short-lived link token.
- **Volume backups** and a short **privacy note** (emails of EU users are stored).
- **Open CSV export** of verified data.

---

## 7. The plan

### Phase 1 — Hygiene ✅ (done 2026-11-11)
See section 8.

### Phase 2 — Wizard rework
1. Server: match free-text composers and works to existing rows before inserting
   (normalised name / title within the composer). Accept and store the nickname.
2. Composer search chain: local → OpenOpus composers → Wikidata (filtered by occupation,
   Spanish labels) → free text. Store the OpenOpus id when found.
3. Search quality: accent-insensitive local search, URL-encoded queries, ignore stale
   responses, search local works alongside OpenOpus, cache the OpenOpus catalogue per
   composer.
4. Prepopulation: show the works already reported for this event first, then frequent
   composers for the discipline. Check participation before the user fills anything in.
5. Show movement/excerpt details on the event page; store them in a consistent form.
6. Submission: fix the no-Turnstile case and token reset; show errors for failed
   magic-link requests, 4xx votes and 429s.
7. Move the wizard onto `base.html`, in Spanish, sharing the auth modal.

Decided: titles in Spanish where possible, and movement details belong to the report
(see the end of section 8).

### Phase 3 — Admin tools
Merge two works or two composers (moving their reports and votes), delete a report, clear
a flag. A small page gated on `role == "Admin"`, or CLI scripts if that is enough. Then
use it to clean the existing duplicates and any empty events created before Phase 1.

### Phase 4 — Statistics and discovery
Statistics view, work and composer pages, year × discipline table, analytics, sitemap
entries for the new pages.

### Phase 5 — Email capture (ready by spring 2027)
"Avísame" sign-up with explicit consent, one mailing after the June exams, privacy note.

### Alongside, when convenient
Rate-limit keying and limits (finding 4), session length and link token (5), cold-start
weight (9), backups (10), pinning dependencies, Sentry account, domain.

---

## 8. Phase 1 record: what changed

**Removed**
- `error.log`, `coverage.xml` (now git-ignored).
- `scripts/cleanup_duplicates.py`, `scripts/test_openopus.py`, `scripts/verify_services.py`,
  `tests/manual_verify_voting.py`, `tests/verify_auth_flow.py`,
  `tests/verify_openopus_integration.py`.
- The stray "Andalucía Piano 2026" event from `scripts/seed.py`; an unused test fixture.

**Events are no longer created on page view**
- The contribute page only validates region, discipline and year.
- The wizard now sends `region_slug`, `discipline_slug` and `year` instead of `event_id`;
  `ReportService.get_or_create_event` creates the event with the first report.
- Valid years are `Calendar.MIN_YEAR` (2000) up to the latest exam already held
  (`ExamService.latest_exam_year`); anything else is a 404.
- Side effect: a wizard form left half-filled in a browser before this change will start
  empty, because the saved-state key changed.

**One vote per user and event, enforced by the database**
- `votes.event_id` added and backfilled; unique index `uix_vote_user_event` on
  `(user_id, event_id)`. A concurrent duplicate now gets "Ya has participado".
- Migration `a3f1c2d4e5b6`. Because migrations run at boot and a failure keeps the site
  down, it **skips the unique index if existing data already violates it** and logs
  `SKIPPED unique index uix_vote_user_event`. The local dev database has 5 such pairs, so
  the index is skipped there. Production was checked before deploying and had no such
  pairs, so the index is created there.

**robots.txt and sitemap**
- Both use the site's own address (https in production). The sitemap lists the home page
  and only events that have reports.

**Docs**
- Fixed links and stale statuses listed in section 3; `CLAUDE.md` and
  `technical_specs.md` describe the new event and vote rules.

**Verification**
- 85 tests pass (9 new), `ruff` and `mypy` clean.
- The migration was run on two copies of the local database: one with duplicate votes
  (index skipped, column backfilled) and one cleaned (index created; `alembic check`
  reports no drift; downgrade works).

**State of production (read-only check, 2026-11-11, before deploying)**
- 21 reports, 23 votes, 26 composers, 17 works.
- 6 user rows. One account holds all 21 reports and 21 of the votes; two other accounts
  cast one vote each; three never voted (a row is created when a link is requested).
- No duplicate votes, no orphan votes, no events outside the valid year range.
- 114 events, 93 of them empty (created by page views). They are harmless and no longer
  listed in the sitemap; Phase 3 can remove them.

**Decisions taken for Phase 2**
- Work titles and stored details should be in Spanish where possible.
- Movement/excerpt details belong to the report, not to each vote.
