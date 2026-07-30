---
baseline_commit: 6c79201
---

# Story 3.1: Semantic retrieval, marked suggestive

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a lawyer looking for *pièces* about a topic,
I want ranked results that never pretend to be the complete set,
so that I am never misled into thinking a suggestion was a proof.

## Scope note — the semantic ENGINE + the truth-status DATA CONTRACT + the constant-site GATE; not the UI

Epic 3 has two engines with two *truth statuses* (AD-20): the **semantic** engine finds and never claims completeness (**suggestive**); the **deterministic** engine (Story 3.2) proves and returns the whole match set (**exhaustive**). This story builds the **semantic engine** and — the load-bearing half — the **truth-status data contract** that makes "a suggestion is never a proof" a property carried in data, plus the **static gate** that no configuration can ever relabel a semantic set **exhaustive** (AD-20, the anti-pattern being v1's off-corpus gate: *a similarity threshold shipped disabled by default, a guess in the costume of a proof*).

**What this story builds (all CI-verifiable):** a scoped semantic search in the one read entry point `core/app/read/` (AD-14) that embeds the query, runs an HNSW cosine nearest-neighbour search over `chunk` (the 0021 `vector`/`ix_chunk_vector_hnsw` surface), and returns a **result set** whose `truth_status` is the **constant** `SUGGESTIVE`, ranked, with a stated `k`, each result carrying its *pièce* identity and *chunk* provenance resolvable to the exact passage (Story 2.9); the `TruthStatus` domain type and the suggestive result-set shape; the **config-as-data** similarity threshold (AD-24); and the **structural check** that `truth_status` is set at exactly one construction site per engine and is a constant there (FR-12, FR-56, AD-20).

**What is deferred (honestly):**
- **The display / export UI** — the epic DoD's "in the interface and in any export" is a user-facing surface with **no UX contract yet** (as with 2.10/2.11). This story makes *truth status* a **data** property present on the result set and reachable by any future surface; the visual/verbal distinction and the export wording are Story 3.4's surface work. The result set already refuses to expose a count phrased as a total, so no surface can render one.
- **The comprehensive RBAC one-read-path consolidation + the adversarial out-of-scope suite over both engines + mutating revoke/grant** — Story 3.3. This story applies scope as a query **pre-filter** (AD-13) and keeps `no_post_filter_in_retrieval` green, but the exhaustive cross-surface proof is 3.3.
- **The deterministic engine + its `exhaustive`/`denominator`** — Story 3.2 (the constant-site check is written here to already admit a second engine).
- **Recall quality / the gold-set number** — Epic 4 (the gate exists from 2.12; `recall_at_the_line` stays deferred).

## Acceptance Criteria

1. **A semantic query returns a ranked, suggestive result set with provenance (FR-12, AD-16, AD-20).** `core/app/read` exposes a semantic search taking `(tenant, scopes, query, *, k)` — no identifier-only method — that embeds the query via the `Embedder` port, runs a **scoped** HNSW cosine nearest-neighbour search over `chunk`, and returns a result set carrying: `truth_status == TruthStatus.SUGGESTIVE`, the stated `k`, and up to `k` ranked results each carrying its *pièce* identity, its *chunk* provenance resolvable to the exact passage (Story 2.9 `resolve_chunk`/`resolve_passage`), and its similarity score. *(tests: a query over a small fake-embedded corpus returns a ranked ≤k suggestive set; every result resolves to its pièce + chunk offsets; results are ordered by similarity.)*

2. **The set never carries a count phrased as a total (AD-20).** The suggestive result-set type exposes **no** field, property, or wording that can be read as completeness — no `total`, no `count_of_all`, no *denominator*; it carries `k` and a fixed wording token (e.g. `"top {k} of the corpus by similarity"`) that cannot be read as a proof of absence. A *denominator* is a property only an **exhaustive** set has. *(tests: the suggestive result-set type has no total/denominator field; the wording token is the suggestive one; constructing it with a denominator is impossible by type.)*

3. **The gate: `truth_status` is set at exactly one construction site per engine and is a constant there — no configuration can label a semantic set exhaustive (FR-12, FR-56, AD-20).** A structural property (house pattern — `apx/checks/`, registered in manifest + registry + README lockstep) asserts that each result-set construction site sets `truth_status` to a **constant** enum literal (never a variable, a conditional, a threshold/config-derived value), and that the semantic engine's site is `SUGGESTIVE`. It admits a second engine (3.2's `EXHAUSTIVE`) without change. *(tests: green on the real tree; fires on a fixture where the semantic site sets `truth_status` from a variable / a threshold comparison / a config lookup; README ↔ manifest lockstep; check count rises.)*

