---
baseline_commit: c2b0e35
---

# Story 2.9: Chunking with provenance to the exact passage

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a lawyer,
I want every *chunk* traceable to the exact place in the source it came from, and a failed resolution shown as failed,
so that an extract in an export a court reads later cannot silently be pointing at nothing.

## Scope note — real passage chunking + provenance-BY-RESOLUTION; flat, deterministic, French-legal-aware

This story replaces Story 2.8's **one-whole-piece placeholder chunk** with real multi-passage chunking and makes provenance-to-the-exact-passage true and verifiable. Two things it deliberately is NOT:

- **NOT hierarchical parent/child chunking.** The v1 build used a parent/child + contextual-header strategy (`../apx-platform/**/domain/chunking/strategies.py`). It cannot be adopted as-is: **AD-9 froze the `chunk` column set with no parent reference**, and that set is the increment's one irreversible decision (`chunk_columns_enumerated` fails the build on any extra column). Flat passage chunking is what the frozen schema and FR-11 (provenance + determinism) actually require. Any hierarchical/expanded-context retrieval is an **epic-4 retrieval-time** concern achieved *within* the frozen schema (parent context re-derived at query time from `position`), never a stored hierarchy.
- **NOT the visual surfaces.** The *pièce* viewer with per-format passage highlighting (FR-44) and the export UI (FR-46) need a UX pass and are later stories. 2.9 builds the **domain mechanism** — the deterministic chunker, the resolver, the containment verifier, the honest degraded verdict — that those surfaces will consume.

The load-bearing idea: **provenance is RESOLVED, not stored.** AD-9 permits no offset column on `chunk`, so a chunk carries only `(position, full_text_version, chunking_config_version)`. To locate the passage you re-chunk the *pièce*'s stored full text (AD-10) under the recorded config and take the chunk at `position`; because chunking is deterministic under a fixed configuration (FR-11), this reproduces the exact span, and an exact-string-containment check proves the extract still matches the source at read time.

## Acceptance Criteria

1. **Deterministic boundaries, stable identity (FR-11).** Chunking the same full text under the same chunking configuration is a pure, deterministic function: it produces identical passages with identical `chunk_id`s across runs, processes and installations. Re-chunking is byte-identical (same spans, same positions, same ids). *(unit test: `chunk(text, cfg) == chunk(text, cfg)`; ids stable; never a counter.)*

2. **Real multi-passage chunking replaces the placeholder (FR-11).** An admitted *pièce* whose full text spans multiple passages yields **N chunks at positions `0..N-1`**, each embedded from **its own passage text** (not the whole piece), each written through the single `write_chunk` seam, each stamped with the active `chunking_config_version`. The Story 2.8 whole-piece chunk (`embed([piece.full_text])`, `position=0`) is gone. *(test: a multi-passage pièce → N>1 chunks at 0..N-1; each vector embeds its passage.)*

3. **Provenance to the exact passage (FR-11).** A chunk **resolves** to the exact source span — `(start, end)` character offsets into the *pièce* full text — and the resolved passage text passes **exact-string containment** against that full text. Resolution opens the source *pièce* and locates the passage; the offsets are recomputed by the deterministic chunker, never stored (AD-9). *(test: resolve a chunk → correct `(start,end)`, `full_text[start:end] == passage`, containment holds.)*

