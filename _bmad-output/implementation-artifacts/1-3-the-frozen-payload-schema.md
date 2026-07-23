---
baseline_commit: 493b8c8c32f58c7ca718bcd983951498a767223a
---

# Story 1.3: The frozen payload schema

Status: review

## Story

As a lawyer whose matters must stay walled apart for years,
I want every indexed *chunk* to carry a complete, versioned provenance record that cannot be written incomplete,
so that the one decision that cannot be undone later — what travels on every *chunk* — is made once and made right.

**Scope in one line:** the `piece` and `chunk` tables and the **one** *chunk* writer, with the payload's mandatory fields, the separate addressable full text, the date-vs-ingestion split, and the one-writer + no-scope-column structural checks. The first real Alembic migration. **No retrieval, no embedding, no ingestion pipeline** — those consume this schema in their stories.

> **This is the increment's only irreversible decision.** Adding a mandatory field later means re-indexing every installed site, blind. The reviews for this story are the full three-reviewer pass (unlike the infrastructure stories).

## Acceptance Criteria

> **Given** the *payload schema* writer, **When** a *chunk* is written, **Then** it carries every mandatory non-nullable field — *tenant*, *matter*, *RBAC scope*, *custodian*, source *pièce* identifier, source position, extraction method and extractor version, schema version, ingestion timestamp, and the *pièce*'s own date or an explicit "undetermined" (FR-8).
> **And** the full extracted text of a *pièce* is stored addressably, separately from its *chunks*, with its own identity and version recorded on the *pièce*.
> **And** the *pièce*'s borne date and its ingestion date are stored separately and neither is ever substituted for the other.
> **And** a static check asserts there is exactly one *chunk* writer, that it takes *RBAC scope* as a required argument, and that no default value for that argument exists anywhere in source (FR-8, FR-56; per AD-40 scope is a write-time check, never a column, and the permitted `chunk` columns are enumerated).
> **And** *(failure path)* a *chunk* write missing any mandatory field is rejected at the boundary, fails the *import job* loudly, and enters the *failure register* — never written with a default, never with an empty *RBAC scope*.
> **And** *(failure path)* an *import job* that spans a schema or chunking version change completes under the versions it started with, or halts and restarts — it never produces two generations of *chunks* inside one *matter*.

