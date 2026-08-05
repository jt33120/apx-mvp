---
baseline_commit: 9688dee
---

# Story 4.7: One ranked order, nothing deleted, nothing categorised

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a firm bound by "never destroy a document",
I want triage to be one ranked order with the *retained* and *discarded* sets **derived** from it,
nothing stored as membership,
so that reversibility is a **structural property**, not a promise someone must keep.

## Scope note — the sets are VIEWS `f(order, line, pins)`; the line/pins are INPUTS here

Story 4.3 persisted **one ranked order per *matter* per *ranking version*** (append-only). Story 4.7
makes the ***retained set*** and the ***discarded set*** **views derived at read time** from that order
— never stored memberships (AD-39) — and proves the load-bearing promise **discard is not deletion**: a
*pièce* in the *discarded set* is still returned by exhaustive search (FR-13). It also binds every
derived set to the *ranking version* it means (the ambiguous-referent rule) and declares the
retained-version retention bound as configuration.

**The line and the pins are OPERANDS of the derivation, not machinery built here.** AD-39's rule: the
sets are "computed over one ranked order plus *pins*, in that sequence, at read time" and a *pièce*
moves between them "only because the order changed, **the line** moved or a *pin* was added or
removed." So 4.7 delivers the pure derivation `views = f(order, line-cut, pins)` and takes a `Line` and
a set of `Pin`s **as typed inputs**. Their owning use cases are later stories in the SAME architecture
unit (U15): **the line** (its system-placement, refusal conditions, ordinal-cut-plus-last-retained-pièce
storage) is **Story 4.8 / FR-17**; **the pin** (one-action pin in/out, its one-line reason, the
*override* record, carry-across-versions) is **Story 4.11 / FR-43**.

**IN scope:** (1) a pure Domain `triage_sets.py` — `Line` (the cut, modelled by the identity of the
**last retained *pièce***, not a bare integer), `Pin`/`PinSide` (a per-*pièce* override), `TriageSets`
(the derived view naming its `version_id`, with the retained / discarded / unscored sets and the count
of pins in force), and `derive_triage_sets(order, line, pins) -> TriageSets` — order → line → pins, in
that sequence (AD-39); (2) a store read `read_triage_sets(...)` that reads the persisted order (Story
4.3) and applies the derivation, scope pre-filtered (AD-13, non-disclosing), naming its version — **no
stored membership**; (3) the **FR-13 proof** — a test that a *pièce* in the *discarded set* is still
returned by `exact_search` (discard ≠ deletion, AD-7); (4) **version-binding** — the derived set names
its *ranking version*; re-ranking yields a new version, previous readable (Story 4.3), each set names
its own version; (5) a **structural check** `triage_sets_have_one_derivation` (mirroring
`confidence_has_one_derivation`) — the retained/discarded VIEW is built in exactly one place, never
hand-rolled in a surface; the existing AD-39 `no_retained_or_discarded_set_column` stays green; (6) the
**retained-versions bound** as configuration — the key `retained_ranking_versions_max` (defaulted) + a
thin read reporting versions against it.

**OUT of scope (do NOT build):** **the line**'s placement / refusal conditions / storage (Story 4.8,
FR-17 — 4.7 takes a `Line` as input); the **pin** action / its *override* record / carry-across-versions
(Story 4.11, FR-43 — 4.7 takes `Pin`s as input, empty by default); the actual **retirement** of
over-bound versions (AD-7 — a `retired` state transition through the one named administrative entry
point, a later story / 4.12's remit) and the **full referenced-by exemption** (versions cited by a
*confidence bound* (Epic 5), a *pin* (4.11), an export (Epic 6) or a downstream audit act — those
referencing entities do not exist yet), so 4.7 **executes no retirement and deletes nothing**; the
*audit drawer* / any UX surface (needs a UX pass); *confidence bounds* / *sampling* (Epic 5).

## Acceptance Criteria

**AC-1 (FR-16 / AD-39 — one ranked order; the sets are VIEWS, never memberships).** The *retained set*
and *discarded set* are **derived at read time** from one ranked order + the line cut + pins, **in that
sequence** — never stored as a membership, a column or a materialised table. `derive_triage_sets` is the
**one** pure derivation; a scope-pre-filtered store read computes the view. No ORM column or table names
a retained/discarded set (the existing `no_retained_or_discarded_set_column` check stays green), and a
new `triage_sets_have_one_derivation` check asserts the view is built in exactly one place.

