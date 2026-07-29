---
baseline_commit: eb54a0e
---

# Story 2.7: The inventory guarantee and the permanent denominator

Status: done

## Story

As a lawyer who must one day tell a court what was and was not reviewed,
I want a permanent, on-screen accounting where every submitted *pièce* is in exactly one of three named, countable places,
so that "nothing relevant was silently lost" is a number, not a hope.

## Scope note — the record + the guarantee are built in full; the visual home is deferred

This story replaces a **stopgap**. Stories 2.4/2.6 shipped a placeholder `Inventory` value object whose "invariant" is a **tautology** — `store.inventory()` returns `Inventory(in_corpus + failures, in_corpus, failures, 0)` ([store.py:910](apx/adapters/store_postgres/store.py#L910)), so `submitted` is *defined as* the sum it is supposed to be checked against and can never catch a miscount. That defeats SM-3 entirely. Story 2.7 makes the denominator **real**: the six-field AD-38 record, an invariant sourced so it is **falsifiable**, the filesystem-noise exclusion as configuration-as-data with a durable countable list, the two structural properties AD-38 names, and the release-blocker invariant test.

Consistent with every Epic-2 backend story, this builds the **complete, automatically-verifiable domain + store + API read contract** and **defers only the visual/interaction chrome**: the permanent home-screen *widget* rendering (Story 2.11, the worklist/matters zone) and the completion-summary *screen* (Story 2.10). The denominator's persistent **display contract** (the exact form, the named lines, the "not indexed" label, the words for unknown cardinality) is captured and asserted at the read-model/API level; nothing here pre-commits a visual design.

## Acceptance Criteria

Verbatim from [epics.md §Story 2.7](_bmad-output/planning-artifacts/epics.md) (FR-6 as corrected 21 July 2026, FR-57, FR-28; AD-38 the denominator record, AD-17 the application-owned ledger, AD-33 structural properties, AD-14/AD-13 the scoped read, AD-7 retired-never-deleted, AD-28 no verbatim fragments, AD-41 the noise list is client data). Each AC is decomposed into the assertion the dev must make fire.

**AC1 — `submitted = in corpus + open failures + declared exclusions`, no fourth bucket, no unnamed remainder; every term separately countable and displayed as its own line; asserted after every import job and every retry, at the design target.**
Given any *matter*, when its *denominator* is computed, then the identity holds **at all times**, each term separately countable and displayed as its own line, nothing in two terms or in none, with no fourth bucket and no unnamed remainder — asserted by an invariant test after every *import job* and every retry (FR-6, FR-57).
- *Assert:* the denominator is the **six-field AD-38 record** — `submitted_pieces`, `in_corpus`, `open_register_entries`, `excluded_as_noise`, `retired`, `unknown_cardinality_entries` — all disjoint, all read back durably. The **typed invariant** (per AD-38 + the spine's inventory state-machine note, [SPINE L1512-1518](_bmad-output/planning-artifacts/architecture/architecture-apx-mvp-2026-07-21/ARCHITECTURE-SPINE.md)) is `submitted_pieces == in_corpus + open_register_entries` over **known** pièces — `excluded_as_noise` and `retired` sit **outside** the identity as their own named lines; `unknown_cardinality_entries` is a **subset** of `open_register_entries` (`0 <= unknown <= open_register_entries`), **never summed** into any total, rendered in words. `submitted_pieces` is read from an **independent, durable, frozen source** (the AD-17 ledger), not recomputed as `in_corpus + open_register_entries` — the change that turns the tautology into a check. The ingestion completion path and `retry_failure` call `require_consistent()`; a violation **raises** (SM-3 hard failure).

**AC2 — Filesystem noise is a declared, configured, countable exclusion class, reported as its own line, one click from the list of what was excluded — neither silently dropped nor dominating the register.**
Given enumeration, when a file matches the declared noise list, then it is **excluded as noise** — configuration-as-data (`.DS_Store`, `Thumbs.db`, lock files, `desktop.ini`, resource forks), its excluded count reported as its own named line, and the excluded items durably listable — *"1 240 excluded as filesystem noise"* (FR-6).
- *Assert:* the noise list is **configuration-as-data** (the `exclusion_list` config key, resolved in the adapter and passed into pure core — never core reading the store), not a hard-coded constant; a matched file becomes an `excluded_as_noise` count that is **durable** (survives the transient ingestion result) and **enumerable** one line per excluded item within RBAC scope (the "one click from the list" backend); noise is **separate from the failure register** (it never inflates `open_register_entries`) and is **outside** the `submitted_pieces` identity. Default coverage includes lock files (`~$*`, `.~lock.*`), `__MACOSX/`, AppleDouble `._*`, alongside the existing `.DS_Store`/`Thumbs.db`/`desktop.ini`.

**AC3 — The denominator is permanent and visible on the home screen, carrying the failure-register count and the unknown-cardinality containers explicitly.**
Given the home screen, then the *scoped denominator* is displayed persistently in the stated form, carrying the *failure register* count and the unknown-cardinality containers explicitly (FR-28, FR-6, FR-57).
- *Assert:* the read model + API expose all six named counts **plus** the rendered unknown-cardinality phrase (*"N archive(s) unopened, contents unknown"*, never a number folded into a total) and the consistency flag; the **scoped** denominator (what a user sees, RBAC-filtered, recomputed live per read — FR-14/FR-28) and the **matter/tenant** denominator (what SM-3 is asserted over, unscoped/complete) are **two named quantities**, never one presented as the other; the read is scope-pre-filtered through the AD-14 entry point (`ScopeDenied` → 403, fail-closed, existence never disclosed). *(The permanent home-screen widget rendering is Story 2.11; the display contract is asserted here at the API level.)*

**AC4 — (failure path) A deliberately induced miscount — a pièce in two terms, or in none — fails the invariant test, which is a release blocker (SM-3).**
Given a deliberately induced miscount, when the invariant test runs, then it **fails** — SM-3, a single violation is a release blocker (FR-6).
- *Assert:* a test induces a pièce **in two terms** (e.g. a corpus pièce that also has an open register entry) and one **in none** (a durable `submitted_pieces` that exceeds `in_corpus + open_register_entries`), and asserts `require_consistent()` **raises** in each case. This is only writable because `submitted_pieces` is sourced **independently** of the RHS — the linchpin that proves the invariant is real, not tautological. Two **structural properties** back it (AD-33): (a) the inventory record declares **exactly** AD-38's six fields; (b) `unknown_cardinality_entries` is **never an operand of a sum** (AD-38: "never summed into any total" — the concrete no-`int`-collapse enforcement). Each has a firing failure-path fixture.

## Tasks / Subtasks

> Red-green-refactor, in order. Gate after each with `export PATH="$PWD/.venv/bin:$PATH"` then `.venv/bin/ruff check .`, `.venv/bin/python -m pytest` (**NO** `DATABASE_URL` override — it breaks the API/offline tests), `.venv/bin/python -m apx.checks`, and `alembic upgrade head` + a reversible downgrade for the migration task.

- [x] **Task 1 — The six-field AD-38 record + the corrected, falsifiable invariant (AC1, AC4).**
  - In [apx/core/domain/inventory.py](apx/core/domain/inventory.py): bring the **existing** `Inventory` to AD-38's **exactly-these-six** fields — rename `submitted → submitted_pieces`, `failures → open_register_entries`, `exclusions → excluded_as_noise`; **add** `retired: int = 0`; keep `unknown_cardinality_entries`. **Extend the one record, do not add a parallel `Denominator`** — AD-38 mandates *"one record with exactly these fields"*, and `MatterSummary`/`InventoryOut`/`IngestionResult.inventory` already carry this one. This record **is** "the denominator" (glossary, [prd.md:231](_bmad-output/planning-artifacts/prds/prd-apx-mvp-2026-07-20/prd.md#L231)).
  - Rewrite `is_consistent()` to the **AD-38 identity**: `submitted_pieces == in_corpus + open_register_entries` (known pièces); `excluded_as_noise` and `retired` are **outside** the identity (non-negative, displayed, not summed in); `0 <= unknown_cardinality_entries <= open_register_entries`; all counts `>= 0`. **Drop the `+ exclusions` term** — the old three-term form is the stopgap. `require_consistent()` keeps raising `ValueError` (SM-3). Keep `unknown_cardinality_phrase()` unchanged.
  - Update [tests/domain/test_inventory.py](tests/domain/test_inventory.py) to the new field names and the corrected identity; **add** the linchpin negative tests (AC4): a record with a pièce in two terms and one in none each fail `is_consistent()` / raise from `require_consistent()`.

- [x] **Task 2 — `submitted_pieces` as an independent, durable, frozen tally (AC1, AC4).**
  - The invariant is only a check if `submitted_pieces` is sourced **independently** of `in_corpus + open_register_entries`. Add a **durable per-matter frozen tally** maintained by the ingestion at post-expansion save time (AD-17: *the ledger is the only authority for every user-visible figure*), **idempotent under re-import** (a recognised-already-present pièce does **not** re-increment — reuse `SaveOutcome.pieces_new`, never `pieces_already_present`). Recommended home: a small durable per-`(tenant, matter)` row (a new `MatterInventory` table, or a `submitted_pieces` column folded onto the existing per-matter `matter_scope` row — dev's choice; the **contract** is durable + frozen + independent + idempotent, not the table shape).
  - `store.save()` ([store.py:590-639](apx/adapters/store_postgres/store.py)) increments the matter's `submitted_pieces` by the genuinely-new distinct submitted pièces of this result (`pieces_new + <new failures>`, excluding already-present and excluding noise). `store._counts`/`inventory`/`matters` read `submitted_pieces` from this durable source, **not** from `in_corpus + open_register_entries`.
  - *Falsifiability check (this is AC4 at the store level):* an adapter test deletes a `Piece` row (a pièce lost from the corpus) **without** touching the frozen `submitted_pieces`, then asserts `store.inventory(...).require_consistent()` raises. A tautological source cannot pass this test — that is the point.

- [x] **Task 3 — Filesystem noise as configuration-as-data, durable and listable (AC2).**
  - Wire the **orphaned** `exclusion_list` config key ([config.py:159-162](apx/core/domain/config.py#L159), `str_list`, default `[]`, defined but read nowhere) into enumeration. Resolve it in the **adapter** and pass the value into pure `apx/core/app/ingest.py`, exactly as `expansion_bounds(lambda k: store.get_config(tenant, k))` does at [queue/__init__.py:89](apx/adapters/store_postgres/queue/__init__.py#L89) — **core never reads the store** (`no_tenant_conditional_in_core`, `no_egress_call_site_outside_adapters`). Give the key a **non-empty default** covering `.DS_Store`, `Thumbs.db`, `desktop.ini`, `.gitkeep` (today's hard-coded `NOISE_NAMES`, [ingest.py:36](apx/core/app/ingest.py#L36)) **plus** lock files (`~$*`, `.~lock.*`), `__MACOSX/`, AppleDouble `._*`. Replace `_is_noise`'s `NOISE_NAMES` lookup with a matcher over the resolved list (glob/exact — keep it a pure function of `(name, patterns)`). **Document the key in the `README.md` config-keys block** between the markers, or `config_reference_is_complete` fails the build.
  - Persist excluded items **durably** so the count survives and the list is one-click reachable: a new `NoiseExclusion` model — `(tenant, matter, submitted_path, filename, pattern, timestamp)`, PK `sha256(tenant \0 matter \0 submitted_path)` (idempotent re-exclusion, exactly like `_failure_id`, [store.py:402](apx/adapters/store_postgres/store.py#L402)); `submitted_path`/`filename` are `EncryptedText` (AD-31/AD-28/AD-41 — the path is frequently the privileged fact) and added to `ENCRYPTED_COLUMNS` in [backfill.py](apx/adapters/store_postgres/backfill.py) (the 2.5 drift-guard will otherwise fail — good). `store.save()` writes the noise rows insert-if-absent from `IngestionResult.exclusions`. Add `store.noise_exclusions(matter, tenant, scopes)` (scope-checked read, the list backend) — the clickable **screen** is deferred with the UX pass.

- [x] **Task 4 — Durable counts for every term + the scoped/unscoped denominators (AC1, AC2, AC3).**
  - Extend `store._counts` ([store.py:864-876](apx/adapters/store_postgres/store.py#L864)) to also count: `excluded_as_noise` = `count(NoiseExclusion WHERE tenant, matter)`; `unknown_cardinality_entries` = `count(Failure WHERE tenant, matter, resolution_state='open', cardinality='unknown')`; `retired` = **0** for now (reserved — no retirement transition exists yet; wire it to `count(Piece WHERE retired)` the day a retired state lands, mirroring `Chunk.external_ref` reserved-unused). `store.inventory()`/`matters()` build the full six-field record from these + the durable `submitted_pieces`, dropping the hard-coded `0`s.
  - Provide the **matter/tenant denominator** (unscoped, complete) that SM-3 is asserted over, distinct from the **scoped denominator** the user reads (FR-6: *"two quantities with two names; no surface presents one as the other"*). The scoped read stays scope-pre-filtered (`ScopeDenied` fail-closed); the unscoped assertion path is internal (the invariant test + the post-job/post-retry `require_consistent()`), never a scoped user surface.

- [x] **Task 5 — Assert the invariant after every import job and every retry (AC1, AC4).**
  - The queue completion path (`finish_import`, [queue/__init__.py](apx/adapters/store_postgres/queue/__init__.py)) and `retry_failure`/`bulk_retry` ([store.py:1015+](apx/adapters/store_postgres/store.py)) compute the matter/tenant denominator and call `require_consistent()` — a violation **raises loudly** (SM-3), never silently proceeds. Keep the existing `ingest_folder` call to `result.inventory.require_consistent()` ([ingest.py:295](apx/core/app/ingest.py#L295)) working under the new field names.
  - Tests: after a real import job and after a retry that resolves an entry, the invariant holds; the AC4 induced-miscount tests assert it **fails** as a release blocker.

- [x] **Task 6 — The two structural properties (AC4; AD-33).**
  - New check module `apx/checks/inventory_record.py` (model on [register_ownership.py](apx/checks/register_ownership.py); reuse `_iter_py`/`_parse`/`_is_call_to` from `payload_schema`):
    - **(A) `inventory_record_fields_enumerated`** — the `Inventory` domain dataclass declares **exactly** AD-38's six fields (mirrors `payload_schema.chunk_columns_enumerated`). A dropped/added/renamed field fails the build.
    - **(B) `unknown_cardinality_never_summed`** — `unknown_cardinality_entries` (and `excluded_as_noise`, `retired`) is **never an operand of `+`** nor an argument to `sum(...)` across `apx/**` (AD-38: *"never summed into any total"*, *"the denominator has no `int` representation anywhere"* — the concrete decidable shadow). Fails closed on an unparseable file.
  - Register **both** via the three-edit lock-step: append to `CHECKS` ([registry.py](apx/checks/registry.py)), add a `_p(...)` row each to `PROPERTY_MANIFEST` ([manifest.py](apx/checks/manifest.py)), add a README table row each between the `<!-- structural-properties:start/end -->` markers. **No count to bump** — the six meta-checks reconcile by function identity; `tests/checks/test_manifest_checks.py` goes red on any drift. Add `tests/checks/test_inventory_record.py` (green-on-tree + fires-on-fixture for each) with a `tests/_fixtures/structural_violations/<name>/` fixture per check.

- [x] **Task 7 — The migration + the API read surface (AC2, AC3).**
  - Migration `0020_inventory_denominator.py` (`down_revision = "0019_failure_register_fields"`): the durable `submitted_pieces` surface (Task 2) and the `NoiseExclusion` table (Task 3), with backfill of `submitted_pieces` for existing matters from the current durable counts (a safe post-hoc freeze: `in_corpus + open_register_entries`), and `excluded_as_noise` starting empty. No cascade FK (AD-7). Reversible downgrade. Add the encrypted columns to `ENCRYPTED_COLUMNS`.
  - Extend `InventoryOut` ([app.py:295-300](apx/api/app.py#L295)) + `_inventory_out` to all six named counts, the `unknown_cardinality_phrase`, and `consistent`. The scoped read endpoint already exists (`read_inventory`, [app.py:1267-1276](apx/api/app.py#L1267)) and `GET /api/matters` carries the record; verify both surface the full record. **DEFERRED to the UX pass** (recorded, not built): the noise-exclusion **list** endpoint's screen and the permanent home-screen **widget** (Story 2.11) — the store read (`noise_exclusions`) and the six-field API record are complete and tested, so AC2/AC3 hold at the contract level.

- [x] **Task 8 — Gate + docs.** Full green: `ruff`, `pytest` (no regressions — mind the `Inventory` field rename touching `test_inventory.py`, `ingest.py`, three `store.py` construction sites, `InventoryOut`/`_inventory_out`, and any test constructing `Inventory(...)`), `apx.checks` (both new checks live, manifest + README in lock-step), `alembic upgrade head` + reversible downgrade, the `ENCRYPTED_COLUMNS` drift-guard green with the new encrypted columns. Update the `inventory.py` module docstring (it currently states the three-term stopgap identity — correct it to AD-38's two-term identity with noise/retired outside), and the README structural-properties + config-keys blocks.

## Dev Notes

### The load-bearing decision: AD-38 governs, and `submitted_pieces` must be independently sourced

Two reconciliations the dev **must** get right — they are exactly the "three legitimate implementations of one number" AD-38 exists to stop a unit deciding unilaterally.

1. **The identity is two-term over known pièces, not the epics' literal three-term sum.** [epics.md §2.7](_bmad-output/planning-artifacts/epics.md) and the corrected [FR-6 (prd.md:345)](_bmad-output/planning-artifacts/prds/prd-apx-mvp-2026-07-20/prd.md#L345) read `submitted = in corpus + open failure register entries + declared exclusions`. **AD-38** ([SPINE L1088-1099](_bmad-output/planning-artifacts/architecture/architecture-apx-mvp-2026-07-21/ARCHITECTURE-SPINE.md#L1088)) and the spine's inventory **state-machine note** ([L1512-1518](_bmad-output/planning-artifacts/architecture/architecture-apx-mvp-2026-07-21/ARCHITECTURE-SPINE.md#L1512)) make it precise and **govern**: *"`submitted_pieces = in_corpus + open_register_entries`, over KNOWN pieces after expansion, exactly, always. `excluded_as_noise` and `retired` sit outside the identity; `unknown_cardinality_entries` is never summed into any total and is rendered in words."* `submitted_pieces` counts **pièces** (post-expansion, noise already removed) — noise was never a pièce, so it is a **separate named line outside** the identity, not a summed term. The "no unnamed remainder / nothing in two or none" guarantee is honoured across the **full accounting** (every enumerated object is a pièce → `submitted_pieces` → `in_corpus` xor `open_register_entries`, **or** `excluded_as_noise`); the SM-3 identity is the two-term core. The stopgap's `submitted == in_corpus + failures + exclusions` is the wrong form — correct it.
2. **`submitted_pieces` is a frozen independent tally, never `in_corpus + open` recomputed.** Today `store.inventory()` returns `Inventory(in_corpus + failures, …)` — `submitted` *is* the RHS, so `is_consistent()` is `x == x`, always true, catches nothing. AD-17 ([SPINE L507](_bmad-output/planning-artifacts/architecture/architecture-apx-mvp-2026-07-21/ARCHITECTURE-SPINE.md#L507)): *"the application-owned ledger is the single authority for every user-visible progress figure."* Source `submitted_pieces` from a durable, frozen-at-expansion, idempotent ledger so a dropped pièce (in **none**) or a double-counted pièce (in **two**) makes the two sides **diverge** and `require_consistent()` **raise**. The AC4 negative test is the acceptance mechanism: it is unwritable against a tautological source, so passing it *proves* the invariant is real.

### Architecture guardrails (binding)

- **AD-38 (the denominator record):** one record, exactly six disjoint fields, all displayed with their own names wherever any is displayed; `unknown_cardinality_entries` never summed, rendered in words; **no `int` representation** of the denominator anywhere — enforced by the two new structural properties. Asserted by test at the design target.
- **AD-17 (the ledger is the only authority):** `submitted_pieces` and every count come from the application-owned durable store, never from Procrastinate's queue table, never recomputed as the thing they check.
- **AD-14 / AD-13 / AD-41 (the scoped read):** the denominator and the noise list read through the one entry point, scope-pre-filtered (`ScopeDenied` fail-closed, existence never disclosed); the noise list is **client data** (its path is privileged) — encrypted at rest, tenant-then-scope guarded, exactly like the register.
- **AD-7 (retired, never deleted):** `retired` is a **named reserved count** (0 now); nothing hard-deletes to shrink a denominator term. No `ON DELETE` on the new FK (RESTRICT).
- **AD-28 (no verbatim fragments):** the noise list stores a filename/path (encrypted) and a matched **pattern** — never a document fragment; nothing content-bearing enters a count or a diagnostic.
- **AD-24/AD-25 (configuration-as-data):** the noise list is a config key resolved in the adapter and passed into pure core (`no_tenant_conditional_in_core`), documented in the README config block (`config_reference_is_complete`), audited on change (`set_config`).
- **AD-33 (a property with no check is not a property):** both new properties name their check, their AD, and the pattern they inspect, and each fails on a real fixture. Registered in lock-step (registry + manifest + README); the meta-checks enforce it.

### Files to touch (and blast radius)

- [apx/core/domain/inventory.py](apx/core/domain/inventory.py) — the six-field record; the corrected two-term identity; docstring fix.
- [apx/core/app/ingest.py](apx/core/app/ingest.py) — noise matcher over the resolved config list (not `NOISE_NAMES`); `IngestionResult.inventory` under the new field names; keep the `require_consistent()` call.
- [apx/adapters/store_postgres/models.py](apx/adapters/store_postgres/models.py) — the durable `submitted_pieces` surface (a `MatterInventory` row or a `matter_scope` column); the new `NoiseExclusion` model.
- [apx/adapters/store_postgres/store.py](apx/adapters/store_postgres/store.py) — `save()` maintains `submitted_pieces` (idempotent) + writes noise rows; `_counts`/`inventory`/`matters` build the full record; `noise_exclusions()` read; the matter/tenant (unscoped) denominator for the assertion.
- [apx/adapters/store_postgres/queue/__init__.py](apx/adapters/store_postgres/queue/__init__.py) — resolve `exclusion_list` (the `expansion_bounds` pattern) and pass it in; `finish_import` asserts the invariant.
- [apx/adapters/store_postgres/backfill.py](apx/adapters/store_postgres/backfill.py) — the new encrypted columns in `ENCRYPTED_COLUMNS`.
- [apx/adapters/store_postgres/migrations/versions/0020_inventory_denominator.py](apx/adapters/store_postgres/migrations/versions/) — new (durable `submitted_pieces` + `NoiseExclusion`, backfill, reversible).
- `apx/checks/inventory_record.py` (new) + [registry.py](apx/checks/registry.py) + [manifest.py](apx/checks/manifest.py) + [README.md](README.md) — the two structural properties (+ the config-key doc row for Task 3).
- [apx/api/app.py](apx/api/app.py) — `InventoryOut`/`_inventory_out` to six fields + phrase + consistent; verify the read endpoints.
- Tests: `tests/domain/test_inventory.py` (rename + negative AC4), `tests/adapters/test_inventory_denominator.py` (durable counts, idempotent `submitted_pieces`, falsifiability, noise persistence + scope), `tests/checks/test_inventory_record.py` (+ two fixtures), `tests/api/test_inventory_api.py` (six-field record + scope 403), plus the queue/ingest tests updated for the field rename and the post-job assertion.

### What NOT to build (scope discipline)

- The permanent home-screen **widget** rendering and the matters-zone layout — Story 2.11. Build the read model + API record; not the visual home.
- The completion-summary **screen** — Story 2.10. Keep the summary **counts** available (newly indexed / already present / excluded as noise / expanded from containers / failures by class already exist in `SaveOutcome` + the audit detail); do not build the screen.
- The **retirement transition** (what moves a pièce to `retired`) — a re-extraction/supersession concern (Epic 4 / Story 2.8 index). Reserve the `retired` count at 0; do not invent a transition.
- A parallel `Denominator` value object — AD-38 mandates **one** record; extend `Inventory`, do not duplicate it.
- Live **push**-invalidation of the scoped figure on a scope change (FR-14) — the per-request recompute already satisfies *"within a bounded interval, not at next login"*; a push/session-invalidation mechanism is out of scope. Note it, don't build it.
- Any change to the frozen chunk payload (AD-40) — untouched.

### Project Structure Notes

Hexagonal boundaries hold: the `Inventory` record + its invariant are **Domain** (pure, stdlib-only, `require_consistent()` raising); the durable counts, the `submitted_pieces` ledger, and the noise persistence are **store adapter** (inherently the ledger's authority, AD-17); the config value is resolved in the adapter and handed to pure core as a value (never core→store). The two structural properties live with the other build-time checks. The API is a thin scoped pass-through cloning `read_inventory`.

### References

- [epics.md §Story 2.7](_bmad-output/planning-artifacts/epics.md) (the four ACs verbatim); FR-6 corrected ([prd.md:340-352](_bmad-output/planning-artifacts/prds/prd-apx-mvp-2026-07-20/prd.md#L340)), FR-57 ([prd.md:1059-1065](_bmad-output/planning-artifacts/prds/prd-apx-mvp-2026-07-20/prd.md#L1059)), FR-28 ([prd.md:663-671](_bmad-output/planning-artifacts/prds/prd-apx-mvp-2026-07-20/prd.md#L663)), SM-3 ([prd.md:1232](_bmad-output/planning-artifacts/prds/prd-apx-mvp-2026-07-20/prd.md#L1232)); the *Denominator*/*Failure register* glossary ([prd.md:230-231](_bmad-output/planning-artifacts/prds/prd-apx-mvp-2026-07-20/prd.md#L230)).
- `ARCHITECTURE-SPINE.md`: **AD-38** (L1076-1099, the record + the no-`int` type — the load-bearing read), the inventory **state-machine note** (L1499-1520, the governing two-term identity), **AD-17** (L501-520, the ledger authority), AD-14/AD-13/AD-41 (the scoped read; the register/noise as client data), AD-7 (retired), AD-28 (no fragments), AD-33 (structural properties), AD-42 (the exhaustive set carries the scoped denominator — the downstream consumer, Epic 3).
- Existing seams: the stopgap `Inventory` + `test_inventory.py`; `store._counts`/`inventory`/`matters` (the tautology to fix); the orphaned `exclusion_list` key ([config.py:159](apx/core/domain/config.py#L159)) + the `expansion_bounds` adapter→core pattern; `_failure_id` (the idempotent PK idiom for `NoiseExclusion`); `EncryptedText` + the 2.5 `ENCRYPTED_COLUMNS` drift-guard; the 3-edit check lock-step (`register_ownership.py` as the module template); `read_inventory` (the API clone target).

## Senior Developer Review (AI)

**Reviewed:** 2026-07-29 · **Outcome:** Approved after fixes · **Method:** three parallel adversarial reviewers (distinct lenses — invariant honesty; durability & security; structural checks & blast radius), each execution-verified (mutate → run the specific test → confirm catch → revert; working tree left byte-identical). All action items below are resolved and re-gated (**ruff clean · 663 passed / 9 skipped · 47 structural checks**).

### Action items — all resolved

- [x] **[HIGH · cross-confirmed by two reviewers] A retry that resolves a failure to a content-DUPLICATE broke SM-3.** `_reconcile_retry` resolves when any same-matter pièce is recovered, and `_insert_piece_if_absent` dedups; when the recovered pièce was already in the corpus, `in_corpus` stayed flat while `open` dropped, so the monotonic `max` watermark exceeded the live sum → `retry_failure` raised + rolled back (entry stuck open forever), `bulk_retry` committed a **wedged, permanently-inconsistent matter** (every later `finish_import` then raised). *Fixed:* the retry paths now **settle** `submitted_pieces` to the reconciled population (`_settle_submitted_after_retry` — a dup-collapse legitimately decrements) instead of `max`; submission paths keep the monotonic `max`. Falsifiability preserved (a raw deletion runs no retry). Regression tests added for `retry_failure` **and** `bulk_retry`.
- [x] **[HIGH] The new `noise_exclusion` ledger was not backed up.** It was absent from `_BACKUP_TABLES`, so a tenant restore silently dropped the encrypted noise list + reset `excluded_as_noise` to 0 (a disaster-recovery / AD-41 client-data loss; the invariant stayed True because noise is outside it, so it was *silent*). *Fixed:* added to `_BACKUP_TABLES`; `test_backup_restore` now asserts the count **and** the decrypted list survive.
- [x] **[MED] `bulk_retry` omitted the `require_consistent()` tripwire** Task 5 mandates. *Fixed:* added per-entry after the settle (parity with `retry_failure`).
- [x] **[MED · cross-confirmed] The `unknown_cardinality_never_summed` check missed `sum(...)`.** `sum([inv.in_corpus, inv.unknown_cardinality_entries])` — the canonical total idiom AD-38 forbids — shipped green. *Fixed:* the check now flags `sum(...)`/`math.fsum(...)` over a literal iterable; a dedicated fixture + test added.
- [x] **[MED] The `InventoryOut` rename broke the existing SPA** (`api.ts` type + `App.tsx` rendered `inventory.failures` → "undefined à revoir"). *Fixed:* frontend source updated to the AD-38 names (`tsc --noEmit` clean). `apx/web/dist` is gitignored and rebuilt from source at deploy (`vite build`), so no stale bundle ships.
- [x] **[LOW] The sum-check would false-positive on a bare `retired` local** (a common word). *Fixed:* `retired` is now matched only as an attribute (`inv.retired`); the two distinctive names still match as bare names. Test added.
- [x] **[LOW] The `ingest` audit detail carried stale labels** (`submitted=`/`failures=`/`exclusions=`) over new values. *Fixed:* relabelled to `submitted_pieces=`/`open_register=`/`noise=` (AD-38); the asserting test updated.
- [x] **[LOW] `exclusion_list` replace-not-merge semantics** were only in a code comment → surfaced in the README config table. **[LOW] `matter_scope.submitted_pieces`** given a `server_default="0"` (model + migration) so a raw INSERT can never violate NOT NULL.
- Accepted (not fixed): the field-shape check misses a 7th field added via an inherited base dataclass (contrived — the record has no base), and the sum-check misses aliasing / `reduce` / `fsum(var)` (inherent AST limits; `sum()` was the realistic idiom and is now closed).

### Confirmed sound (execution-verified by the reviewers)

The core mechanism is honest: `submitted_pieces` is a genuinely independent, frozen watermark (no read-path recomputes it as the sum), maintained on every population-changing write, with no false-trip on restore / `finish_import` / undetermined-matter paths. Security & durability are clean — `_noise_id` is tenant+matter-qualified (no Story-2.6-style cross-tenant collision), both noise columns are encrypted and covered by the drift-guard (verified red-on-removal), config-as-data layering holds (core never reads the store), the noise read is scope-pre-filtered fail-closed, and migration 0020 is reversible with a single linear head. The field rename left no stale `Inventory` reference; the two structural checks fire on their fixtures and the 3-edit lock-step is real (verified by deleting a README row → red).

## Dev Agent Record

### Agent Model Used

claude-opus-4-8 (1M context) — BMAD dev-story.

### Debug Log References

Gate after each task: `ruff check .`, `pytest` (no `DATABASE_URL` override), `python -m apx.checks`. Final: **ruff clean · 659 passed / 9 skipped · 47 structural checks · alembic single head 0020** (linear chain, no branch). The `Inventory` field rename touched ~15 files (three `store.py` construction/audit sites + ~12 test files); each caught by the suite and fixed to the AD-38 names. The alembic chain runs Postgres-only; the 0020 backfill is tested on SQLite via the extracted `backfill_submitted_pieces` helper (the 2.6 pattern).

### Completion Notes List

- **The load-bearing correction (AC1):** replaced the 2.4/2.6 stopgap `Inventory` — whose `submitted` was *defined as* `in_corpus + failures` (a tautology that can never fail SM-3) — with AD-38's six-field record and the governing two-term identity `submitted_pieces == in_corpus + open_register_entries` over known pièces; `excluded_as_noise`/`retired` are their own named lines OUTSIDE the identity; `unknown_cardinality_entries` is a subset of `open_register_entries`, never summed, rendered in words. The epics' loose three-term phrasing is reconciled to AD-38 + the spine's state-machine note, which govern.
- **submitted_pieces made independent (AC1/AC4):** a durable, monotonic high-water mark on `matter_scope.submitted_pieces` (AD-17 ledger), raised to `max(stored, in_corpus + open)` on every population-changing write (`save`, `quarantine_unit`, `retry_failure`, `bulk_retry`) and READ frozen (never recomputed as the sum). This is what makes the invariant falsifiable: a corpus pièce lost after being counted makes the watermark exceed the live sum → `require_consistent()` raises. Idempotent under re-import; invariant under retry resolution (in_corpus +1 / open −1).
- **Filesystem noise as config-as-data (AC2):** wired the previously-orphaned `exclusion_list` config key (default now the OS/editor-detritus set incl. lock files / `__MACOSX` / AppleDouble `._*`), resolved in the adapter and passed into pure core as `noise_patterns` (matched by `fnmatchcase`); persisted each excluded file to a new durable, idempotent, encrypted `NoiseExclusion` ledger (count + one-click list backend), separate from the failure register and outside the identity.
- **The runtime tripwire + the release-blocker tests (AC1/AC4):** `finish_import` and `retry_failure` call `require_consistent()` (fail loud, roll back); a deliberately-induced miscount fails it at the domain level (in-two-terms / in-none), the store level (delete a Piece), and the import-job level (inflated watermark → `finish_import` raises).
- **Two structural properties (AC4, AD-33):** `inventory_record_fields_enumerated` (the record declares exactly AD-38's six fields) and `unknown_cardinality_never_summed` (`unknown_cardinality_entries`/`excluded_as_noise`/`retired` never an operand of `+` across `apx/**` — the decidable no-`int`-collapse shadow), each with a firing fixture; registered via the 3-edit lock-step (registry + manifest + README), 45 → 47 checks.
- **Deferred, faithfully:** the permanent home-screen *widget* (Story 2.11) and the completion-summary *screen* (Story 2.10) — the six-field API record + the noise-list read (`noise_exclusions`) are complete and tested, so AC2/AC3 hold at the contract level. `retired` is a reserved named count (0 today — no retirement transition exists yet). FR-14 live push-invalidation is out of scope (the per-request recompute already satisfies "within a bounded interval").

### File List

**New**
- `apx/checks/inventory_record.py` — the two AD-38 structural properties.
- `apx/adapters/store_postgres/migrations/versions/0020_inventory_denominator.py` — submitted_pieces + noise_exclusion.
- `tests/adapters/test_inventory_denominator.py` — the durable denominator, falsifiability, noise persistence/scope.
- `tests/adapters/test_inventory_migration.py` — the 0020 backfill (SQLite).
- `tests/checks/test_inventory_record.py` — the two checks (green + fires + fail-closed).
- `tests/_fixtures/structural_violations/inventory_record_fields/wrong_inventory.py`, `tests/_fixtures/structural_violations/unknown_summed/sums_unknown.py` — the firing fixtures.

**Modified (source)**
- `apx/core/domain/inventory.py` — the six-field record + the corrected invariant + docstring.
- `apx/core/domain/config.py` — `DEFAULT_EXCLUSION_LIST`; `exclusion_list` default.
- `apx/core/app/ingest.py` — `noise_patterns` (config-as-data) threaded; field rename; docstring.
- `apx/adapters/store_postgres/models.py` — `MatterScope.submitted_pieces`; `NoiseExclusion`.
- `apx/adapters/store_postgres/store.py` — watermark helper + maintenance; noise persistence; `_durable_inventory`; `noise_exclusions`; `_noise_id`; `finish_import`/`retry_failure` invariant assertions; `NoiseExclusionEntry`; import.
- `apx/adapters/store_postgres/queue/__init__.py` — resolve + pass `exclusion_list`.
- `apx/adapters/store_postgres/backfill.py` — `noise_exclusion` encrypted columns; `backfill_submitted_pieces`.
- `apx/api/app.py` — six-field `InventoryOut` + `_inventory_out`; `noise_patterns`; import.
- `apx/checks/registry.py`, `apx/checks/manifest.py`, `README.md` — the two new properties (lock-step) + the `exclusion_list` config-doc row.

**Modified (tests — `Inventory` field rename + new assertions)**
- `tests/domain/test_inventory.py` (rewrite), `tests/domain/test_domain.py`, `tests/adapters/{test_store,test_multiformat_ingest,test_failure_register,test_encryption_at_rest,test_backup_restore,test_msg_extraction,test_container_expansion}.py`, `tests/app/{test_ingest,test_ingest_expansion}.py`, `tests/worker/test_import_job.py` (+ the import-job release-blocker test), `tests/api/test_ingest_api.py`.