4. **The similarity threshold is configuration-as-data, recorded on the result, with a guarantee-preserving default (FR-12, AD-24).** A `similarity_threshold` config key (float, config-as-data, per-tenant via `set_config`) governs the minimum cosine similarity a result must meet; it is **recorded on the result set** (so the result declares the threshold it ran under); it has a **defined default**, and a default that disables the behaviour it governs is a defect — enforced by the existing `config_defaults_preserve_guarantees` check (`default_preserves_guarantee`). *(tests: the key exists, coerces to float, has a guarantee-preserving default; the threshold is recorded on the result set; a candidate below threshold is excluded; the defaults-preserve check still passes.)*

5. **Scope is a query PRE-filter, never a post-filter; no scope → empty (AD-13, AD-14, FR-14).** The scope predicate constrains the **query** (joined in the SQL, AD-13), never a result-set post-filter: the search signature takes `(tenant, scopes, query)` with no fetched-result-set parameter, so `no_post_filter_in_retrieval` stays green; a caller whose scope set is empty receives an **empty** result set, not the corpus (fail-closed, AD-12), for administrative and system identities alike. *(tests: `no_post_filter_in_retrieval` green with the engine present; an empty-scope caller gets zero results and zero metadata; the read method requires `tenant` + `scopes`, no id-only overload.)*

6. **The gate stays green, no schema change (AC: all).** `ruff` clean; the full suite green; `python -m apx.checks` passes with the new truth-status check registered (count rises by one; README ↔ manifest lockstep); the Story 2.13 perf-ceiling gate stays green — `k` is a result-shape bound (a top-k), **not** an invented latency/throughput target, and nothing declares a perf ceiling; `alembic heads` = single **0021** (the `vector` column and `ix_chunk_vector_hnsw` already exist — **this story adds no migration**).

## Tasks / Subtasks

- [x] **Task 1 — the truth-status domain type + the suggestive result set (AC1, AC2).**
  - [x] `apx/core/domain/` — a `TruthStatus` enum with exactly two members (`SUGGESTIVE`, `EXHAUSTIVE`) and a `SemanticResult` (pièce identity + chunk provenance handle + similarity score) and a `SuggestiveResultSet` (frozen: `truth_status` fixed to `SUGGESTIVE`, `k`, `results`, `similarity_threshold`, a suggestive `wording` token). The type carries **no** total/denominator field — a denominator is an exhaustive-only concept. *(`apx/core/domain/retrieval.py`: `truth_status` is a `field(default=SUGGESTIVE, init=False)` — a caller cannot supply it, frozen forbids reassigning it, so the constant is baked into the TYPE. The "one construction site per engine" is the type itself.)*
  - [x] Tests (`tests/core/domain/` or `tests/domain/`): the enum has two members; a suggestive set is `SUGGESTIVE`, ranked, ≤k, carries its threshold, and has no total/denominator attribute. *(`tests/domain/test_retrieval.py`, 5 tests incl. passing `truth_status=EXHAUSTIVE` raises TypeError, reassigning raises FrozenInstanceError.)*

