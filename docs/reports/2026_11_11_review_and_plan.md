# Project Review & Plan — November 2026

A full read of the app, templates, docs and scripts, done on 2026-11-11, and the plan that
came out of it. Phase 1 (hygiene) was carried out and deployed the same day (section 8).
Phase 2 (wizard rework) was written, reviewed and released the same day (section 9).
Phase 3 (admin tools) was written and released the same day (section 10).
The code half of the side items (sessions, rate limits, cold start, pinned dependencies)
was written and released on 2026-11-12 (section 11). Phase 4 is in progress (section 13). Phase 5 has not been started.

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

### Phase 2 — Wizard rework (done 2026-11-11, see section 9)
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

### Phase 3 — Admin tools (done 2026-11-11, see section 10; production cleanup pending)
Merge two works or two composers (moving their reports and votes), delete a report, clear
a flag. A small page gated on `role == "Admin"`, or CLI scripts if that is enough. Then
use it to clean the existing duplicates and any empty events created before Phase 1.

### Phase 4 — Statistics and discovery (in progress, see section 13)
0. Groundwork: one definition of an exam's outcome; https canonical addresses; addresses
   in Spanish. ✅
1. Work and composer pages. ✅
2. Statistics page (`/estadisticas`): most frequent composers and works, by discipline.
   ✅
3. Coverage table per region (`/examenes/andalucia`): disciplines × years.
   ✅
4. Sitemap entries and structured data for the new pages. ✅
5. Analytics with GoatCounter (page views plus the steps of the contribute form), and a
   short privacy page.

Decided with the owner: a work counts for an exam when its report is the verified one or
the only one (shown as unconfirmed); disputed exams count for nobody. The same work set
for two disciplines in one year counts twice, because those choices are made
independently. Releases after steps 1, 3 and 4, each reviewed first.

### Phase 5 — Email capture (ready by spring 2027)
"Avísame" sign-up with explicit consent, one mailing after the June exams, privacy note.

### Alongside, when convenient
Done (section 11): rate-limit keying and limits (finding 4), session length and link
token (5), cold-start weight (9), pinning dependencies.
Done (section 12): backups (10), domain.
Still open: Sentry account (the owner is setting it up).

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

---

## 9. Phase 2 record: the wizard rework

Status: written and tested on branch `feat/wizard-rework`, reviewed by the project owner,
then merged to `main` and released on 2026-11-11.

**Duplicates (finding 1)**
- A composer or work typed by hand is matched against existing rows before a new one is
  created. Matching ignores case, accents, punctuation and the spelling of "number"
  (`n.º`, `nº`, `no.`, `núm.`). Works are matched within their composer.
- Composers and works get a `search_text` column holding that normalized form, kept up to
  date by listeners in `app/models.py`. Migration `b7d2e9f0a1c3` adds and fills it.
- Ids sent by the browser are confirmed against the catalogue before anything is marked
  verified: an OpenOpus composer id must match the composer OpenOpus returns for that
  name, and a work's title is taken from the composer's catalogue, not from the request.
- The same person picked from two catalogues is stored once: a Wikidata pick whose
  Spanish or English name matches a stored composer is attached to it.

**Search**
- Composer chain: local database → OpenOpus → Wikidata → free text. The external step
  runs by itself when nothing local matches; the "use it as I typed it" option only
  appears after it has run.
- Wikidata search is restricted to people whose occupation is composer and returns
  Spanish names where Wikidata has them. A catalogue hit for a composer already stored
  under another spelling ("Chaikovski" → "Tchaikovsky") is offered as the stored one.
- A new Wikidata composer is linked to OpenOpus when the names match exactly, so their
  works become searchable.
- Work search matches every word typed, in any order, against local works and the
  composer's OpenOpus catalogue together. The catalogue is downloaded once per composer
  and cached for a day. If OpenOpus is down, local works are still returned.
- Search endpoints are rate-limited and no longer return raw exception text.

**Spanish titles**
- `app/services/titles.py` renders OpenOpus's English titles in Spanish: "Piano Sonata
  no. 14 in C sharp minor, op. 27 no. 2" becomes "Sonata para piano n.º 14 en do
  sostenido menor, op. 27 n.º 2", and well-known nicknames get their Spanish form
  ("Claro de luna"). The original English words stay searchable.
