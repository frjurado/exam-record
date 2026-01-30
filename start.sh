#!/bin/sh
set -e

# Run migrations
echo "Running migrations..."
alembic upgrade head

# Start application
echo "Starting application..."
exec gunicorn app.main:app --workers 4 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8080
