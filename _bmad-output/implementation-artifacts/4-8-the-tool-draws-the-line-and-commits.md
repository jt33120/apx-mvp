---
baseline_commit: 8456a02
---

# Story 4.8: The tool draws the line and commits

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a lawyer who is paying not to make the judgement herself,
I want the tool to commit to a recommended cut with a stated basis, not hand me an undifferentiated
ranking,
so that a ranked list that refuses to decide does not push the work back onto me.

## Scope note — 4.8 OWNS the line's placement + storage; the derivation substrate is already built

Story 4.7 (committed `8456a02`) already delivered the pure derivation
`views = derive_triage_sets(order, line, pins)` and the typed **`Line(last_retained_piece_id)`** value
object (the line modelled by the identity of the last retained *pièce*, **not** a bare integer —
FR-17-ready), taking the line **as an input**. Story 4.3 already persists **one ranked order per
*matter* per *ranking version*** (append-only) with each row's `rank`, `band`, `outcome`, `score`,
`confidence`. Story 4.8 now delivers the line's **owning use case** (AD-37): the system **chooses** where
the line falls, **states its basis**, **stores** it as an ordinal cut over a named *ranking version*
carrying the **identity of the last retained *pièce*** with author + timestamp, and guarantees the two
load-bearing invariants — an import that adds *pièces* never silently moves what the line designates,
and placing the line never reorders the underlying ranked order.

**IN scope:**
1. A pure Domain `apx/core/domain/line.py` — `recommend_line(order, retain_bands) -> Line | None`: the
   **recall-first** placement policy. Walk the ranked order (rank 1..N); the line is placed after the
   **deepest-ranked *pièce* whose band is a configured retain-band** (default: `confident-relevant` ∪
   `uncertain` — recall over precision, keep the uncertain). The last retained *pièce* is that pièce;
   returns `Line(last_retained_piece_id)`. Returns **None** — an honest non-commitment — when no *pièce*
   qualifies (every scored *pièce* is confidently discardable, or there is no ranked *pièce*): the tool
   does **not fabricate** a retained set (AD-19 — nothing imputed).
2. The **stated basis**, inherited from the *ranking version* the line cuts (never invented): the store
   derives it from `ranking_version.basis` + `case_theory_version_id` (the case-theory path) or the
   named `IntrinsicSignal`s (the intrinsic path) — exactly "the case theory where one exists, or the
   named intrinsic signals" (FR-17).
3. A new **append-only, version-bound** model `LinePlacement` (table `line_placement`) + Alembic
   migration `0027` — storing the cut as `(ranking_version_id, seq, last_retained_piece_id, basis,
   placed_by, at)`, with **no bare-integer ordinal column** (the FR-17 "never a bare integer" made
   structural). The **current line = the max-`seq` row** for the version (a ledger, so 4.9's priced move
   and reversal append, never overwrite — AD-7).
4. The store's **owning use case** `place_line(...)` (AD-37): reads the version + its ranked bands,
   calls `recommend_line`, and when a cut exists appends one `LinePlacement` row (server monotonic `seq`,
   AD-49) **atomic** with one `line_placed` audit entry (AD-22), a **conditional commit** on `seq`
   (AD-37). Touches **only** `line_placement` — never `ranked_entry` — so placing the line cannot
   reorder the order. Plus the read view `read_current_line(...)`, scope pre-filtered (AD-13,
   non-disclosing), naming its `version_id` (AD-23).
5. A **core port + use-case seam** (AD-4) — `core/ports/line.py` (`LinePlacementRecorder` Protocol) and
   `core/app/line.py` (thin forwarders) — mirroring 4.5's `taxonomy_label` port + `label` app.
6. Two **structural checks** (harness lockstep — registry + manifest + README): `line_stored_by_piece_
   identity` (FR-17 — the `LinePlacement` model has `last_retained_piece_id` and **no** bare-integer
   ordinal column; mirrors `no_retained_or_discarded_set_column`) and `line_placement_is_append_only`
   (AD-7 — `LinePlacement` constructed only in the store, no UPDATE/DELETE; mirrors
   `taxonomy_label_ownership`).
