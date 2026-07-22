# Story 1.1: The repository, born from empty, with the layering rule enforced

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As the APX build (one lead plus AI coding agents),
I want the product repository created from nothing with the spine's prescribed hexagonal source tree, the layering rule enforced by a static check, and an empty `checks/` harness wired into CI,
So that every later story is written against a structure a machine already guards, rather than one that drifts.

**Scope in one line:** repository scaffolding only. No feature, no schema, no endpoint, no auth, no encryption, no ingestion, no embedder. This story stands up the *shape* and the *guardrail*, and nothing that runs a feature. See **Dev Notes › What this story must NOT do**.

## Acceptance Criteria

Reproduced verbatim from `epics.md` Story 1.1, then decomposed into numbered criteria for task tagging. The decomposition adds no scope — AC1–AC3 are the three conjuncts of the single **Then**; AC4 and AC5 are the two **And** clauses.

> **Given** no repository exists and the spine names no starter or paved path,
> **When** Story 1.1 is complete,
> **Then** the source tree matches the spine's prescribed layout (a hexagonal core with adapter boundaries), a `checks/` harness runs in CI and is green on an empty project, and the pinned stack versions from the spine are declared in the lockfiles (PostgreSQL 18.4, pgvector ≥ 0.8.5, Procrastinate 3.9.x, FastAPI 0.139.2, Starlette 1.3.1, Vite 8.1.5, React Router 8.2.0).
> **And** a static check asserts the layering rule — the core imports no adapter — and fails the build on violation (per AD's hexagonal-core rule).
> **And** *(failure path)* a deliberately introduced import from the core to an adapter turns the build red, proving the check is live and not decorative.

1. **AC1 — Source tree.** The source tree matches the spine's prescribed layout (a hexagonal core with adapter boundaries): `apx/core/{domain,ports,app,app/read}`, `apx/adapters/{store_postgres,embedder_bgem3,llm_openai_compat,extraction,ocr_tesseract}`, `apx/api`, `apx/worker`, `apx/web`, `apx/checks`, `apx/eval`, plus top-level `tests/` and `deploy/`. [Source: ARCHITECTURE-SPINE.md#Structural-Seed › Source tree]
2. **AC2 — Harness green on empty.** A `checks/` harness runs in CI and exits green (zero violations) on the empty project.
3. **AC3 — Pinned versions in lockfiles.** The pinned stack versions from the spine are declared and committed in the lockfiles: PostgreSQL 18.4, pgvector ≥ 0.8.5, Procrastinate 3.9.x, FastAPI 0.139.2, Starlette 1.3.1, Vite 8.1.5, React Router 8.2.0.
4. **AC4 — Layering check enforced.** A static check asserts the layering rule — the core (`apx.core`) imports no adapter (`apx.adapters`) — and fails the build on violation. [Source: ARCHITECTURE-SPINE.md#AD-4]
5. **AC5 — Failure path (the check is live).** A deliberately introduced import from the core to an adapter turns the build red, proving the check is live and not decorative. Codified as a permanent regression test so the proof does not rot.

## Tasks / Subtasks

Ordered as a build order. Each task is one focused session. `[ASSUMPTION]` marks a concrete choice the spine left open — flagged for the reviewer.

- [ ] **Task 1 — Initialize the `uv`-managed Python project at the repo root, target Python 3.13.14** (AC: #3)
  - [ ] Create `pyproject.toml` at `apx-mvp/` root (alongside `_bmad/`, `_bmad-output/`, `docs/`, `design-artifacts/` — those stay untouched). Project name `apx`; `requires-python = ">=3.13,<3.14"`. [Source: docs/context/05-stack-research-2026-07.md#8 "Target Python 3.13, not 3.14"]
  - [ ] Raise the Python pin: update the existing root `.python-version` from `3.12` to `3.13.14`, and run `uv python install 3.13.14`. **Flag:** the local machine currently pins 3.12; the target is 3.13.14. `uv` fetches and manages 3.13 independently of the system Python, so raising is low-risk. See **Open Questions**.
  - [ ] Configure the build backend so `apx` is the importable package and `apx/web` (a non-Python npm project) is excluded from the wheel. [ASSUMPTION] hatchling backend with an explicit `packages`/`include` limited to `apx` Python subpackages; exclude `apx/web`.
  - [ ] Add dev tooling to a dev dependency group: `import-linter` (layering check, Task 5), `pytest` (test runner), `ruff` (lint). [ASSUMPTION] these tools — the spine names "grep, lint, import-graph or architecture rule" (AD-33) but no specific tool; import-linter is the conventional Python import-graph enforcer, pytest the conventional runner.
  - [ ] Confirm `.gitignore` covers `.venv/`, `__pycache__/`, `uv`'s cache, `apx/web/node_modules/`, `apx/web/dist/`, and secrets (`.env*`). An adequate `.gitignore` already exists at root — extend, do not replace.

- [ ] **Task 2 — Create the hexagonal source tree with layer docstrings and entrypoint boundaries** (AC: #1)
  - [ ] Create the package tree exactly as the spine prescribes (Dev Notes › Project Structure Notes), each Python package with an `__init__.py` carrying a one-line docstring naming its layer and its permitted dependency direction (copied from the spine's layer table). No logic in any of them.
    - `apx/core/domain/`, `apx/core/ports/`, `apx/core/app/`, `apx/core/app/read/`
    - `apx/adapters/{store_postgres,embedder_bgem3,llm_openai_compat,extraction,ocr_tesseract}/`
    - `apx/api/`, `apx/worker/`, `apx/checks/`, `apx/eval/`
    - `apx/web/` (npm project — **no** `__init__.py`; scaffolded in Task 4)
    - top-level `tests/` and `deploy/`
  - [ ] Add the app/entrypoint boundaries only (no routes, no tasks, no features):
    - [ASSUMPTION] `apx/api/app.py` exposing `app = FastAPI()` with **zero** routes — the HTTP surface boundary, per the layer table (`api/` → Application). [Source: ARCHITECTURE-SPINE.md#Design-Paradigm]
    - [ASSUMPTION] `apx/worker/app.py` exposing a Procrastinate `App` object with **zero** tasks — the worker entrypoint boundary. [Source: ARCHITECTURE-SPINE.md#AD-6]
  - [ ] Confirm `apx/core/domain/__init__.py` imports nothing outside itself; `apx/core/app/__init__.py` imports (nothing yet, but is permitted only) Domain and Ports; no adapter imports another adapter. These are empty now — the constraint is what Task 5 enforces. [Source: ARCHITECTURE-SPINE.md#AD-4]

- [ ] **Task 3 — Pin the backend stack in `pyproject.toml` and lock it** (AC: #3)
  - [ ] Add runtime dependencies at the exact versions (Dev Notes › Exact versions): `fastapi==0.139.2`, `starlette==1.3.1`, `uvicorn==0.51.0`, `pydantic==2.13.4`, `sqlalchemy==2.0.51`, `psycopg==3.3.4`, `alembic==1.18.5`, `procrastinate>=3.9,<3.10`, and the `pgvector` Python helper (SQLAlchemy `halfvec` types) at a version compatible with the pinned SQLAlchemy [ASSUMPTION on the helper's version — the *extension* pin 0.8.5 lives in docker-compose, Task 8].
  - [ ] `uv lock` then `uv sync`. Commit `uv.lock`.
  - [ ] **Version trap (verify explicitly):** open `uv.lock` and confirm `starlette` resolved to **exactly 1.3.1**, not a transitive bump. FastAPI 0.139.2 declares `starlette>=0.46.0` — an open lower bound spanning the 0.46→1.x major boundary; the lockfile is the discipline. [Source: ARCHITECTURE-SPINE.md#Stack Starlette row; review-versions H4]
  - [ ] Do **not** add auth, embedder, extraction or LLM dependencies here — those belong to their own stories (Dev Notes › What this story must NOT do).

- [ ] **Task 4 — Scaffold the static-SPA frontend in `apx/web/` (Vite + React Router), pin and lock** (AC: #1, #3)
  - [ ] Initialize an npm project in `apx/web/` [ASSUMPTION npm + `package-lock.json`; pnpm/yarn acceptable if the lockfile is committed]. Pin `vite@8.1.5` and `react-router@8.2.0` exactly in `package.json`, plus `react`, `react-dom`, `typescript`, `@vitejs/plugin-react`. [Source: ARCHITECTURE-SPINE.md#AD-29, #Stack]
  - [ ] Record the build-time Node version: `24.18.0` LTS via `apx/web/.nvmrc` and/or `engines` [ASSUMPTION]. Node is **build-time only — no Node runtime ships** (AD-29). [Source: ARCHITECTURE-SPINE.md#AD-29]
  - [ ] Minimal SPA that builds to static files and nothing more: `index.html`, `src/main.tsx`, `src/App.tsx`, a `react-router` router with a single empty route, and one design-token file (e.g. `src/tokens.css`) establishing the **single token set** convention (no colour/spacing/type value outside it — the *enforcing* check is FR-59/1.12, not here). [Source: ARCHITECTURE-SPINE.md#AD-29]
  - [ ] Run `npm ci && npm run build`; confirm it emits static assets to `apx/web/dist/`. Commit the lockfile.

- [ ] **Task 5 — Build the `checks/` harness and ship the layering check, green on empty** (AC: #2, #4)
  - [ ] In `apx/checks/`, create a runner [ASSUMPTION `apx/checks/__main__.py`, invocable as `python -m apx.checks`] that executes every registered check and exits non-zero if **any** fails. Structure it as a list of checks so later stories (1.12) append without editing the runner. Each check states, in code or in a docstring, **its pattern and the AD it enforces** (AD-33 requirement). [Source: ARCHITECTURE-SPINE.md#AD-33; epics.md#Additional-Requirements]
  - [ ] Configure import-linter for the layering rule: a `[tool.importlinter]` block (in `pyproject.toml`) or `.importlinter` file [ASSUMPTION] with a **forbidden** contract named e.g. "core imports no adapter": `source_modules = apx.core`, `forbidden_modules = apx.adapters`. This is the one mandated check for 1.1. [Source: ARCHITECTURE-SPINE.md#AD-4]
  - [ ] Register the import-linter run inside the harness (shell `lint-imports`, or its Python API), so `python -m apx.checks` runs the layering check among its set.
  - [ ] Scaffold — but do **not** yet enforce beyond core→adapter — the finer contracts the paradigm ultimately requires (`apx.core.domain` imports nothing outside itself; `apx.core.app` imports only Domain+Ports; no adapter imports another adapter). Leave them commented or clearly marked "tightened in 1.12" so the reviewer sees the intent without 1.1 over-reaching. [Source: ARCHITECTURE-SPINE.md#AD-4]
  - [ ] Run the harness on the empty tree: it must exit **green** (zero violations), since no core module imports anything yet (AC2).

- [ ] **Task 6 — Write the failure-path regression test proving the layering check is live** (AC: #5)
  - [ ] Commit a deliberately violating fixture, isolated from the real package [ASSUMPTION `tests/_fixtures/layering_violation/`]: a fake `core_fake` package that imports a fake `adapter_fake` package.
  - [ ] Write a test [ASSUMPTION `tests/checks/test_layering_check.py`] that runs the layering contract against the fixture (import-linter's Python API, or `lint-imports --config <selftest-config>` as a subprocess) and asserts a violation is reported / non-zero exit. This is the permanent form of "the check is live". [Source: epics.md#Story-1.1 failure path]
  - [ ] Document (in the README, Task 10) the one-off manual demonstration for the acceptance review: temporarily add `from apx.adapters.store_postgres import x` inside `apx/core/domain/`, confirm CI / `lint-imports` goes **red**, then revert. The committed test is what keeps it honest afterward.
  - [ ] Ensure the fixture is not collected as a test module and is **not** importable from any runtime module under `apx/` (the "no runtime import from the test tree" rule is FR-33/AD-16, enforced by a check in 1.12; here just respect it). [Source: ARCHITECTURE-SPINE.md#AD-16]

- [ ] **Task 7 — Set up an empty Alembic environment (no migrations)** (AC: #1)
  - [ ] `alembic init` producing `env.py`, `script.py.mako` and an **empty** `versions/` directory. [ASSUMPTION] place the migration environment under `apx/adapters/store_postgres/migrations/` (migrations live with the store per the spine's capability map) and put `alembic.ini` at the repo root with `script_location` pointing there. [Source: ARCHITECTURE-SPINE.md#Capability-Map §4.2; #AD-46]
  - [ ] Read the DB URL from an environment variable (no credentials in source — FR-51/AD-47). **No** migration scripts, **no** schema. [Source: ARCHITECTURE-SPINE.md#AD-47]
  - [ ] Note in a comment that the **fail-closed `upgrade.sh` wrapper** around Alembic (verified `pg_dump` first, head recorded, collation asserted) is AD-46 and belongs to the backup/deploy story (1.11), **not** here. [Source: ARCHITECTURE-SPINE.md#AD-46]

- [ ] **Task 8 — Author `docker-compose.yml` declaring the single stateful service (PostgreSQL + pgvector)** (AC: #1, #3)
  - [ ] [ASSUMPTION `deploy/docker-compose.yml`] Declare exactly **one** `postgres` service — the only stateful service (AD-5) — using `pgvector/pgvector:pg18`, which bundles pgvector on PostgreSQL 18. Pin by **digest** and choose the digest whose image provides **PostgreSQL 18.4 + pgvector 0.8.5** (verify at runtime: `SELECT extversion FROM pg_extension WHERE extname='vector'` → `0.8.5`). [Source: ARCHITECTURE-SPINE.md#AD-5, #AD-30; Stack rows]
  - [ ] Service essentials only: `POSTGRES_USER`/`POSTGRES_PASSWORD`/`POSTGRES_DB` from the environment (no committed secrets), a named volume, a healthcheck. **Exactly one endpoint** — no replica, no standby, no routing pooler (AD-5). [Source: ARCHITECTURE-SPINE.md#AD-5]
  - [ ] Parameterize the image tag/digest via an env var (e.g. `POSTGRES_IMAGE`) so a later story can run a **PG17↔PG18 matrix** without editing the compose file (prep for the deferred parity check — Task 11 note). [Source: ARCHITECTURE-SPINE.md#AD-5 Open-Question-5 resolution; docs/context/06]
  - [ ] Comment (do not implement) that collation pinning — `LC_COLLATE`, `LC_CTYPE`, provider, ICU version declared and asserted at start-up, mismatch fails to start — is AD-5's start-up gate owned by the store/encryption story, **not** 1.1. No schema, no app service needs to run a feature here. [Source: ARCHITECTURE-SPINE.md#AD-5]

- [ ] **Task 9 — Add the CI workflow running the checks harness and the (empty) test suite** (AC: #2, #4, #5)
  - [ ] [ASSUMPTION GitHub Actions] `.github/workflows/ci.yml` at the repo root. The repo is on GitHub (per project context); GitHub Actions is the conventional CI.
  - [ ] Python job: install `uv`, `uv python install 3.13.14`, `uv sync`, then run **the checks harness** (`python -m apx.checks`, which runs the layering check), `ruff check`, and `pytest` (which includes the Task 6 failure-path test). A layering violation must fail the job (AC4); the failure-path test passing proves the check is live (AC5); on the empty tree everything is green (AC2).
  - [ ] Web job: set up Node `24.18.0`, `npm ci` and `npm run build` in `apx/web/`.
  - [ ] Confirm the whole workflow is **green on the empty project**. [Source: epics.md#Story-1.1; #Story-1.2 for what CI will grow into]

- [ ] **Task 10 — Write the developer README with run instructions** (AC: #1)
  - [ ] A README (repo root or `apx/`) covering: prerequisites (`uv`, Docker + Compose, Node 24.18.0); setup (`uv sync`; `docker compose -f deploy/docker-compose.yml up -d postgres`; `cd apx/web && npm ci && npm run build`); how to run the checks harness; how to run tests; the source-tree map; the layering rule in one paragraph; the manual failure-path demonstration (Task 6); and a short **"what does NOT belong in this repo yet"** list pointing at the owning stories (Dev Notes › What this story must NOT do). [Source: task brief; ARCHITECTURE-SPINE.md#Structural-Seed]
  - [ ] Do not commit any `.env` or example secret values (FR-51/AD-47). [Source: ARCHITECTURE-SPINE.md#AD-47]

- [ ] **Task 11 — Verify green-on-empty end to end, confirm pins, commit** (AC: #1, #2, #3, #4, #5)
  - [ ] Run the full pipeline locally (harness + ruff + pytest + web build + `docker compose up postgres`): all green.
  - [ ] Confirm `uv.lock` and the JS lockfile are committed and carry the AC3 versions (Starlette **1.3.1** exactly; Vite 8.1.5; React Router 8.2.0; Procrastinate 3.9.x; FastAPI 0.139.2). Confirm docker-compose pins PostgreSQL 18 + pgvector 0.8.5.
  - [ ] Confirm the failure-path demonstration goes red then reverts to a clean green tree.
  - [ ] **Deferred here, recorded so it is not forgotten:** the **PG17↔PG18 parity check** (AD-5, Open Q5) is **not** implemented in 1.1 — an empty schema has nothing to diverge. It belongs to the first story that introduces schema and queries (1.3, the payload schema) or the store unit, driven over the matrix Task 8 made parameterizable. [Source: ARCHITECTURE-SPINE.md#AD-5; docs/context/06-postgres-managed-tier-check-2026-07.md]

## Dev Notes

### Architecture compliance

Story 1.1 is the physical realization of the spine's paradigm and its cheapest guarantee. Each rule below is cited by AD number; the spine is the authority.

- **Hexagonal core, pipes-and-filters ingestion; the core imports no adapter.** The layer table is the contract: `core/domain/` may depend on nothing outside itself; `core/ports/` on Domain; `core/app/` (incl. the one read entry point `core/app/read/`) on Domain + Ports; `adapters/` on Ports; edges (`api/`, `worker/`, `web/`) on Application. "The domain never imports an adapter, and no adapter imports another adapter" is **AD-4** and is *checked, not documented*. 1.1 ships the mandated minimum of that check — core imports no adapter — and structures the harness so the finer contracts are added later. [Source: ARCHITECTURE-SPINE.md#Design-Paradigm; #AD-1; #AD-4]
- **One artefact, three environments; deployment is packaging.** 1.1 creates exactly one buildable product with no per-environment or per-client fork. Hosted dev, the CI container and the on-premise install will differ only by configuration rows and wired adapters — never by which code was built. **AD-3.** [Source: ARCHITECTURE-SPINE.md#AD-3]
- **One stateful service: PostgreSQL.** The compose file declares a single `postgres` service (relational data, vectors, deterministic text index and the Procrastinate queue all live here later) with **exactly one endpoint** — no replica, no standby, no routing pooler. No second stateful service (no Redis, no Qdrant) is introduced. **AD-5.** The collation-pinning and `pg_is_in_recovery()` start-up refusals are AD-5's start-up gate, owned by the store story, not 1.1. [Source: ARCHITECTURE-SPINE.md#AD-5]
- **The frontend is a static SPA (Vite + React Router); no Next.js.** Build-time Node only; no Node runtime ships; one token set. **AD-29.** [Source: ARCHITECTURE-SPINE.md#AD-29]
- **The `checks/` harness owns the structural properties (AD-33), and it is owned in `checks/` deliberately** so a later cut cannot drop it. 1.1 stands the harness up green-on-empty with the layering check; 1.12 fills in the full set (deny-list, egress, one-chunk-writer, etc.). **AD-33, and AD-3/AD-45 for the checks that live here later.** [Source: ARCHITECTURE-SPINE.md#AD-33; epics.md#Story-1.12]
- **Owned auth stack — recorded, not built here.** Opaque server-side PostgreSQL sessions with Argon2id via `pwdlib[argon2]`; PyJWT for internal service tokens only; no Supabase Auth, no RLS. **AD-15, AD-1.** None of it is installed in 1.1 (auth is 1.5/1.8). [Source: ARCHITECTURE-SPINE.md#AD-15]
- **No starter/paved path exists** — the spine names none, and the previous build at `../apx-platform/` is reference-only, never an edit target. 1.1 therefore builds from empty. [Source: epics.md#Additional-Requirements "Starter or paved path — stated plainly"; CLAUDE.md]

### Exact versions and why

The spine's `Stack` table is authoritative; where it gives a range or `≥`, that is kept. **Pin exactly** in the lockfiles. Versions land in three places: the Python lockfile (`uv.lock`), the JS lockfile (`apx/web/`), and the docker-compose image pin.

| Library / component | Version (1.1 pins) | Declared in (1.1) | Source |
| --- | --- | --- | --- |
| Python | 3.13.14 (target) | `.python-version`, `pyproject` `requires-python` | [Stack]; docs/context/05 §8 |
| FastAPI | 0.139.2 | `uv.lock` | [Stack]; AD-6 |
| **Starlette** | **1.3.1 (pinned, not inherited)** | `uv.lock` | [Stack]; review-versions H4 — **trap, below** |
| Uvicorn | 0.51.0 | `uv.lock` | [Stack] |
| Pydantic | 2.13.4 (2.14.0a1 is alpha — do not ship) | `uv.lock` | [Stack] |
| SQLAlchemy | 2.0.51 (2.1.0b3 is beta — do not ship) | `uv.lock` | [Stack] |
| psycopg | 3.3.4 (**LGPL-3.0-only**, in-process, to counsel) | `uv.lock` | [Stack]; AD-28 |
| Alembic | 1.18.5 | `uv.lock` | [Stack]; AD-46 |
| Procrastinate | 3.9.x (`>=3.9,<3.10`) | `uv.lock` | [Stack]; AD-5/AD-6 |
| pgvector (PostgreSQL extension) | **0.8.5 exactly** (`halfvec` + HNSW, 1024-dim) | docker-compose image (`pgvector/pgvector:pg18`, digest-pinned) | [Stack]; AD-5/AD-11 |
| pgvector (Python helper) | compatible w/ SQLAlchemy [ASSUMPTION] | `uv.lock` | AD-11 |
| PostgreSQL | 18.4 on-prem/Railway · 17 on Supabase dev | docker-compose image | AD-5; docs/context/06 |
| Vite | 8.1.5 | `apx/web/` lockfile | [Stack]; AD-29 |
| React Router | 8.2.0 | `apx/web/` lockfile | [Stack]; AD-29 |
| Node.js | 24.18.0 LTS (**build-time only**) | `apx/web/.nvmrc` / `engines` | [Stack]; AD-29 |
| import-linter | latest compatible [ASSUMPTION] | `uv.lock` (dev) | AD-4/AD-33 (tool unnamed by spine) |
| pytest | latest compatible [ASSUMPTION] | `uv.lock` (dev) | AD-33 verbs (runner unnamed) |
| ruff | latest compatible [ASSUMPTION] | `uv.lock` (dev) | AD-33 "lint" |

**Two version traps the reviews found — both must be honoured:**

1. **Starlette must be pinned; it is not safely inherited.** FastAPI 0.139.2 declares `starlette>=0.46.0` — an *open* lower bound spanning the 0.46→1.x **major** boundary (and `pydantic>=2.9.0` likewise). There is no lockstep. The lockfile is the discipline, and it is load-bearing because AD-3 builds one artefact and AD-30 pins by digest. Verify `uv.lock` shows `starlette==1.3.1`. [Source: ARCHITECTURE-SPINE.md#Stack Starlette row; review-versions H4; docs/context/05 §8]
2. **PyJWT is for internal service tokens only — never user sessions.** User sessions are opaque server-side rows (AD-15). When PyJWT is later added (auth story), every `jwt.decode` passes `algorithms=["HS256"]` explicitly, and `PyJWK`/`PyJWKClient`/`jwks` appear in no runtime module. **PyJWT is not installed in 1.1** — recorded here so it is not reached for by whoever next reads a FastAPI tutorial. [Source: ARCHITECTURE-SPINE.md#AD-15]

**On `pgvector ≥ 0.8.5` (AC3) vs `== 0.8.5` (Stack):** AD-5 pins the extension **exactly** (0.8.3/0.8.4 were HNSW vacuum-corruption fixes on an index nobody can inspect remotely; AD-30 pins by digest). Pinning `== 0.8.5` satisfies the AC's `≥ 0.8.5`. The *invariant* is the extension contract — pgvector ≥ 0.8 with `halfvec` + HNSW on the newest major the environment offers (18.4 on-prem/Railway, 17 on Supabase dev) — not the server patch number. [Source: ARCHITECTURE-SPINE.md#AD-5, #AD-11, #AD-30]

**Deferred dependencies — do NOT add in 1.1** (their stories own them, and adding them here is over-building): BGE-M3 weights + embedder runtime (embedder/index story; 1.4 GB of weights ride inside the artefact per AD-11); vLLM 0.25.1 / Ollama 0.32.1 / Mistral (LLM story, AD-27); Docling 2.114.0 / Tesseract 5.5.2 / pypdf 6.14.2 / pdfplumber 0.11.10 / extract-msg 0.56.0 / python-docx 1.2.0 / openpyxl 3.1.5 (extraction, story 2.3, AD-28); pwdlib[argon2] 0.3.0 / argon2-cffi 25.1.0 / PyJWT 2.13.0 / pyotp 2.10.0 / py_webauthn 3.0.0 (auth, 1.5/1.8, AD-15); cosign 3.1.2 + Docker packaging (deploy, 1.11 / fitness 1.2, AD-30). [Source: ARCHITECTURE-SPINE.md#Stack; epics.md#Epic-1]

### Project Structure Notes

**Product code lives at the `apx-mvp/` root, alongside the planning folders.** `_bmad/`, `_bmad-output/`, `docs/`, `design-artifacts/`, `.claude/` all stay exactly where they are and are not touched. 1.1 adds: `apx/`, `tests/`, `deploy/`, `pyproject.toml`, `uv.lock`, `.github/`, an updated `.python-version`, and an extended `.gitignore`. The top-level Python package is `apx` (no clash with the repo directory name `apx-mvp`).

The tree below is reproduced verbatim from the spine (the authority). Reproduce it exactly. [Source: ARCHITECTURE-SPINE.md#Structural-Seed › Source tree]

```text
apx/
  core/
    domain/        # entities, payload record, identity fn, ranked order, estimator, truth status
    ports/         # Embedder, LanguageModel, Extractor, Ocr, Store, Clock — protocols only
    app/           # use cases; the ONE chunk writer; the cascade; the AD-37 transition owners
      read/        # the ONE read entry point — every read of tenant data, search or not (AD-14)
  adapters/
    store_postgres/    # pgvector, Procrastinate, full-text, the append-only ledgers
    embedder_bgem3/    # exactly one non-test Embedder implementation
    llm_openai_compat/ # vLLM and Ollama profiles behind one client
    extraction/        # extract-msg, pypdf, pdfplumber, Docling — each out-of-process
    ocr_tesseract/
  api/             # FastAPI routes: validate, authorise, enqueue, return
  worker/          # Procrastinate worker entrypoint
  web/             # Vite + React Router SPA, built to static files
  checks/          # AD-33 structural checks; each names its pattern and its AD
                   #   incl. the AD-3 package deny-list and the AD-45 egress check
                   #   (owned here, not by the projection unit, so a cut cannot drop it)
  eval/            # gold set mapping, degradation pipeline, estimator simulation
tests/             # unreachable from any runtime module — enforced by a check
deploy/            # compose bundle, upgrade.sh, cosign verification, backup scripts
```

Notes, variances and `[ASSUMPTION]`s the reviewer should see:
- `apx/web/` is a standalone **npm** project (its own `package.json`/lockfile), **not** a Python subpackage — it carries no `__init__.py` and is excluded from the Python wheel. It is nested under `apx/` because the spine places it there; if Python packaging friction arises, relocating it to a repo-root `web/` is the obvious escape, but default to the spine's layout. `[ASSUMPTION]`
- `apx/checks/` and `apx/eval/` are Python subpackages that are build/CI-time tooling; they sit inside `apx/` per the spine. In 1.1, `eval/` is an empty package (populated by 2.12 / 5.3); `checks/` carries only the runner + the layering check.
- Empty-in-1.1 (just `__init__.py` + docstring, no logic): every `core/*`, every `adapters/*`, and `eval/`. `api/` and `worker/` carry only their entrypoint boundary object.
- Files whose exact name/location the spine leaves open (all `[ASSUMPTION]`): the checks runner (`apx/checks/__main__.py`); the API entrypoint (`apx/api/app.py`); the worker entrypoint (`apx/worker/app.py`); the Alembic env location (`apx/adapters/store_postgres/migrations/`) and `alembic.ini` at root; the compose file (`deploy/docker-compose.yml`); the failure-path fixture (`tests/_fixtures/layering_violation/`); CI at `.github/workflows/ci.yml`.

### The fitness function — what 1.1 sets up for 1.2

Story 1.2 ("The offline fitness function, running in CI from week one") drives the structure 1.1 builds; it does **not** build that structure. 1.2 will boot the whole application in a **network-isolated** container with no outbound network except a stubbed model endpoint, from a cold cache, in an image built with `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`, `DO_NOT_TRACK=1`, `SCARF_NO_ANALYTICS=1`, and assert the end-to-end path plus the AD-45 no-egress property. [Source: ARCHITECTURE-SPINE.md#AD-2; epics.md#Story-1.2]

For that to be possible, 1.2 will **expect 1.1 to have delivered**: an importable `apx` package; the `apx/api` and `apx/worker` entrypoint boundaries; a `docker-compose.yml` declaring the single `postgres` service; the `checks/` harness runnable in CI; and committed, digest-/version-pinned lockfiles. What 1.1 must **not** pre-build for it: the network isolation, the model stub, the offline env vars, the end-to-end drive, and the Dockerfile that vendors the embedder weights — all AD-2 / 1.2 territory. Keeping those out of 1.1 is the point. [Source: ARCHITECTURE-SPINE.md#AD-2, #AD-11]

### What this story must NOT do

Scaffolding only. Building any of the following here is a scope violation — each has an owning story:

- **No payload schema, no `chunk` writer, no tables, no migration scripts** — empty Alembic only. Owner: **1.3** (the frozen payload schema; the one irreversible decision). [AD-9, AD-40]
- **No authentication, no sessions, no password hashing, no PyJWT** — owner **1.5** (+ **1.8** for secrets/keys). [AD-15]
- **No encryption, no fail-closed start-up gate** — owner **1.7**. [AD-31]
- **No tenancy write-boundary / read-path enforcement** — owner **1.4** (tenant isolation) and the read-path unit. [AD-12, AD-14]
- **No config/provisioning surface** — owner **1.9**. [AD-25]
- **No content-free projection, no egress check** — owner **1.10** / **1.12**. [AD-26, AD-45]
- **No backup/restore, no `upgrade.sh`, no cosign packaging** — owner **1.11** / deploy. [AD-32, AD-46, AD-30]
- **No embedder, no extraction, no OCR, no LLM client, no ML weights** — owners in Epic 2 and the LLM/embedder units. [AD-11, AD-27, AD-28]
- **No structural checks beyond the layering rule** — the full harness (deny-list, one-chunk-writer, no-post-filter, no-secret-in-source, …) is **1.12**. 1.1 ships *only* the layering check, green on empty. [AD-33; epics.md#Story-1.12]
- **No HTTP endpoints, no worker tasks, no features** — only the bare `FastAPI()` and Procrastinate `App` entrypoint boundary objects.

### Testing standards

- **Where tests live:** top-level `tests/`, unreachable from any runtime module. The **FR-33 / AD-16** rule — no runtime module under `apx/` imports from the test tree, no runtime module reads a fixture directory — is *respected* in 1.1 (fixtures under `tests/_fixtures/`, runtime imports none of it) and *enforced by a check* in 1.12. Do not wait for the check to obey the rule. [Source: ARCHITECTURE-SPINE.md#AD-16]
- **Test runner:** pytest `[ASSUMPTION]` (the spine names none; pytest is the Python convention and the salvaged v1 suite used it). [Source: epics.md#Salvage `tests/unit/test_guardrails.py`]
- **The checks harness is itself tested.** The layering check is a guard, and a guard that never fires is indistinguishable from no guard — so Task 6's failure-path test is mandatory and permanent: it asserts the layering contract **reports a violation** against a deliberately violating fixture. This is the "test of the check itself" the AC5 failure path requires. [Source: epics.md#Story-1.1]
- **Frontend tests:** none required in 1.1 beyond a passing `npm run build` (and, if trivial, a type-check). A web unit runner (Vitest is the Vite-native choice) is a later concern. `[ASSUMPTION]`
- **Green on empty is the bar.** With no feature code, the harness finds zero violations, pytest passes (the failure-path test is the only meaningful assertion), ruff is clean, and both CI jobs are green. [Source: epics.md#Story-1.1 AC2]
- **Verbs are not conflated (AD-33/NFR-51):** the layering rule is *enforced as a structural property* (a static check decides). Do not describe it as "asserted by test" in any doc string — the distinction is load-bearing across the programme. [Source: ARCHITECTURE-SPINE.md#AD-33]

### References

- [Source: ARCHITECTURE-SPINE.md#Design-Paradigm] — the layer table; "the domain never imports an adapter, and no adapter imports another adapter" (= AD-4).
- [Source: ARCHITECTURE-SPINE.md#AD-1] — deployment-agnostic core; every third-party edge is a port; Supabase Auth and RLS forbidden.
- [Source: ARCHITECTURE-SPINE.md#AD-2] — the offline fitness function as a network-isolated CI job from week one (drives, in 1.2, what 1.1 scaffolds).
- [Source: ARCHITECTURE-SPINE.md#AD-3] — one artefact, three environments; deployment is packaging; the deny-list in `checks/`.
- [Source: ARCHITECTURE-SPINE.md#AD-4] — dependency direction is one-way and checked by an import-graph rule in CI (the layering rule this story ships).
- [Source: ARCHITECTURE-SPINE.md#AD-5] — one stateful service, PostgreSQL; pgvector ≥ 0.8 + `halfvec` + HNSW on the newest major; exactly one endpoint; PG17↔PG18 parity check; collation pinned; pgvector `== 0.8.5`.
- [Source: ARCHITECTURE-SPINE.md#AD-6] — work happens in the queue; the HTTP request validates/authorises/enqueues/returns (the api & worker entrypoint boundaries).
- [Source: ARCHITECTURE-SPINE.md#AD-15] — owned auth; PyJWT for internal service tokens only, never user sessions; `algorithms=["HS256"]` explicit.
- [Source: ARCHITECTURE-SPINE.md#AD-16] — one ingestion path; tests unreachable from runtime; no fixture directory read.
- [Source: ARCHITECTURE-SPINE.md#AD-28] — extraction adapters out-of-process, licence-isolated; psycopg LGPL-3.0-only in-process; the copyleft licence position.
- [Source: ARCHITECTURE-SPINE.md#AD-29] — static SPA (Vite 8.1.5 + React Router 8.2.0); no Next.js; build-time Node only; one token set; nothing carrying tenant data is cacheable.
- [Source: ARCHITECTURE-SPINE.md#AD-30] — offline packaging, cosign, everything pinned by digest (why the pgvector image is digest-pinned).
- [Source: ARCHITECTURE-SPINE.md#AD-33] — structural properties are static checks; the three verbs; the harness lives in `checks/`.
- [Source: ARCHITECTURE-SPINE.md#AD-45] — exactly three egress paths; the egress check owned in `checks/` (1.12).
- [Source: ARCHITECTURE-SPINE.md#AD-46] — upgrade fails closed; Alembic behind the `pg_dump`-first wrapper (why 1.1's Alembic is empty and un-wrapped).
- [Source: ARCHITECTURE-SPINE.md#Stack] — the pinned version table, verbatim; the Starlette-pin correction (review-versions H4).
- [Source: ARCHITECTURE-SPINE.md#Structural-Seed › Source tree] — the prescribed directory layout reproduced above.
- [Source: epics.md#Epic-1] — "A firm installs APX, and it is safe from the first minute"; DoD; FR coverage.
- [Source: epics.md#Story-1.1] — the user story and acceptance criteria (the spine of this file).
- [Source: epics.md#Story-1.2] — the offline-fitness CI job that will drive this structure.
- [Source: epics.md#Story-1.12] — the structural-properties harness that extends `checks/` beyond the layering rule.
- [Source: epics.md#Additional-Requirements] — "no starter/paved path"; the prescribed source tree; the full list of structural checks (1.12's scope).
- [Source: docs/context/05-stack-research-2026-07.md#8] — "Target Python 3.13, not 3.14"; the Starlette 1.0/FastAPI pin trap; framework sanity check (Django near-miss, Next.js rejected).
- [Source: docs/context/06-postgres-managed-tier-check-2026-07.md] — Supabase dev tier is PG 17 (cannot BYO image); Railway/on-prem PG 18.4; the PG17↔PG18 parity rationale.
- [Source: CLAUDE.md] — language rule (docs/code English, French terms of art stay French); `../apx-platform/` is reference-only, never an edit target.

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List

## Open Questions for the human

1. **Raise the Python pin from 3.12 to 3.13 now?** The root `.python-version` currently reads `3.12`; the spine's target is **3.13.14** ([Stack]; docs/context/05 §8). This story assumes we raise it. `uv` fetches and manages 3.13 independently of the system Python, so the risk is low and no product code depends on 3.12 yet — but the root pin also governs any repo-level Python tooling, so confirm nothing outside `apx/` expects 3.12 before flipping it. **Recommendation: raise to 3.13.14 in this story.**
2. **`apx/web/` nested vs. repo-root `web/`.** The spine nests the SPA under `apx/`, which puts a non-Python npm project inside the Python package directory. It works (excluded from the wheel), but a repo-root `web/` sibling to `apx/` is the more conventional monorepo shape. Default taken: follow the spine (`apx/web/`). Confirm, or approve relocation.
3. **Tooling choices the spine left unnamed** (all `[ASSUMPTION]`): **import-linter** for the layering rule, **pytest** as the test runner, **GitHub Actions** as CI, **npm** as the JS package manager. AD-33 only requires "grep, lint, import-graph or architecture rule". Confirm these, or substitute (e.g. `tach` for import-graph, `pnpm` for JS) — whatever is chosen, the lockfile must be committed.
4. **pgvector image digest.** 1.1 pins `pgvector/pgvector:pg18` by digest and requires the running extension to be **0.8.5** exactly (AD-5). The dev must resolve a digest whose image actually ships PostgreSQL 18.4 + pgvector 0.8.5; if no single public tag provides that pair, flag it — it may force a custom image build earlier than the deploy story.
5. **PG17↔PG18 parity check is deferred** (rationale: an empty schema has nothing to diverge). Confirm it lands with the first schema-bearing story (1.3) or the store unit, driven over the matrix Task 8 made parameterizable — not in 1.1.
