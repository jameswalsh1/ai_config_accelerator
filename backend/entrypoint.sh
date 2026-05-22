#!/bin/sh
set -e

echo "Running database migrations (with retry for MySQL startup)..."
i=1
while [ "$i" -le 30 ]; do
  if alembic upgrade head; then
    echo "Migrations completed."
    break
  fi
  if [ "$i" -eq 30 ]; then
    echo "Migration failed after 30 attempts, exiting."
    exit 1
  fi
  echo "Attempt $i/30 failed, retrying in 3s..."
  sleep 3
  i=$((i + 1))
done

echo "Starting server..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
