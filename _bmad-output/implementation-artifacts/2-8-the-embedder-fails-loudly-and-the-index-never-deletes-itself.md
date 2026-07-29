---
baseline_commit: c216f47
---

# Story 2.8: The embedder fails loudly and the index never deletes itself

Status: done

## Story

As a firm whose *corpus* took days to build,
I want embedding to stop the work rather than degrade silently, and no automatic process to ever wipe the index,
so that one transient error cannot turn retrieval into noise or destroy the *corpus*.

## Scope note — the embedder + the index write path; real inference & the vector query are the Postgres leg

This story lands the **one real `Embedder`** the whole product has reserved (the port `apx/core/ports/embedding.py` + the empty `apx/adapters/embedder_bgem3/` package), wires embedding into the ingestion pipeline as a **precondition of corpus admission**, adds the **embedding trio** (the `halfvec` vector + `model_id` + `model_version`) the `Chunk` schema reserved for "story 2.8", and makes the two already-live structural properties (`embedder_has_one_implementation`, `destructive_index_ops_single_entry`) **non-vacuous** and green.

Two things are the **Postgres leg** (a `tests/adapters/test_*_postgres.py` skipped without a PostgreSQL `DATABASE_URL`, the established pattern): the real `halfvec` column write and any vector query. Three things are **deferred, faithfully**: the **real chunking** into passages with provenance (Story 2.9 — this story writes one whole-piece chunk as the placeholder `chunking_config_version`, which 2.9 re-chunks under a new version, retiring the old by state per AD-40); the **visual worklist line** (Story 2.11 — the durable open register entry *is* the worklist line, the Story 2.6 split); and the **chunk-write on a *successful retry***. On the forward path a pièce enters the corpus only WITH its chunk (embed-before-admission). The retry *primitive* (`retry_failure`, Story 2.6) resolves an embedder-failure entry when re-ingestion recovers the pièce; coupling that resolve with re-embedding + the chunk write — so a retried pièce is immediately searchable — is the job of the **retry handler**, which lands with the worklist/retry UX (Story 2.11), exactly as the retry HTTP surface itself was deferred from Story 2.6. Until then there is no way to *trigger* a retry (no endpoint), so no retry-recovered-without-a-chunk pièce exists in production; the store primitive is tested (a still-failing retry keeps the entry open with its class). Real BGE-M3 inference runs only where its dependency is installed (the offline deployment); the suite substitutes a fake `Embedder` **at the port boundary inside the test process** (AD-11), never a stub in the runtime tree.

## Acceptance Criteria

Verbatim from [epics.md §Story 2.8](_bmad-output/planning-artifacts/epics.md) (FR-9 the embedder fails loudly, FR-10 the index never self-deletes, FR-56 structural; AD-11 the embedder is swappable/one-impl/1024-dim halfvec, AD-7 nothing hard-deleted, AD-38/SM-3 the denominator, AD-17 the ledger, AD-16 one ingestion path). Each AC is decomposed into the assertion the dev must make fire.

**AC1 — Any embedder failure halts the affected unit, records it in the register with its class, generates a worklist line, and never produces a chunk (FR-9).**
Given the embedder, when it fails — unavailability, rate limit, timeout, dimension mismatch, auth failure — then it halts the affected unit, records it in the *failure register* with its **error class**, generates a *worklist* line, and **never produces a *chunk*** (FR-9).
- *Assert:* the `Embedder` adapter raises a **typed** failure (a small exception taxonomy — unavailable / rate-limited / timeout / dimension-mismatch / auth-failed); the ingestion pipeline catches it and records **one open `Failure`** with the matching **new `ErrorClass`** (append-only set), `cardinality` `one`, a **redacted** diagnostic (AD-28), and **writes no `Piece` and no `Chunk`** for that unit. The durable register entry is the worklist line (its visual render is Story 2.11). A failure is retryable via the Story 2.6 retry.

**AC2 — There is no fallback embedder: exactly one non-test implementation, no exception handler constructs an embedder, no config selects one outside the enumerated list (FR-9, FR-56).**
Given the artefact, then the `Embedder` interface has **exactly one non-test implementation**, **no exception handler in the embedding path constructs an embedder**, and **no configuration key selects one by name outside the enumerated provider list** (FR-9/AD-11; the v1 defect was a silent 1024→256 hash fallback on any exception).
- *Assert:* `forward_looking.embedder_has_one_implementation` is **green and non-vacuous** — exactly one concrete embedder class (in `apx/adapters/embedder_bgem3/`, method `encode`/`embed`), none constructed in an `except` handler (the adapter **raises** on failure, never falls back), and every test double lives under `tests/` (injected at the port boundary, never in the runtime tree). No hash/bag-of-words/non-semantic embedder exists at runtime under any configuration. Per AD-11 ("no configuration-as-data key … selects one") there is **no embedder config key at all** — the one impl is hardcoded and stamps every chunk with its own `model_id`/`model_version`, so a config label can never diverge from the model that produced the vector. The check is hardened to count a class by the port SHAPE (`dimensions` + an embed/encode method), so a disguised fallback named anything is still caught.