7. The **encrypted-column rekey registration** for `line_placement.placed_by` (the 4.5 regression: an
   `EncryptedText` column MUST be listed in `backfill.py::ENCRYPTED_COLUMNS`, else
   `test_rekey_covers_every_encrypted_column` fails) + the encryption-check plaintext allowlist for
   `LinePlacement`'s categorical/identity columns.

**OUT of scope (do NOT build):**
- The **priced human move** of the line — moving the line and showing Δ pièces-to-read + Δ estimated
  prevalence before committing (Story 4.9 / FR-19). 4.8 builds the append-only placement path the priced
  move will *reuse*; 4.8 itself writes only the **system-recommended** placement. Do not build the
  pricing projection.
- The **pin** (Story 4.11 / FR-43) — 4.8 takes no pin action; `read_triage_sets` already accepts pins as
  an input.
- The **editable table / change-log UI** and any **audit-drawer surface** (needs the just-finalised UX
  contract; those are Stories 4.10/4.6). 4.8 is backend + structural.
- Any **retirement** of versions or the referenced-by exemption (AD-7 — deferred, per 4.7).
- **Confidence bounds / sampling** (Epic 5). The line's basis is a **projection register**, never a
  sampling bound — but 4.8 stores no projection; that is 4.9.

## Acceptance Criteria

**AC-1** — **Given** a completed ranking, **When** the line is placed, **Then** it has a position
**chosen by the system** with a **stated basis** — the *case theory* where one exists, or the named
intrinsic signals — and the placement records the commitment (the "in my view, everything above this"
statement is the UI's rendering of the stored `last_retained_piece_id` + `basis`; the store persists the
structured basis, not a bare divider) (FR-17).
- *Testable:* `place_line` on a ranking whose version `basis == "case-theory"` stores
  `basis == "case-theory:<case_theory_version_id>"`; on an `intrinsic` version it stores
  `basis == "intrinsic:<named IntrinsicSignals>"`. The stored basis is never empty.

**AC-2** — **Given** a placed line, **Then** its position is stored as an **ordinal cut over a named
*ranking version*** together with the **identity of the last retained *pièce***, with **author and
timestamp** — **never a bare score, never a bare integer** (FR-17).
- *Testable:* the `line_placement` row carries `ranking_version_id`, `last_retained_piece_id`,
  `placed_by` (encrypted), `at`; there is **no** integer position/cut-index/ordinal column on the model
  (asserted structurally by `line_stored_by_piece_identity`). The current line is the max-`seq` row.

**AC-3 (failure path)** — **Given** a placed line, **When** an import adds *pièces*, **Then** it does
**not silently move what the line designates**, because the line is stored against the **last retained
*pièce***, not a bare position 180 that becomes position 180 of a larger set (FR-17).
- *Testable:* place the line on version *v* (last retained = *piece_X*). Add more *pièces* (a re-rank ⇒
  a **new** version *v+1*, per AD-23). The stored line on *v* is **unchanged** and still names *piece_X*;
  `read_current_line(version_no=v)` still resolves *piece_X*; `read_triage_sets(line=that line,
  version_no=v)` yields the same retained/discarded split it did before. (The order within a version is
  immutable — 4.3 append-only — so "adding pièces" is always a new version; the line stays bound to the
  version it was placed against, AD-23.)

**AC-4 (invariant)** — **Given** a placed line, **When** the line changes, **Then** it **never reorders
the underlying ranked order** (FR-17).
- *Testable:* snapshot `read_ranked_order(version)` before `place_line`; assert byte-identical after.
  Structurally: `place_line` writes only `line_placement` and never `INSERT/UPDATE/DELETE` on
  `ranked_entry` (the model touched is a different table; `recommend_line` is a pure read-only function
  over the order).

**AC-5 (honest non-commitment)** — **Given** a ranking whose scored *pièces* are all confidently
discardable (no *pièce* in a retain-band), **When** placement runs, **Then** the tool commits to **no
line** rather than fabricating a retained set (`recommend_line -> None`, nothing stored), and
`read_current_line` returns None; the tool never invents a cut (AD-19).

## Tasks / Subtasks

