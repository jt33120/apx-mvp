# APX

Mass-document triage for law firms. Hexagonal core, adapters at the edges, **one
stateful service** (PostgreSQL). Runs the same one artefact hosted, in CI, and
air-gapped inside a firm (AD-3).

> **Status: story 1.5 — owned authentication.** The frozen `piece`/`chunk` payload schema
> and its one writer (1.3), the *tenant* wall proven by an adversarial cross-tenant suite
> (1.4), and now **owned auth** — Argon2id passwords and opaque server-side sessions, with
> lockout-in-audit and per-tenant MFA (1.5) — exist; ingestion, retrieval and the model tiers
> do not yet. What is deliberately absent, and which story owns it, is listed at the bottom.

Planning artefacts (PRD, architecture spine, epics, stories) live under
`_bmad-output/planning-artifacts/`. The previous implementation at
`../apx-platform/` is reference only — never an edit target.

## Prerequisites

- [`uv`](https://docs.astral.sh/uv/) (Python 3.13 is fetched by `uv`, not the system)
- Docker + Docker Compose
- Node — build-time only; pin in `apx/web/.nvmrc` (24.18.0). No Node runtime ships (AD-29).

## Setup

```bash
uv sync --group dev                 # backend deps + dev tools, into .venv
cd apx/web && npm ci && npm run build   # static SPA -> apx/web/dist
```

Start the single stateful service (PostgreSQL + pgvector). Credentials come from
the environment — **never commit them** (AD-47):

```bash
POSTGRES_USER=apx POSTGRES_PASSWORD=change-me \
  docker compose -f deploy/docker-compose.yml up -d postgres
```

## Run the checks and tests

```bash
uv run python -m apx.checks   # structural-property checks (AD-33) — the layering rule (AD-4)
uv run ruff check .           # lint
uv run pytest -q              # tests, incl. the layering failure-path regression
```

All three are green on the empty project, and CI (`.github/workflows/ci.yml`)
runs them on every push.

## Source tree

```
apx/
  core/            # the hexagon — imports NO adapter (AD-4)
    domain/  ports/  app/  app/read/
  adapters/        # third-party edges (store_postgres, embedder_bgem3, llm_openai_compat, extraction, ocr_tesseract)
  api/             # FastAPI edge — validate, authorise, enqueue, return (empty in 1.1)
  worker/          # Procrastinate worker entrypoint (no tasks in 1.1)
  checks/          # structural-property checks (AD-33); a cut cannot drop them
  eval/            # gold set / degradation / estimator simulation (empty in 1.1)
  web/             # Vite + React Router SPA, built to static files (AD-29)
tests/             # unreachable from any runtime module (AD-16)
deploy/            # docker-compose (the single service); upgrade/backup land later
```

## Offline fitness (AD-2)

"Can this run, unmodified, on one machine inside a firm with no internet?" is
measured in CI from week one, not discovered in front of a client.

```bash
uv run python -m apx.fitness   # the end-to-end driver (asserts what exists, marks the rest PENDING)
uv run pytest tests/fitness -q # offline boot (no outbound network) + driver honesty
```

The frame guarantees today: the app boots with the offline env set and makes no
outbound network call, and the **egress deny-list** fails the build if any `apx`
runtime module imports a hosted-provider SDK (`supabase`, `boto3`, `google`, …;
`openai` is forbidden in the core — it belongs behind the local-LLM adapter). The
driver enumerates the full FR-55 pipeline; stages that do not exist yet are printed
`PENDING (story N)` and are **never** faked green. Coverage grows as the pipeline
is built.

## The layering rule (AD-4)

The core imports no adapter, and the dependency direction is one-way. This is
**enforced as a structural property** — a static import-graph check
(`import-linter`), not a runtime test. It runs via `python -m apx.checks` and in
CI, and fails the build on violation.

**Manual demonstration for the acceptance review** (the committed regression test
in `tests/checks/test_layering_check.py` keeps it honest afterward):

```bash
# add, temporarily, inside apx/core/domain/__init__.py:
#     from apx.adapters.store_postgres import x
uv run python -m apx.checks     # -> FAIL, non-zero exit
# then revert the line
uv run python -m apx.checks     # -> PASS
```

## The frozen payload schema (AD-9)

The increment's one irreversible decision: what travels on every indexed *chunk*. A
`piece` holds a document's full extracted text once — the target of exhaustive search —
with its own `text_identity` and `text_version`. A `chunk` carries only the enumerated
provenance: `chunk_id`, `piece_id`, `tenant`, `matter`, `position`, `full_text_version`,
`chunking_config_version`, `schema_version`, and a reserved external-authority reference.
The embedding vector and its `model_id`/`model_version` are added by the embedder story
(2.8); adding a *mandatory* field later would mean re-indexing every installed site blind,
so the set is fixed here.

Two things are deliberately **not** columns (AD-9/AD-13/AD-40): *RBAC scope* and
*custodian*. Scope is a **required write-time argument** the writer checks against the
matter's authoritative `matter_scope` — never persisted — so a re-scope takes effect at
the next read with nothing to propagate. There is exactly **one** `chunk` writer; it
defaults nothing and rejects, with a typed error, an incomplete payload, an unauthorised
or empty scope, or a schema/chunking version that differs from the import job's (one
*matter* never holds two generations).