**AC-2 (FR-16 / FR-13 / AD-7 — nothing deleted; a discarded pièce is still found).** No triage operation
deletes a *pièce*, removes it from the *corpus*, or excludes it from retrieval. **Asserted by test:** a
*pièce* placed in the *discarded set* is **still returned by exhaustive search** (`store.exact_search`)
— the exhaustive engine shares no membership with the ranking, so a discard is a derived view, not a
deletion.

**AC-3 (FR-16 / FR-43 — a pin moves exactly one pièce; the order and the line do not move).** Applying a
`Pin` (an input here; its creation is Story 4.11) moves **exactly one** *pièce* across the line: the
*retained set* changes by exactly that *pièce*, the **ranked order is unchanged**, **the line does not
move**, and **no other *pièce*'s membership changes**. The derivation applies pins **after** the line
(AD-39 sequence); the **count of pins in force** is reported wherever the sets are counted (FR-43).

**AC-4 (FR-16 / AD-23 — version-binding; the ambiguous-referent rule).** Every derived set **names the
*ranking version*** it was computed against (`TriageSets.version_id`). Re-running ranking produces a new
*ranking version* (Story 4.3); previous versions remain readable; the sets derived against each version
name **that** version. An unqualified reference is structurally impossible — the view always carries its
version id.

**AC-5 (FR-16 / AD-24 — the retained-versions bound is configuration).** The number of retained *ranking
versions* is bounded by a per-*tenant* **configuration** value (`retained_ranking_versions_max`, with a
defined default); a scope-pre-filtered read reports the matter's version count against the bound. The
retention **execution** (retiring over-bound versions) and the full **referenced-by exemption** are
DEFERRED and documented (AD-7's `retired` transition through the one admin entry point; the exempting
entities — bound / pin / export / downstream audit — are Epic 5 / 4.11 / Epic 6); 4.7 **deletes
nothing**.

**AC-6 (the line and pins are typed INPUTS; their committing is later).** `Line` is modelled by the
**identity of the last retained *pièce*** (not a bare integer position), so Story 4.8's guarantee — an
import that adds *pièces* does not silently move what the line designates — is directly supported. The
line's placement (FR-17 / 4.8) and the pin action (FR-43 / 4.11) are out of scope: 4.7 consumes a `Line`
and a set of `Pin`s and never chooses or stores them.

## Tasks / Subtasks