- [x] **Task 1 — Domain: the recall-first placement policy** (AC: 1, 5)
  - [x] Create `apx/core/domain/line.py`. Import `Line` from `apx.core.domain.triage_sets` (do NOT
        redefine it). Add a small frozen input carrier `RankedBand(piece_id: str, band: str | None)` (a
        pièce's rank-ordered band; `None` for a REJECTED/UNSCORED pièce with no stage-2 band).
  - [x] `recommend_line(order: Sequence[RankedBand], *, retain_bands: frozenset[str]) -> Line | None`:
        the `order` is in rank order (rank 1..N, ranked pièces only — the unscored tail is excluded by
        the caller). Find the **deepest** (last, highest-rank) pièce whose `band in retain_bands`; return
        `Line(last_retained_piece_id=that.piece_id)`. If none qualifies, or `order` is empty, return
        `None` (honest non-commitment — never fabricate; AD-19).
  - [x] Module docstring: recall-first (retain-bands default = confident-relevant ∪ uncertain), the cut
        is ordinal (a position between two rows), the line's identity is the last-retained *pièce* (never
        a bare integer). Note that the *basis* is inherited from the ranking version (the store composes
        it), not invented here.
  - [x] Tests `tests/domain/test_line.py`: recall-first cut (uncertain retained), all-retain (last
        retained = last ranked), no-qualifying → None, empty order → None, retain-band set honoured.

- [x] **Task 2 — Config: the retain-band policy as config-as-data** (AC: 1, 5) — AD-24/AD-25
  - [x] Add `ConfigKey("line_retain_bands", "list", ["confident-relevant", "uncertain"], governs=...,
        valid=lambda v: bool(v) and all(isinstance(x, str) and x in _BAND_VALUES for x in v))` to
        `apx/core/domain/config.py`, where `_BAND_VALUES = {b.value for b in Band}` (import `Band` from
        `apx.core.domain.cascade`). Recall-first default; validates each entry is a real `Band` value
        (an unknown band can never leak into the cut).
  - [x] README `<!-- config-keys -->` block: add the `line_retain_bands` row (the 4th lockstep site,
        guarded by `apx/checks/configuration.py` — match the first-column key name exactly).
  - [x] Tests `tests/domain/test_config_line.py`: default value, rejects an unknown band, rejects empty.

