#!/bin/sh
set -e

# Run migrations (must succeed before the app serves)
echo "Running migrations..."
alembic upgrade head

# Seed reference data (regions/disciplines) so new entries reach production.
# It runs in the background so a cold start does not wait for it: the web server binds
# first. Best-effort ONLY: a hang is bounded by `timeout`, a failure is only logged, and
# seeding is idempotent, so if it is skipped on one boot it converges on a later one.
# (It cannot move to Fly's release_command: that machine does not mount the data volume.)
echo "Seeding reference data in the background..."
( timeout 30 python scripts/seed.py || echo "WARN: seeding skipped (timed out or errored)" ) &

# Start application (exec so gunicorn is PID 1 and receives Fly's stop signals).
# Two workers: the machine has one CPU, and each extra worker adds to wake-up time.
echo "Starting application..."
exec gunicorn app.main:app --workers 2 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8080 --access-logfile -