4. **A failed resolution is honest and never silently shown (FR-11, the court-facing invariant).** A resolution that fails at read time — the *pièce* is gone, its text changed under re-extraction (`text_version`/`text_identity` no longer matches the chunk's `full_text_version`), the recorded config no longer yields that `position`, or the containment check fails — returns an explicit **FAILED** verdict carrying the cause. The extract is **never** returned as though it resolved. *(tests: one per cause — pièce-gone, text-changed, position-out-of-range, containment-fail — each a typed FAILED verdict.)*

5. **A failed extract degrades its container (FR-11 / AD-23).** An export or citation that carries a resolved extract is marked **degraded** when any extract it contains fails to resolve; a degraded container states it on its face and its failed extracts are not presented as current. *(test: a container assembled over a failing resolution is `degraded=True`; a container over only-good resolutions is not.)* The wiring into a real extract-bearing export UI is deferred with those surfaces (epic 4); the domain mechanism and its guarantee land here.

6. **The chunking configuration is configuration-as-data and cannot diverge from what it produced (FR-11 / AD-40).** The chunking configuration is data (a tenant-editable value object), its identity `chunking_config_version` is **derived from the configuration content** so the version stamped on a chunk can never drift from the parameters that produced it, and it is recorded on every chunk. Chunks produced under different configurations have **different identities** (distinguishable), and a configuration change is a **new generation** (AD-40) — it never silently re-chunks or re-interprets existing chunks. *(tests: change a param → different version → different `chunk_id`s; a chunk's version equals the hash of the config that built it.)*

7. **The denominator invariant is preserved (Story 2.7 / AD-38, all-or-nothing per pièce).** A *pièce* is admitted to the *corpus* only when **all** its passages embed successfully; if embedding any passage fails, the **whole pièce** enters the *failure register* (its error class), **zero** chunks are written, and `submitted_pieces == in_corpus + open_register_entries` still holds (a unit is in exactly one of corpus/register). *(test: an embedder that fails on the 2nd of 3 passages → the pièce is one register entry, 0 chunks, denominator consistent.)*

8. **French legal text is not mangled (FR-11 determinism, the v1 defect).** A passage boundary never falls inside a recognised French legal citation or abbreviation — `art. L. 1235-3`, `n° 21-12.345`, `M.`, `Mme`, `Cass. soc.`, `art. 145 CPC`, `n°`, ordinals — the exact forms the v1 sentence splitter broke mid-token. *(test: a text seeded with each form → no boundary inside any of them.)*

9. **The gate stays green, with no schema change.** `ruff` clean; the full suite green; the **47** structural checks still pass (notably `chunk_columns_enumerated` — no new `chunk` column — and `one_chunk_writer` — `write_chunk` stays the only construction site); alembic remains a single linear head **0021** (2.9 adds **no migration**: provenance-by-resolution means no new column on `chunk` or `piece`).

## Tasks / Subtasks

- [x] **Task 1 — the deterministic, French-legal-aware chunker (AC1, AC3, AC8).** New pure-domain package `apx/core/domain/chunking/` (no adapter, no DB — AD-4).
  - [x] `Passage` value object: `text`, `start`, `end` (char offsets into the source full text).
  - [x] `chunk(full_text: str, config: ChunkingConfig) -> list[Passage]` — deterministic; boundaries snap to sentence/paragraph ends; a target size + optional overlap from `config`; offsets exact and contiguous-covering (every char of a passage lies at `full_text[start:end]`).
  - [x] The French-legal guard: a boundary is forbidden inside the enumerated citation/abbreviation forms (AC8). Hand-rolled and deterministic — **no** `langchain`/`nltk`/`spacy` (offline, version-stable, no heavy dep; the 1.4 GB BGE-M3 is already the weight budget). Protect at minimum: `art. L. 1235-3`, `art. 145 CPC`, `n° 21-12.345`, `M.`, `Mme`, `Me`, `Cass. soc.`, `Cass. civ.`, `al.`, `p.`, ordinals (`1er`, `2e`).
  - [x] **RED first**: write the determinism, span-correctness, and French-citation tests before the implementation (the v1 note: "Zero tests exist — write them first").

- [x] **Task 2 — the chunking configuration as data with a derived identity (AC6).** 
  - [x] `ChunkingConfig` frozen value object (the params) with a **content-derived** `version` (a short stable hash of its canonical form) — so `chunking_config_version` ⟺ params, never a free string that can drift.
  - [x] Resolve a `ChunkingConfig` from tenant config-as-data (mirror `config.expansion_bounds(get)`), with a `defaults()` for callers holding no tenant. Reconcile the existing `chunking_config_version` config key ([apx/core/domain/config.py:156](apx/core/domain/config.py#L156)): either derive-and-store it, or keep it and **assert** it equals the derived hash on every write/admission (a value that could diverge is the 2.8-review lesson — a stamp that can lie is a bug).
  - [x] Tests: same params → same version; changed param → new version; the version is the hash of the params.

- [x] **Task 3 — wire real chunking into admission (AC2, AC7).** 
  - [x] `apx/core/app/embedding.py::embed_result` — for each surviving *pièce*: `passages = chunk(piece.full_text, config)`; `vectors = embedder.embed([p.text for p in passages])`; emit one `EmbeddedChunk` per passage at `position=i`. `_payload_for` gains a `position` (and keeps `full_text`/`text_identity`/`text_version` at the **pièce** level — AD-10 provenance; only `position` varies). Width/empty-vector guards apply per passage.
  - [x] **All-or-nothing per pièce (AC7)**: if embedding any passage raises `EmbedderError` (or returns a wrong-width/empty vector), the **whole pièce** → `failures` with its class, **no** chunks emitted for it. Preserve the Story 2.8 disjointness (an already-corpus pièce is not re-embedded).
  - [x] `apx/adapters/store_postgres/admission.py::admit` — resolve the `ChunkingConfig` from tenant config, pass it into `embed_result`, stamp `chunking_config_version = config.version`. The `ChunkStore(...)` write loop is unchanged (one `write_chunk` per `EmbeddedChunk`).
  - [x] Update the Story 2.8 tests that encode the whole-piece assumption ([tests/adapters/test_embedding_ingest.py](tests/adapters/test_embedding_ingest.py) counts at lines 82/93/168): "one chunk per pièce" becomes "one chunk **per passage**"; add a genuinely multi-passage case.

- [x] **Task 4 — the resolver + containment verifier (AC3, AC4).** A read-path function (`apx/core/app/read/`) that, given a chunk (or `chunk_id`), returns `ResolvedPassage(text, start, end)` **or** a typed `FailedResolution(cause)`:
  - [x] Load the *pièce*; gone → FAILED(`piece-gone`).
  - [x] `piece.text_version != chunk.full_text_version` **or** `sha256(piece.full_text) != chunk`'s recorded `text_identity` lineage → FAILED(`text-changed`).
  - [x] Re-chunk under the chunk's `chunking_config_version` config; `position >= len(passages)` → FAILED(`position-out-of-range`); else take `passages[position]`.
  - [x] Exact-containment: `passage.text` must equal `full_text[start:end]` and be contained in `full_text` → else FAILED(`containment-failed`).
  - [x] Tenant-owned reads live under `core/app/read/` (AD-14); the SQL is a store method. Tests: one per cause + the happy path.

- [x] **Task 5 — the degraded-container mechanism (AC5).** A small domain helper: given a set of extract resolutions, a container is `degraded` iff any resolution is FAILED; a FAILED extract is never emitted as current. Test the helper directly (no visual surface). Document the export-UI wiring as deferred (epic 4, FR-46/FR-44).

- [x] **Task 6 — full re-gate (AC9).** `ruff check .`; `pytest` (no `DATABASE_URL` override — SQLite baseline); `python -m apx.checks` = **47** (confirm `chunk_columns_enumerated` and `one_chunk_writer` stay green); `alembic heads` = single **0021** (no new migration). The Postgres halfvec leg ([tests/adapters/test_embedding_postgres.py](tests/adapters/test_embedding_postgres.py)) stays a skipped `postgresql://` test.

## Dev Notes

### The two load-bearing decisions

1. **Provenance is resolved, not stored (AD-9 frozen schema + AD-10 + FR-11).** The `chunk` row carries no offsets and no chunk text — only `position`, `full_text_version`, `chunking_config_version` (plus the 2.8 embedding trio). The passage is recovered by re-chunking the *pièce*'s stored full text (AD-10, `piece.full_text` at `piece.text_version`) under the recorded config and taking `position`. Determinism (AC1) makes the recovered span exact; the containment check (AC3) proves it still matches at read time. This is why 2.9 needs **no migration** and adds **no column**: the entire feature rides on the frozen schema + a deterministic function + a read path.

2. **The chunking-config identity is derived from the config content (AD-40).** A chunk stamped `chunking_config_version` must resolve under *that* configuration. If the version were a free string set independently of the params (today's `config.py` default `"v1"`), a param change without a version bump would leave chunks stamped `"v1"` but un-resolvable under the current `"v1"` params — a stamp that lies (the exact failure the 2.8 review killed for the embedder model stamp). Derive the version from the config content so the two cannot diverge; a config change is then a new version = a new generation (AD-40), old chunks keep their version and are **retired by state / re-chunked by a later migration**, never silently re-interpreted (AD-7).

### The denominator stays honest (Story 2.7 / AD-38)

The 2.8 seam already makes embedding a precondition of admission. 2.9 keeps it **all-or-nothing per pièce**: all passages of a pièce embed, or the whole pièce is a register entry with zero chunks. A partially-embedded pièce (some passages in, some failed) must never exist — it would be a corpus pièce whose provenance is incomplete, and it would break `submitted == in_corpus + open`. The 2.7 watermark tautology (`submitted = max(stored, in_corpus+open)`) can MASK a double-count, so the test must assert `in_corpus`, `open_register_entries` AND the chunk count independently (the pattern the 2.8 review established).

### Why flat, deterministic, hand-rolled — not v1's parent/child, not an NLP library

- **Flat, not parent/child**: AD-9 froze the columns; there is no parent reference and adding one fails the build. FR-11 asks for provenance + determinism, not a stored hierarchy. Hierarchical context is an epic-4 retrieval concern re-derived from `position` at query time.
- **Hand-rolled deterministic splitter, not `langchain`/`nltk`/`spacy`**: the install is offline and single-machine; determinism must hold across runs and installations (AC1) and library tokenizers drift across versions and locales. The v1 splitter mangled French legal citations — 2.9's guard (AC8) exists precisely to prevent that.
- **No contextual header in 2.9** — embed each passage's own text **as-is**. The v1 "contextual header" (prepending a doc/section header to the embedded text) is a retrieval-quality optimisation and a *trap for provenance*: if the containment-verified text (AC3) were `header + passage`, containment against the source `full_text` would fail for **every** chunk (the header is not in the source). Deferred to epic-4 retrieval quality, where any such enrichment must apply to the embedded vector **only** and never to the resolved/containment-checked passage.
- Passage size/overlap are **config-as-data** and will be tuned by the timed 5 000-document run (Story 2.13 / U2, the gate that measures chunk yield and p95); do not hard-code them and do not over-fit numbers here.
- **The fakes are already multi-passage-ready**: `FakeEmbedder.embed(texts)` / `FailingEmbedder.embed(texts)` ([tests/embedding_fakes.py](tests/embedding_fakes.py)) return one vector **per input text**, so embedding N passages works unchanged; `FailingEmbedder(error, fails_on=lambda t: ...)` targets a specific passage — use it for the AC7 partial-failure test (fail on the 2nd passage → the whole pièce to the register, 0 chunks).

### Architecture guardrails (binding)

- **AD-9** — the `chunk` column set is exactly enumerated; no offset/text/parent column. `chunk_columns_enumerated` enforces it.
- **AD-40** — chunk identity is `chunk_id(piece_id, full_text_version, position, chunking_config_version)` ([apx/core/domain/identity.py:36](apx/core/domain/identity.py#L36)); deterministic, never a counter; a re-extraction (new `full_text_version`) or re-chunk (new `chunking_config_version`) is a new generation with new ids, retired by state not overwritten. Immutable chunking config, version guard ([chunk_writer.py:106](apx/adapters/store_postgres/chunk_writer.py#L106)).
- **AD-10** — the *pièce*'s full text is a first-class addressable artefact with its own identity/version (`piece.full_text`, `text_version`, `text_identity`); it is the resolver's source of truth.
- **AD-11** — every chunk carries the embedder trio (2.8); each passage is embedded from its own text.
- **AD-7** — no hard delete, no cascade; old generations retire by state.
- **AD-23** — a change to a `affects_retrieval` config (chunking included) marks derived artefacts stale; the degraded verdict is the read-time face of the same idea.
- **AD-14** — SQL/ORM over tenant-owned tables lives under `core/app/read/` (the resolver) or the store adapter; not scattered.
- **AD-4** — `core/` imports no adapter; the chunker and the resolver's domain logic are pure.

### Files to touch (and blast radius)

**New**
- `apx/core/domain/chunking/__init__.py` (+ `chunker.py` / `config.py`) — `Passage`, `ChunkingConfig` (derived `version`), `chunk(full_text, config)`. Pure domain.
- `apx/core/app/read/` — the resolver + containment verifier + the degraded-container helper (read orchestration; AD-14).
- Tests: `tests/domain/test_chunking.py` (determinism, spans, French citations, config→version), `tests/app/test_chunk_resolution.py` (resolve + the four failure causes + degraded container), and multi-passage cases added to `tests/adapters/test_embedding_ingest.py`.

**Modified (source)**
- `apx/core/app/embedding.py` — `embed_result` chunks + embeds per passage; `_payload_for` gains `position`; the all-or-nothing-per-pièce failure path.
- `apx/adapters/store_postgres/admission.py` — resolve the `ChunkingConfig`, pass it in, stamp `config.version`.
- `apx/core/domain/config.py` — reconcile `chunking_config_version` with the derived identity (and any chunking param keys added as config-as-data).
- Possibly `apx/adapters/store_postgres/store.py` — a read method for the resolver (load a chunk + its pièce full text under scope).

**NOT touched** — `models.py` (no new column), no alembic migration (head stays 0021), `chunk_writer.py` (the write seam is unchanged — still one `write_chunk` per chunk; it already takes `position`).

### What NOT to build (scope discipline)

- No *pièce* viewer, no per-format highlighting (FR-44 — later, UX pass).
- No retrieval, ranking, retained extracts, or justification (epic 4 — FR-14/FR-41/FR-46).
- No parent/child stored hierarchy (AD-9 frozen).
- No contextual header on the embedded text (a provenance trap — see Dev Notes; epic 4).
- No re-chunk migration of existing generations (retire-by-state is AD-7; the migration that produces a new generation on a config change is a later story). Because only the derived config *version* is stored (not the old params), once the chunking config changes every existing chunk resolves as `config-superseded` — uniformly degraded, not resolvable — so 2.9 **enforces AD-40 immutability**: `set_config` refuses a `chunking_target_chars` change once a corpus exists (the change is allowed only before the first chunk, or via the deferred audited re-chunk).
- No new heavy dependency (no `langchain`/`nltk`/`spacy`).

### Project Structure Notes

- The chunker is pure domain (`core/domain/chunking/`), consumed by the app layer (`core/app/embedding.py`) and the read path (`core/app/read/`) — the same core-imports-no-adapter layering (AD-4) the rest of `core/` follows.
- The resolver's tenant-table reads belong under `core/app/read/` (AD-14); the raw SQL is a store method, mirroring how the store already exposes `existing_piece_ids`, `inventory`, etc.
- `chunking_config_version` already exists as a config-as-data key ([config.py:156](apx/core/domain/config.py#L156), default `"v1"`, `affects_retrieval=True`) — 2.9 makes it load-bearing and derives it, rather than introducing a parallel key.

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story-2.9] — the three acceptance-criteria bullets (provenance + determinism; honest failed resolution + degraded export; configuration-as-data + distinguishable).
- [Source: _bmad-output/planning-artifacts/epics.md#FR-11] — "Every chunk traces to the exact position it came from, chunk boundaries are deterministic under a fixed configuration, every quoted extract is verified by exact string containment at the moment it is shown, and a resolution that fails is surfaced as such and marks the containing export degraded."
- [Source: ARCHITECTURE-SPINE.md] — AD-9 (enumerated chunk columns), AD-10 (full text a first-class artefact), AD-11 (embedder trio), AD-40 (piece/chunk identity, immutable chunking config, version guard), AD-7 (no hard delete), AD-23 (staleness), AD-14 (read path), AD-4 (core imports no adapter).
- v1 salvage (reference only, never an edit target): `../apx-platform/**/domain/chunking/strategies.py` — keep the *contextual-header* idea where it doesn't add a column or break determinism; **discard** the sentence splitter that broke French legal citations; parent/child is not adopted (frozen AD-9 schema).
- Seam under change: [apx/core/app/embedding.py](apx/core/app/embedding.py) (the placeholder whole-piece chunk), [apx/adapters/store_postgres/admission.py](apx/adapters/store_postgres/admission.py) (the admit seam), [apx/core/domain/identity.py:36](apx/core/domain/identity.py#L36) (`chunk_id`), [apx/adapters/store_postgres/chunk_writer.py](apx/adapters/store_postgres/chunk_writer.py) (the one write seam), [apx/adapters/store_postgres/models.py:128](apx/adapters/store_postgres/models.py#L128) (`Chunk`).

## Dev Agent Record

### Agent Model Used

claude-opus-4-8 (1M context) — BMAD dev-story.

### Debug Log References

Gate after each task: `ruff check .`, `pytest` (no `DATABASE_URL` override — SQLite baseline), `python -m apx.checks`. Final (post-review): **ruff clean · 698 passed / 10 skipped · 47 structural checks · alembic single linear head 0021 (no migration — provenance by resolution adds no column)**. The adversarial three-reviewer pass added four regression tests (containment-anchored, whitespace-only register, AD-40 immutability guard, store-level AC7), taking the count 694 → 698 — see the Senior Developer Review (AI) section. One cross-cutting fix during the build: dropping the free-string `chunking_config_version` config key (replaced by `chunking_target_chars`, version derived) required updating the README config-key table (the `config_defaults`/documentation checks and the fitness driver's "structural checks pass" stage all read it) — four tests went red on the stale README row and green once it matched `CONFIG_SCHEMA`.

### Completion Notes List

- **Provenance is resolved, not stored (the load-bearing decision).** AD-9 freezes the `chunk` columns with no offset column, so a chunk carries only `position` + `full_text_version` + `chunking_config_version`. `store.resolve_chunk` re-chunks the pièce's stored full text (AD-10) under the recorded config and takes `position` — the deterministic chunker (`core/domain/chunking.chunk`) makes the recovered span exact, and every passage is an exact slice `full_text[start:end]` so containment is trivially true for a fresh passage. This is why 2.9 adds **no column and no migration**.
- **The chunking-config identity is derived from the config content (AD-40).** The free-string `chunking_config_version` config key (which could stamp "v1" on chunks a different configuration produced — the 2.8 embedder-stamp lesson) was **dropped**; the chunking parameter is now `chunking_target_chars` (config-as-data), and `ChunkingConfig.version` is a content hash of the params, so the identity on a chunk cannot diverge from what produced it. A config change is a new generation; a chunk whose version ≠ the current config resolves as `config-superseded` (never silently re-interpreted, AD-40).
- **Real multi-passage chunking, all-or-nothing per pièce (AC2/AC7).** `embed_result` chunks each pièce's full text, embeds **each passage's own text**, and emits one chunk per passage at positions `0..N-1`. If any passage fails to embed (raise / empty extraction / wrong count / wrong width), the WHOLE pièce is a register entry with zero chunks — never partial provenance — so `submitted == in_corpus + open` still holds (Story 2.7). The 2.8 whole-piece placeholder is gone.
- **The resolver is honest and scope-checked (AC3/AC4/AC5).** `resolve_passage` (pure domain) returns a typed `FailedResolution` for each enumerated cause — `text-changed` (a new `full_text_version`, or the stored text no longer hashing to its recorded identity), `config-superseded`, `position-out-of-range`, `containment-failed` (a supplied stored extract no longer exactly contained) — and `piece-gone` is detected by `store.resolve_chunk`, which is fail-closed on scope (an out-of-scope or unknown chunk is refused, existence never disclosed). `is_degraded` marks a container degraded if any extract it carries failed.
- **French legal text is not mangled (AC8).** The hand-rolled splitter (no `langchain`/`nltk`/`spacy`) never cuts inside `art. L. 1235-3`, `n° 21-12.345`, `M.`, `Cass. soc.`, … — the exact forms the v1 `.split(".")` splitter shattered. Passage size is config-as-data and awaits the Story 2.13 chunk-yield measurement (values not invented here).
- **Deliberate deviations from the story's file plan (all more consistent with the codebase):** the chunker is a **flat module** `apx/core/domain/chunking.py` (not a package — matching `identity.py`/`payload.py`); the resolver is a **store method** `store.resolve_chunk` (not a `core/app/read/` module — matching how every read in this codebase is a store method; `core/app/read/` stays the placeholder it is). No separate `ChunkingConfig.defaults()` — `ChunkingConfig()` is the default and `chunking_config(get)` reads config-as-data.
- **Deferred, faithfully:** the pièce viewer + per-format highlighting (FR-44), the export-UI wiring of the degraded verdict (FR-46), hierarchical parent/child + contextual headers (AD-9 has no parent column; a contextual header on the embedded text is a provenance trap — both are epic-4 retrieval-time concerns), and the audited re-chunk migration of a superseded generation (AD-7 retire-by-state; after a config change every old chunk is uniformly `config-superseded`/degraded until re-chunked, and `set_config` refuses the change while a corpus exists — the audited re-chunk is the later story).

### File List

**New**
- `apx/core/domain/chunking.py` — `Passage`, `ChunkingConfig` (derived `version`), `chunk` (the deterministic French-legal-aware splitter), `chunking_config` (config-as-data), `resolve_passage` + `ResolvedPassage`/`FailedResolution` + the enumerated causes, `is_degraded`.
- `tests/domain/test_chunking.py` — determinism, exact spans, French citations, config→version.
- `tests/domain/test_chunk_resolution.py` — the resolver's happy path + every failure cause (pure domain).
- `tests/adapters/test_chunk_resolution_store.py` — the store-backed round-trip on real admitted chunks + text-changed / piece-gone / containment / scope / degraded.

**Modified (source)**
- `apx/core/app/embedding.py` — `embed_result` chunks + embeds per passage (all-or-nothing per pièce); `_payload_for` gains `position`.
- `apx/adapters/store_postgres/admission.py` — `admit` resolves the `ChunkingConfig` and stamps `config.version`.
- `apx/adapters/store_postgres/store.py` — `resolve_chunk` (the scope-checked provenance round-trip); imports `Chunk` + the chunking domain.
- `apx/core/domain/config.py` — dropped `chunking_config_version`, added `chunking_target_chars` (config-as-data, `affects_retrieval`), version derived.
- `README.md` — the config-key table row updated to `chunking_target_chars`.

**Modified (tests)**
- `tests/adapters/test_embedding_ingest.py` — the `embed_result` signature; multi-passage cases (AC2/AC7) + the whitespace-only register test (review). `tests/adapters/test_config_surface.py` — the retrieval-key-change test now sets `chunking_target_chars`.

*Review fixes also touched:* `apx/adapters/store_postgres/store.py` (`set_config` AD-40 immutability guard + the `resolve_chunk` non-disclosing scope refusal), `apx/core/domain/chunking.py` (position-anchored containment + honest resolver docstring), and added regression tests (containment-anchored, scope-no-leak, AD-40 guard, store-level AC7).

## Senior Developer Review (AI)

**Reviewed:** 2026-07-29 · **Outcome:** Approve (all Med resolved, Low triaged) · **Method:** three parallel adversarial reviewers, each execution-verifying its findings against in-memory SQLite and confirming the working tree byte-identical afterwards, each on a distinct lens: (R1) provenance & determinism correctness, (R2) the denominator invariant & all-or-nothing per pièce, (R3) config-as-data / AD-40 immutability / the frozen schema / scope & security. (One R3 launch died producing injection-shaped text — a fake "read SKILL.md and follow it" instruction — which was correctly treated as data and ignored; R3 was relaunched.)

The reviewers verified the core as **solid**: the deterministic chunker tiles `[0, len)` exactly with exact slices over ~24 000 adversarial inputs (0 gaps/overlaps); determinism holds across processes; all-or-nothing per pièce is airtight (verified 6 ways — raise mid-passage, N±1 vectors, a wrong-width vector buried at index 3, idempotent re-admit); the derived config version is stable and non-divergent; dropping the config key has a clean blast radius; the 47 structural checks stay honest; and there is no cross-tenant resolution.

### Action items — resolved

| # | Sev | Finding | Resolution |
|---|-----|---------|------------|
| R1-1 | Med | Containment checked the whole `full_text`, not the resolved passage — an extract living in a *different* passage passed (FR-11 "at the moment it is shown"). | `resolve_passage` computes the passage first, then checks `expected_text in passage.text`. Regression: `test_containment_is_anchored_to_the_resolved_passage_not_the_whole_text`. |
| R3-1 | Med | `store.resolve_chunk` disclosed chunk existence + the matter id across the Chinese wall via the `ScopeDenied` argument (unknown → echoed the supplied id; out-of-scope → echoed the derived matter). | The out-of-scope branch now raises `ScopeDenied(chunk_id)` — echoes only the caller-supplied id, indistinguishable from the unknown branch. Regression: `test_resolution_is_scope_checked_and_discloses_nothing`. |
| R3-2 | Med | AD-40 immutability unenforced — a routine `set_config("chunking_target_chars", …)` silently supersedes the entire tenant corpus (every chunk → `config-superseded`, old params unrecoverable). | `set_config` refuses a `chunking_target_chars` change once a corpus exists (`_refuse_immutable_chunking_change`, `ConfigError`); allowed before the first chunk or via the deferred audited re-chunk. Regression: `test_chunking_config_is_immutable_once_a_corpus_exists`. Corrected the inaccurate "resolvable under their own version" prose. |
| R1-2 | Med (doc) | The sha256 `text_identity` check is a tautology (the store always writes `text_identity = sha256(full_text)`), so it is a torn-row/corruption backstop, not the independent text-change detector the docstring/AC advertised; the real guard is `full_text_version`. | Made the docstring honest (primary guard = the version; sha256 = a torn-row backstop, never the ingestion path). |
| R1-3 / R2 | Low | A whitespace-only pièce was embedded as a junk corpus chunk instead of `EXTRACTED_EMPTY` (the `if not passages` guard only caught truly empty text). | Guard on `piece.full_text.strip()` → `EXTRACTED_EMPTY`. Regression: `test_a_whitespace_only_piece_is_a_register_entry_not_a_corpus_chunk`. (Exotic zero-width-only content remains a documented Low — an extraction-layer concern.) |
| R2 | Low | AC7 (all-or-nothing) had no *store-level* test — only `embed_result`'s return values were asserted. | Added `test_a_multi_passage_partial_embed_failure_fails_the_whole_piece_in_the_store`, asserting `in_corpus`/`open`/chunk-count independently (the 2.8-review pattern, since `is_consistent()` alone can be watermark-masked). |

### Triaged — acknowledged, not actioned (rationale recorded)

- **R2 Med — a register pièce re-imported successfully is counted in BOTH corpus and register (masked double-count).** Reproduced, but **pre-existing from Story 2.8** — the reviewer verified via `git show c2b0e35` that `admit`'s `existing_piece_ids`-only disjointness guard is identical; 2.9 did not introduce it. `admit` queries the Piece table only, so a unit still sitting in the *failure register* (no Piece yet) is treated as new on re-import and its open `Failure` is never resolved. Its correct fix is the **retry-reconciliation handler (Story 2.11)**, where "a re-imported failed path resolves its register entry" belongs (the same place the retry UX and `retry_failure`/`bulk_retry` wiring land). Deferred there, not bolted onto the chunking story.
- **R2 Low/info — the `save` → N×`write_chunk` atomicity window widened from 1 to N.** A crash between the pièce commit and the last chunk write leaves a partial `0..N-1` chunk set. Not a denominator break (the pièce is counted once) and it self-heals on idempotent re-admit (`session.merge` by deterministic `chunk_id`); an atomic batch-write would change the frozen one-`write_chunk`-per-chunk seam and is deferred.
- **R3 Low — 60-bit truncated version hash** (~2⁻⁶⁰ collision for small-int params, cryptographically negligible) and **`position-out-of-range`** being unreachable on the clean path (a deliberate determinism/corruption tripwire, as AC4 asks). No action.