- [x] **Task 2 — the read port + the semantic engine in `core/app/read/` (AC1, AC5).**
  - [x] A read **port** (Protocol) method for a **scoped** semantic nearest-neighbour search: `search_semantic(tenant, scopes, query_vector, *, k, min_similarity) -> list[<row>]` — scope is a **required** argument constraining the query, there is **no** id-only method and **no** result-set post-filter (keep `no_post_filter_in_retrieval` green). The engine (`core/app/read/semantic.py`) embeds the query via the `Embedder` port, calls the read port, resolves each hit to its pièce + passage (Story 2.9), and constructs the `SuggestiveResultSet` at **one** site with the constant `SUGGESTIVE`. *(`apx/core/ports/read.py::SemanticReader` returns `list[SemanticResult]` (identity + score, no result-set param); `apx/core/app/read/semantic.py::search_semantic` injects the Embedder + reader ports and builds the set. `no_post_filter_in_retrieval` stays green.)*
  - [x] Empty-scope → empty result set (fail-closed), asserted for administrative/system identities too. *(engine short-circuits before embedding when `scopes` is empty; the port contract also returns `[]`.)*
  - [x] Tests: engine over a **fake read adapter** (Python cosine over in-memory vectors, mirroring `tests/embedding_fakes.py`) returns a ranked suggestive set; empty scope → empty; the embedder is faked (no real BGE-M3). *(`tests/core/app/read/test_semantic.py`, 5 tests incl. the closest-but-out-of-scope hit never appears + threshold exclusion.)*

- [x] **Task 3 — the Postgres adapter: the scoped HNSW cosine query (AC1, AC5).**
  - [x] `apx/adapters/store_postgres/` — implement the read port with a single SQL statement: HNSW cosine nearest-neighbour (`vector <=> :q` over `ix_chunk_vector_hnsw`, `halfvec_cosine_ops`), the **scope predicate joined as a pre-filter** (AD-13 — resolved from the authoritative source at query time, never a denormalised column), `tenant` first (AD-12), `min_similarity` applied in the query, ordered by distance, `LIMIT k`. No SQL naming a tenant-owned table appears outside `core/app/read/`'s adapter boundary (AD-14 direction; the comprehensive check is 3.3). *(`semantic_query.py::semantic_search_stmt` — a pure `Select` builder; `SqlStore.search_semantic` executes it + maps rows to `SemanticResult` (`similarity = 1 - distance`) with the empty-scope short-circuit. `<=>` via `Chunk.vector.op("<=>")` — pgvector's comparator isn't exposed through the `Halfvec` TypeDecorator.)*
  - [x] Tests: guarded to run only where PostgreSQL + pgvector are available (skip on the SQLite baseline, like the other pgvector-only store tests); assert the query shape (scope joined, `LIMIT k`, ordered by `<=>`). The CI-portable proof of the engine is Task 2's fake adapter. *(Since `<=>` is PG-only — exactly as the migrations are — CI asserts the query by its compiled PostgreSQL SQL shape (scope join pre-filter, tenant, scope IN, `<=>` order, LIMIT, similarity floor) with no DB, plus the empty-scope short-circuit on SQLite. `tests/adapters/test_semantic_query.py`, 4 tests. The live vector round-trip runs on the target.)*

- [x] **Task 4 — the similarity threshold as configuration-as-data (AC4).**
  - [x] Add a `similarity_threshold` `ConfigKey` (float) in `apx/core/domain/config.py` with a defined, **guarantee-preserving** default (a value that returns useful results, never one that disables retrieval); wire `default_preserves_guarantee`. The engine reads it via the tenant config getter and records it on the result set. *(`similarity_threshold` float default `0.3`, `valid = -1≤v≤1` (cosine range), `preserves_guarantee = v < 1.0` (a 1.0 default admits ~nothing → disables retrieval, the v1 shape), `affects_retrieval=True`; README config-keys row added (lockstep). The engine takes a `config_get` and resolves the threshold itself, so the recorded value is the configured one, never a caller override.)*
  - [x] Tests: the key exists/coerces/defaults; `config_defaults_preserve_guarantees` stays green; the threshold excludes a below-threshold candidate and is recorded on the result. *(`test_config_schema.py` new test; `no config default disables its guarantee` + both config-lockstep checks stay green; engine test asserts `similarity_threshold` recorded + below-threshold exclusion.)*

