#!/bin/sh
# Apply migrations, then serve. Fails fast if the DB is unreachable (no silent start).
set -e

if [ -z "$APX_SECRET_KEY" ]; then
  echo "APX_SECRET_KEY is required (no insecure default)." >&2
  exit 1
fi

echo "apx: applying migrations…"
alembic upgrade head

# First-admin bootstrap (idempotent): runs only when APX_BOOTSTRAP_ADMIN_EMAIL is set.
if [ -n "$APX_BOOTSTRAP_ADMIN_EMAIL" ]; then
  python -m apx.manage ensure-admin
fi

# Railway (and most hosts) inject $PORT; fall back to 8000 for local/compose.
PORT="${PORT:-8000}"
echo "apx: starting on :$PORT"
exec uvicorn apx.api.app:app --host 0.0.0.0 --port "$PORT"
