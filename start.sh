#!/bin/sh
set -e

# Run migrations (must succeed before the app serves)
echo "Running migrations..."
alembic upgrade head

# Seed reference data (regions/disciplines) so new entries reach production.
# Best-effort ONLY: this must never block or fail startup. A hang is bounded by
# `timeout`, and any non-zero exit is swallowed so `set -e` cannot abort boot.
# Seeding is idempotent, so if it is skipped on one boot it converges on a
# later one. This keeps the web server's availability independent of seeding.
echo "Seeding reference data..."
timeout 30 python scripts/seed.py || echo "WARN: seeding skipped (timed out or errored); continuing startup"

# Start application (exec so gunicorn is PID 1 and receives Fly's stop signals)
echo "Starting application..."
exec gunicorn app.main:app --workers 4 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8080 --access-logfile -