**AC3 — No code path performs a bulk deletion/recreation/truncation of indexed material in response to any error/schema/dimension/version difference; destructive ops are reachable from exactly one named administrative entry point (FR-10, FR-56).**
Given the index write path, then no runtime code path bulk-deletes, recreates or truncates a *tenant*'s indexed material in response to an error, a schema mismatch, a dimension mismatch or a version difference; the destructive operations are reachable from **exactly one named administrative entry point**, asserted statically (FR-10/AD-7; the v1 defect wiped the whole collection on a vector-size mismatch).
- *Assert:* `forward_looking.destructive_index_ops_single_entry` is **green** — the vector write path is **INSERT-only** (a chunk row with its vector), with **no** `drop_index`/`delete_collection`/`recreate_*`/`truncate`/raw `DROP`/`TRUNCATE` reachable from more than one runtime function. Index DDL (the pgvector extension + the HNSW index) lives in an **alembic migration** (exempt from the check). A dimension/schema/version mismatch **raises** (halts the unit → register entry), it never deletes.

**AC4 — A dimension or schema mismatch halts that unit, surfaces a worklist line, and leaves the existing corpus intact and queryable; recovery does not require a full re-index.**
Given a *chunk* whose embedding dimension (or schema/version) does not match the existing *corpus*, when it is processed, then that unit halts, an actionable register/worklist line naming the mismatch is written, and the existing *corpus* stays **intact and queryable**; recovery does **not** require re-indexing the whole *corpus* (FR-10).
- *Assert:* a dimension-mismatch failure records an `embedder-dimension-mismatch` register entry and writes no chunk; every previously-indexed pièce is unchanged and still readable; the only recovery is the per-entry retry (no bulk re-index, no self-delete).

**AC5 — (failure path) Injecting a transient embedder failure into a multi-pièce job leaves some indexed, the failed ones in the register, the denominator consistent, and a retry that completes them (FR-9).**
Given an *import job*, when a transient embedder failure is injected, then some *pièces* are indexed, the failed ones are in the *failure register*, the *denominator* is **consistent** (`submitted_pieces == in_corpus + open_register_entries`, SM-3), and a retry completes them (FR-9).
- *Assert:* a job over N pièces with an embedder that fails on a subset yields: the succeeded pièces in the corpus **with chunks + vectors**, the failed ones as open register entries (their class), `store.inventory(...).is_consistent()` **true** throughout (a failed pièce is a register entry, **never** also a corpus pièce — no double count). The failed entries are **retryable** (`retry_failure`, Story 2.6): a retry that re-embeds and still fails keeps the entry open with its class; a retry that succeeds resolves it, and the chunk write on that successful retry is the retry handler's job (Story 2.11 — see the scope note). *(The real `halfvec` write/query is the Postgres leg; the register/no-chunk/denominator/retry semantics are asserted on the SQLite store with an injected failing fake embedder.)*

## Tasks / Subtasks

> Red-green-refactor, in order. Gate after each with `export PATH="$PWD/.venv/bin:$PATH"` then `.venv/bin/ruff check .`, `.venv/bin/python -m pytest` (**NO** `DATABASE_URL` override), `.venv/bin/python -m apx.checks`, and `alembic upgrade head` + a reversible downgrade for the migration task. The Postgres-only leg (real halfvec) runs under a `DATABASE_URL=postgresql://…` and is skipped otherwise.

- [x] **Task 1 — The embedding trio on `Chunk` + a dialect-portable vector type + migration 0021 (AC1, AC3).**
  - New `apx/adapters/store_postgres/vector_types.py`: a `Halfvec(dim)` `TypeDecorator` (mirror `crypto_types.EncryptedText`) with `load_dialect_impl` — the pgvector `HALFVEC(dim)` on PostgreSQL (the `pgvector` helper is already a dependency), a portable type (`JSON`, a list of floats) on SQLite so `Base.metadata.create_all` works in the in-memory tests. `cache_ok = True`.
  - Extend [models.py::Chunk](apx/adapters/store_postgres/models.py) with the trio the docstring reserves for 2.8: `model_id: Mapped[str]` (String, NOT NULL), `model_version: Mapped[str]` (String, NOT NULL), `vector: Mapped[list[float]]` (`Halfvec(1024)`, NOT NULL). No cascade FK (AD-7) — unchanged. Update the class docstring (drop "added by the embedder story (2.8)"; state the trio is now present).
  - The `chunk_columns_enumerated` check ALREADY allows `model_id`/`model_version`/`vector` ([payload_schema.py `_PERMITTED_CHUNK_COLUMNS`](apx/checks/payload_schema.py)) — no check edit. Extend the Postgres-test `_ENUMERATED` set in [tests/adapters/test_chunk_writer_postgres.py](tests/adapters/test_chunk_writer_postgres.py) to include the three (or its `cols == _ENUMERATED` assertion fails).
  - Migration `0021_chunk_embedding.py` (`down_revision = "0020_inventory_denominator"`): `CREATE EXTENSION IF NOT EXISTS vector` (PostgreSQL); add the three columns; create the **HNSW** index on `vector` (`halfvec_cosine_ops`) — index DDL lives HERE (alembic is exempt from the destructive-op check, and creating an index is not destroying one). Reversible downgrade (drop index + columns). Add `1024` as the dimension consistent with AD-11 and the `Embedder.dimensions` port.