- [x] **Task 5 — the constant-construction-site check (AC3) — the load-bearing gate.**
  - [x] `apx/checks/` — a structural check `semantic_result_status_is_constant` (or `truth_status_constant_per_engine`) asserting every result-set construction sets `truth_status` to a **constant** enum literal (AST: a `Name`/`Attribute` resolving to a `TruthStatus` member, never a variable/`BoolOp`/`Compare`/`IfExp`/`Subscript`/config call), and the semantic site is `SUGGESTIVE`. Anchor on the construction of the result-set type (mirror `one_chunk_writer`/`scope_arg_required` in `payload_schema.py`). Fail-closed on an unparseable file; injectable `roots`. Admit a second engine's `EXHAUSTIVE` site (3.2) without change. *(`apx/checks/truth_status.py::truth_status_is_constant_per_engine`: anchors on the `truth_status` field of any result-set TYPE and requires it be a constant `TruthStatus.<MEMBER>` declared non-overridable — `field(default=…, init=False)` or a `ClassVar` — so a caller/config cannot supply it. `timedrun` excluded like the other checks. Fires on an init-able default, a threshold `IfExp`/`Compare`, or a config `Call`.)*
  - [x] Register in `apx/checks/manifest.py` + `apx/checks/registry.py` + the README property block (README ↔ manifest lockstep). *(Row `truth-status-constant-per-engine`, FR-12 / AD-20; `python -m apx.checks` 49 → 50; lockstep green.)*
  - [x] Tests (`tests/checks/`): green on the real tree; fires on a fixture whose semantic site derives `truth_status` from a variable / a `Compare` (threshold) / a config lookup; the check count rises and lockstep holds. *(`tests/checks/test_truth_status.py`, 7 tests: constant/init=False passes; overridable default, threshold-`IfExp`, config-`Call` each fire; vacuous; real tree passes; fail-closed.)*

- [x] **Task 6 — full re-gate (AC6).** `ruff check .`; `pytest` (no `DATABASE_URL` override — SQLite baseline); `python -m apx.checks` (count rises by the truth-status check; `no_post_filter_in_retrieval`, the perf-ceiling gate, and README ↔ manifest all green); `alembic heads` = single **0021** (no migration). *(`ruff check .` clean; `pytest` 768 passed / 10 skipped; `python -m apx.checks` 50 (49 → 50); `no_post_filter_in_retrieval` + perf-ceiling gate green; `alembic heads` = single `0021` — no migration.)*

## Dev Notes

### The load-bearing idea: truth status is data, and no config can forge a proof

AD-20 is the spine of Epic 3: *truth status* is a **property of the result set, carried in data**, two values only — **suggestive** (semantic, ranked, top-k — supports a finding, never proves absence) and **exhaustive** (deterministic, complete, carries a *denominator*). It is **set at exactly one construction site per engine and is a constant there; no threshold in any configuration can produce an exhaustive label.** The v1 defect this prevents: an off-corpus gate that was a similarity threshold shipped disabled by default — *a guess in the costume of a proof, worse than nothing* (`addendum.md` §4). So the two deliverables that matter most here are (a) a suggestive result set that **cannot** express completeness (no total, no denominator — by type), and (b) the **static check** that the semantic engine's `truth_status` is a hard-coded `SUGGESTIVE`, unreachable by any config path. The retrieval mechanics (embed → HNSW → rank) are the easy half.

### Reuse — do not rebuild

- **Embedding**: the `Embedder` port (`apx/core/ports/embedding.py`) — embed the query with the same model that embedded the chunks; fails loud (AD-11), never a fallback. CI uses the fake embedder (`tests/embedding_fakes.py`), never the real BGE-M3.
- **The vector surface**: migration **0021** already added the `chunk.vector` `halfvec(1024)` column, `model_id`/`model_version`, and the **`ix_chunk_vector_hnsw`** HNSW cosine index (`halfvec_cosine_ops`). **No new migration.** `apx/adapters/store_postgres/vector_types.py` degrades `halfvec` on SQLite — so the cosine `<=>` query is **PostgreSQL-native**; the engine sits behind a read **port** so CI proves it with a Python-cosine fake adapter.
- **Provenance**: Story 2.9's `store.resolve_chunk` / `resolve_passage` / `is_degraded` resolve a chunk to its exact passage (AD-9 frozen columns; provenance is RESOLVED, not stored). Each semantic result carries the handle needed to resolve+open the passage; the viewer itself is 3.5.
- **Config-as-data**: `apx/core/domain/config.py` — `ConfigKey`, `default_preserves_guarantee`, `set_config`/`get_config`, `default_config()`. Add `similarity_threshold` there; the `config_defaults_preserve_guarantees` and `documented_config_keys_exist`/`config_reference_is_complete` checks already guard it (update the README config-keys block too if those checks require it).
- **Scope/tenant**: the write side proved "one writer, scope required" (`ChunkWriter.write_chunk(payload, *, rbac_scope)`); the read side mirrors it — scope is a **required** query argument, resolved at query time from the authoritative `matter_scope` (AD-13), joined as a pre-filter.
- **Structural-check house pattern**: `CheckResult`, `_p(...)` in `manifest.py`, `CHECKS` in `registry.py`, the README `<!-- structural-properties:start/end -->` block (lockstep enforced both ways). Mirror `payload_schema.one_chunk_writer` / `scope_arg_required` for the single-construction-site AST check; mirror `gold_gate.py` / `perf_gate.py` for the fail-closed + injectable-`roots` shape.