1. **AC1 — The payload is complete and non-nullable.** Every `chunk` row carries, all `NOT NULL`: `tenant`, `matter`, `custodian`, `source_piece_id`, `source_position`, `extraction_method`, `extractor_version`, `schema_version`, `chunking_config_version`, `ingestion_timestamp`, `piece_date` (nullable) **paired with** `piece_date_status` (`NOT NULL`, ∈ {`determined`,`undetermined`}). A DB-level constraint enforces that `piece_date IS NOT NULL` iff `piece_date_status = 'determined'`.
2. **AC2 — RBAC scope is a write-time check, never a column** *(the reconciliation of FR-8 with AD-40/AD-13)*. The `chunk` table has **no** `rbac_scope` column. Scope is derived from `matter` at query time via the authoritative scope table (AD-13). The writer takes `rbac_scope` as a **required argument** and verifies at write time that the caller is authorised for the `matter`'s scope; it does not persist it. "Carries RBAC scope" (FR-8) means *written under an authorised scope*, not *stored as a field*.
3. **AC3 — Full text stored addressably, separate from chunks.** A `piece` row holds the full extracted text (the target of FR-13's exhaustive search), with a `text_identity` and `text_version` recorded on the `piece`. Chunks reference their `piece`; the full text lives once, on the piece, not duplicated per chunk.
4. **AC4 — Piece identity is `(content_hash, matter)`** (AD-40): the same file in two matters is two pieces; provenance path is an attribute, not identity. Chunk identity is `(piece_id, position, chunking_config_version)` — deterministic, never from a restarting counter.
5. **AC5 — One writer, enumerated columns, no default scope, no cascade FK.** A static check asserts: exactly one function writes a `chunk`; it takes `rbac_scope` as a required parameter with **no default anywhere in source**; the `chunk` model's columns are exactly the enumerated permitted set (no `rbac_scope` column present); and no `chunk`/`piece` foreign key uses `ON DELETE CASCADE` (AD-7 — a `retired` state instead).
6. **AC6 — Failure paths.** A write missing any mandatory field is rejected at the writer boundary, fails loudly, and produces a *failure-register*-shaped error (the register table is 2.6; here the writer raises a typed error carrying the reason) — never a default, never an empty scope. And a version guard: a writer refuses to write a `chunk` whose `schema_version`/`chunking_config_version` differ from the ones an in-flight *import job* started with (the job is stamped with its versions; a mismatch halts rather than mixing generations in one matter).
7. **AC7 — The migration runs and reverses.** The first Alembic migration creates `piece` and `chunk` (and the authoritative `matter_scope` table AC2 needs), runs green against PostgreSQL 18/17 + pgvector, and is exercised in CI at reduced scale; the offline fitness driver's `index` stage stays PENDING (indexing is 2.8) but a new `schema` assertion confirms the tables exist after migration.

## Tasks / Subtasks

- [x] **Task 1 — Domain: the payload record and identity functions** (AC: #1, #2, #4) — pure `apx/core/domain`, no DB. The `PayloadRecord` dataclass (the enumerated mandatory fields, no `rbac_scope`); the deterministic `piece_id(content_hash, matter)` and `chunk_id(piece_id, position, chunking_config_version)`; the `piece_date`/`piece_date_status` invariant as a domain validation.
- [x] **Task 2 — Port: the Store write contract** (AC: #2, #5) — `apx/core/ports`: a `ChunkWriter` protocol whose single method takes the payload **and** `rbac_scope` as a required argument (no default). The port is where "one writer, scope required" is expressed; the adapter implements it.
- [x] **Task 3 — Adapter: SQLAlchemy models + the one writer** (AC: #1–#6) — `apx/adapters/store_postgres`: the `piece`, `chunk`, `matter_scope` models (enumerated columns, NOT NULL, the CHECK constraint, no cascade FK, no `rbac_scope` column on `chunk`); the **single** `write_chunk(...)` implementation that validates completeness, checks scope authorisation against `matter_scope`, and enforces the version guard. Full text on `piece`.
- [x] **Task 4 — The first Alembic migration** (AC: #7) — a real migration creating the three tables + constraints; runs up and down; `DATABASE_URL` from env (already wired in 1.1).
- [x] **Task 5 — Structural checks** (AC: #5) — extend `apx/checks`: (a) exactly one `chunk` writer (import-graph / AST — the only caller-visible write path); (b) `rbac_scope` is a required param with no default (AST scan of the writer signature); (c) the `chunk` model carries none of a forbidden column set (`rbac_scope`); (d) no `ON DELETE CASCADE` on `chunk`/`piece` FKs. Each with a failure-path fixture proving it fires (the 1.1/1.2 pattern). Register in the harness with the per-contract floor.
- [x] **Task 6 — Tests** (AC: all) — domain unit tests (identity determinism, the date invariant); an integration test against a real PostgreSQL (via the compose service or a CI service container) that writes a chunk, rejects an incomplete one, rejects an unauthorised scope, and rejects a version-mismatched write; a migration up/down test.
- [x] **Task 7 — Fitness `schema` stage + verify + commit** (AC: #7) — add a `schema` assertion to the fitness driver (tables exist post-migration); full green (checks, harness, tests, migration, web, compose); README schema section; the three-reviewer pass.

## Dev Notes

- **The RBAC-scope reconciliation is the subtlety that must not be gotten wrong** (AC2). FR-8's text lists "RBAC scope" among the chunk's mandatory fields; AD-40 and AD-13 (the amendment made during the 1.1-era architecture work) say scope is resolved at query time from a single authoritative source and is **never denormalised onto indexed rows**. The resolution, locked here: scope travels as a **required write-time argument** that the writer *checks* against the `matter`'s authoritative scope, and the durable scope lives in `matter_scope` (matter → scope), joined at query time. No `rbac_scope` column on `chunk`. This is what makes a re-scope take effect at the next query with nothing to propagate (the FR-49 amendment). Getting this wrong — a raw scope column — reintroduces the stale-wall defect and the blind re-index. [Source: ARCHITECTURE-SPINE.md#AD-13, #AD-40; PRD FR-8, FR-49 amendment]
- **Piece vs chunk split** (AC3, AC4): full text on `piece` (FR-13's exhaustive-search target, stored once), payload provenance on `chunk` (self-describing). Piece identity `(content_hash, matter)`; chunk identity `(piece_id, position, chunking_config_version)`. No cascade FK (AD-7); deletion is a `retired` state, added by the story that needs it — 1.3 just forbids cascade.
- **Version guard** (AC6): the *import job* is stamped with `schema_version` + `chunking_config_version` at start; the writer refuses a chunk under different versions, so one matter never holds two generations. The job/register tables are 2.x — here the writer raises a typed domain error; wiring it to the register is 2.6.
- **This story needs a real PostgreSQL** for the integration test. Use the compose service locally and a CI `services: postgres` container (pgvector image). The migration and the writer are the first code that touches the DB.

### What this story must NOT do

- No embedding/vector column population (embedder story), no chunking *algorithm* (just the id + config-version contract), no retrieval, no ingestion pipeline, no failure-register *table* (2.6 — here a typed error), no auth beyond the scope-authorisation check against `matter_scope` (the grant mechanics are 1.6). Building any is a scope violation.

### Testing standards

Domain tests pure and fast; the DB integration test gated on a reachable PostgreSQL (skipped with a clear message if absent locally, run for real in CI). Structural checks are static (AD-33), each with a failure-path fixture. Tests unreachable from runtime (AD-16).

### References

- [Source: PRD FR-8] — the payload schema, verbatim mandatory fields.
- [Source: ARCHITECTURE-SPINE.md#AD-40] — scope is a write-time check, never a column; enumerated chunk columns.
- [Source: ARCHITECTURE-SPINE.md#AD-13] — scope resolved at query time from a single authoritative source.
- [Source: ARCHITECTURE-SPINE.md#AD-7] — no cascade FKs; a `retired` state instead of DELETE.
- [Source: ARCHITECTURE-SPINE.md#AD-5] — PostgreSQL the one stateful service; pgvector.
- [Source: PRD FR-49 amendment (2026-07-22)] — re-scope takes effect at the next query with nothing to propagate.
- [Source: implementation-artifacts/1-1, 1-2] — the structural-check + failure-path-fixture + floor pattern this story reuses.

## Dev Agent Record

### Agent Model Used

Claude Opus 4.8 (1M context) — Claude Code dev-story workflow.

### Debug Log References

- `uv run pytest -q` → **182 passed, 8 skipped** (the 8 skips = PostgreSQL-gated tests, run in the CI `db` job).
- `uv run python -m apx.checks` → **5 passed** (import contracts + the 4 new frozen-schema checks).
- `uv run python -m apx.fitness` → **3 asserted, 9 pending** (new ASSERTED stage: *frozen payload schema defined*).
- `uv run ruff check .` → clean. `alembic heads` → single head `0009_chunk_payload_schema`.

### Completion Notes List

- **The scope/custodian reconciliation (AC2, generalised — the subtlety the story flags).** FR-8 lists both *RBAC scope* and *custodian* among a chunk's "mandatory fields", but AD-9 states plainly that **no column named or aliased as a scope or a custodian exists on `chunk`, `piece` or `full_text`**, and AD-13/AD-40 make scope a query-time resolution. AC2 spells the reconciliation out for scope only; I extended the *same* reading to custodian, since AD-9 treats them identically. Locked: `rbac_scope` is a **required write-time argument** the writer checks against `matter_scope` and never persists; *custodian* is piece-level provenance (kept on the existing `piece`, never a `chunk` column). "Carries X" (FR-8) means *written under an authorised/attributed X*, not *stored as a chunk field*. A raw scope/custodian column on `chunk` fails the build (check `chunk_columns_enumerated`).
- **Environment reconciliation (recorded per the 1.1 deviation convention).** `piece` and `matter_scope` already existed from the pre-BMAD ad-hoc build (migrations 0001/0002) and already satisfied most of AC1/AC3/AC4 (piece identity `(content_hash, matter)`, the `piece_date`/`piece_date_status` CHECK, full text on the piece). Story 1.3's real work against the live tree was therefore: the **`chunk` table**, the **one `write_chunk` writer**, the **domain payload record + `chunk_id`**, the **`ChunkWriter` port**, the **structural checks**, and the missing **`text_identity`** on `piece` (AC3). The "first Alembic migration" (AC7) is delivered *in substance* as `0009` — the first migration to create the frozen `chunk` schema — rather than re-creating tables that already exist.
- **`text_identity` (AC3).** Added to `piece` (AD-10: the full text is a first-class artefact with its own identity beside its version). Migration `0009` adds the column, backfills existing rows with the exact hash the writer computes (`encode(sha256(convert_to(full_text,'UTF8')),'hex')`), then sets `NOT NULL`. The ad-hoc `save` path was updated to set it (kept green).
- **Embedding trio deferred (per story scope).** `chunk` carries AD-9's non-embedding enumeration plus the reserved `external_ref`; the `halfvec` vector and `model_id`/`model_version` are the embedder story (2.8). The structural column check permits the full AD-9 set and forbids anything else (esp. scope/custodian), so 2.8 adds them without a schema fight.
- **The writer writes only the `chunk` row** (the piece pre-exists via the FK), but validates the **whole** payload for completeness — so a chunk can never be indexed under incomplete provenance (AC6) — and enforces the version guard against the versions it was stamped with at construction (the import job's generation, AD-40). Idempotent by deterministic `chunk_id` (`merge`, never a duplicate).
- **Migration up/down (AC7 / Task 6).** Reversibility is exercised by the existing CI `db` job steps (`alembic upgrade head → downgrade base → upgrade head`), which now include `0009`; the pytest DDL assertions (enumerated columns, no-cascade FK, `text_identity NOT NULL`, FK-refuses-missing-piece) run there too against `pgvector/pgvector:pg18`.
- **Open Questions 1–3 resolved with the story's recommended defaults:** (1) `1.3` reuses/extends the minimal `matter_scope` (matter, tenant, scope); (2) chunks store no own text copy — the span is derivable from `piece.full_text` + `position`; (3) the integration tests run against a real PostgreSQL in CI and skip locally with a clear message. A SQLite pass additionally covers the writer's guard logic on every machine.

### File List

**New**
- `apx/core/domain/payload.py` — `PayloadRecord` + validation + typed `IncompletePayload`.
- `apx/core/ports/store.py` — the `ChunkWriter` protocol.
- `apx/adapters/store_postgres/chunk_writer.py` — the one `write_chunk` (`ChunkStore`), `UnauthorizedScope`, `VersionMismatch`.
- `apx/adapters/store_postgres/migrations/versions/0009_chunk_payload_schema.py` — the migration.
- `apx/checks/payload_schema.py` — the four structural checks.
- `tests/domain/test_payload.py`, `tests/adapters/test_chunk_writer.py`, `tests/adapters/test_chunk_writer_postgres.py`, `tests/checks/test_payload_schema_checks.py`.
- `tests/_fixtures/payload_schema_violations/{two_writers,scope_defaulted,forbidden_column,cascade_fk}/*.py` — the failure-path fixtures.

**Modified**
- `apx/core/domain/identity.py` — added `chunk_id(piece_id, position, chunking_config_version)`.
- `apx/adapters/store_postgres/models.py` — the `Chunk` model; `piece.text_identity`; imports.
- `apx/adapters/store_postgres/store.py` — `save` sets `text_identity`.
- `apx/checks/__main__.py` — registered the four payload-schema checks.
- `apx/fitness/driver.py` — new `schema` ASSERTED stage; the checks stage runs the full registry.
- `tests/adapters/test_store_postgres.py` — the direct INSERT includes `text_identity`.
- `README.md` — the frozen-payload-schema section; status; the not-yet table.

### Change Log

| Date | Change |
|---|---|
| 2026-07-23 | Implemented story 1.3 — the frozen payload schema: `chunk` table + one `write_chunk` writer (completeness / scope / version guards), `PayloadRecord` domain + `chunk_id`, `ChunkWriter` port, `piece.text_identity`, migration `0009`, four structural checks with failure fixtures, fitness `schema` stage. 182 passed / 8 skipped, checks + ruff green. Status → review. |

## Open Questions for the human

1. **`matter_scope` shape.** AC2 puts the authoritative scope in a `matter_scope` table (matter → scope). Story 1.4 (tenant isolation) and 1.6 (grant-time authorisation) own the *grant* mechanics; 1.3 needs only enough of `matter_scope` for the write-time check. Confirm 1.3 may create a minimal `matter_scope` (matter, scope) that 1.4/1.6 extend, rather than waiting for them.
2. **Chunk text vs piece text.** The design stores full text on `piece` (once) and provenance on `chunk`; a chunk's own text span is derivable from `piece.full_text` + `source_position` rather than duplicated. Confirm chunks do not store their own text copy in 1.3 (the embedding/vector column is a later story anyway).
3. **CI PostgreSQL.** The integration test needs a real DB. Confirm a CI `services: postgres` (pgvector image) is acceptable, and that the local integration test may skip (with a clear message) when no DB is reachable.
