#!/bin/sh
# Apply migrations, then serve. Fails fast if the DB is unreachable (no silent start).
set -e

if [ -z "$APX_SECRET_KEY" ]; then
  echo "APX_SECRET_KEY is required (no insecure default)." >&2
  exit 1
fi

echo "apx: applying migrations…"
alembic upgrade head

echo "apx: starting on :8000"
exec uvicorn apx.api.app:app --host 0.0.0.0 --port 8000