- [x] **Task 3 — Model + migration: the append-only, version-bound line ledger** (AC: 2, 3) — AD-7/AD-49
  - [x] Add `LinePlacement` to `apx/adapters/store_postgres/models.py` (table `line_placement`):
        `id` = `sha256(ranking_version_id \x00 seq)`; `tenant`, `matter`; `ranking_version_id`
        (`ForeignKey("ranking_version.id")`, **no ondelete** AD-7); `seq` (per-version monotonic, AD-49);
        `last_retained_piece_id` (`String(64)`, **NOT NULL** — the line's identity, FR-17);
        `basis` (`String`, plaintext — inherited version identity, no PII/content); `placed_by`
        (`EncryptedText` — actor PII, AD-31); `at` (`DateTime(timezone=True)`).
        `UniqueConstraint("ranking_version_id", "seq")`; `Index("ix_line_placement_version", "tenant",
        "matter", "ranking_version_id")`; `ForeignKeyConstraint((tenant,matter) → matter_scope)` no
        ondelete. **Docstring must state: NO bare-integer ordinal column — the line is stored by pièce
        identity (FR-17), asserted by `line_stored_by_piece_identity`; APPEND-ONLY (AD-7), asserted by
        `line_placement_is_append_only`.**
  - [x] Migration `apx/adapters/store_postgres/migrations/versions/0027_line_placement.py`
        (`down_revision = "0026_taxonomy_label_entry"`, no backfill). `upgrade` creates the table +
        constraints + index; `downgrade` drops it. (Mirror `0026`.)
  - [x] Add `"line_placement"` to `_BACKUP_TABLES` in `store.py`.
  - [x] Tests `tests/adapters/test_line_placement_migration.py`: upgrade creates the table with the
        columns + unique constraint; downgrade drops it (mirror the 0026 migration test).

- [x] **Task 4 — Encrypted-column rekey + encryption allowlist** (AC: 2) — the 4.5 regression guard
  - [x] Add `("line_placement", "id", "placed_by", "line_placement.placed_by")` to
        `apx/adapters/store_postgres/backfill.py::ENCRYPTED_COLUMNS` (single-PK `id`, so rotation
        addresses it directly). **Without this, `test_rekey_covers_every_encrypted_column` fails.**
  - [x] If `apx/checks/encryption.py` enumerates plaintext columns per model, add the `LinePlacement`
        plaintext columns (e.g. `("LinePlacement", "basis")`, `("LinePlacement", "last_retained_piece_
        id")`) to its qualified allowlist — mirror the `("TaxonomyLabelEntry", "source")` entry. Run the
        encryption check to confirm no plaintext-PII violation.

- [x] **Task 5 — Store: the owning use case + the read view** (AC: 1, 2, 3, 4, 5) — AD-22/AD-37/AD-13
  - [x] `place_line(*, tenant, matter, actor, scopes, version_no=None) -> LinePlacementView | None`
        inside an `_audited_tx`: scope-check (`ScopeDenied`, non-disclosing); resolve the target version
        (latest when `version_no` None); read its ranked rows `(piece_id, rank, band)` in rank order
        (ranked only, rank not NULL); build `[RankedBand(pid, band) ...]`; `recommend_line(...,
        retain_bands=<config, read in-tx like `_current_taxonomy`>)`. If `None` → **write nothing**,
        return None (AC-5). Else compose `basis` from the version (`_line_basis(session, version_row)` —
        `case-theory:<ctv_id>` when `version.basis == "case-theory"`, else `intrinsic:<INTRINSIC_SIGNALS
        joined>`), mint monotonic `seq` (conditional commit on the observed max, AD-37), append the
        `LinePlacement` row **atomic** with one `line_placed` audit entry (AD-22) via `_append_audit`.
        Return the `LinePlacementView`.
  - [x] `read_current_line(*, tenant, matter, scopes, version_no=None) -> LinePlacementView | None`: the
        VIEW — scope pre-filter; resolve the version; the max-`seq` `line_placement` row for it; return
        the view naming `version_id`/`version_no` + `last_retained_piece_id` + `basis` + `seq` + `at`.
        None when out of scope / absent / no version / no line placed yet (non-disclosing). Not audited.
  - [x] Add DTO `LinePlacementView(version_id, version_no, last_retained_piece_id, basis, seq, at)` (no
        `placed_by` in the read view unless a caller needs it; keep PII out of the default read).
  - [x] Tests `tests/adapters/test_line_placement_store.py`: (a) place on a case-theory version → basis
        `case-theory:<id>`, current line names the deepest retain-band pièce; (b) place on an intrinsic
        version → basis `intrinsic:...`; (c) **AC-4 invariant** — `read_ranked_order` byte-identical
        before/after `place_line`; (d) **AC-3 failure path** — after a re-rank adds pièces at v+1, the v
        line is unchanged and still names the same pièce, and `read_triage_sets(line, version_no=v)` is
        unchanged; (e) append-only — a second `place_line` (or a later move) is a new `seq`, the prior
        row still present; (f) AC-5 — an all-confident-discard version → `place_line` returns None,
        nothing written; (g) scope denial is non-disclosing (out-of-scope matter → None).

- [x] **Task 6 — Core port + use-case seam** (AC: 1, 2) — AD-4
  - [x] `apx/core/ports/line.py`: `LinePlacementRecorder` Protocol — `place_line(*, tenant, matter,
        actor, scopes, version_no=None) -> LinePlacementView | None` and `read_current_line(...) ->
        LinePlacementView | None`. (Mirror `core/ports/taxonomy_label.py`.) Keep the `LinePlacementView`
        type where the port can name it without importing the adapter (a core DTO or a `Protocol`-level
        structural type — mirror how `taxonomy_label`/`ranking` ports name their return DTOs).
  - [x] `apx/core/app/line.py`: thin seams `place_line(recorder, ...)` / `read_current_line(recorder,
        ...)` forwarding to the port (AD-4 — core imports no adapter). Mirror `core/app/label.py`.
  - [x] Tests `tests/app/test_line_use_case.py`: the app seam forwards to a fake recorder (like
        `test_label_use_case.py`).

- [x] **Task 7 — Structural checks (lockstep) + README** (AC: 2, 4) — AD-33
  - [x] `apx/checks/line_stored_by_piece_identity.py` (NEW): `line_is_stored_by_piece_identity` (FR-17) —
        AST-inspect the `LinePlacement` model class: it MUST declare a `last_retained_piece_id` column
        and MUST NOT declare any bare-integer ordinal column (name matching `position|cut|ordinal|
        index|rank_cut` with an `Integer` type). Mirror `checks/ranking_sets_are_views.py` /
        `no_retained_or_discarded_set_column`'s column-inspection approach. Fails closed on unparseable.
  - [x] `apx/checks/line_placement_ownership.py` (NEW): `line_placement_is_append_only` (AD-7) —
        `LinePlacement` constructed only in the store adapter (the place-line path); no `UPDATE`/`DELETE`
        of `line_placement`; no in-place mutation of a loaded instance. Mirror
        `checks/taxonomy_label_ownership.py`.
  - [x] Register BOTH in the three lockstep sites: `apx/checks/registry.py` (import + `CHECKS`),
        `apx/checks/manifest.py` (`PROPERTY_MANIFEST` — `_p(key, fr, ad, name, check_callable,
        inspects)`), and the README `<!-- structural-properties -->` block. Keys: `line-stored-by-piece-
        identity` (FR-17) and `line-placement-append-only` (AD-7). **Verify the meta-checks pass** (they
        match by key/FR/AD/verb/check-`__name__`).
  - [x] Each new check gets a failure-path fixture test (`tests/checks/test_line_stored_by_piece_
        identity.py`, `tests/checks/test_line_placement_ownership.py`) that actually FIRES on a
        synthetic offender (a model with an integer `position` column; a stray `LinePlacement(...)`
        construction / an UPDATE) — not just the green path.

- [x] **Task 8 — Full gate + reconcile** (all ACs)
  - [x] `cd apx-mvp && export PATH="$PWD/.venv/bin:$PATH"` then: `ruff check .` (line-length 100; reflow
        accented lines BY HAND), `python -m apx.checks.run` (or the harness entrypoint — the new checks
        live and green; the AD-39 `no_retained_or_discarded_set_column` stays green), `lint-imports`
        (import-linter 3/0 — core imports no adapter), `pytest` (all pass, no `apx-platform/` collection).
  - [x] Update the structural-check count wherever asserted (a meta-test may assert the total).

## Dev Notes

### The substrate 4.8 consumes (do NOT re-implement)

- **`apx/core/domain/triage_sets.py`** (Story 4.7) — `Line(last_retained_piece_id: str)` (import it;
  never redefine), `Pin`, `PinSide`, `TriageSets`, `derive_triage_sets(*, ranked, unscored, line, pins,
  version_id)`. The retained/discarded sets are VIEWS; `TriageSets` is constructed ONLY there
  (`triage_sets_have_one_derivation`) — 4.8 must not construct it. [Source:
  apx/core/domain/triage_sets.py]
- **`apx/adapters/store_postgres/store.py::read_triage_sets(..., line=None, pins=(), version_no=None)`**
  already takes the line as an input and derives the sets. 4.8 adds `place_line` + `read_current_line`;
  it does not change `read_triage_sets`. [Source: store.py:3165]
- **`RankingVersion`** (`ranking_version`) carries `basis` (`"case-theory"|"intrinsic"`),
  `case_theory_version_id` (NULL on the intrinsic path), `version_no` (per-matter monotonic), `id` (=
  version_id). Append-only (AD-23/AD-37). The line INHERITS this basis. [Source: models.py:560]
- **`RankedEntry`** (`ranked_entry`) carries `rank` (1-based; **NULL = unscored**, AD-19), `band`
  (`Band` value or NULL), `outcome`, `score`, `confidence`. Ordered by `rank` with the unscored tail by
  `piece_id`. **No retained/discarded column** (AD-39). 4.8 reads it read-only; it must never write it.
  [Source: models.py:602, store.py::read_ranked_order:2953]
- **`Band`** (`apx/core/domain/cascade.py`): `confident-relevant`, `uncertain`, `confident-discard`.
  **`IntrinsicSignal`**: document-type, participant-roles, date-distribution, duplication, obvious-noise
  (+ `INTRINSIC_SIGNALS` tuple). [Source: cascade.py:32,56]

### The write pattern to mirror exactly (Story 4.5's label ledger)

`place_line` mirrors `assign_label` + `_append_label_entry` [Source: store.py:2998-3048]:
- run inside `self._audited_tx(_work)` [Source: store.py:2568];
- scope-check with `self._matter_held(session, tenant, matter, scopes)` → `raise ScopeDenied(matter)`
  (non-disclosing);
- read config **in-tx** like `_current_taxonomy` [Source: store.py:2991] so the retain-band policy is the
  one current at write time (AD-24/25): `require_key("line_retain_bands")` + `TenantSetting` /
  `loads_value` fallback to `spec.default`;
- mint the monotonic `seq` = `max(existing seq for this version) + 1`; **conditional commit** — a
  concurrent double-write collides on `UniqueConstraint(ranking_version_id, seq)` and fails loudly
  (AD-37), never a silent overwrite;
- `id = sha256(f"{ranking_version_id}\x00{seq}".encode()).hexdigest()`;
- `session.add(LinePlacement(... placed_by=actor ...))` then `self._append_audit(session, tenant, matter,
  actor, "line_placed", f"version={version_no} last_retained={piece_id[:12]} basis={basis} seq={seq}",
  now)` — the row + audit are one atomic tx (AD-22).

### Encrypted-column rekey — the 4.5 regression (do NOT skip)

`line_placement.placed_by` is `EncryptedText`. It MUST be added to `backfill.py::ENCRYPTED_COLUMNS`
(`("line_placement", "id", "placed_by", "line_placement.placed_by")`), or
`test_rekey_covers_every_encrypted_column` fails — a real key-rotation durability bug. [Source:
backfill.py:30-58, and the Story 4.5 review finding.]

### Structural check patterns

- `line_stored_by_piece_identity` mirrors `checks/ranking_sets_are_views.py`
  (`no_retained_or_discarded_set_column`) — AST-inspect the model's `mapped_column` declarations.
- `line_placement_is_append_only` mirrors `checks/taxonomy_label_ownership.py` — construction confined to
  the store adapter, no UPDATE/DELETE, no in-place mutation. [Source: apx/checks/taxonomy_label_
  ownership.py, apx/checks/triage_sets_one_derivation.py for the `_is_call_to`/`_iter_py`/`_parse`
  helpers from `payload_schema`.]
- The lockstep is 3 sites (registry + manifest + README structural-properties) for a check; config keys
  add a 4th (README config-keys). Meta-checks match by key/FR/AD/verb/check-`__name__`, NOT the
  `inspects` prose.

### Testing standards

- uv-managed: `.venv/bin/ruff`, `.venv/bin/python`, `.venv/bin/pytest`. **Always `cd apx-mvp` first**
  and `export PATH="$PWD/.venv/bin:$PATH"` in the SAME Bash call (shell state does not persist between
  calls). **Never `export DATABASE_URL`.** ruff line-length 100 — accented chars (*pièce*, é, →, ∪) push
  lines over; reflow BY HAND (auto-reflow corrupts trailing-comment lines).
- Store tests use the existing Postgres test fixtures (see `test_taxonomy_label_store.py` /
  `test_triage_sets_store.py` for the `_seed_piece` / ranking-version seeding helpers). The AC-3 failure
  path and AC-4 invariant are the two must-have proofs.

### Project Structure Notes

- New files: `apx/core/domain/line.py`, `apx/core/ports/line.py`, `apx/core/app/line.py`,
  `apx/adapters/store_postgres/migrations/versions/0027_line_placement.py`,
  `apx/checks/line_stored_by_piece_identity.py`, `apx/checks/line_placement_ownership.py`, and their
  tests.
- Updated files: `apx/core/domain/config.py` (+ `line_retain_bands`), `apx/adapters/store_postgres/
  models.py` (+ `LinePlacement`), `apx/adapters/store_postgres/store.py` (+ `place_line`,
  `read_current_line`, `LinePlacementView`, `_line_basis`, `_BACKUP_TABLES`),
  `apx/adapters/store_postgres/backfill.py` (+ ENCRYPTED_COLUMNS row), `apx/checks/encryption.py`
  (+ allowlist), `apx/checks/registry.py`, `apx/checks/manifest.py`, `README.md` (config-keys +
  structural-properties).
- Naming: follow the module's existing idiom (snake_case; frozen dataclasses; StrEnum for closed
  vocabularies). Do NOT add a `retained`/`discarded`/`position` column anywhere.

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story-4.8] — the four ACs + the two "UX pass
  required" notes (now satisfied by the UX contract below).