- [x] **Task 1 — Domain: the pure view derivation (AC-1, AC-3, AC-4, AC-6)**
  - [x] Create `apx/core/domain/triage_sets.py`: `PinSide(StrEnum)` (`RETAIN`, `DISCARD`); frozen `Pin`
    (piece_id, side); frozen `Line` (last_retained_piece_id: str — the cut is the identity of the last
    retained *pièce*, FR-17-ready); frozen `TriageSets` (version_id, retained: tuple[str,...],
    discarded: tuple[str,...], unscored: tuple[str,...], pins_in_force: int; + count properties).
  - [x] `derive_triage_sets(order: RankedOrder, line: Line | None, pins: Iterable[Pin], *,
    version_id: str) -> TriageSets` — pure. Sequence (AD-39): the ranked rows in fixed rank order →
    split at the last-retained *pièce* (line None ⇒ no split: retained/discarded both empty, the ranked
    set is undecided) → apply pins (RETAIN pulls a discarded *pièce* in, DISCARD pushes a retained one
    out; **exactly one *pièce* per pin**; a pin's *pièce* must be in the ranked set, else a loud error).
    `unscored` = `order.unscored_rows` (its own set, never folded into discarded — AD-36/AD-19). The
    order is **never reordered**. `pins_in_force` = number of pins applied.
  - [x] Invariants enforced/tested: retained ∩ discarded = ∅; retained ∪ discarded = the ranked set; a
    pin changes the retained set by exactly one *pièce*; a Line's last-retained *pièce* must be in the
    ranked set (loud error otherwise).
  - [x] Unit tests `tests/domain/test_triage_sets.py`: the split at the last-retained *pièce*; line
    None ⇒ undecided; a RETAIN pin pulls one across, a DISCARD pin pushes one across, order unchanged;
    unscored stays its own set; pins_in_force counted; out-of-order pin/line piece raises.

- [x] **Task 2 — Store: the read that computes the view, scope pre-filtered (AC-1, AC-2, AC-4)**
  - [x] `SqlStore.read_triage_sets(*, tenant, matter, scopes, line: Line | None, pins=(),
    version_no=None) -> TriageSetsView | None` — `_matter_held` guard (non-disclosing None); read the
    persisted order (reuse the `read_ranked_order` shape → a `RankedOrder`), apply `derive_triage_sets`,
    return a `TriageSetsView` naming the `version_id`. Not audited (a read). **No stored membership.**
  - [x] Tests `tests/adapters/test_triage_sets_store.py`: derive over a recorded ranking (retained /
    discarded / unscored + version_id); scope isolation (None out of scope); `[]`/empty when no ranking;
    the view names the correct version across two versions.

- [x] **Task 3 — The FR-13 proof: a discarded pièce is still found by exhaustive search (AC-2)**
  - [x] Test (in `tests/adapters/test_triage_sets_store.py`, consolidated with the read tests): seed a
    `Piece` with full text (mirror
    `tests/adapters/test_deterministic_query.py::_seed`), record a ranking including it, derive the
    sets with a `Line` that puts the *pièce* **below** the cut (discarded), then assert
    `store.exact_search(tenant, scopes, normalize(term))` **still returns its `piece_id`** — the two
    subsystems share no membership, so discard ≠ deletion (AD-7).

- [x] **Task 4 — The retained-versions bound as configuration (AC-5)**
  - [x] Add `ConfigKey("retained_ranking_versions_max", "int", <default>, governs=..., valid=lambda v:
    1 <= v <= <ceiling>)` to `CONFIG_SCHEMA` (mirror `cascade_calibration_sample`); `affects_retrieval`
    stays False (a retention bound does not invalidate derived artefacts). Add the matching row to the
    README `<!-- config-keys -->` block (the 4th lockstep site, guarded by `configuration.py`).
  - [x] Thin read `SqlStore.read_version_retention(*, tenant, matter, scopes) -> VersionRetentionView |
    None` — scope-pre-filtered; reports (total versions, the configured bound, over_bound count).
    Executes **no** retirement (AD-7); documents the deferral of retirement + the referenced-by
    exemption.
  - [x] Tests: `coerce("retained_ranking_versions_max", 0)` rejects (out of range); the read reports the
    count vs the bound; over-bound counted but nothing deleted.

- [x] **Task 5 — The structural check: one derivation of the sets (AC-1)**
  - [x] `apx/checks/triage_sets_one_derivation.py::triage_sets_have_one_derivation` (FR-16 / AD-39) —
    mirror `confidence_derivation.confidence_has_one_derivation`: `TriageSets(...)` is constructed only
    in `core/domain/triage_sets.py` (excluding checks/fitness dirs), so the retained/discarded view has
    one auditable derivation, never hand-rolled in a surface. Registered in `registry.py` +
    `manifest.py` + README `<!-- structural-properties -->` (lockstep, 64 → 65).
  - [x] Failure-path fixture `tests/checks/test_triage_sets_one_derivation.py` — fires on a synthetic
    second construction site, passes on the real tree, fails closed.

- [x] **Task 6 — Gate + close**
  - [x] `ruff check` clean (accents risk E501); import-linter 3/0 (core imports no adapter — the
    derivation is pure Domain, the store read is the adapter); 65 structural checks green (incl. the new
    one + AD-39 `no_retained_or_discarded_set_column` still green + gold gate AD-34 green); full pytest
    green.
  - [x] Update the Change Log; fill Dev Agent Record (File List, Completion Notes).

## Dev Notes

### The load-bearing design — the sets are a pure derivation, nothing is stored

FR-16's whole point (and AD-39's): **reversibility is a shape, not a promise.** The *retained set* and
*discarded set* are **never** stored — they are `derive_triage_sets(order, line, pins)`, recomputed at
read time. A *pièce* moves between them only because the order changed (a new *ranking version*), the
line moved (Story 4.8) or a pin was added/removed (Story 4.11) — each an audited AD-37 transition owned
by its use case. So there is no membership row to drift, and "irreversibility is unrepresentable."