- It is a glossary, not a translator. Titles it does not recognise (proper names, titles
  in German or French, English phrases outside the glossary) are left as they are, so
  some catalogue entries remain in English. The glossary is the place to extend.
- The migration applies the same rendering to works already stored from OpenOpus.
- Composer names are kept as their source gives them (OpenOpus's form, or Wikidata's
  Spanish label).

**Prepopulation**
- The form opens with the works already reported for that exam ("¿Es una de estas?")
  and the composers most reported for the discipline.
- After choosing a composer, their most reported and most popular works are listed
  before anything is typed.
- A signed-in user who already participated is sent to the exam page instead of the form.

**Describing a work by hand**
- Fields: type (with suggestions), instrument, number, catalogue (prefilled with the
  composer's usual prefix: BWV, K., D., Hob.…), key as note + accidental + mode,
  nickname. The resulting Spanish title is shown before it is used, and matching
  catalogue works are offered while typing.

**Details**
- Stored as plain Spanish text ("Mov. 2 (Adagio) · fragmento: cc. 1-40"), shown on the
  exam page under the work. They belong to the report: a later voter joins the report as
  it stands. The migration strips the old `[Movement]` / `[Excerpt]` prefixes.

**Submission and errors**
- The form works without Turnstile keys, and gets a fresh token after a failed attempt.
- Failed magic-link requests, rejected votes and rate limits now show a message (a toast
  for HTMX actions).
- The contribute page extends `base.html`, is in Spanish, has real breadcrumbs, and
  shares the email-verification panel with the vote flow.
- The magic-link email is in Spanish.

**Also done (finding 4, in part)**
- The rate limiter keys on `Fly-Client-IP`, so visitors no longer share one bucket behind
  Fly's proxy. The limits themselves are unchanged; the classroom case (many people on
  one school IP) is still open.

**Verification**
- 143 automated tests pass; `ruff` and `mypy` clean. Tests can no longer reach the real
  external services by accident.
- Both migrations run on copies of the local database.
- The app was run locally against the live OpenOpus and Wikidata services: searches,
  two users typing the same unlisted work (one verified entry with two votes), the
  redirect for a participant, and details on the exam page.
- The wizard's own script was run under Node against that server (18 checks covering
  search, the builder, details text, the email round trip and error handling).
- The project owner reviewed the result before release. No automated test drives the
  form in a real browser, so layout, the Turnstile widget and the email round trip are
  covered only by that manual pass.

**Left for later**
- Wizard state still lives in the browser, so opening the email link on another device
  starts an empty form.
- A composer picked from Wikidata with no exact OpenOpus match has no searchable
  catalogue; the work is described by hand.
- Existing duplicate works and composers are not merged (Phase 3).
- `work_card.html` is still two near-identical halves; consensus logic still exists twice.

---

## 10. Phase 3 record: admin tools

Status: written and tested on branch `feat/admin-tools`, approved by the project owner,
then merged to `main` and released on 2026-11-11. The cleanup of production data with
these tools is still to be done (see "To do after deploying").

**The page**
- `/admin`, server-rendered, in Spanish. Only a signed-in user whose role is `Admin` can
  open it or post to it; everyone else gets a 404. Admins see an "Admin" link in the header.
- A role is granted with `python scripts/set_role.py <email> Admin` (`--list` shows the
  users). The role is read from the database on each request, so it applies at once.
- Every action is a form post that returns to the page with a message saying what
  happened, or why nothing was changed. Destructive ones ask for confirmation first.
  Actions are written to the server log (`admin: ...`). There is no undo.

**What it can do**
- Reports: remove a flag; delete a report together with its votes (the exam row goes too
  when that was its last report).
- Works: merge one into another, edit title / nickname / IMSLP address, delete a work
  nobody reported, and link a hand-typed work to its OpenOpus catalogue entry.