- [Source: _bmad-output/planning-artifacts/prds/prd-apx-mvp-2026-07-20/prd.md] — FR-17 (the line).
- [Source: _bmad-output/planning-artifacts/ux-designs/ux-apx-mvp-2026-07-27/EXPERIENCE-EPIC4.md#The-line]
  — the behavioural contract: the line speaks its commitment, is named by the last retained pièce, the
  failure-path banner, the invariant; a11y (the line is a keyboard-operable separator).
- [Source: .../DESIGN.md] — `{components.the-line}` (the visual spec: a cut between two rows, gold
  hairline, kept/discard tier, basis eyebrow, last-retained-pièce chip). [Source: .../mockups/epic-4-
  triage-table.html] — screen 1.
- [Source: architecture ARCHITECTURE-SPINE.md] — AD-4, AD-7, AD-13, AD-19, AD-22, AD-23, AD-24/25, AD-37,
  AD-39, AD-49.
- Sibling patterns: Story 4.7 (`triage_sets`, `read_triage_sets`, the one-derivation check), Story 4.5
  (the append-only ledger + port + use-case seam + the rekey registration), Story 4.3 (the ranked order +
  ranking version identity).

## Dev Agent Record

### Agent Model Used

claude-opus-4-8 (dev-story)

### Debug Log References

- Gate green: ruff clean · 67 structural checks (incl. new `line-stored-by-piece-identity`,
  `line-placement-append-only`; AD-39 `no-retained-discarded-set` stays green after the
  boundary-identity exemption) · import-linter 3/0 · **1200 passed / 12 skipped**.
- Regression caught + fixed by the gate: the Story-4.3 AD-39 check
  `no_retained_or_discarded_set_column` flagged `LinePlacement.last_retained_piece_id` on the
  substring "retained". The column is the line's **boundary identity** (one *pièce*, FR-17 — the cut
  that DERIVES the sets), the opposite of a stored set membership. Refined the check with an exact-
  name exemption (`_BOUNDARY_IDENTITY_COLUMNS`) + a test proving a genuine `retained` membership
  column is still caught.