- [x] **Task 2 — The embedder failure taxonomy + the register error classes (AC1, AC4).**
  - In [apx/core/ports/embedding.py](apx/core/ports/embedding.py) (or a sibling `apx/core/ports/embedding_errors.py`): a small exception hierarchy `EmbedderError` with `EmbedderUnavailable`, `EmbedderRateLimited`, `EmbedderTimeout`, `EmbedderDimensionMismatch`, `EmbedderAuthFailed`. These are the port's failure contract — the adapter raises them; the pipeline maps each to an `ErrorClass`.
  - Append to [failures.py::ErrorClass](apx/core/domain/failures.py) (append-only, a new comment banner): `EMBEDDER_UNAVAILABLE = "embedder-unavailable"`, `EMBEDDER_RATE_LIMITED = "embedder-rate-limited"`, `EMBEDDER_TIMEOUT = "embedder-timeout"`, `EMBEDDER_DIMENSION_MISMATCH = "embedder-dimension-mismatch"`, `EMBEDDER_AUTH_FAILED = "embedder-auth-failed"`. `cardinality_for` auto-returns `one` (no edit). A one-to-one `EmbedderError → ErrorClass` map (in the app layer); an unclassified embedder exception → `UNKNOWN` with `redacted_diagnostic` (AD-28), never `str(exc)`.

- [x] **Task 3 — The ONE real `Embedder` adapter + its config keys (AC2).**
  - `apx/adapters/embedder_bgem3/bgem3.py`: the single concrete `Embedder` — `dimensions = 1024`, `encode(texts) -> list[list[float]]` (BGE-M3, AD-11 default). **Lazy-import** the model backend (`FlagEmbedding`) INSIDE `encode` so the module imports where the dependency is absent (the extraction/OCR convention); a missing backend raises `EmbedderUnavailable` (fails loud — the AD-11 "no stub" rule). Map backend/HTTP faults to the taxonomy (a 429 → `EmbedderRateLimited`, a timeout → `EmbedderTimeout`, a 401 → `EmbedderAuthFailed`, a returned-width ≠ `dimensions` → `EmbedderDimensionMismatch`). **No `try/except` that constructs or returns a fallback embedder** — the `embedder_has_one_implementation` check fails the build on an embedder built in an `except` handler.
  - Declare the embedder dependency (`FlagEmbedding`, bounded) in `pyproject.toml` per the established lazy-import convention (a comment noting the licence + that it is imported lazily); prefer an **optional extra** if adding it to the base install would pull the heavy `torch` tree into CI — the gate must stay green **without** the model installed (tests inject a fake at the port boundary). Relock `uv` if the environment supports it; otherwise record the relock as a deployment step (the dep declaration is the contract).
  - Config keys ([config.py](apx/core/domain/config.py) `CONFIG_SCHEMA`): `embedding_model` (str, default the BGE-M3 id, `governs=` the embedder, `affects_retrieval=True`), `embedding_model_version` (str), `embedding_dimensions` (int, default 1024). The value is used as **data** (never `if tenant ==`), documented in the README config block (or `config_reference_is_complete` fails). The provider/model must be selected from an **enumerated** set — no arbitrary-name selection (AC2).

