# April Fixes Todo

I'm listing here bugs & other issues to be fixed at some point.

- `gunicorn` is unpinned in `requirements.txt`, which points to a structural issue: requirements should be divided between development & production.
- Tests are failing. Have to examine this issue carefully and fix it before adding more coverage.
