# Deploying APX

APX is **one artifact**: the FastAPI process serves the API (`/api/*`) and the built
SPA (everything else). Its only stateful dependency is PostgreSQL. It runs **fully
offline**; the LLM tier is optional and opt-in.

## On one machine (the on-prem form-factor)

The intended deployment for a firm: the app + Postgres, on a single machine, no
Internet required.

```sh
# 1. A session-signing secret — generate once, keep it stable.
export APX_SECRET_KEY=$(openssl rand -hex 32)

# 2. (optional) the LLM tier — EU-hosted Mistral, or an on-prem model.
#    Leave unset to run the deterministic cascade fully offline.
export MISTRAL_API_KEY=…            # or LLM_API_KEY + LLM_BASE_URL + LLM_MODEL

# 3. Build and start (app on :8000, Postgres alongside; migrations run on boot).
docker compose up --build

# 4. Bootstrap the first admin (once).
docker compose exec app python -m apx.manage create-user \
    --tenant cabinet --email patron@cabinet.fr --name "Le Patron" --admin \
    --scope pole-assurance
#   (you'll be prompted for a password; or set APX_NEW_PASSWORD)
```

Open <http://localhost:8000>, log in, and manage the rest of the users from the
**Cockpit**.

### Staying offline for the LLM tier

Point the provider-agnostic adapter at a model running on the firm's own hardware
(vLLM or Ollama expose an OpenAI-compatible endpoint):

```sh
export LLM_BASE_URL=http://ollama:11434/v1/chat/completions
export LLM_MODEL=mistral        # whatever the local server serves
export LLM_API_KEY=not-needed   # any non-empty value; the adapter just needs one set
```

## To a hosted URL (dev / demo)

The same container image runs on any container host (Railway, Fly.io, Render): set
`DATABASE_URL` to a managed Postgres (e.g. Supabase), `APX_SECRET_KEY`, and optionally
the LLM vars. The core has **no vendor lock-in** — Supabase/Vercel are a convenience
for the hosted split, never a dependency (no Supabase Auth, no RLS).

## Configuration

| Variable | Required | Meaning |
| --- | --- | --- |
| `DATABASE_URL` | yes | `postgresql+psycopg://…` |
| `APX_SECRET_KEY` | yes | signs session cookies (no insecure default) |
| `MISTRAL_API_KEY` / `LLM_API_KEY` | no | enables the LLM tier (else offline) |
| `LLM_BASE_URL`, `LLM_MODEL` | no | provider/model override (default: Mistral) |
| `JUDGE_WORKERS` | no | LLM concurrency (default 8) |

Secrets live only in the environment — never in the image or the repo.