### Architecture guardrails (binding)

- **AD-20** — two truth statuses, one **constant** construction site per engine; no config can forge `exhaustive`; a `LIMIT`/`top_k`/page size never applies to an exhaustive set (that is 3.2's constructor-takes-no-limit rule — irrelevant to the suggestive engine, which IS a top-k).
- **AD-16** — the semantic engine runs over **chunks** (dense retrieval); the deterministic engine (3.2) runs over full text/names. Do not conflate them.
- **AD-13** — scope resolved at query time from the single authoritative source, **joined as a pre-filter**; no mutable attribute (scope, custodian) denormalised onto the indexed row.
- **AD-14** — one read entry point (`core/app/read/`); the read port exposes **no method that accepts an identifier without a tenant and a scope argument**; **no** result-set post-processing function accepts a scope. (3.1 keeps `no_post_filter_in_retrieval` green; 3.3 adds the "exactly one read path" grep + the adversarial suite.)
- **AD-12** — tenant before scope; a caller with no scope gets an **empty** corpus, admin/system identities included (fail-closed).
- **NFR-2 / Story 2.13** — no invented latency/throughput target. `k` is a result-shape bound derived from the user journey (a page of results), **not** a perf ceiling; declare no latency constant (the perf-ceiling gate would fire). If a retrieval latency ceiling is ever needed, it derives from the pending timed-run measurement record.
- **AD-4 / AD-3** — the core imports no provider SDK and no pgvector-only Python dependency beyond the adapter; no ParadeDB/pgvectorscale (that is AD-21/3.2 territory anyway).

### The constant-site check — anchor robustly, best-effort like the gold/perf gates

Detect the result-set **construction** (the `SuggestiveResultSet(...)`/`TruthStatus`-carrying constructor call) and assert its `truth_status` argument (or the class attribute default) is a **constant** `TruthStatus` member — reject a `Name` bound to a non-constant, a `Compare` (a threshold test), an `IfExp`, a `BoolOp`, a `Subscript`/`Call` (a config lookup). This is the AD-20 "constant there" rule made mechanical. Carry the Story 2.12/2.13 review lesson: anchor on the type/enum (not a guessed name), state best-effort, fail closed on an unparseable file, injectable `roots`, and add a failure-path fixture that actually fires. Keep the check general enough that 3.2's `EXHAUSTIVE` site passes unchanged.

### Files to touch (and blast radius)

**New**
- `apx/core/domain/` — `TruthStatus`, `SemanticResult`, `SuggestiveResultSet` (a new `retrieval.py`, or extend `search.py` which today holds only the deterministic `snippet` helper — keep the two engines' domain types clearly separated).
- `apx/core/app/read/semantic.py` — the semantic engine (embed → scoped search → resolve → construct suggestive set at one site).
- `apx/core/ports/` — the read port method for the scoped semantic search (extend the store/read port surface).
- `apx/adapters/store_postgres/` — the HNSW cosine query implementation (scope pre-filter).
- `apx/checks/<truth_status>.py` — the constant-construction-site check.
- Tests: `tests/domain/…`, `tests/core/app/read/…` (engine over a fake read adapter), `tests/adapters/…` (pg-guarded query), `tests/checks/test_<truth_status>.py`.

**Modified**
- `apx/core/domain/config.py` — the `similarity_threshold` config key.
- `apx/checks/manifest.py`, `apx/checks/registry.py`, `README.md` — register the truth-status property (+ the config-keys block if the config checks require it).

**NOT touched** — **no alembic migration** (head stays 0021); no display/export UI; no deterministic engine; no change to the write path (`ChunkWriter`), the embedder adapter, or the cascade/Judge.

### What NOT to build (scope discipline)

- No display, no export, no interface wording surface (Story 3.4; no UX contract). Truth status is made a **data** property only.
- No deterministic/exhaustive engine, no `denominator`, no full-text search (Story 3.2).
- No comprehensive one-read-path grep, no adversarial out-of-scope suite over every surface, no mutating revoke/grant (Story 3.3 — but 3.1 must not introduce a post-filter and must fail closed on empty scope).
- No recall/quality measurement, no ranking version, no confidence (Epic 4).
- No new dependency; no invented latency/throughput target (NFR-2, the 2.13 gate).

### Project Structure Notes

- `apx/core/app/read/` exists today as the AD-14 entry-point placeholder (only `__init__.py`); 3.1 gives it its first real reader. The one-read-path invariant is asserted comprehensively in 3.3; here, just place the semantic read inside it and keep the tenant-owned-table SQL in the adapter it belongs to.
- `apx/core/domain/search.py` currently holds only the deterministic `snippet` helper (for 3.2). Keep the semantic domain types separate so the two engines never share a construction site (AD-20: one site **per engine**).

### References

- [Source: epics.md#Story-3.1] (lines 999–1012) — the four ACs (ranked suggestive set with stated k + provenance + openable position; never a count phrased as a total; the one-constant-site static check; the config-as-data similarity threshold with a non-disabling default).
- [Source: ARCHITECTURE-SPINE.md#AD-20] (580–613) — two truth statuses, one constant construction site per engine, no config can forge exhaustive; the v1 off-corpus-gate anti-pattern.
- [Source: ARCHITECTURE-SPINE.md#AD-13] (380–398) and [#AD-14] (400–434) — scope as a query pre-filter from a single authoritative source; one read entry point; no id-only method; no result-set post-filter; the read-path sequence diagram.
- [Source: ARCHITECTURE-SPINE.md#AD-16] (~332–365) — the semantic engine runs over chunks (dense retrieval), the deterministic over full text/names.
- [Source: ARCHITECTURE-SPINE.md#AD-12] (365–376) — tenant before scope; no scope → empty corpus; admin/system included.
- Reuse: `apx/core/ports/embedding.py` (Embedder), migration `0021_chunk_embedding` (the `vector`/`ix_chunk_vector_hnsw` surface), `apx/adapters/store_postgres/vector_types.py` (halfvec + SQLite degradation), Story 2.9's `resolve_chunk`/`resolve_passage`, `apx/core/domain/config.py` (config-as-data), `apx/checks/payload_schema.py` (`one_chunk_writer`/`scope_arg_required` AST pattern), `apx/checks/gold_gate.py` + `perf_gate.py` (fail-closed, injectable roots, best-effort framing), `tests/embedding_fakes.py` (the fake embedder / the pattern for a fake read adapter).

## Dev Agent Record

### Agent Model Used

claude-opus-4-8[1m] (Opus 4.8, 1M context) — dev-story.

### Debug Log References

- Full suite: 768 passed, 10 skipped (60 s), SQLite baseline (no `DATABASE_URL`).
- `python -m apx.checks`: 50 structural properties (49 → 50; the constant-truth-status gate added).
- `no_post_filter_in_retrieval` green with the engine present (scope is a query pre-filter, no result-set param); perf-ceiling gate green (`k` is not a perf ceiling).
- `alembic heads`: single `0021_chunk_embedding` — no migration (the `vector` column + HNSW index already exist).

### Completion Notes List

- **The truth-status data contract (AD-20, the load-bearing half).** `apx/core/domain/retrieval.py`: `TruthStatus` (two members) + `SuggestiveResultSet` whose `truth_status` is a `field(default=SUGGESTIVE, init=False)` — baked into the TYPE, so a caller can't supply it (`TypeError`) and frozen forbids reassigning it (`FrozenInstanceError`). The set carries `k`, the `similarity_threshold` it ran under, and a `wording` token; it has **no** total/denominator field. No configuration can make a semantic set claim completeness.
- **The semantic engine (AC1, AC5).** `apx/core/app/read/semantic.py::search_semantic` (the first reader through the AD-14 entry point `core/app/read/`) embeds the query (Embedder port), runs the scoped search via the `SemanticReader` port (`apx/core/ports/read.py`), and builds the suggestive set. Empty scope → empty set without a query (fail-closed, AD-12). CI proves it with a Python-cosine fake reader (no real BGE-M3).
- **The Postgres query (AC1, AC5).** `apx/adapters/store_postgres/semantic_query.py::semantic_search_stmt` — HNSW cosine (`<=>`) over `chunk.vector`, the scope predicate **joined from `matter_scope` as a pre-filter** (AD-13, never denormalised), tenant first (AD-12), a min-similarity floor, ranked, `LIMIT k`. `SqlStore.search_semantic` executes it. `<=>` is PG-only, so CI asserts the query by its compiled PostgreSQL SQL shape (no DB); the live vector round-trip runs on the target.
- **Scope is a pre-filter, never a post-filter (AC5).** The signature is `(tenant, scopes, query…)` with no fetched-result-set parameter — `no_post_filter_in_retrieval` stays green.
- **The similarity threshold is config-as-data (AC4).** `similarity_threshold` (float, default 0.3, `preserves_guarantee = v < 1.0`, `affects_retrieval=True`) — a default of 1.0 admits ~nothing (the v1 off-corpus-gate shape), caught by `config_defaults_preserve_guarantees`. The engine resolves it from `config_get`, so the recorded threshold is the configured one.
- **The gate (AC3).** `apx/checks/truth_status.py::truth_status_is_constant_per_engine` requires every result-set type's `truth_status` to be a constant, non-overridable `TruthStatus` member; fires on an init-able default, a threshold `IfExp`, or a config `Call`. Registered (49 → 50), README ↔ manifest lockstep.
- **No schema change (AC6).** No migration; alembic head stays `0021`. `k` is a result-shape bound, not a perf target (NFR-2).

### File List

**New**
- `apx/core/domain/retrieval.py` — `TruthStatus`, `SemanticResult`, `SuggestiveResultSet`.
- `apx/core/ports/read.py` — the `SemanticReader` read port.
- `apx/core/app/read/semantic.py` — the semantic engine.
- `apx/adapters/store_postgres/semantic_query.py` — the scoped HNSW cosine query builder.
- `apx/checks/truth_status.py` — the constant-truth-status structural check.
- `tests/domain/test_retrieval.py`, `tests/core/app/read/test_semantic.py`, `tests/adapters/test_semantic_query.py`, `tests/checks/test_truth_status.py`.

**Modified**
- `apx/adapters/store_postgres/store.py` — `SqlStore.search_semantic` + imports.
- `apx/core/domain/config.py` — the `similarity_threshold` config key.
- `apx/checks/manifest.py`, `apx/checks/registry.py`, `README.md` — register the truth-status property + the config-keys row.
- `tests/domain/test_config_schema.py` — the `similarity_threshold` schema test.

### Change Log

- 2026-07-30 — Story 3.1 implemented (semantic retrieval, marked suggestive). The truth-status data contract (`SuggestiveResultSet`, `TruthStatus`), the semantic engine + read port in `core/app/read/`, the Postgres HNSW cosine query with the scope pre-filter, the `similarity_threshold` config key, and the AD-20 constant-truth-status gate (49 → 50 checks). No migration (head 0021). ruff clean; 768 passed / 10 skipped.
- 2026-07-30 — Adversarial 3-reviewer review + fixes. Resolved 1 HIGH + 4 MED + 2 LOW (see Senior Developer Review): reworked the AD-20 gate to anchor on the `TruthStatus` TYPE (catches a computed `@property`, an alt-named field, a conditional selection, a `__setattr__` relabel, and a denominator on a suggestive type — the previous name-anchored check reported those "vacuous"); pinned the Chinese-wall join's tenant-equality with a test + a defence-in-depth `.where(MatterScope.tenant == tenant)`; unit-tested the distance→similarity mapping; hardened the config-threshold resolution (`coerce`) and the empty-embedder path. ruff clean.

## Senior Developer Review (AI)

**Reviewers:** three independent adversarial lenses (the AD-20 truth-status gate / the scope pre-filter + Chinese wall / ports-adapters correctness + honesty), execution-verified (SQL compiled to PostgreSQL without a DB, runtime probes, mutate→run→revert). All three returned; the working tree was verified byte-identical to a pre-review backup and the tenant-qualified join confirmed present. **Outcome: Changes Requested → all resolved.** All three independently confirmed the shipped code is sound — no leak, correct ranking math, no layering violation, no regression, an honest CI-vs-PG deferral. One reviewer reported instruction-shaped "external edits" to `semantic_query.py` inside its own sandbox; treated as untrusted data and independently disproven (the live file's tenant-join is intact).

**Findings (all fixed):**
1. **[HIGH] The AD-20 gate anchored on the field NAME `truth_status`, so the v1 anti-pattern reincarnated as a computed `@property` (a threshold-derived label) — plus an alt-named field or a plain `Assign` — passed as "vacuous".** The gate is the load-bearing deliverable; a "looks live but detects nothing" gate is exactly what the review exists to catch. **Fix:** reworked `truth_status.py` to anchor on the `TruthStatus` **type** — it now fires on a member selected by a condition (`IfExp`/`BoolOp`) anywhere, a `@property`/method returning a member, an init-able/non-constant status field (any name, annotation-based), an `object.__setattr__` relabel, and a suggestive type carrying a denominator; it is never "vacuous" while a member appears; an aliased `TS.SUGGESTIVE` no longer false-positives. Tests: 13 (6 new bypass fixtures).
2. **[MED] "No total/denominator by type" (AC2) was under-enforced** — the domain test used an exact-name denylist (`total_in_corpus` slipped through) and no structural check guarded it. **Fix:** the gate rejects a completeness-shaped field on a suggestive type; the domain test is now an exact allowlist (`{results, k, similarity_threshold, truth_status}`).
3. **[MED] (R2+R3) The Chinese-wall join's tenant-equality was untested** — removing `& (MatterScope.tenant == Chunk.tenant)` left the whole suite green, and scope strings aren't tenant-qualified, so a regression there would leak cross-tenant. **Fix:** a test pins both the join tenant-equality and a WHERE tenant pin; added a defence-in-depth `.where(MatterScope.tenant == tenant)` so the wall holds even if the join clause regressed.
4. **[MED] The adapter's `1.0 - distance` similarity inversion had zero CI coverage** (mutating it to `distance` passed the suite). **Fix:** extracted `results_from_rows` and unit-tested the distance→similarity mapping + rank preservation (DB-free).
5. **[MED-2 doc] The gate docstring overstated its runtime guarantee** (`object.__setattr__` bypasses frozen). **Fix:** docstring softened + the `__setattr__` relabel is now flagged statically.
6. **[LOW] The engine used bare `float(config_get(...))`, looser than `coerce`** (a stray `True` → `1.0` silently disabling). **Fix:** resolve via `coerce("similarity_threshold", …)` (validates type + cosine range, fails loud).
7. **[LOW] `embedder.embed([query])[0]` raised a bare `IndexError` on a non-conforming embedder.** **Fix:** an explicit `EmbedderError` guard.

**Verified sound (no change):** the scope predicate is a genuine query PRE-filter (inner join to `matter_scope`, tenant on both sides, `scope IN` before ORDER BY/LIMIT — an out-of-scope high-similarity chunk cannot leak); empty scope → empty at both the engine (before embedding) and the adapter/raw builder; the ranking math (`similarity = 1 - cosine_distance`, ORDER BY distance ASC = best-first) is correct; the pg deferral is honest (the `<=>` query is genuinely PG-only, correctly halfvec-typed, and the compile-shape test catches a dropped scope filter); `no_post_filter_in_retrieval` stays green and meaningful; domain imports only stdlib (AD-4); no real model/GPU loads in CI; README ↔ manifest lockstep (50 checks).