- Composers: merge one into another, rename, and link a hand-typed composer to their
  OpenOpus record (added right after release, when the first cleanup showed that
  hand-typed works usually have a hand-typed composer too). OpenOpus rejects searches
  under four letters, so name lookups now fall back from a short surname to the other
  words of the name ("Fernando Sor" is found through "fernando"); this also fixes the
  contribute form for such composers. Composers OpenOpus does not have (Clementi) stay
  unlinked and their works are edited by hand.
- Exams: delete those with no reports (left over from before Phase 1).

**How merging behaves**
- Merging works moves the reports. When both works were reported for the same exam, the
  two reports become one: the votes are added together, and missing details and a flag
  are carried over. No vote can be lost or doubled, because a user has one vote per exam.
- The kept work takes the catalogue id, nickname and IMSLP address it lacks. If it takes
  the catalogue id it also takes the catalogue title.
- Merging composers moves the works; works with the same title (ignoring case, accents
  and punctuation) are merged as above. The kept composer keeps its name and gains the
  OpenOpus / Wikidata ids it lacks.
- Linking a work to the catalogue gives it the catalogue's title and id, or merges it
  into the stored copy of that catalogue work if there is one.

**Also in this pass**
- The year list on a region/discipline page links IMSLP for the work it names whether or
  not the exam is verified (it used to appear only for verified ones).
- Nickname glossary: "Facile" → "Fácil", "Salzburg Symphony no. N" → "Sinfonía de
  Salzburgo n.º N", and a dozen other common ones. Nicknames already stored are not
  rewritten; they can be edited on the admin page.
- Choosing a catalogue work in the form now adopts a same-titled hand-typed work of that
  composer instead of storing a second copy.

**Verification**
- 168 automated tests pass; `ruff` and `mypy` clean.
- Run locally against a copy of the local database and the live OpenOpus service:
  access refused when signed out, catalogue link (which merged two works), work merge,
  deletion of an unreported work, refusal to delete a reported one, empty-exam cleanup.
- No automated test drives the page in a real browser, so layout and the confirmation
  dialogs are covered only by manual use.

**To do after deploying**
- Grant the Admin role to the owner's account.
- Delete the 93 empty exams, link or merge the four hand-typed works, and fix the two
  stored nicknames ("Facile", "Salzburg Symphony no. 3").

**Left for later**
- No history of admin actions beyond the server log, and no undo. Take a backup of the
  database before a large cleanup.
- No tool to spot likely duplicates; the lists are sorted so that they sit together.
- Users cannot be managed from the page (roles are set with the script).

---

## 11. Side items record: sessions, rate limits, cold start, dependencies

Status: written and tested on branch `feat/side-items`, then merged to `main` and released
on 2026-11-12.

**Signing in (finding 5)**
- The emailed link now carries a link token valid for 15 minutes. Opening it sets a
  separate session token valid for 30 days. Neither is accepted in place of the other,
  so a leaked or forwarded link stops working after 15 minutes.
- The link can be opened more than once within those 15 minutes. Making it single-use
  would need a table of spent links, and mail scanners that pre-open links would spend
  them before the user does.
- The cookie is marked `secure` in production.
- After signing in, the visitor is only ever sent to a page on this site; any other
  `next` address goes to the home page.
- The link in the email always uses https in production.
- A user row is created when the link is opened, not when it is requested, so mistyped
  or never-verified addresses no longer leave rows behind. Rows created that way before
  this change are still there.
- An expired or invalid link shows a short page in Spanish instead of a JSON error.
- The role is no longer copied into the token; it was already read from the database.
- Side effect on release: everyone signed in is signed out once, and links emailed
  before the release stop working.

**Rate limits (finding 4)**
- Votes and reports are counted per signed-in user (20 and 10 per hour), so a class
  sharing the school's address is no longer limited as one person. The anonymous click
  that opens the email form is still counted per address.
- Link requests: 30 per hour per address (was 5 per minute), and 5 per hour per target
  email, so nobody can flood someone else's inbox.
- Counters live in each worker's memory. With two workers the real limits are up to
  twice the figures; accepted for now.

**Cold start (finding 9)**
- 2 gunicorn workers instead of 4 (the machine has one CPU).
- Seeding runs in the background after the web server starts, instead of before it. It
  stays best-effort and bounded by a 30-second timeout. It cannot move to Fly's
  `release_command`, because that machine does not mount the data volume.
