#!/bin/sh
set -e

# Run migrations
echo "Running migrations..."
alembic upgrade head

# Seed reference data (idempotent - skips existing rows)
echo "Seeding reference data..."
python scripts/seed.py

# Start application
echo "Starting application..."
exec gunicorn app.main:app --workers 4 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8080 --access-logfile -