### Completion Notes List

- The line is stored by the identity of the **last retained *pièce*** (never a bare integer, FR-17)
  in a new append-only, version-bound ledger `line_placement`; the current line is the max-`seq`
  view. Placing the line touches only `line_placement`, never `ranked_entry` — so it structurally
  cannot reorder the order (AC-4).
- The system chooses the cut **recall-first** (`recommend_line`, config `line_retain_bands` =
  confident-relevant ∪ uncertain); when no *pièce* qualifies the tool commits to **no line** rather
  than fabricate a retained set (AC-5, AD-19).
- The basis is **inherited** from the ranking version (`case-theory:<id>` or `intrinsic:<signals>`),
  never invented (AC-1).
- AD-4 seam: `core/ports/line.py` + `core/app/line.py`; the store is a structural
  `LinePlacementRecorder`. `LinePlacementView` lives in `core/domain/line.py` (a core return type).
- Rekey durability: `line_placement.placed_by` (EncryptedText) registered in
  `backfill.py::ENCRYPTED_COLUMNS` — `test_rekey_covers_every_encrypted_column` green.

### File List

**New:** `apx/core/domain/line.py` · `apx/core/ports/line.py` · `apx/core/app/line.py` ·
`apx/adapters/store_postgres/migrations/versions/0027_line_placement.py` ·
`apx/checks/line_stored_by_piece_identity.py` · `apx/checks/line_placement_ownership.py` ·
`tests/domain/test_line.py` · `tests/domain/test_config_line.py` ·
`tests/adapters/test_line_placement_migration.py` · `tests/adapters/test_line_placement_store.py` ·
`tests/app/test_line_use_case.py` · `tests/checks/test_line_placement_ownership.py` ·
`tests/checks/test_line_stored_by_piece_identity.py`

