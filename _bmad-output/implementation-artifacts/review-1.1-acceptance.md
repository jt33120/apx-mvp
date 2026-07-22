# Acceptance Review — Story 1.1 (Repository born from empty, layering rule enforced)

**Auditor:** Acceptance Auditor
**Date:** 2026-07-22
**Diff:** `story-1.1.diff` (1110 lines, 43 files added)
**Verdict:** **All 5 acceptance criteria met. Scope respected — no over-delivery.** Two low-severity findings only, both deviations rather than unmet criteria (one recorded/deferred, one silent). No blocking violation.

---

## AC-by-AC result

| AC | Criterion | Result | Evidence |
|----|-----------|--------|----------|
| AC1 | Source tree matches spine layout | **MET** | Every prescribed package present with `__init__.py` + layer docstring: `apx/core/{domain,ports,app,app/read}`, `apx/adapters/{store_postgres,embedder_bgem3,llm_openai_compat,extraction,ocr_tesseract}`, `apx/api`, `apx/worker`, `apx/web`, `apx/checks`, `apx/eval`, top-level `tests/` + `deploy/`. Diff lines 310–676, 498–520, 838–865. Nothing missing or misnamed. |
| AC2 | Harness green on empty | **MET** | `apx/checks/__main__.py` runs registered checks, exits non-zero on any failure (diff 528–580); registers exactly one check (layering). On the empty tree no `apx.core` module imports `apx.adapters`, so `lint-imports` returns 0. Dev record reports 8/8 green; structurally sound. |
| AC3 | Pinned versions in lockfiles | **MET** (image portion recorded-deferred — see F1) | `uv.lock`: starlette **1.3.1** (trap honored), fastapi 0.139.2, uvicorn 0.51.0, pydantic 2.13.4, sqlalchemy 2.0.51, psycopg 3.3.4, alembic 1.18.5, procrastinate **3.9.0**, pgvector(py) 0.4.2. `package-lock.json`: vite **8.1.5**, react-router **8.2.0**, react/react-dom 19.2.8, typescript 5.9.3. All lockfile-locked deps exact. |
| AC4 | Layering check enforced | **MET** | `[tool.importlinter]` forbidden contract `source_modules=[apx.core]`, `forbidden_modules=[apx.adapters]` (diff 975–982); `apx/checks/layering.py` runs `lint-imports` as subprocess and propagates exit code (581–640); CI runs `uv run python -m apx.checks` (diff 30). |
| AC5 | Failure path proves check is live | **MET** | Violating fixture `tests/_fixtures/layering_violation/` (`core_fake` imports `adapter_fake`, diff 1015–1053) + permanent regression `tests/checks/test_layering_check.py` asserting real tree PASSES and fixture REPORTS a violation with non-zero exit and `core_fake` named (1054–1110). Manual demo documented in README (diff 129–135). |

### The version trap (AC3, explicit)
`uv.lock` resolves **starlette == 1.3.1 exactly** — verified by direct read. FastAPI 0.139.2's `starlette>=0.46.0` open lower bound spanning the 0.46→1.x major did **not** produce a transitive bump. The trap the reviews flagged (review-versions H4) is honored. Vite 8.1.5 and React Router 8.2.0 are likewise exact in `package-lock.json`.

---

## Findings

