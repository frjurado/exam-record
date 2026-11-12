# 002 — One domain, and where future content would go

Date: 2026-11-12. Status: the domain part is decided and in place; the content ideas are
recorded for later and nothing is planned yet.

## Decision: everything lives at `wikianalisis.org`, in paths

The site is served at `wikianalisis.org`. Its `www` form and the `exam-record-beta.fly.dev`
address redirect to it (`CANONICAL_HOST` in `fly.toml`, `app/core/urls.py`).

Future sections go in paths beside the exam registry (`/exams/...` today; for example
`/obras/...`, `/analisis/...`), not in subdomains.

Why:
- The most useful link between the registry and other material is per work: one page
  showing where a work fell in exams and what there is to study it with. Subdomains would
  split that page in two.
- Search engines treat a subdomain almost as a separate site. With low, seasonal traffic,
  every page should add to the standing of a single domain.
- One sign-in cookie covers everything.
- Exam pages already sit under `/exams/`, so new sections need no change to existing links.

A subdomain is the right choice only for a part run by a different tool (a video
platform, a forum). That part would get the subdomain; the registry stays where it is.

## Ideas for later

Deferred until the site has more exam records and users. None is scheduled.

1. **Complementary material in several formats.** Example analyses by professionals,
   video explanations, explorable explanations. Some would be tied to works in the
   registry; some would be general material on music analysis.
2. **The work page as the hub.** Phase 4 of the November 2026 plan adds a page per work
   and per composer. If it leaves room for "resources on this work", it becomes the
   junction between the registry and everything in point 1.
3. **Curate before creating.** Link each work to good material that already exists
   (scores on IMSLP are already linked; recordings, published analyses, videos). Cheap,
   useful at once, and it shows which works deserve original content.
4. **Contributed analyses.** Teachers and users submitting their own, in the spirit of
   the name. Needs moderation, so it comes after the others.
5. **The home page changes role.** Today `/` is the registry's index. When a second
   section exists, `/` becomes a general landing page and the index moves to `/exams`.
6. **The email list.** The "avísame" sign-up planned for spring 2027 (Phase 5) is also
   the audience to tell about new material, with the consent wording written to allow it.