**Modified:** `apx/core/domain/config.py` (+`line_retain_bands`, `Band` import) ·
`apx/adapters/store_postgres/models.py` (+`LinePlacement`) ·
`apx/adapters/store_postgres/store.py` (+`place_line`/`read_current_line`/`_line_basis`/
`_line_retain_bands`, `LinePlacement`+`LinePlacementView` imports, `_BACKUP_TABLES`) ·
`apx/adapters/store_postgres/backfill.py` (ENCRYPTED_COLUMNS) · `apx/checks/encryption.py`
(allowlist) · `apx/checks/ranking_sets_are_views.py` (boundary-identity exemption) ·
`apx/checks/registry.py` · `apx/checks/manifest.py` · `README.md` (config-keys +
structural-properties) · `tests/checks/test_ranking_sets_are_views.py` (exemption tests)

## Change Log

| Date       | Version | Description                                   | Author |
|------------|---------|-----------------------------------------------|--------|
| 2026-08-05 | 0.1     | Story drafted (create-story), ready-for-dev   | create-story |
| 2026-08-05 | 0.2     | Implemented; adversarial review 0 findings; done | dev-story |

## Senior Developer Review (AI)

**Reviewed:** 2026-08-05 · **Outcome:** Approve · **Method:** adversarial Workflow — 3 parallel lenses
(correctness, security/isolation, architecture/scope), each finding independently skeptic-verified
with a default-REFUTED bias. Reviewers inspected the uncommitted working tree against baseline
`8456a02`.