### F1 — Postgres/pgvector image pinned by mutable TAG, not digest; PG 18.4 + pgvector 0.8.5 asserted only in comments — LOW (acceptable, recorded-deferred)
- **Constraint:** AC3 ("PostgreSQL 18.4, pgvector ≥ 0.8.5 declared and committed"); Task 8 subtask "Pin by digest".
- **Evidence:** `deploy/docker-compose.yml:30` — `image: ${POSTGRES_IMAGE:-pgvector/pgvector:pg18}` is a floating tag, not a digest. The `pg18` tag does not lock server to **18.4**, and pgvector **0.8.5** appears only as a comment + runtime `SELECT extversion` instruction (compose lines 21–22), never pinned. Task 8's `[x] Pin by digest` checkbox is thus not literally satisfied by the diff.
- **Disposition:** **Acceptable — recorded deviation.** The story's own Dev Notes relax this ("the invariant is the extension contract … not the server patch number"), Open Question #4 explicitly defers digest resolution, and Completion Notes record it ("Deferred as planned: #4 pgvector image digest"). Not a lockfile item; nothing in 1.1 runs a DB. No action required in 1.1, but the digest + `== 0.8.5` runtime assertion must land with the first DB-bearing story (1.3) as promised.

### F2 — `psycopg[binary]` extra added silently vs spec's plain `psycopg==3.3.4` — LOW (silent deviation / nit)
- **Constraint:** Task 3 and Dev Notes version table both specify `psycopg==3.3.4` (no extra); AD-28 flags psycopg's LGPL-3.0-only, **in-process** position "to counsel".
- **Evidence:** `pyproject.toml:941` — `"psycopg[binary]==3.3.4"`; `uv.lock` confirms `psycopg` extra `["binary"]`. The `[binary]` extra is not mentioned in Task 3, the version table, or the Completion Notes — a silent choice.
- **Disposition:** Version is identical (3.3.4); only the wheel-selection extra differs. Harmless for scaffolding, but `psycopg[binary]` is the vendor-discouraged production choice and the addition is undocumented. Per the review rubric a silent deviation is a finding. Recommend either dropping `[binary]` or recording the rationale.

---

## Over-delivery / scope audit ("What this story must NOT do") — CLEAN

Every forbidden item checked against the diff; none built:
- **Schema/tables/migrations:** Alembic env is empty — `target_metadata = None`, `versions/.gitkeep` only, no revision scripts (diff 403, 495). ✓
- **Auth/sessions/PyJWT:** none present; no `pwdlib`, `PyJWT`, `argon2` in `pyproject.toml`. ✓
- **Encryption / start-up gate:** none. ✓
- **Tenancy write-boundary / read-path:** `apx/core/app/read/__init__.py` is docstring-only (diff 655–661). ✓
- **Config/provisioning surface:** none. ✓
- **Content-free projection / egress check:** none. ✓
- **Backup/restore/upgrade.sh/cosign:** none; compose comments defer `upgrade.sh` to 1.11. ✓
- **Embedder/extraction/OCR/LLM/ML weights:** all adapter packages docstring-only; no such runtime deps. ✓
- **Structural checks beyond layering:** `CHECKS` registry holds exactly `[layering.run]` (diff 557–559); finer contracts commented "tightened in 1.12" (diff 984–993). ✓
- **HTTP routes / worker tasks:** `apx/api/app.py` = `FastAPI(...)` with zero routes (diff 520); `apx/worker/app.py` = Procrastinate `App` with zero tasks + in-memory connector placeholder (diff 865). ✓

No scaffolding quietly does more than scaffolding.

---

## Deviations: recorded vs silent

**Recorded (notes, not findings):** react/react-dom 19.2.0→**19.2.8** (react-router 8.2.0 peer), `@vitejs/plugin-react`→**6.0.4** (5.x caps at Vite 7), `@types/react(-dom)` added, Node built locally with v26 (target `.nvmrc` = 24.18.0, build-time only). All in the Dev Agent Record; the exact-pin-in-lockfile intent is preserved and Vite/React-Router stay exact.

**Silent (findings):** F2 (`psycopg[binary]`). F1 is recorded-but-deferred rather than silent.

**Conclusion:** the diff faithfully implements Story 1.1. All five ACs are met, the Starlette 1.3.1 trap and the Vite/React-Router pins hold in the committed lockfiles, scope is respected in both directions, and the only two findings are low-severity deviations — one sanctioned by the story's own Open Questions, one a harmless-but-undocumented dependency extra.