- Migrations still run before the server starts.
- The wake-up time in production has not been measured before or after. Locally the
  seeding step takes under a second, so most of any gain will come from the workers.

**Dependencies**
- `requirements.txt` holds the runtime packages only, all pinned (gunicorn 27.0.0).
  `requirements-dev.txt` adds the test and lint tools, pinned. The production image
  installs the first; CI and developers install the second.
- Alpine.js is pinned to 3.17.5, the version the `3.x.x` address was serving.

**Verification**
- 193 automated tests pass (19 new); `ruff` and `mypy` clean.
- A clean Python 3.12 environment with only `requirements.txt` imports the app, runs the
  migrations and seeds.
- The production image was built and run locally on one CPU, on a copy of the local
  database and on an empty one: it migrates, seeds in the background, starts two workers
  and serves the pages. The sign-in round trip was checked against it (secure 30-day
  cookie, link token refused as a session, off-site `next` sent to the home page).
- First page after start, same image and machine, three runs each: 5.1 s with the old
  start-up (seed first, 4 workers), 3.8 s with the new one. Production wake-up time
  itself was not measured.
- With two workers the per-email link limit let 6 requests through instead of 5, as
  expected from per-worker counters.
- In development under gunicorn the simulated email (the link) is not printed to the
  log; under `uvicorn --reload`, the documented way to run locally, it is.

**Still open**
- Backups: written, waiting for the bucket (section 12).
- Sentry: the owner is creating the project and setting `SENTRY_DSN`.
- Domain: done, see section 12.

---

## 12. Backups and domain record

Status: written and tested on branch `feat/backups`, then merged to `main` and released on
2026-11-12, once the owner had created the bucket.

**Backups (finding 10)**

- `scripts/backup.py` takes a consistent, integrity-checked, gzipped snapshot of the
  database and uploads it to a private bucket on Fly's storage (Tigris), keeping the
  newest 90.
- `.github/workflows/backup.yml` runs it on the app machine every night. The backup goes
  from the machine straight to the bucket and never passes through GitHub: the
  repository is public, and its workflow artifacts can be downloaded by any signed-in
  GitHub user.
- The admin page has a link that downloads a snapshot to the admin's computer.
- Setup, manual use and restoring are in `docs/tech/backups.md`.

**Verification**
- 200 automated tests pass; `ruff` and `mypy` clean.
- The script was run on the local database: the unpacked copy holds the same reports.
- Not verified: the upload to Tigris, the nightly job, and the restore steps on the real
  machine. None of these can be tried until the bucket exists. The first manual run of
  the workflow is the test.

**Domain**
- `wikianalisis.org` already served the app. Its `www` form and the `fly.dev` address now
  redirect to it (`CANONICAL_HOST`), so links, search engines and the session cookie use
  one address.
- Decided: future sections go in paths on this domain, not in subdomains. The reasons,
  and the content ideas put aside for later, are in
  `docs/decisions/002_domain_and_future_content.md`.

---

## 13. Phase 4 record: statistics and discovery

### Steps 0 and 1 — groundwork, work and composer pages

Status: written and tested on branch `feat/work-pages`, reviewed by the owner, then merged
to `main` and released on 2026-11-12.

**Groundwork**
- `ConsensusService.event_outcome` is now the only place that decides what an exam's
  reports add up to. The year list had its own copy of the rule; it uses this one.
- Pages declared an `http://` canonical and sharing address in production. They now
  declare `https://`.
- Exam pages moved from `/exams/...` to `/examenes/...`. The old addresses redirect, so
  existing links and search results keep working.

**Work pages** (`/obras/{id}-{slug}`)
- Title, nickname, composer, IMSLP link, and the exams where the work fell: year,
  discipline, region, status and movement details, each linked to its exam page.
- Reports that do not count (the exam is disputed, or another work was verified) are
  listed apart as "Menciones sin confirmar".
- A work with no counted appearance has a page, but asks search engines not to index it.
- A place is reserved in the template for study material (decision 002). Nothing is
  shown there until such material exists.