**Result: 0 findings → 0 confirmed / 0 refuted.** All three lenses returned an empty findings set
(verified by reading the workflow `journal.jsonl` — each lens returned `{"findings": []}`; ~40
tool-uses and ~160k tokens per lens, a substantive read, not an empty-error). No skeptic-verify
agents were needed. The architecture lens specifically scrutinised the highest-risk change — the
AD-39 check exemption — and found it sound.

**Integrity manifest:** all 22 touched code files byte-identical since the pre-review snapshot — the
review mutated nothing. **Secret scan:** clean (no key/token in the diff; LLM key env-only).

**Notes on the one non-trivial change beyond the ACs.** The Story-4.3 AD-39 check
`no_retained_or_discarded_set_column` was refined with an exact-name `_BOUNDARY_IDENTITY_COLUMNS`
exemption for `last_retained_piece_id`. Justification: that column is the line's **boundary
identity** — one *pièce* (the ordinal cut that DERIVES the sets), the structural opposite of a stored
set membership AD-39 forbids. The exemption is exact-name-only and covered by a new test proving a
genuine `retained` membership column is still caught alongside the exempt one, so the shipped
guarantee is preserved.

**Gate at done:** ruff clean · **67 structural checks** (incl. new `line-stored-by-piece-identity`,
`line-placement-append-only`; AD-39 stays green) · import-linter 3/0 · **1200 passed / 12 skipped**.

## Dev Questions / Assumptions (ratified by the delegate — do not block)

1. **Placement heuristic.** Assumed recall-first: the cut falls after the **deepest retain-band pièce**
   (default retain-bands = `confident-relevant` ∪ `uncertain`), config-driven (`line_retain_bands`). This
   honours the product's recall-over-precision rule and keeps the boundary config-as-data. A richer
   heuristic (score-margin, confidence) is deferred; the structural guarantees (identity-not-integer,
   append-only, invariant) do not depend on it.
2. **Basis is inherited, not invented.** The line's stored `basis` = the *ranking version*'s basis
   (`case-theory:<ctv_id>` or `intrinsic:<signals>`). This is exactly FR-17's "the case theory where one
   exists, or the named intrinsic signals" and avoids a second, divergible basis derivation.
3. **Honest non-commitment (AC-5).** When no *pièce* is in a retain-band, the tool stores **no line**
   (`recommend_line -> None`) rather than fabricate a retained set. Consistent with AD-19 (nothing
   imputed) and the product ethos; the human can place one manually via 4.9.
4. **Ledger keyed by version.** The line is an append-only ledger keyed by `ranking_version_id` (current
   = max-`seq`), so 4.9's priced move and any reversal APPEND (AD-7), and the line stays bound to the
   version it was placed against (AD-23). 4.8 writes only the system-recommended row.
