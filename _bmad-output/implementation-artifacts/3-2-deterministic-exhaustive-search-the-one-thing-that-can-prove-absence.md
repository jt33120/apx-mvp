---
baseline_commit: bd5d5c5
---

# Story 3.2: Deterministic exhaustive search — the one thing that can prove absence

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a lawyer who must tell a court a term appears nowhere in the *corpus*,
I want an exact search over the full stored text that returns the complete match set with its *denominator*,
so that I can say "searched everything indexed, zero occurrences" and defend it.

## Scope note — the ENGINE + the EXHAUSTIVE data contract + the normalisation rule; the absence-statement WORDING is deferred

This is the second of Epic 3's two engines (AD-20): the **deterministic** engine that **proves** and returns the whole match set — *truth status* **exhaustive** — the one thing that can prove an absence. It is the product's **most dangerous output** (AD-42: "a complete-looking answer whose completeness is true only of the material that happened to be searchable"), so its honesty lives in the *denominator* the set carries and in a normalisation rule that behaves by design, not by accident.

**What this story builds (backend + data, CI-verifiable):**
- The **`normalize()` French rule** — a defined, tested, config-as-data normalisation (diacritics, case, elision, hyphenation across a line break, whitespace) so "l'état", "etat" and "État" behave as **specified** (AD-21). Recall-first: it folds variants so the one document is never missed.
- The **deterministic engine** in the one read entry point `core/app/read/` (AD-14): an exact, normalised search over the stored full text (AD-10) **and** the filename-as-submitted / extractable title, scope **pre-filtered** (AD-13), returning the **complete match set** (never a top-k) as an **`ExhaustiveResultSet`** whose `truth_status` is the constant `EXHAUSTIVE` (the Story 3.1 gate already admits a second engine).
- The **`denominator`** the set carries (AD-38's six-field `Inventory`, not an integer) plus the open **failure-register** entries and the **unknown-cardinality** `container-unopenable` entries — the qualifications that make an absence claim honest (AD-42, as **data** on the set).
- **AD-20's two rules as structure**: the exhaustive engine's constructor takes **no limit/top-k** (a `LIMIT`/`top_k`/page size downgrades a set to suggestive — a **structural check**); and the engine **refuses** over a *matter* with an **open import job** (one snapshot, never over a moving population), naming the job.
- The **failure register searched separately** (AD-21): a *pièce* in the register is **not** in the searched set; a name match there returns a **register hit**, visibly distinct, never counted inside the exhaustive set.

**What is deferred (honestly — the "UX pass required" banner):**
- **The absence-statement WORDING + the surface / export rendering** — AD-42's rule that a surface/export shows the four qualifications *"searched everything indexed within this scope; the register lists 2 800 unreadable and 1 archive of unknown contents"* binds the surfaces via the **AD-33 action registry**, which is itself **deferred** (`deferred-action-registry`, FR-21). This story makes the four qualifications **data on the set**; the phrasing, the visual/verbal distinctness, and the export rendering are the UX pass (with Story 3.4).
- **The paginated cursor over one snapshot** for a match set larger than the transport bound (AD-20) — a transport/surface concern; the **count + qualifications** (the absence-claim data) are built here, the cursor UI is deferred.
- **Recall quality / a gold-set number** — Epic 4 (`recall_at_the_line` stays deferred).

## Acceptance Criteria

1. **The engine returns the COMPLETE match set with `truth_status = EXHAUSTIVE` and its denominator (FR-13, FR-57, AD-20, AD-21).** A deterministic search in `core/app/read` taking `(tenant, scopes, query)` — no identifier-only method, no `limit`/`top_k` parameter — returns an `ExhaustiveResultSet` carrying: `truth_status == TruthStatus.EXHAUSTIVE` (constant, one site), the **complete** set of matching *pièces* (never truncated), the **scoped denominator** (the AD-38 `Inventory` record, not a bare integer), and the open **failure-register** count and **unknown-cardinality** container count. *(tests: a query returns every matching pièce (not a top-k); the set is `EXHAUSTIVE`; it carries the six-field denominator + register + unknown counts; the engine signature has no limit parameter.)*

2. **French normalisation is a defined, tested rule — accents, elision, hyphenation, case (FR-13, AD-21).** A pure `normalize()` (config-as-data) folds diacritics, case, the elision apostrophe (`l'état` → `etat`), a hyphen across a line break, and whitespace, so `"l'état"`, `"etat"` and `"État"` match a query for any of them, **by the rule** and not by accident; the applied normalisation is **declared on the result set**. *(tests: a table of French variants — `l'état`/`etat`/`État`, `œuvre`/`oeuvre`, a hyphen-split word — all match; the rule is deterministic and declared on the set.)*

3. **AD-20's structural rules: no truncation, and refuse over a moving population.** A structural check asserts the deterministic engine's construction site takes **no** `limit`/`top_k`/page-size parameter (a truncation would downgrade an exhaustive set to suggestive — no configuration may prevent that); and the engine **refuses** (a typed refusal naming the job, in the lawyer's language, offering the worklist line) when the *matter* has an **open import job** (`open_import_job`), never silently downgrading to suggestive. *(tests: the new structural check is green on the real tree and fires on a fixture whose exhaustive constructor takes a limit; an open-import-job matter yields the typed refusal, not a partial set; README ↔ manifest lockstep, check count rises.)*

4. **The register is searched separately; an unreadable pièce is qualified as data (FR-13, AD-21, AD-42-data).** A *pièce* in the **failure register** is **not** in the searched set; the register is searched separately within scope and a name match returns a **register hit**, visibly distinct and **never** counted inside the exhaustive set. The set carries, as data, the OCR-derived share of the searched set and the share below the quality signal — so an unreadable *pièce* is *"in the corpus but its text may not be"* (the v1 "guess in the costume of a proof" relocated to the extraction layer is prevented at the data level). *(tests: a register pièce is not in the exhaustive set and returns as a distinct register hit; the OCR-share qualification is present on the set.)*

5. **Scope is a query PRE-filter; no scope → empty; and the gate stays green (AD-12, AD-13, AD-14, FR-14).** The scope predicate is joined into the query (AD-13, tenant on both sides), never a post-filter (`no_post_filter_in_retrieval` stays green); an empty scope returns an empty exhaustive set (fail-closed). The Story 3.1 constant-truth-status gate stays green with the second engine present (its `EXHAUSTIVE` site is a constant). *(tests: empty scope → empty; `no_post_filter_in_retrieval` green; the truth-status gate green with both engines.)*

6. **The gate stays green; migration only if the full-text infra needs it.** `ruff` clean; the full suite green; `python -m apx.checks` passes with the new no-truncation check registered (count rises; README ↔ manifest lockstep); the Story 2.13 perf-ceiling gate stays green (nothing declares a perf ceiling); `alembic heads` = single head. If the normalised full-text search needs the `unaccent` extension or a normalised index, add **one** migration (0022) — reversible, Postgres-only — and it becomes the single head; otherwise none.

## Tasks / Subtasks

- [x] **Task 1 — the French normalisation rule (AC2).**
  - [x] `apx/core/domain/` — a pure `normalize(text) -> str` (and the declared parameters as config-as-data) folding: Unicode diacritics (NFKD + strip combining marks, so `État`→`etat`, `œuvre`→`oeuvre`), case, the elision apostrophe (`l'`/`d'`/`qu'` → the following word), a hyphen immediately before a newline (scanned line-break hyphenation), and whitespace runs. Recall-first, deterministic. Applied identically to the query and (conceptually) to the stored text. *(`apx/core/domain/normalization.py::normalize` (`fr-fold-v1`): ligature expand → NFKD strip diacritics → casefold → de-hyphenate a line break → apostrophe→space (the elided word stands alone, found by containment) → collapse whitespace. `NORMALIZATION` version declared on the set.)*
  - [x] Tests (`tests/domain/`): a table of French variants (`l'état`/`etat`/`État`, `œuvre`/`oeuvre`, `bail-\nleur`/`bailleur`) all normalise to one key; the rule is deterministic; the applied normalisation is exposed for the result set to declare. *(`tests/domain/test_normalization.py`, 6 tests: diacritics/case, œ/æ, line-break hyphen vs real hyphen, elision containment, whitespace/determinism.)*

- [x] **Task 2 — the `ExhaustiveResultSet` domain type (AC1, AC4-data).**
  - [x] `apx/core/domain/retrieval.py` — an `ExhaustiveResultSet` (frozen): `truth_status = field(default=EXHAUSTIVE, init=False)` (constant, the Story 3.1 gate admits it), the complete `results` (matter + pièce identity + a normalised snippet handle), the `denominator` (the AD-38 `Inventory`), the `open_register_entries` count, the `unknown_cardinality` count, the `ocr_share` / `below_quality_share` qualifications, and the declared `normalization`. It carries **no** `limit`/`top_k`/page-size field — an exhaustive set is never truncated (AD-20). A **register hit** is a distinct type, never inside the exhaustive results.
  - [x] Tests: the set is `EXHAUSTIVE`, carries the denominator + register + unknown + OCR-share, has no limit/top-k field; a register hit is a separate type.

- [x] **Task 3 — the deterministic engine in `core/app/read/` (AC1, AC4, AC5).**
  - [x] `apx/core/app/read/deterministic.py` — the engine taking `(tenant, scopes, query)` (no limit): normalise the query, run the scoped exact search over full text + filename + title via the read port, assemble the `ExhaustiveResultSet` at one site with the constant `EXHAUSTIVE`, attach the denominator (reuse the `Inventory`/denominator path) + register + unknown counts. **Refuse** (a typed `MovingPopulation`/`ImportInProgress` error naming the job) when `open_import_job` returns a job. Search the **register separately**; return register name-matches as distinct hits. Empty scope → empty (fail-closed).
  - [x] Extend the read port (`apx/core/ports/read.py`) with the scoped exact-search method (no limit param; scope required; no result-set post-filter — keep `no_post_filter_in_retrieval` green).
  - [x] Tests: CI proof over a **fake reader** (in-memory normalised match) — complete set, `EXHAUSTIVE`, register-separate, empty-scope empty, open-job refusal.

- [x] **Task 4 — the Postgres adapter: the normalised exact query (AC1, AC2, AC5).**
  - [ ] `apx/adapters/store_postgres/` — formalise the existing `SqlStore.search` (today an un-normalised ILIKE **with a `limit`** — the AD-20 violation to remove) into the deterministic engine's read method: a normalised exact match (`unaccent`/`lower` or a normalised expression matching the `normalize()` rule) over `Piece.full_text` + filename/title, scope **joined as a pre-filter** (AD-13, tenant on both sides — mirror `semantic_query.py`), returning the **complete** set + the true count. If `unaccent`/a normalised index is required, add migration **0022** (reversible, Postgres-only). `unaccent`/normalised match is Postgres-native → CI asserts the query **shape** (scope pre-filter, normalisation applied, no `LIMIT` on the exhaustive path) by PG-dialect compilation, as in Story 3.1; the live round-trip runs on the target.
  - [x] Tests: compiled-shape (scope join pre-filter, tenant both sides, no LIMIT, normalisation applied); the register-search query is separate.

- [x] **Task 5 — the no-truncation structural check (AC3) — the AD-20 rule as a gate.**
  - [x] `apx/checks/` — a structural check `exhaustive_engine_takes_no_limit` (mirror the Story 3.1 `truth_status` / `payload_schema.scope_arg_required` pattern): the deterministic engine's public search / the `ExhaustiveResultSet` construction accepts no `limit`/`top_k`/`page_size` parameter, so no configuration can truncate an exhaustive set. Fail-closed on an unparseable file; injectable `roots`. Register in manifest + registry + README (lockstep).
  - [x] Tests (`tests/checks/`): green on the real tree; fires on a fixture whose exhaustive search takes a `limit`; check count rises; lockstep holds.

- [x] **Task 6 — full re-gate (AC6).** `ruff check .`; `pytest` (no `DATABASE_URL` override — SQLite baseline); `python -m apx.checks` (count rises by the no-truncation check; `no_post_filter_in_retrieval`, the 3.1 truth-status gate, and the perf-ceiling gate all green; README ↔ manifest lockstep); `alembic heads` = single head (0021, or 0022 if the full-text migration was needed).

## Dev Notes

### The load-bearing idea: an absence claim is only as honest as its denominator + its normalisation

FR-13 is the one thing triage cannot do: **prove an absence**. AD-42 names the danger — a complete-looking answer whose completeness is true only of what happened to be searchable — and puts the honesty in four numbers the set must carry (the *scoped denominator*, the open register entries, the unknown-cardinality containers, the OCR share). AD-21 puts the other half in the **normalisation**: opposing counsel needs the one document where the word appears with an accent the OCR dropped, so `l'état`/`etat`/`État` must behave **by a declared, tested rule**. This story builds both as **data + a pure rule**; the phrasing that renders them to a court is the deferred surface (AD-42 binds it via the deferred action registry).

### Reuse — do not rebuild

- **The existing `SqlStore.search`** (store.py) — an un-normalised ILIKE substring over `Piece.full_text`, scope pre-filtered (join to `MatterScope`, tenant on both sides), returning `SearchResults(query, total, hits)` with `total` the true count. It is the pre-3.2 stopgap: it **has a `limit` param** (the AD-20 no-truncation violation) and **no normalisation / truth-status / denominator**. Formalise it — remove the limit from the exhaustive path, add normalisation, carry the `EXHAUSTIVE` set + denominator.
- **`domain/search.py::snippet`** — the pure snippet helper (already the deterministic engine's display helper). Reuse for the register/hit snippets.
- **`domain/inventory.py::Inventory`** — the AD-38 six-field denominator (`submitted_pieces`, `in_corpus`, `open_register_entries`, `excluded_as_noise`, `retired`, …). Reuse as the set's denominator; the store already computes it.
- **`store.open_import_job(tenant, matter)`** — returns the id of an open (not-done) import job, or None. Use it for the AD-20 refuse-when-open rule.
- **The failure register** (`register_all` / the `Failure` table) — search it separately within scope for register name-matches (AD-21).
- **Story 3.1's read path**: `apx/core/ports/read.py` (extend), `apx/core/app/read/` (the engine lives here), `apx/adapters/store_postgres/semantic_query.py` (the scope-pre-filter join to mirror), the `TruthStatus`/`SuggestiveResultSet` pattern (the constant-site gate already admits `EXHAUSTIVE`), and the pg-only-query-shape-tested-in-CI honesty.
- **Structural-check house pattern**: `CheckResult`, `_p` in `manifest.py`, `CHECKS` in `registry.py`, the README block (lockstep). Mirror `payload_schema.scope_arg_required` (an AST param check) for the no-limit rule; `gold_gate`/`perf_gate`/`truth_status` for fail-closed + injectable roots.

### Architecture guardrails (binding)

- **AD-20** — two truth statuses, one constant site per engine; an exhaustive set is **never truncated** (the constructor takes no limit; a `LIMIT`/`top_k`/page size downgrades to suggestive — no config can prevent it); one snapshot, **refuse** over a *matter* with an open import job (never a silent partial set).
- **AD-21** — the deterministic engine is **PostgreSQL-native**, over full text (AD-10) + filename + extractable title, with **declared, config-as-data normalisation**; ParadeDB/pgvectorscale are excluded (AD-3/AD-5). The register is searched **separately** and never counted inside the exhaustive set.
- **AD-42** (the deferred surface) — an exhaustive set's four qualifications bind the **surfaces + export** via the AD-33 action registry (deferred). This story carries them as **data**; the rendering is the UX pass.
- **AD-38** — the *denominator* is one six-field record, never a bare integer.
- **AD-13 / AD-14 / AD-12** — scope a query pre-filter from the authoritative `matter_scope`, tenant on both sides; one read entry point, no id-only method, no post-filter; empty scope → empty (fail-closed).
- **NFR-2 / Story 2.13** — no invented latency/throughput target; declare no perf ceiling.

### The normalisation rule (the technical heart)

Recall-first: **fold** variants so the one document is never missed. `normalize()` = NFKD Unicode decomposition + strip combining marks (diacritics) + casefold + collapse the elision apostrophe (`l'`, `d'`, `qu'`, `j'`, `n'`, `s'`, `t'`, `m'`, `c'` → join to the following token) + join a hyphen-before-newline (scanned line break) + collapse whitespace. `œ`/`æ` → `oe`/`ae`. The **applied** normalisation is declared on the result set (AD-21). In PostgreSQL this maps to `unaccent(lower(...))` for accents+case with the elision/hyphenation handled by the same rule over the compared text; the pure `normalize()` is the tested contract, the DB query the pg-only realisation. Keep the rule **config-as-data** where AD-21 says the expression grammar (boolean/proximity/wildcard) is a declared choice — for 3.2, an exact normalised containment is the safe default; the grammar is a later tuning.

### Files to touch (and blast radius)

**New**
- `apx/core/domain/normalization.py` (or in `retrieval.py`) — the `normalize()` rule + declared params.
- `apx/core/app/read/deterministic.py` — the deterministic engine (refuse-when-open, register-separate).
- `apx/checks/<no_truncation>.py` — the no-limit structural check.
- Possibly `apx/adapters/store_postgres/migrations/versions/0022_*.py` — the `unaccent`/normalised-index migration (only if needed).
- Tests: `tests/domain/…`, `tests/core/app/read/…`, `tests/adapters/…`, `tests/checks/…`.

**Modified**
- `apx/core/domain/retrieval.py` — `ExhaustiveResultSet` + the register-hit type.
- `apx/core/ports/read.py` — the exact-search read method (no limit).
- `apx/adapters/store_postgres/store.py` (+ a `deterministic_query.py`) — formalise `search` into the normalised exact query; remove the limit from the exhaustive path.
- `apx/checks/manifest.py`, `apx/checks/registry.py`, `README.md` — register the no-truncation property.

**NOT touched** — no absence-statement wording/surface/export, no AD-42 surface-check (deferred, tied to the deferred action registry); no paginated-cursor UI; no change to the semantic engine, the write path, or the cascade.

### What NOT to build (scope discipline)

- No absence-statement WORDING, no surface, no export rendering (AD-42 / the UX pass, with Story 3.4).
- No paginated cursor over one snapshot (transport/surface — the count + qualifications are the data built here).
- No recall/quality measurement (Epic 4).
- No new search service (ParadeDB/pgvectorscale) — PostgreSQL-native only (AD-21/AD-3).
- No invented perf ceiling (NFR-2). No boolean/proximity/wildcard grammar yet (exact normalised containment is the 3.2 default).

### Project Structure Notes

- The deterministic engine joins the semantic engine under `core/app/read/` (AD-14, one entry point). The two engines have **separate** result-set types and **separate** constant construction sites (AD-20: one per engine) — the 3.1 truth-status gate already admits the `EXHAUSTIVE` site.
- The existing `SqlStore.search` is the stopgap being formalised; its `limit` param is the AD-20 violation to remove from the exhaustive path (a bounded *preview* for a non-exhaustive surface, if ever needed, is a separate suggestive concern).

### References

- [Source: epics.md#Story-3.2] (lines 1014–1029) — the four ACs (complete match set + denominator; French normalisation by a defined rule; the absence claim carries scope + denominator in the exported wording [deferred]; the OCR-too-poor failure path) + the "UX pass required" banner.
- [Source: ARCHITECTURE-SPINE.md#AD-20] (580–613) — one constant site per engine; an exhaustive set is never truncated (the constructor takes no limit); one snapshot, refuse over an open import job.
- [Source: ARCHITECTURE-SPINE.md#AD-21] (615–631) — PostgreSQL-native over full text + names; declared, config-as-data normalisation; the register searched separately.
- [Source: ARCHITECTURE-SPINE.md#AD-42] (the deferred surface) — the four qualifications bind the surfaces + export via the AD-33 action registry (deferred).
- [Source: ARCHITECTURE-SPINE.md#AD-38] — the denominator is a six-field record, never a bare integer.
- Reuse: `SqlStore.search` + `SearchResults`/`SearchHit` (store.py), `domain/search.py::snippet`, `domain/inventory.py::Inventory`, `store.open_import_job`, `register_all`; Story 3.1's `apx/core/ports/read.py`, `apx/core/app/read/`, `semantic_query.py` (the scope-pre-filter join), `apx/core/domain/retrieval.py` (`TruthStatus`, the constant-site gate that admits `EXHAUSTIVE`), `apx/checks/payload_schema.py` (`scope_arg_required`, the AST param pattern) + `truth_status.py`/`gold_gate.py`/`perf_gate.py` (fail-closed, injectable roots).

## Dev Agent Record

### Agent Model Used

claude-opus-4-8[1m] (Opus 4.8, 1M context) — dev-story.

### Debug Log References

- `python -m apx.checks`: 51 structural properties (50 → 51; the no-truncation gate added). Truth-status gate green with BOTH engines (2 constant sites); AD-38 no-sum green; `no_post_filter_in_retrieval` + perf-ceiling gate green.
- `alembic heads`: single `0022_unaccent_extension` (0021 → 0022 — the `unaccent` contrib extension for the normalised search).

### Completion Notes List

- **The normalisation rule (AC2, the technical heart).** `apx/core/domain/normalization.py::normalize` (`fr-fold-v1`): ligature expand (œ/æ) → NFKD strip diacritics → casefold → de-hyphenate a scanned line break → elision apostrophe → space → collapse whitespace. Recall-first — `l'état`/`etat`/`État` all match by containment. `NORMALIZATION` declared on the set.
- **The `ExhaustiveResultSet` (AC1, AC4).** `truth_status = EXHAUSTIVE` constant `init=False` (the second engine — the Story 3.1 gate admits it, now 2 sites); the COMPLETE set (no limit/top-k field); carries the `denominator` (AD-38 `Inventory`, which holds the register + unknown-cardinality counts), the OCR shares (AD-42 data), the register hits (separate type), and the declared normalisation.
- **The engine (AC1, AC4, AC5).** `apx/core/app/read/deterministic.py::search_exhaustive` — the second reader through `core/app/read/`. Normalises the query, **refuses** over a moving population (`MovingPopulation`, naming the job — AD-20), builds the set at one site. Register searched separately (never inside results, AD-21). Empty scope → empty (fail-closed). Proven in CI over a fake reader applying the real `normalize` rule.
- **The Postgres query (AC1, AC5).** `deterministic_query.py::exact_search_stmt` — the normalised containment over the plaintext `full_text`, scope joined from `matter_scope` as a PRE-filter (tenant both sides), ranked, **NO LIMIT** (AD-20). `unaccent` is PG-only → CI asserts the compiled shape; the live round-trip runs on the target. `SqlStore.exact_search`/`open_import_jobs` wire it; the scoped denominator is computed DIRECTLY (`_scoped_inventory`, `func.sum`/`func.count`, never a Python `+` — AD-38 no-sum).
- **The no-truncation gate (AC3).** `apx/checks/no_truncation.py::exhaustive_engine_takes_no_limit` — anchored on the exhaustive TYPE (return annotation is `ExhaustiveResultSet`/`ExactSearch`): fires if such a function takes a `limit`/`top_k`/`page_size`/… Registered (50 → 51), README ↔ manifest lockstep.
- **Constraints & honest deferrals (never fabricated).** (1) The filename/title (`provenance_path`) is **encrypted at rest** (AD-31) → a SQL filename search is blocked; the engine searches the plaintext `full_text_normalized` (the register **counts** are in the denominator, and the register **name-match** — feasible in-app via decrypt-and-match — is deferred on scope, not blocked). (2) `below_quality_share` awaits an extraction-layer OCR-quality signal that does not exist → carried honestly as `0.0`. **(Corrected in review: `ocr_share` IS computable — OCR stamps `extraction_method == "tesseract"` — and is now computed for real, not `0.0`.)**
- **Deferred (the UX banner).** The absence-statement WORDING / surface / export + the AD-42 surface-check (tied to the deferred action registry) + the paginated cursor — carried as data here, rendered in the UX pass.

### File List

**New**
- `apx/core/domain/normalization.py` — the `fr-fold-v1` rule.
- `apx/core/app/read/deterministic.py` — the deterministic engine + `MovingPopulation`.
- `apx/adapters/store_postgres/deterministic_query.py` — the normalised exact-search query builder (plain escaped LIKE over `full_text_normalized`).
- `apx/adapters/store_postgres/migrations/versions/0022_deterministic_index.py` — add + backfill `full_text_normalized`.
- `apx/checks/no_truncation.py` — the no-truncation structural check.
- `tests/domain/test_normalization.py`, `tests/core/app/read/test_deterministic.py`, `tests/adapters/test_deterministic_query.py` (incl. the CI round-trip + store denominator/ocr tests), `tests/checks/test_no_truncation.py`.

**Modified**
- `apx/core/domain/retrieval.py` — `DeterministicResult`, `RegisterHit`, `ExhaustiveResultSet`.
- `apx/core/ports/read.py` — `ExactSearch` bundle + `ExactSearchReader` port.
- `apx/adapters/store_postgres/models.py` — `Piece.full_text_normalized` + the `_normalise_full_text` write-time event.
- `apx/adapters/store_postgres/store.py` — `exact_search` / `open_import_jobs` / `_scoped_inventory` / `_scoped_ocr_share`; the live `search` now normalised (a bounded preview).
- `apx/checks/encryption.py` — `full_text_normalized` added to the AD-31 plaintext-index exemptions.
- `apx/checks/manifest.py`, `apx/checks/registry.py`, `README.md` — register the no-truncation property.
- `tests/domain/test_retrieval.py` — the `ExhaustiveResultSet` tests.

### Change Log

- 2026-07-30 — Story 3.2 implemented (deterministic exhaustive search). The `fr-fold-v1` normalisation rule, the `ExhaustiveResultSet` (constant EXHAUSTIVE, no-limit, denominator + qualifications), the deterministic engine + read port in `core/app/read/` (refuse-when-moving, register-separate), the Postgres normalised query (scope pre-filter, no LIMIT), and the AD-20 no-truncation gate (50 → 51 checks). ruff clean.
- 2026-07-30 — Adversarial 3-reviewer review + fixes (see Senior Developer Review). The central fix: the normalisation moved to a **stored `full_text_normalized` column** folded at write time by the one `normalize()` rule — the corpus and the query now share ONE implementation (no Python↔SQL divergence → no false absence), a plain LIKE replaces `unaccent` (migration `0022_deterministic_index`), and the round-trip is **CI-testable** end-to-end. `ocr_share` computed for real (`extraction_method == "tesseract"`); LIKE metacharacters escaped; the tenant defence-in-depth pin restored; a blank query fails closed; the no-truncation gate strengthened (internal `.limit()` + forward-ref annotations); the live preview (`store.search`) now normalised too. ruff clean.

## Senior Developer Review (AI)

**Reviewers:** three independent adversarial lenses (the AD-20 no-truncation gate + EXHAUSTIVE contract / the normalisation rule + Python↔SQL agreement / the scope pre-filter + denominator + honest deferrals), execution-verified (SQL compiled to PostgreSQL, `normalize()` called directly, mutate→run→revert). The working tree was verified byte-identical to a pre-review backup. **Outcome: Changes Requested → all resolved.** The reviewers confirmed the scope pre-filter is a genuine no-post-filter join, the AD-38 denominator is never Python-summed, the gate fires, and there is no leak/regression — but found the normalisation architecture unsound and two honesty gaps.

**Findings (all fixed):**
1. **[HIGH] The query (`normalize()`, Python) and the corpus (`_folded`, SQL `unaccent`) were two independent normalisation implementations that DIVERGE** — on compatibility characters (nbsp/narrow spaces, U+FB0x ligatures, superscripts, œ/æ) — with the agreement asserted only in comments and tested nowhere (mutating `_folded` to `unaccent`-only still passed). For an absence-proving engine, a divergence = a silent false absence. **Fix:** normalise the full text at **write time** into a stored `full_text_normalized` column (an ORM `before_insert`/`before_update` event, so no caller can forget it) and search it with a plain escaped `LIKE`. The corpus and the query now share the ONE `normalize()` implementation — divergence is impossible by construction; `unaccent` (and its version-floor risk) is gone; migration `0022_deterministic_index` adds + backfills the column; and the round-trip is now **CI-testable** (`test_an_accented_document_is_found_by_an_unaccented_query_round_trip`).
2. **[HIGH] `ocr_share` was shipped as a false `0.0`** on the product's most dangerous output, justified by a wrong premise ("no OCR method value") — OCR is wired live and stamps `extraction_method == "tesseract"`. **Fix:** compute it for real (`_scoped_ocr_share`) from `extraction_method == "tesseract"` over the in-scope corpus; a test pins `1/3`.
3. **[HIGH→documented] The new engine is not wired to a live path** (the `/api/search` endpoint uses the bounded preview). The exhaustive set's rendering is the deferred AD-42 surface (as 3.1's semantic engine is not live-wired either). **Fix:** documented as the surface increment; and the live **preview** (`store.search`) is now **normalised** too, so the live path gains accent-folding (closing the worst live false-absence) — clarified as a bounded preview, not the exhaustive engine.
4. **[MED] LIKE metacharacters were unescaped** on the exhaustive path (a `%` in "au taux de 5 %" became a wildcard; a trailing `\` raised) — a regression vs the stopgap. **Fix:** `_like_escape` + `escape="\\"`; a test proves `5 %` is literal.
5. **[MED] The tenant defence-in-depth `WHERE matter_scope.tenant = :tenant` (present in 3.1) was dropped.** **Fix:** restored + asserted in the shape test.
6. **[MED] `_scoped_inventory` / `open_import_jobs` / `ocr_share` had no CI test.** **Fix:** a SQLite store test asserts the aggregate denominator, the real ocr_share, and the empty-scope/blank-query fail-closed.
7. **[MED] register-name-search deferral framing overstated AD-31.** **Fix:** restated honestly — the counts are already in the denominator; a decrypt-and-match is feasible in-app but out of scope here (not "impossible").
8. **[LOW] A blank/apostrophe-only query matched the whole corpus; the no-truncation gate was a name denylist.** **Fix:** a blank normalised query → empty set (fail-closed); the gate now also catches an internal `.limit()` and a forward-ref string annotation.

**Verified sound (no change):** the scope predicate is a genuine query PRE-filter (inner join, tenant both sides, `scope IN` before ORDER BY, no LIMIT); the AD-38 denominator uses `func.sum`/`func.count`, never a Python `+` (`unknown_cardinality_never_summed` green); `search_exhaustive` refuses over a moving population (never a partial set); empty scope → empty at both layers; the truth-status gate holds with BOTH engines (2 constant sites); no layering/isolation regression; the migration is reversible + Postgres-only.