**Composer pages** (`/compositores/{id}-{slug}`)
- The composer's works that fell in an exam, most frequent first, with year and
  discipline; unconfirmed mentions apart; a Wikidata link when known.

**Addresses**
- The number decides which page is shown. A missing or outdated slug redirects to the
  current one, so renaming a work does not break links.
- A work removed by an admin merge returns 404 at its old address. Accepted for now.

**Links in**
- On an exam page, the work title and the composer name link to their pages. The year
  list on a discipline page is unchanged: each row is already one link to the exam.

**Verification**
- 223 automated tests pass (14 new); `ruff` and `mypy` clean.
- Both pages were rendered from a copy of the local database and looked at as desktop
  screenshots. Phone width was not checked: the screenshot tool could not go below about
  500 px.

### Steps 2 and 3 — statistics and coverage table

Status: written and tested on branch `feat/stats-coverage`, reviewed by the owner (who asked
for six years and larger, equal-sized marks in the table), then merged to `main` and
released on 2026-11-12.

**Statistics** (`/estadisticas`, filter `?especialidad=piano`)
- Most frequent composers: exams counted and distinct works, each linked to the
  composer's page.
- "Obras que se repiten": only works that fell at least twice, with the exams. Works
  that fell once are counted in a line below and found on each composer's page.
- The page says how many exams the figures rest on, how many disputed exams are left
  out, and that with so few the figures are a guide, not a prediction.
- The filter lists only disciplines that have data.
- On the local database: 5 exams counted, three composers, no repeated work yet. The
  page is honest but thin until more exams are on record.

**Coverage table** (`/examenes/{region}`)
- Disciplines as rows, the last 6 exam years as columns, newest first. Each cell is
  verified, a single report, disputed, or empty. Filled cells link to the exam; empty
  ones link to its contribute form. Cells with data are drawn large so they stand out
  from the empty ones.
- Six years because most data is recent and recent exams are the ones people can still
  report. A "Todos los años" switch (and a line under the table) shows every year since
  2000, scrolling sideways, for someone who took the exam longer ago.
- Disciplines with most data come first. The discipline column stays in place when the
  table scrolls sideways on a narrow screen.
- A line above gives the count of exams on record out of the total.

**Ways in**
- The home page links to both pages under the region's name.
- Breadcrumbs on discipline and exam pages now go up through the region page.

**Verification**
- 230 automated tests pass (7 new); `ruff` and `mypy` clean.
- Statistics, coverage and home were looked at as screenshots from a copy of the local
  database, at desktop width and (coverage) at 500 px. Narrower phones were not checked.

### Step 4 — sitemap and structured data

Status: written and tested on branch `feat/sitemap-structured-data`, approved by the owner,
then merged to `main` and released on 2026-11-12. Step 5 (analytics and privacy page) is
next; it needs a GoatCounter account from the owner.

**Sitemap**
- Now lists, besides the home page and the exams with reports: the statistics page, each
  region page, each discipline page that has data, and the work and composer pages that
  have at least one counted appearance.
- Works and composers that only appear in disputed exams are left out, in line with
  their pages asking not to be indexed.
- The file is served as XML (it was labelled HTML).

**robots.txt**
- Asks crawlers to stay out of `/api/`, `/admin` and `/auth/`.

**Structured data**
- Work pages describe themselves as a schema.org `MusicComposition` (title, nickname,
  composer, the stored IMSLP address when there is one); composer pages as a `Person`
  (name, Wikidata address when known).
- Whether search engines use it for anything visible is up to them; it costs nothing.

**Canonical address**
- The "Todos los años" view of a region declares the plain region address as canonical,
  so it is not indexed as a second page.

**Verification**
- 236 automated tests pass (6 new); `ruff` and `mypy` clean.
- Not verified: how Google reads the sitemap and the structured data. That can only be
  checked after release, with Google's Rich Results Test and Search Console.

**After the release that included steps 2 and 3**
- The first deploy attempt failed on Fly's side ("insufficient memory available" on the
  machine's host); the site stayed up on the previous version and a retry succeeded.
  If this recurs, the machine may need moving to another host.

