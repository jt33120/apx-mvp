#!/bin/sh
# Apply migrations, then serve. Fails fast if the DB is unreachable (no silent start).
set -e

if [ -z "$APX_SECRET_KEY" ]; then
  echo "APX_SECRET_KEY is required (no insecure default)." >&2
  exit 1
fi

# Encryption pre-flight (AD-31), BEFORE migrations/bootstrap and independent of the ASGI
# lifespan gate — so a real boot fails fast even under --lifespan off, and the backfill
# migration has the key it needs. The lifespan gate does the rigorous key validation; this is
# the fast fail-closed check on both layers.
if [ -z "$APX_ENCRYPTION_KEY" ]; then
  echo "APX_ENCRYPTION_KEY is required (encryption at rest, AD-31 — no insecure default)." >&2
  exit 1
fi
case "$APX_VOLUME_ENCRYPTED" in
  1|true|yes|TRUE|YES) ;;
  *)
    echo "APX_VOLUME_ENCRYPTED must attest the data volume is encrypted (set 1 once the disk is" \
         "backed by dm-crypt/LUKS or a provider-managed encrypted volume), AD-31." >&2
    exit 1 ;;
esac

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