Four static checks defend this at build time (`python -m apx.checks`): one writer,
`rbac_scope` required with no default, no scope/custodian column on `chunk`, and no
`ON DELETE CASCADE` on the piece FK (a *retired* state instead — AD-7). Each has a
failure-path fixture proving it fires. The migration is exercised up **and** down against
real PostgreSQL in CI.

## Tenant isolation (AD-12)

The wall between firms is the product's premise, and a cross-*tenant* leak is silent — no
error, no message. So it is a **proven, checked** property, not a hope. Every *tenant*-owned
table pins a non-nullable `tenant` (a record without one cannot be written); every read is
constrained by `tenant` **before** *RBAC scope* (scope is applied after tenant, never
instead of it); a user with no scope gets an **empty** corpus, not the whole one; and an
unknown *tenant* or a foreign *matter* fails closed (empty / `ScopeDenied`), never another
firm's rows.

Two build-time guards (`python -m apx.checks`) keep it from regressing: `tenant` is NOT
NULL on every owned table, and no store method applies a `scopes` filter without a
`tenant`. An **adversarial suite** (`tests/adapters/test_tenant_isolation.py`) seeds two
tenants sharing a common word and asserts zero cross-*tenant* results, counts or metadata
across every read surface. *(The full AD-14 single-read-entry-point consolidation — one
`core/app/read/` path plus a grep forbidding tenant-table queries elsewhere — is a
separate, larger unit; 1.4 delivers the tenant guarantee and a store-scoped check.)*

## Owned authentication (AD-15)

Auth is the application's own, so the same identity model works air-gapped and hosted with no
third party between a lawyer and the wall. Passwords are **Argon2id** (`pwdlib[argon2]`); a
legacy scrypt hash still logs in and is re-hashed to Argon2id on the next login
(upgrade-on-verify). Sessions are **opaque, server-side rows in PostgreSQL** — the cookie is an
unguessable id, authority is the row — with absolute and idle lifetimes (config-as-data), so
sign-out, a password change and a scope revocation take effect immediately (the row is deleted,
or scopes re-resolve live on the next request), never "wait for a token to expire". **No JWT
for user sessions.** Repeated failures are rate-limited **and recorded in the audit trail**;
MFA (TOTP) is configuration-as-data per tenant.

Two build-time guards (`python -m apx.checks`): **no reversible credential storage** (a
plaintext password column fails the build — passwords live only as a one-way hash), and every
`jwt.decode` must pin a literal `algorithms=[...]` (vacuous today; ready for internal service
tokens). `pwdlib[argon2]` and `pyotp` are pinned exactly (AD-30); PyJWT / WebAuthn are deferred.

## What does NOT belong in this repo yet

Scaffolding only. Each item below has an owning story; building it here is a
scope violation.

| Not yet | Owner |
|---|---|
| Internal service tokens (PyJWT), WebAuthn as a 2nd factor; MFA enrolment UX | later |
| Secret / key management (the session/DB secrets' custody) | 1.8 |
| Encryption + fail-closed start-up gate | 1.7 |
| Single read entry point (`core/app/read/`) + outside-read grep (AD-14) | later (1.12 / epic 3) |
| Config / provisioning surface | 1.9 |
| Content-free projection, egress check | 1.10 / 1.12 |
| Backup, restore, `upgrade.sh`, cosign packaging | 1.11 / deploy |
| Embedder, extraction, OCR, LLM client, ML weights | Epic 2 |
| Structural checks beyond the layering rule | 1.12 |
| Offline-fitness CI job (network-isolated, end-to-end) | 1.2 |