The existing `no_retained_or_discarded_set_column` check (Story 4.3) already forbids any ORM
table/column named `retained`/`discarded` (a plain substring match over real DB column names) — so the
`TriageSets` **domain** value's `retained`/`discarded` **fields are fine** (that check scans only
`__tablename__`-bearing ORM classes, not dataclasses). 4.7 adds no ORM column; the check stays green.
The new `triage_sets_have_one_derivation` check is the complementary teeth: the view is built in ONE
place, so no surface can hand-roll a divergent membership.

### The line modelled by the last-retained pièce (FR-17-ready), not a bare integer

`Line(last_retained_piece_id)` — the cut is the **identity** of the last retained *pièce*, so that
Story 4.8's failure-path AC (an import that adds *pièces* does not silently move what the line
designates — a bare "position 180" would become position 180 of a larger set) is supported by
construction. 4.7 does not *choose* or *store* the line (that is 4.8/FR-17's owning use case,
`LINE_POSITION` in the AD-37 table, a conditional commit against the observed position **and** the
*ranking version*); it only *consumes* a `Line`.

### Pins are inputs; applied AFTER the line; exactly one pièce each (FR-43)

`Pin(piece_id, side)` overrides one *pièce*'s membership. The derivation applies pins **after** the line
(AD-39's "in that sequence"), each pin moving **exactly one** *pièce* — the ranked order and the line
are untouched (a pin is not a rank). The `pins_in_force` count travels with the view (FR-43: "the count
of pins in force is stated wherever the sets are counted"). Pin **creation**, its mandatory one-line
reason, the *override* record (FR-25) and carry-across-versions are Story 4.11 — here pins default to
empty.

### FR-13 — discard is not deletion (the proof)

The exhaustive engine (`store.exact_search` / `core/app/read/deterministic.py::search_exhaustive`,
Story 3.2) searches `piece.full_text_normalized` with a complete `LIKE`, **content-blind to the
ranking** — it shares no table with `ranked_entry`. So a *pièce* in a derived *discarded set* is
unchanged in the *corpus* and still found. The FR-13 test makes this structural: seed a searchable
*pièce*, discard it via the derivation, assert `exact_search` still returns it. (SM-13 / SM-C1 are the
metrics this operationalises; SM-C1 — gold relevant *pièces* in the discarded set — "may never rise".)

### The retained-versions bound — the honest MVP (AD-7 respected)

FR-16 requires the number of retained versions be "bounded by configuration, with versions referenced by
a *confidence bound*, a *pin*, an export or an *audit record* entry exempt." 4.7 delivers the
**configuration** (`retained_ranking_versions_max`, defaulted) and an observable read, but **retires
nothing**: AD-7 makes retirement a `retired` state transition through the **one** named administrative
entry point (not a DELETE), and the exempting entities do not exist yet (bounds = Epic 5, pins = 4.11,
exports = Epic 6). Building the exemption now would guess a contract whose inputs are absent (note also
that **every** version already has a `ranking_recorded` audit entry, so a naive "audit-referenced ⇒
exempt" reading is vacuous — the intended exemption is a *downstream* citation, which awaits those
stories). So 4.7 declares the bound as data and defers execution — honest, forward-compatible, and
never destructive. Related open questions: OQ-8 (lawful erasure vs never-delete), OQ-23 (legal
hold/sealing a matter under a quoted bound).

### Existing seams to reuse

- The persisted order + reads: `record_ranking`, `read_ranked_order` (rows ordered `rank.is_(None),
  rank, piece_id`), `read_ranking`, `list_ranking_versions` (`store.py`); `RankedOrder`/`RankedRow`
  (`core/domain/ranking.py`).
- Scope pre-filter (AD-13): `_matter_held(...)` → non-disclosing None. Not audited (reads).
- Exhaustive search (FR-13): `store.exact_search(*, tenant, scopes, normalized_query)`; seed helper
  pattern in `tests/adapters/test_deterministic_query.py::_seed`.
- Config numeric key + `valid=`: `cascade_calibration_sample` (`config.py`); the README config-keys
  block + `configuration.py` lockstep (4th site).
- One-derivation check template: `confidence_derivation.py` (`Confidence(...)` built only in
  `piece_confidence.py`); registration lockstep registry + manifest + README (65 after this).

### Test / lint conventions (house rules)

uv venv (`.venv/bin/ruff`, `.venv/bin/python`; no pip). The gate is `ruff check` (line-length 100 —
accents *pièce*/*é*/`→`/`≥`/`∩`/`∪` push lines over; reflow **by hand**, the auto-reflow corrupts code
lines with trailing comments). Run pytest with `export PATH="$PWD/.venv/bin:$PATH"`; **never export
`DATABASE_URL`**.

### Project Structure Notes

- New: `apx/core/domain/triage_sets.py`, `apx/checks/triage_sets_one_derivation.py`, and their tests.
- Modified: `apx/core/domain/config.py` (the retention key), `apx/adapters/store_postgres/store.py`
  (`read_triage_sets` + `read_version_retention` + DTOs), `apx/checks/registry.py`,
  `apx/checks/manifest.py`, `README.md` (config-keys + structural-properties blocks).
- No ORM/migration change (the sets are views — no new table/column; AD-39).

### References

- [Source: prd.md#FR-16] `:487-497` — one order; views not memberships; nothing deleted (test:
  discarded still found); re-rank → new version; every surface names its version; retained-versions
  bound + exemption. [Source: prd.md#FR-43] `:860-872` the pin. [Source: prd.md#FR-13] `:437-449`
  exhaustive search. [Source: prd.md#FR-17] `:499-508` the line (Story 4.8). SM-13 `:1248`, SM-C1
  `:1266`, SM-11 `:1244`; retention bound `:496`/`:1313`, A-31 `:1620`; OQ-8 `:1536`, OQ-23 `:1570`.
- [Source: ARCHITECTURE-SPINE.md] AD-39 `:1101-1115` (views, never memberships), AD-7 `:226-258`
  (nothing hard-deleted; `retired` state; no DELETE/TRUNCATE/DROP token in runtime), AD-23 `:656-697`
  (version identity + conditional commit + staleness), AD-13 `:380-398` (scope pre-filter), AD-37
  `:1029-1073` (owns `LINE_POSITION`/`PIN` — later stories), AD-49 `:1328-1341` (monotonic).
- [Source: WORK-BREAKDOWN.md] U15 `:628-656` — the order + the line + the pin are one unit; FR-16/17/
  39/40/43/58; owns `LINE_POSITION`/`PIN`; sets are views computed after pins, never a column.
- [Source: epics.md] Story 4.7 `:1185-1198`; Story 4.8 (the line) `:1200-1213`; Story 4.11 (the pin)
  `:1250-1262`.

## Dev Agent Record

### Agent Model Used

claude-opus-4-8 (Opus 4.8, 1M context)

### Debug Log References

- Full gate green: `ruff check` clean · **65** structural checks pass (new `triage-sets-one-derivation`
  + AD-39 `no-retained-discarded-set` still green + meta-checks lockstep) · import-linter 3/0 · **1156
  passed / 12 skipped**. No ORM/migration change (the sets are views — nothing stored).

### Completion Notes List

- **The load-bearing choice:** the retained/discarded sets are a **pure derivation**
  (`derive_triage_sets`), recomputed at read time from the ranked order + the line cut + pins — never a
  stored column/table (AD-39). The store's `read_triage_sets` CALLS the derivation and returns its
  `TriageSets`; it never constructs one — so the new `triage_sets_have_one_derivation` check (one
  auditable view) holds, and the 4.3 `no_retained_or_discarded_set_column` stays green (no ORM column
  added). `TriageSets.retained`/`discarded` are dataclass fields, not ORM columns, so the substring
  check does not flag them.
- **FR-13 (discard ≠ deletion) is structural, not asserted:** the exhaustive engine
  (`store.exact_search`) shares no table with `ranked_entry` — it reads `piece.full_text_normalized`.
  The test seeds a searchable *pièce*, discards it via the derivation, and shows `exact_search` still
  returns it. Nothing could make discard delete, because there is no membership to delete.
- **The line as the last-retained *pièce* identity (FR-17-ready):** `Line(last_retained_piece_id)`, not
  a bare integer — so Story 4.8's "an import does not move what the line designates" is supported by
  construction. The line and pins are **typed inputs**; their owning use cases are 4.8/4.11.
- **The unscored tail is its own set** (AD-19/AD-36) — never folded into discarded (a *pièce* the
  cascade could not score is not silently discarded; recall-bias non-negotiable).
- **The retained-versions bound — honest MVP (AD-7 respected):** the config key
  `retained_ranking_versions_max` (defaulted 20) makes the bound data; `read_version_retention` reports
  the count vs the bound but **retires nothing** — retirement is AD-7's `retired` transition through
  the one admin entry point, and the full referenced-by exemption (bound/pin/export/downstream-audit)
  awaits Epic 5 / 4.11 / Epic 6 (and a naive "audit-referenced ⇒ exempt" reading is vacuous — every
  version already has a creation-audit). So nothing is deleted; the bound is declared and observable.
- **Test file consolidation (honesty note, per the 4.5 review):** the FR-13 proof and the retention
  tests live in `tests/adapters/test_triage_sets_store.py` (with the read tests), NOT in a separate
  `test_discard_is_not_deletion.py` — the drafted Task-3 file name was consolidated; the File List
  below is the actual set of files.

### File List

**Created:** `apx/core/domain/triage_sets.py` · `apx/checks/triage_sets_one_derivation.py` ·
`tests/domain/test_triage_sets.py` · `tests/domain/test_config_retention.py` ·
`tests/adapters/test_triage_sets_store.py` · `tests/checks/test_triage_sets_one_derivation.py`

**Modified:** `apx/core/domain/config.py` (the `retained_ranking_versions_max` key) ·
`apx/adapters/store_postgres/store.py` (`read_triage_sets` + `read_version_retention` +
`VersionRetentionView`) · `apx/checks/registry.py` · `apx/checks/manifest.py` · `README.md`
(config-keys + structural-properties blocks) ·
`_bmad-output/implementation-artifacts/sprint-status.yaml`

## Senior Developer Review (AI)

**Date:** 2026-08-05 · **Outcome:** Approve (no confirmed findings). Adversarial Workflow review, 3
parallel lenses (correctness · security/isolation · architecture/scope) → each finding independently
skeptic-verified (default REFUTED). Result: **1 finding → 0 CONFIRMED / 1 REFUTED**. The
security/isolation and architecture/scope lenses found **zero** defects. Integrity manifest verified:
the review mutated no code file (all 11 snapshotted files byte-identical). (The review journal was
read directly to confirm the aggregation — 3 lens results + 1 verdict — matched the summary.)

**Action Items:**

- [x] **[Refuted · low] `derive_triage_sets` did not guard ranked/unscored disjointness** — the pure
  function checked for duplicates only WITHIN `ranked`, not that `ranked` and the `unscored` tail are
  disjoint (a *pièce* in both would land in a triage set AND the tail). Refuted as **unreachable**:
  the only caller (`read_triage_sets`) partitions `RankedEntry` rows by rank-null so each `piece_id`
  reaches exactly one list, and `UniqueConstraint(ranking_version_id, piece_id)` guarantees no
  duplicate — the finding conceded no live failure. **Hardened anyway** (cheap + principled, matching
  the AD-19 "fails loudly, nothing imputed" ethos and the 4.3 `_sort_key` precedent): the guard now
  refuses any *pièce* appearing more than once across the ranked order + the unscored tail, with a
  regression test. No production-path behaviour change.

## Change Log

| Date       | Version | Description                  | Author |
| ---------- | ------- | ---------------------------- | ------ |
| 2026-08-05 | 0.1     | Story drafted (create-story) | Claude |
| 2026-08-05 | 0.2     | Implemented (dev-story) — gate green | Claude |
| 2026-08-05 | 0.3     | Adversarial review: 0 confirmed / 1 refuted (disjointness guard hardened) | Claude |