- [x] **Task 4 — The chunk write carries the embedding trio; a placeholder whole-piece chunking (AC1, AC5).**
  - Extend [chunk_writer.py::write_chunk](apx/adapters/store_postgres/chunk_writer.py) to accept the embedding trio as **explicit write-time arguments** (e.g. `*, rbac_scope, vector: list[float], model_id: str, model_version: str`) — NOT on `PayloadRecord` (the frozen non-embedding provenance stays frozen; `field_names()`/`test_payload` untouched). Write them onto the `Chunk` row. A `vector` whose width ≠ the column dimension **raises** `VersionMismatch`/a dimension error and writes nothing (AC4 — never a self-delete). This is the single `Chunk(...)` writer (`one_chunk_writer`).
  - A minimal **whole-piece chunking** in the app/domain (one chunk = the piece's `full_text`, `position=0`, a `chunking_config_version` marking it the whole-piece placeholder). Real passage chunking with provenance is Story 2.9 (a new chunking-config-version that retires this one by state, AD-40) — build only the placeholder here, and note the token-limit handling is 2.9's.

- [x] **Task 5 — Embedding as a precondition of corpus admission: the pipeline reshapes the result (AC1, AC5; the load-bearing decision).**
  - Between extraction and persistence, the pipeline embeds each extracted piece's chunk(s). Reshape the `IngestionResult`: on embed **success** the piece stays and yields its chunk-with-vector; on a typed **`EmbedderError`** the piece is **moved from `pieces` to `failures`** (an `IngestedFailure` with the mapped `ErrorClass` + the job custodian) — so an embed-failed pièce is a register entry, **never** in the corpus and **never** a chunk. This keeps `submitted_pieces == in_corpus + open_register_entries` (2.7) consistent by reusing `save`'s piece/failure/watermark logic — a unit is in EXACTLY ONE of corpus / register (Agent-confirmed: `require_consistent()` at `save`/`finish_import` fails loudly on a double count).
  - Wire it at the **worker seam** [queue/__init__.py::_persist_unit](apx/adapters/store_postgres/queue/__init__.py) (between `ingest_one_file` and `store.save`) AND the sync path (`ingest_folder` via `/api/ingest`): the `Embedder` is built **once at the composition root** (`_run_import` / the app), never per unit, and threaded through the `UnitWork` seam. On embed-success, `store.save(pieces)` then `write_chunk(...)` per chunk (the vector computed BEFORE `write_chunk`'s transaction). The core stays adapter-free — the `Embedder` is injected as the port, and embedding orchestration that must touch the store lives in the adapter/app seam, not `core/`.

- [x] **Task 6 — Keep the two structural properties green + update the "vacuous until 2.8" markers (AC2, AC3).**
  - Landing the real adapter makes `embedder_has_one_implementation` **non-vacuous**; its green `detail` changes from `"vacuous until story 2.8"` to naming the one impl. **Update** `tests/checks/test_structural_harness_checks.py::test_forward_looking_checks_name_their_deferral` — the embedder check no longer says "vacuous until" (assert it now names exactly one impl); the index check stays vacuous (INSERT-only). Update the manifest/README "vacuous until 2.8" prose for the embedder property if present.
  - Run `.venv/bin/python -m apx.checks` and confirm BOTH checks green with the real adapter: exactly one embedder impl, none in an `except`, and no destructive index op reachable from >1 function. If BGE-M3's method name differs from `embed`/`encode`, extend `_EMBED_METHODS` in [forward_looking.py](apx/checks/forward_looking.py) (an internal edit to the same callable — no re-registration). Do NOT add a second concrete embedder anywhere under `apx/`.

- [x] **Task 7 — The failure-path job test + the Postgres leg (AC4, AC5).**
  - SQLite store test (`tests/adapters/test_embedding_ingest.py`): a multi-pièce job with an injected **fake `Embedder`** that fails on a subset (and one that always fails one class each — unavailable/timeout/dimension-mismatch) → succeeded pièces in corpus with chunks, failed ones as open register entries with the right class, `inventory().is_consistent()` true, and a `retry_failure`/`bulk_retry` (fake now succeeding) resolves them and writes their chunks. Assert **no `Piece` and no `Chunk`** for a failed unit (AC1), and the existing corpus stays readable after a dimension mismatch (AC4).
  - Postgres leg (`tests/adapters/test_embedding_postgres.py`, `skipif` no `postgresql://` `DATABASE_URL`): a real `halfvec` chunk write via `write_chunk` (a 1024-float vector) round-trips; the HNSW index exists; a nearest-neighbour query returns the row. This proves the pgvector column + index DDL (migration 0021) is real, without burdening the SQLite suite.

- [x] **Task 8 — Gate + docs.** Full green: `ruff`, `pytest` (no regressions — mind the extended `Chunk` model touching `test_chunk_writer`/`_postgres`, the payload untouched, the new ErrorClasses, the updated deferral test), `apx.checks` (both forward-looking checks now non-vacuous/green, lock-step intact), `alembic upgrade head` + reversible downgrade, the `ENCRYPTED_COLUMNS` drift-guard unaffected (the vector is volume-encrypted, not app-encrypted — AD-31/startup.py). Update the `Chunk` docstring, the `embedder_bgem3` package docstring, and the README config-keys block.

## Dev Notes

### The load-bearing decision: embedding is a precondition of corpus admission (so the denominator stays honest)

FR-9 says an embedder failure "records it in the register … and never produces a *chunk*"; AC5 says the failed pièces are "in the register" while "some [are] indexed", with "the *denominator* consistent". Story 2.7's invariant is `submitted_pieces == in_corpus + open_register_entries`, and a unit must be in **exactly one** of corpus / register — a pièce counted as BOTH a `Piece` (in_corpus) AND an open `Failure` double-counts and trips `require_consistent()` (a release blocker). Therefore **a pièce enters the corpus only when its embedding succeeds**: the pipeline embeds *before* persistence and, on a typed `EmbedderError`, **reshapes the result** — the piece is moved from `pieces` to `failures` (with the embedder `ErrorClass`), so it lands as a register entry, not a corpus pièce, and no chunk is written. This reuses `save()`'s existing piece/failure/watermark logic (no new corpus-admission machinery), and the 2.7 tripwire *proves* the no-double-count. A retry re-runs ingestion (re-extract + re-embed) through the Story 2.6 `retry_failure`; on success the entry resolves and the chunk is written.

### The "no fallback / no stub" rule is a hard structural gate (AD-11)

`embedder_has_one_implementation` is **live** (vacuous only because no impl exists yet). The moment the adapter lands it goes non-vacuous, and it fails the build if: there is **more than one** concrete embedder class in the runtime tree (`apx/` minus `checks/`/`fitness/`), OR **any** `except` handler constructs/returns an embedder (the v1 silent-fallback path). So: exactly one class in `apx/adapters/embedder_bgem3/`; **every** test double lives under `tests/` and is injected at the port boundary (AD-11 — "the test tree's fakes are unreachable from any runtime module"); and the adapter's failure paths **raise** the typed error, never fall back to a second embedder or a hash. There is **no stub embedder anywhere** — a missing model backend raises `EmbedderUnavailable`, it does not degrade.

### The index never self-deletes (AD-7 / FR-10)

There is no separate vector store — the vector lives on the `chunk` row, so the "index write path" **is** `write_chunk`, and it is **INSERT-only**. `destructive_index_ops_single_entry` fails the build if any `drop_index`/`delete_collection`/`recreate_*`/`truncate`/raw `DROP`/`TRUNCATE` is reachable from **more than one** runtime function. The pgvector extension + HNSW index DDL live in the alembic migration (exempt). A dimension/schema/version mismatch **raises** (→ register entry, corpus intact); it never bulk-deletes. Any future admin re-index must be a single named entry point.

### Architecture guardrails (binding)

- **AD-11 (the embedder):** 1024-dim `halfvec`; every chunk carries `model_id` + `model_version` (a mixed-provenance corpus is detectable); the embedder is swappable behind the port (changing it is a background migration, never a rebuild — never a self-delete); exactly one non-test impl; no runtime fallback/stub in any environment.
- **AD-7 (nothing hard-deleted):** the index never self-deletes; a mismatch retires/halts by state, never a cascade or a bulk wipe. No `ON DELETE` on the chunk FK (unchanged).
- **AD-38 / SM-3 (the denominator):** an embed-failure is one open register entry (cardinality `one`), no Piece/Chunk — `submitted == in_corpus + open` holds; `require_consistent()` is the tripwire.
- **AD-16 / AD-4 (one ingestion path, core stays pure):** embedding slots into the single ingestion path; the `Embedder` is a port injected at the composition root; `core/` imports no adapter; the embedder is built once, never per unit.
- **AD-28 (no verbatim fragments):** an unclassified embedder exception is recorded with `redacted_diagnostic` (type name only), never `str(exc)` — a provider error message may quote content.
- **AD-31 (encryption at rest):** the `halfvec` vector is a searchable column — it is **volume-encrypted**, not app-encrypted (it can't be, and the boot gate already names it, `apx/api/startup.py`); do NOT add it to `ENCRYPTED_COLUMNS`.
- **AD-33 (structural properties):** both forward-looking checks stay green and become non-vacuous; the "vacuous until 2.8" deferral test is updated in lock-step.

### Files to touch (and blast radius)

- `apx/core/ports/embedding.py` (+ maybe `embedding_errors.py`) — the `EmbedderError` taxonomy.
- `apx/core/domain/failures.py` — the five embedder `ErrorClass` members (append-only).
- `apx/core/domain/config.py` + README — `embedding_model`/`embedding_model_version`/`embedding_dimensions` keys.
- `apx/adapters/embedder_bgem3/bgem3.py` (new) + `__init__.py` (docstring) — the ONE real embedder (lazy dep).
- `apx/adapters/store_postgres/vector_types.py` (new) — the dialect-portable `Halfvec` type.
- `apx/adapters/store_postgres/models.py` — the `Chunk` embedding trio + docstring.
- `apx/adapters/store_postgres/chunk_writer.py` — `write_chunk` carries the trio; the width guard.
- `apx/adapters/store_postgres/migrations/versions/0021_chunk_embedding.py` (new) — extension + columns + HNSW index, reversible.
- `apx/core/app/ingest.py` + `apx/adapters/store_postgres/queue/__init__.py` + `apx/api/app.py` — embed-before-admission (reshape the result), the embedder threaded through the pipeline seam, built once.
- `pyproject.toml` — the embedder dependency (lazy, bounded; optional extra if it would burden CI).
- `apx/checks/forward_looking.py` — only if BGE-M3's method name needs `_EMBED_METHODS` extended.
- Tests: `tests/adapters/test_embedding_ingest.py` (new, SQLite — the failure/register/no-chunk/denominator/retry semantics with a fake embedder), `tests/adapters/test_embedding_postgres.py` (new, PG leg — real halfvec write/query), `tests/adapters/test_chunk_writer_postgres.py` (`_ENUMERATED` extended), `tests/checks/test_structural_harness_checks.py` (the deferral test updated), plus any `test_chunk_writer.py` touched by the trio.

### What NOT to build (scope discipline)

- **Real passage chunking** with provenance to the exact passage — Story 2.9. Write ONE whole-piece chunk as the placeholder; 2.9 re-chunks under a new `chunking_config_version` (retiring the old by state, AD-40).
- **The visual worklist line** — Story 2.11. The durable open register entry is the worklist line (the Story 2.6 split); no screen here.
- **A second embedder / a stub / a hash fallback** — forbidden by AD-11 and the live structural check. One impl, fakes only under `tests/`.
- **Any bulk re-index / collection reset** at runtime — forbidden by FR-10. Index DDL is migration-only; a mismatch raises, never deletes.
- **Real BGE-M3 inference in the suite** — tests inject a fake at the port boundary; the real model runs only where its dep is installed.
- **The judgment LLM / retrieval / ranking** — later epics; this is the embedder + the index write, not search.

### Project Structure Notes

Hexagonal boundaries hold: the `Embedder` **port** + the `EmbedderError` taxonomy are Domain/ports; the ONE concrete embedder is an **adapter** (`embedder_bgem3/`, the only enumerated embedder egress dir in `isolation_harness._EGRESS_ADAPTER_DIRS`); the vector type + chunk write are the store adapter; the embed-before-admission orchestration lives at the app/worker seam (which may touch the store), never in `core/`. The two structural properties live with the build-time checks.

### References

- [epics.md §Story 2.8](_bmad-output/planning-artifacts/epics.md) (the five ACs verbatim); FR-9 ([prd.md:386-395](_bmad-output/planning-artifacts/prds/prd-apx-mvp-2026-07-20/prd.md#L386)), FR-10 ([prd.md:397-405](_bmad-output/planning-artifacts/prds/prd-apx-mvp-2026-07-20/prd.md#L397)).
- `ARCHITECTURE-SPINE.md`: **AD-11** (L336-355, the embedder/1024-halfvec/one-impl/no-fallback — the load-bearing read), **AD-7** (L226, nothing hard-deleted), AD-38/SM-3 (the denominator, Story 2.7), AD-16 (one ingestion path), AD-28 (no fragments), AD-31 (volume-encrypted searchable columns), AD-33 (structural properties).
- Existing seams: the orphaned `chunk_writer.ChunkStore.write_chunk` (the one chunk writer — wire it in); `_persist_unit` (the worker seam) + `_run_import` (the composition root); `quarantine_unit`/`_write_failure`/`retry_failure`/`bulk_retry` (Story 2.6); `_durable_inventory`/`_raise_submitted_watermark`/`_settle_submitted_after_retry` (Story 2.7); `crypto_types.EncryptedText` (the `TypeDecorator` template for `Halfvec`); the two live checks `embedder_has_one_implementation`/`destructive_index_ops_single_entry` + their fixtures; the `pgvector` helper already in `pyproject`.

## Dev Agent Record

### Agent Model Used

claude-opus-4-8 (1M context) — BMAD dev-story.

### Debug Log References

Gate after each task: `ruff check .`, `pytest` (no `DATABASE_URL` override), `python -m apx.checks`. Final (post-review): **ruff clean · 673 passed / 10 skipped · 47 structural checks (both forward-looking checks now non-vacuous-embedder / vacuous-index) · alembic single linear head 0021**. Two structural checks fired on my code during the build: `sensitive_columns_are_encrypted` flagged `Chunk.model_id` (allowlisted — it is categorical embedder identity, AD-11, not content); `no_secret_in_source` flagged the 25-char high-entropy revision id `0021_chunk_embedding_trio` (renamed to `0021_chunk_embedding`, under the token threshold). The embedder adapter was carefully structured so no `embed`-named call sits in an `except` handler (the `embedder_has_one_implementation` heuristic) — the classify helpers build the typed error at module scope and the except only `raise`s their result. The adversarial three-reviewer pass then added six regression tests (double-count-on-re-import, wrong-width-vector, embedder-sourced stamp, two structural evasions, the backup vector round-trip), taking the count 667 → 673 — see the Senior Developer Review (AI) section.

### Completion Notes List

- **The load-bearing decision — embedding is a precondition of corpus admission.** The single seam `admit` (both the async worker `_persist_unit` and the sync API `_persist` route through it) embeds each extracted piece BEFORE persistence: on a typed `EmbedderError` the piece is moved from `pieces` to `failures` (with the mapped `ErrorClass`), so an embed-failed pièce is a register entry — never a `Piece`, never a `Chunk` — and `submitted_pieces == in_corpus + open_register_entries` (Story 2.7) holds (a unit is in EXACTLY one of corpus / register; the 2.7 tripwire proves no double count). This reuses `save()`'s piece/failure/watermark logic (no new admission machinery).
- **The ONE real embedder (AD-11).** `apx/adapters/embedder_bgem3/bgem3.py::Bgem3Embedder` — local BGE-M3, 1024-dim, `.embed` wrapping the model's `.encode`, **lazy-imports** `FlagEmbedding` inside `embed()` so the app + CI run without the heavy `torch` tree; a missing backend RAISES `EmbedderUnavailable` (fail-loud, no stub). Every fault maps to the port taxonomy (unavailable/rate-limited/timeout/dimension-mismatch/auth-failed) → the five append-only `ErrorClass` members. Tests inject a fake at the port boundary (`tests/embedding_fakes.py`), never a runtime stub — the `embedder_has_one_implementation` check is now non-vacuous and green (exactly one impl, none in an `except`).
- **The embedding trio + the index that never self-deletes.** `Chunk` gains `model_id`/`model_version` (categorical, plaintext-allowlisted) + a 1024-dim `halfvec` `vector` (volume-encrypted, AD-31 — NOT `ENCRYPTED_COLUMNS`) via a dialect-portable `Halfvec` `TypeDecorator` (halfvec on PG, JSON on SQLite so `create_all` works); migration 0021 adds them + the pgvector extension + an HNSW index (DDL is alembic-only, exempt). The index write path IS `write_chunk` (INSERT-only) — a dimension mismatch **raises**, never deletes; `destructive_index_ops_single_entry` stays green.
- **No embedder config key — the stamp is the embedder's own identity (AD-11).** The three `embedding_*` config keys were added mid-build then **dropped** on the review's evidence: a config-supplied `model_id` can lie about which model actually produced a vector (the MED finding), and an `embedding_model` key is itself a config-as-data selector of *the* embedder, which AD-11 forbids. Instead the port carries `dimensions` / `model_id` / `model_version`, `admit` stamps each chunk from the embedder that embedded it, and `embed_result` rejects a wrong-width vector as a register entry before any save.
- **Deferred, faithfully** (see the scope note): real passage chunking (2.9 — one whole-piece chunk here); the visual worklist line (2.11); and the **chunk-write on a successful retry** — the retry *primitive* resolves an entry (2.6), the retry *handler* couples resolve+re-embed+chunk and lands with the retry UX (2.11), so no retry-recovered-without-a-chunk pièce is reachable in production (there is no retry endpoint yet).

### File List

**New**
- `apx/adapters/embedder_bgem3/bgem3.py` — the ONE real Embedder (lazy BGE-M3).
- `apx/adapters/store_postgres/vector_types.py` — the dialect-portable `Halfvec` type.
- `apx/adapters/store_postgres/admission.py` — `admit`, the embed-before-admission seam.
- `apx/core/app/embedding.py` — `embed_result` (reshape) + the `EmbedderError → ErrorClass` map.
- `apx/adapters/store_postgres/migrations/versions/0021_chunk_embedding.py` — the trio + HNSW index.
- `tests/embedding_fakes.py` — the fake Embedders (port-boundary substitution).
- `tests/adapters/test_embedding_ingest.py` — forward path (AC1/AC4/AC5) + retry primitive (SQLite).
- `tests/adapters/test_embedding_postgres.py` — the real halfvec write + NN query (Postgres leg).

**Modified (source)**
- `apx/core/ports/embedding.py` — the `EmbedderError` taxonomy.
- `apx/core/domain/failures.py` — the five embedder `ErrorClass` members (append-only).
- `apx/core/domain/config.py` + `README.md` — NO embedder config key added (AD-11 — the comment records why).
- `apx/adapters/store_postgres/models.py` — the `Chunk` embedding trio + `EMBEDDING_DIM`.
- `apx/adapters/store_postgres/chunk_writer.py` — `write_chunk` carries the trio + the width guard.
- `apx/adapters/store_postgres/store.py` — `existing_piece_ids` (the disjointness helper `admit` uses to skip re-embedding an already-corpus pièce).
- `apx/adapters/store_postgres/queue/__init__.py` — the embedder built once + `admit` at the worker seam.
- `apx/api/app.py` — `_embedder()` + `admit` at the sync seam.
- `apx/adapters/embedder_bgem3/__init__.py` — package docstring.
- `apx/checks/encryption.py` — `model_id`/`model_version` plaintext-allowlisted.
- `apx/checks/forward_looking.py` + `apx/checks/manifest.py` + `README.md` — the "vacuous until 2.8" prose (embedder now live).
- `pyproject.toml` — the `embedder` optional extra (FlagEmbedding, lazy).

**Modified (tests)**
- `tests/adapters/test_chunk_writer.py`, `tests/adapters/test_chunk_writer_postgres.py` (the trio + `_ENUMERATED`), `tests/worker/test_import_job.py`, `tests/api/test_ingest_api.py` (inject the fake embedder), `tests/checks/test_structural_harness_checks.py` (the deferral test — embedder now non-vacuous).
- `tests/checks/test_structural_harness_evasions.py` — two review evasions (`embedder-disguised-by-port-shape`, `index-bulk-delete`) + a single-row-`delete` negative test.
- `tests/adapters/test_backup_restore.py` — the chunk embedding trio + halfvec vector survive backup/restore (the L3 review finding).

## Senior Developer Review (AI)

**Reviewed:** 2026-07-29 · **Outcome:** Approve (all High/Med resolved, Low triaged) · **Method:** three parallel adversarial reviewers, each execution-verifying its findings (mutate → run the specific test → confirm the catch → revert to a byte-identical tree), each on a distinct lens: (R1) the denominator invariant vs. the SM-3 watermark, (R2) the fail-loud / no-fallback structural gate, (R3) the index-never-deletes write path + persistence.

The green gate did **not** mean the story was correct: the two High findings are double-counts that the Story 2.7 watermark `submitted = max(stored, in_corpus + open)` actively *masks* — the tautology re-raises the watermark to cover a unit counted in both corpus and register, so the 2.7 tripwire stays green over a real double-count. Both are now closed at the source (the unit is in exactly one of corpus/register by construction), with a regression test that fails against the pre-fix code.

### Action items — resolved

| # | Sev | Finding | Resolution |
|---|-----|---------|------------|
| H1 | High | Re-importing an already-corpus pièce during an embedder outage double-counts it (embed fails → register entry for a pièce already in the corpus), masked by the watermark tautology. | `admit` computes `existing_piece_ids` and embeds **only** the genuinely new pieces; an already-corpus pièce is never re-embedded and cannot become a second register entry. Regression: `test_reimporting_an_already_indexed_piece_during_an_outage_is_not_double_counted`. |
| H2 | High | `write_chunk` could raise **after** the admission commit (blank `model_version`, or a width mismatch), orphaning a corpus pièce with no chunk and double-counting it through quarantine. | The stamp is taken from the embedder (not config); `embed_result` rejects a wrong-width vector as a register entry **before** any save; `admit` asserts `embedder.dimensions == EMBEDDING_DIM` loudly. Regressions: `test_a_wrong_width_vector_is_a_register_entry_never_an_orphaned_corpus_piece`, `test_the_chunk_is_stamped_with_the_embedders_own_identity`. |
| M1 | Med | A config-supplied `model_id` can lie about which model produced a vector. | Port gained `model_id`/`model_version`; the chunk is stamped from the embedder that embedded it. The three `embedding_*` config keys were dropped (an `embedding_model` key is also a forbidden config-as-data selector, AD-11). |
| M2 | Med | `embedder_has_one_implementation` heuristic could be evaded by a second *usable* embedder under a disguised name; `destructive_index_ops_single_entry` missed `DELETE FROM` / bulk `.delete()`. | Hardened `_is_concrete_embedder` with a port-shape leg (`dimensions` + an embed-ish method); added `delete\s+from` and no-arg `.delete()` detection (single-row `session.delete(obj)` deliberately **not** flagged). Evasions locked in `test_structural_harness_evasions.py`. |
| M3 | Med | `uv.lock` not regenerated for the new `embedder` extra — the offline `--extra embedder` install would be unsatisfiable. | `uv lock` regenerated (pure addition: FlagEmbedding + torch tree, no base package changed). |
| L3 | Low | No test proved the halfvec vector survives the logical backup/restore (only its presence was implied). | Direct-`Chunk` seed with a known vector + an assertion that the value round-trips (`test_backup_restore_reproduces_the_tenant_identically`). |

### Triaged — acknowledged, not actioned (rationale recorded)

- **L4 — API embedder cold-start.** `_embedder()` builds the process-global BGE-M3 lazily; a first concurrent burst could construct it more than once. Benign (the last wins, all identical, idempotent) and the API path is single-process today. Revisit if/when the API serves embedding under real concurrency.
- **L5 — `admit` reaches `store._sf`.** The seam uses the store's private session factory to keep the embed-then-persist in one unit of work. Tolerable while `admit` lives beside the store; promote `_sf` to a documented seam if a second caller appears.
- **Deferred by design (not defects):** real passage chunking (2.9), the visual worklist line (2.11), and chunk-write on a *successful retry* (2.11 retry handler) — verified unreachable in production today (no retry endpoint calls the resolve primitive), so no retry-recovered-without-a-chunk pièce exists.
