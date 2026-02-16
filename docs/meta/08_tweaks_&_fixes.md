Some thins to improve & fix in the project after phase 7.2.


## Infrastructure
- Set domain to wikianalisis.org.
- Magic link from any email address?
- Two machines on Fly.io? (load is too slow)
- Change the DB to PostgreSQL? (necesary if more than one machine)

## UI improvements
- Group links on index under "Andalucía" tag to avoid text clutter:
    - Thus, links would be "Piano", "Guitar", etc. instead of "Andalucía - Piano", etc.
- Discipline page: event boxes could show status badge (verified...):
    - If validated, show work title/composer/IMSLP link?

## Features
- Consider opening more disciplines for the exam record:
    - That implies reorganizing the structure in index: grouping them by family (keyboard & guitar, strings, wind).
    - [NOT SURE] For mitigating, the "empty DB" feeling, could we show only the years for which there is data? (and add a button for expanding to every year).

## Text revision
- Index page: revise text.
- Discipline page: revise text ("Obras verificadas"?).
- Event page: title = "Piano - 2025"; subtitle = "Andalucía"
- Event page: revise text & the flagging badge.
- Event page: "IMSLP" button could be next to title & bigger.
- Contribute form & modals: revise text.
- Add a small "About" note at the bottom of index page.

## Bugs & issues
- Revise wizard_buglist.md and fix the most important issues.
