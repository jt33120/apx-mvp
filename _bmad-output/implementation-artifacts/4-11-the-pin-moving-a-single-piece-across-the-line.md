---
baseline_commit: 48a875f
---

# Story 4.11: The pin — moving a single pièce across the line

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a lawyer who knows one discarded document is decisive,
I want to move that one *pièce* across **the line** without dragging the line past everything above it,
so that retaining the decisive piece does not force me to retain four hundred others.

## Scope note — 4.11 OWNS the pin's creation + its override + its ledger; the derivation exists

Story 4.7 already defined the pin as an **input** to the derivation: `Pin(piece_id, side)`,
`PinSide(RETAIN, DISCARD)`, and `derive_triage_sets(ranked, unscored, line, pins, version_id)` applies
the pins **after** the line cut so a pin that disagrees with the line moves **exactly one** *pièce*
(counted in `pins_in_force`). `read_triage_sets(..., pins=...)` already accepts pins. Story 4.11 now
delivers the **owning use case** (AD-37): the pin **action** (a per-*pièce*, per-*matter* override of
the line, retain or discard), its **mandatory one-line reason recorded as an *override*** (FR-25), an
**append-only, version-INDEPENDENT** ledger so pins **survive re-ranking** (carried to new *ranking
versions* marked human-set until explicitly removed), and the read that feeds the current pins into the
derivation.

**Why version-independent (like the 4.5 taxonomy-label ledger, NOT the version-bound line):** FR-43
requires pins to *survive re-ranking* and carry to new *ranking versions*. A pin is about a *pièce*
("retain THIS pièce regardless of its rank"), not about a version — so the ledger is keyed by
`(tenant, matter, piece_id)` with a per-*pièce* monotonic `seq`, and the current pin is a **VIEW** (the
max-`seq` entry, if it is an active pin). Because it is version-independent, a pin applies to whatever
*ranking version* the sets are derived over — survival is **structural**, not a copy step.

**The exactly-one-moves / line-unmoved / order-unchanged guarantees come from 4.7 + separation of
tables:** `derive_triage_sets` moves exactly the pinned *pièce* (AC proof is a `read_triage_sets`
test); pinning writes **only** `pin_entry` — never `line_placement`, never `ranked_entry` — so the
line does not move and the order does not change (structural).

**IN scope:**
1. A pure Domain `apx/core/domain/pin.py` — `PinAction(RETAIN, DISCARD, REMOVED)`; a frozen
   `PinLogEntry(piece_id, seq, action)`; `current_pins(entries) -> tuple[Pin, ...]` (the in-force pins:
   per *pièce*, the max-`seq` entry, mapped to `Pin(piece_id, PinSide)` when RETAIN/DISCARD, excluded
   when REMOVED); `validate_pin_reason(reason)` (a pin **requires** a non-blank one-line reason —
   FR-25; raises `MissingPinReason` on blank/whitespace). Reuses `Pin`/`PinSide` from `triage_sets.py`.
2. A new **append-only, version-independent** model `PinEntry` (table `pin_entry`) + Alembic migration
   `0028` — one row per pin/unpin, keyed by `(tenant, matter, piece_id, seq)`; `action`, `reason`
   (EncryptedText — the override reason, content), `set_by` (EncryptedText — actor), `at`.
3. Store `pin_piece(...)` — the owning use case (AD-37): validate the reason (loud `MissingPinReason`),
   append one `PinEntry` (server monotonic `seq`, AD-49, conditional commit on `expected_seq`, AD-37)
   **atomic** with one audit entry **marked as an *override*** (FR-25: a distinct action + the reason
   verbatim). Scope-checked. Touches only `pin_entry`.
4. Store `remove_pin(...)` — appends a `REMOVED` entry (append-only, AD-7 — a removal is a NEW entry,
   never a delete), atomic with a `pin_removed` audit (a reversible act, **not** an override — it lifts
   a contradiction, it does not make one). Loud if there is no active pin to remove.
5. Store `read_current_pins(...) -> tuple[Pin, ...] | None` — the in-force pins (scope pre-filtered,
   non-disclosing), the input `read_triage_sets(pins=...)` consumes; and `read_pin_change_log(...,
   piece_id)` — the append-only per-*pièce* log (assignment + removal, in `seq` order).
6. A **core port + use-case seam** `core/ports/pin.py` + `core/app/pin.py` (AD-4), mirroring 4.5's
   taxonomy-label seam.
7. The **encrypted-column rekey registration** for `pin_entry.reason` **and** `pin_entry.set_by` (both
   EncryptedText — the 4.5 rekey-regression guard) + the encryption plaintext allowlist for `action`.
8. Two **structural checks** (lockstep): `pin_ledger_is_append_only` (AD-7/AD-37 — `PinEntry`
   constructed only in the store, no UPDATE/DELETE; mirror `taxonomy_label_ownership`) and
   `ranking_order_ignores_the_pin` (FR-43/AD-39 — the ranking modules `ranking.py` / `rank.py` do not
   import/reference the pin axis, so a pin can never be an ordering input; mirror
   `label_not_a_ranking_input`).

**OUT of scope (do NOT build):** the *audit drawer* / export / the override count+filter surface
(FR-26 — a later story; 4.11 records the override in the audit with its reason, which the drawer will
read); the **editable table / change-log UI** (needs the UX contract, which exists — but this story is
backend + structural); partial-RBAC-scope pin semantics beyond the existing per-*matter* `matter_held`
gate (the MVP scope is per-*matter*; FR-43's "she may pin within her scope" is satisfied by the matter
gate); `confidence bounds` / sampling / staleness marking of bounds after a pin (Epic 5 / Story 4.13).
Do NOT change `derive_triage_sets` or `read_triage_sets` (they already take pins).

## Acceptance Criteria

**AC-1 (exactly one moves; line + order unchanged)** — **Given** a ranked *matter*, **When** the
lawyer pins a *pièce* into or out of the *retained set*, **Then** the *retained set* changes by
**exactly one** *pièce*, the ranked order does not change, **the line** does not move, and no other
*pièce*'s membership changes (FR-43).
- *Testable:* `read_triage_sets` with `pins=read_current_pins(...)` after pinning one discarded *pièce*
  RETAIN grows the retained set by exactly one and leaves every other membership identical;
  `read_ranked_order` and `read_current_line` are byte-identical before/after the pin (pinning writes
  only `pin_entry`).

**AC-2 (override with a mandatory reason)** — **And** a pin **requires a one-line reason** and is
**recorded as an *override*** (FR-25), because it contradicts a machine assertion.
- *Testable:* `pin_piece` with a blank/whitespace reason raises `MissingPinReason` and writes nothing;
  a valid pin writes one audit entry marked as an override, carrying the reason verbatim (encrypted),
  attributed and timestamped.

**AC-3 (survives re-ranking, human-set, reversible)** — **And** pins **survive re-ranking** and carry
to new *ranking versions* marked as human-set until explicitly removed, and **removing a pin is itself
a recorded reversible act**.
- *Testable:* pin a *pièce*; re-rank (a new *ranking version*); `read_current_pins` still returns the
  pin, and `read_triage_sets(version_no=new, pins=read_current_pins(...))` reflects it — survival is
  structural (the ledger is version-independent). `remove_pin` appends a `REMOVED` entry (the prior
  entries remain — append-only), `read_current_pins` no longer returns it, and the removal is audited.

## Tasks / Subtasks

- [x] **Task 1 — Domain: the pin ledger vocabulary + the in-force view + the reason rule** (AC: 1,2,3)
  - [x] Create `apx/core/domain/pin.py`. `PinAction(StrEnum)`: `RETAIN="retain"`, `DISCARD="discard"`,
        `REMOVED="removed"` (append-only string values — a persisted action must always decode). Import
        `Pin`, `PinSide` from `apx.core.domain.triage_sets`.
  - [x] Frozen `PinLogEntry(piece_id: str, seq: int, action: PinAction)`.
  - [x] `current_pins(entries: Iterable[PinLogEntry]) -> tuple[Pin, ...]`: group by `piece_id`, take the
        max-`seq` entry per *pièce*; emit `Pin(piece_id, PinSide.RETAIN|DISCARD)` when the latest action
        is RETAIN/DISCARD, exclude it when REMOVED. Deterministic order (by `piece_id`).
  - [x] `class MissingPinReason(ValueError)`; `validate_pin_reason(reason: str) -> None` — raises when
        blank/whitespace (FR-25: a pin cannot be committed without a reason).
  - [x] Tests `tests/domain/test_pin.py`: the in-force view (latest wins; REMOVED drops it; retain vs
        discard maps to PinSide); a blank reason is refused; a valid reason passes.

- [x] **Task 2 — Model + migration: the append-only, version-independent pin ledger** (AC: 2,3) — AD-7/49
  - [x] Add `PinEntry` to `models.py` (table `pin_entry`): `id` = `sha256(tenant\x00matter\x00pid\x00seq)`;
        `tenant`, `matter`, `piece_id`; `seq` (per-*pièce* monotonic, AD-49); `action` (String,
        plaintext categorical); `reason` (`EncryptedText("pin_entry.reason")` — the override reason,
        content); `set_by` (`EncryptedText("pin_entry.set_by")` — actor, PII); `at`. `UniqueConstraint(
        tenant, matter, piece_id, seq)`; `Index(tenant, matter, piece_id)`; composite `ForeignKeyConstraint((tenant,matter) → matter_scope)` no ondelete. Docstring: APPEND-ONLY (AD-7,
        asserted by `pin_ledger_is_append_only`), version-independent (survives re-ranking, FR-43), the
        current pin is a max-`seq` VIEW.
  - [x] Migration `0028_pin_entry.py` (`down_revision = "0027_line_placement"`, no backfill). Mirror
        `0026`. Add `"pin_entry"` to `_BACKUP_TABLES`.
  - [x] Test `tests/adapters/test_pin_entry_migration.py` (mirror the 0026/0027 migration test).

- [x] **Task 3 — Encrypted-column rekey + encryption allowlist** (AC: 2) — the 4.5 regression guard
  - [x] Add BOTH to `backfill.py::ENCRYPTED_COLUMNS`: `("pin_entry", "id", "reason", "pin_entry.reason")`
        and `("pin_entry", "id", "set_by", "pin_entry.set_by")` (single-PK `id`).
  - [x] Add `("PinEntry", "action")` to the `encryption.py` qualified plaintext allowlist (a categorical
        enum, like `("TaxonomyLabelEntry", "source")`).

- [x] **Task 4 — Store: the owning use cases + the reads** (AC: 1,2,3) — AD-22/AD-37/AD-13
  - [x] `class StalePin(Exception)` (mirror `StaleLabel`, carrying the observed vs current seq).
  - [x] `_append_pin_entry(session, now, *, tenant, matter, actor, piece_id, action, reason,
        expected_seq)` (mirror `_append_label_entry`): mint the per-*pièce* monotonic `seq` (conditional
        commit on `expected_seq` → `StalePin`), INSERT the `PinEntry`, and `_append_audit` with the
        override/removal action + the reason. Returns `seq`.
  - [x] `pin_piece(*, tenant, matter, actor, piece_id, side: PinSide, reason, scopes,
        expected_seq=None) -> int` inside `_audited_tx`: scope-check (`ScopeDenied`); `validate_pin_reason(reason)` (loud); append with `action=PinAction(side.value)`, audit action
        `"pin_override"` (FR-25 — an override, reason verbatim). Returns `seq`.
  - [x] `remove_pin(*, tenant, matter, actor, piece_id, scopes, expected_seq=None) -> int`: require a
        current ACTIVE pin (loud `ValueError` if none); append `action=REMOVED`, audit action
        `"pin_removed"` (a reversible act, not an override — no reason required; store an empty/"" reason
        or a fixed note). Returns `seq`.
  - [x] `read_current_pins(*, tenant, matter, scopes) -> tuple[Pin, ...] | None`: scope pre-filter;
        read all `pin_entry` rows for the *matter*; `current_pins(...)`. None when out of scope/absent.
  - [x] `read_pin_change_log(*, tenant, matter, piece_id, scopes) -> list[PinChangeEntry] | None`: the
        append-only per-*pièce* log in `seq` order (a DTO `PinChangeEntry(seq, action, reason, set_by,
        at)`). None when out of scope/absent; `[]` when the *pièce* has no pin history.
  - [x] Tests `tests/adapters/test_pin_store.py`: (a) **AC-1** — pin a discarded *pièce* RETAIN, then
        `read_triage_sets(pins=read_current_pins(...))` grows retained by exactly one, every other
        membership identical, `read_ranked_order`/`read_current_line` byte-identical; (b) **AC-2** — a
        blank reason raises `MissingPinReason` (nothing written); a valid pin writes one `pin_override`
        audit carrying the reason; (c) **AC-3** — after a re-rank (new version) `read_current_pins` still
        returns the pin and `read_triage_sets(version_no=new, pins=...)` reflects it; `remove_pin`
        appends REMOVED (prior rows remain), `read_current_pins` drops it, the removal is audited;
        (d) `expected_seq` conditional commit raises `StalePin`; (e) scope-gated non-disclosing.

- [x] **Task 5 — Core port + use-case seam** (AC: 1,2,3) — AD-4
  - [x] `core/ports/pin.py`: `PinRecorder` Protocol — `pin_piece`, `remove_pin`, `read_current_pins`.
  - [x] `core/app/pin.py`: thin forwarders `pin_piece` / `remove_pin` / `read_current_pins`. Mirror
        `core/app/label.py`.
  - [x] Test `tests/app/test_pin_use_case.py` (mirror `test_label_use_case.py`): forwards to a fake
        recorder; the real store satisfies the port.

- [x] **Task 6 — Structural checks (lockstep) + README** (AC: 1,2,3) — AD-33
  - [x] `apx/checks/pin_ledger_ownership.py` (NEW): `pin_ledger_is_append_only` — `PinEntry` constructed
        only in the store adapter; no UPDATE/DELETE of `pin_entry`. Mirror `taxonomy_label_ownership`.
        Key `pin-ledger-append-only`, FR-43, AD-37.
  - [x] `apx/checks/pin_not_a_ranking_input.py` (NEW): `ranking_order_ignores_the_pin` — `ranking.py` /
        `rank.py` do not import/reference the pin axis (`pin` module / `PinEntry`), so a pin never
        reorders. Mirror `label_not_a_ranking_input`. Key `pin-not-a-ranking-input`, FR-43, AD-39.
  - [x] Register BOTH in registry + manifest + README (check count 68 → 70). Failure-fixture tests for
        each (`tests/checks/test_pin_ledger_ownership.py`, `tests/checks/test_pin_not_a_ranking_input.py`).

- [x] **Task 7 — Full gate + reconcile** (all ACs)
  - [x] `cd apx-mvp && export PATH="$PWD/.venv/bin:$PATH"` then ruff (reflow accents by hand), the check
        harness (the two new checks green; count 70; the rekey test green), import-linter 3/0, pytest
        (all pass, no `apx-platform/` collection).

## Dev Notes

### The substrate 4.11 consumes (do NOT re-implement)

- **`apx/core/domain/triage_sets.py`** (Story 4.7): `Pin(piece_id, side)`, `PinSide(RETAIN, DISCARD)`,
  `derive_triage_sets(..., pins=...)` — the pin is already an INPUT applied AFTER the line, moving
  exactly one *pièce* (counted in `pins_in_force`). 4.11 must NOT change this. [Source: triage_sets.py]
- **`store.read_triage_sets(..., pins=(), version_no=None)`** already accepts pins — 4.11's
  `read_current_pins` feeds it. The AC-1/AC-3 proofs compose the two. [Source: store.py:3165 region]
- **The write pattern to mirror exactly (Story 4.5's label ledger)** — `_append_label_entry` /
  `assign_label` / `revert_label` (conditional-commit `expected_seq`/`StaleLabel`, atomic audit,
  append-only). The pin ledger is the same shape, keyed by `(tenant, matter, piece_id)`, version-
  independent. [Source: store.py::_append_label_entry.]
- **Override = an audit act, not a table** (FR-25 / Glossary): "a user decision that contradicts a
  machine assertion… requires a mandatory one-line reason; recorded in the audit record as an override,
  distinct from an ordinary modification". So the pin's override is the audit entry (a distinct action
  `pin_override` + the reason verbatim in the encrypted `audit_record.detail`), attributed +
  timestamped. No separate override table. [Source: prd.md FR-25 §617, Glossary §239/§249.]
- **Encrypted-column rekey (the 4.5 regression)**: `pin_entry.reason` AND `pin_entry.set_by` are
  EncryptedText → BOTH must be in `backfill.py::ENCRYPTED_COLUMNS`, or `test_rekey_covers_every_
  encrypted_column` fails. [Source: backfill.py, the Story 4.5 finding.]

### Structural-check patterns

`pin_ledger_is_append_only` mirrors `taxonomy_label_ownership.py`; `ranking_order_ignores_the_pin`
mirrors `label_not_a_ranking_input.py` (the ranking modules must not depend on the pin axis).

### Testing standards

uv-managed (`.venv/bin/...`); **always `cd apx-mvp` first + `export PATH` in the same Bash call**;
**never `export DATABASE_URL`**; ruff line-length 100 (reflow accents by hand). Store tests use the
SQLite `_sf()` + `record_ranking` + `_seed_piece` seeding (see `test_triage_sets_store.py` /
`test_taxonomy_label_store.py`).

### Project Structure Notes

- New: `apx/core/domain/pin.py`, `apx/core/ports/pin.py`, `apx/core/app/pin.py`,
  `apx/adapters/store_postgres/migrations/versions/0028_pin_entry.py`,
  `apx/checks/pin_ledger_ownership.py`, `apx/checks/pin_not_a_ranking_input.py`, and their tests.
- Updated: `models.py` (+`PinEntry`), `store.py` (+`pin_piece`/`remove_pin`/`read_current_pins`/
  `read_pin_change_log`/`StalePin`/`PinChangeEntry`/`_append_pin_entry`, `_BACKUP_TABLES`),
  `backfill.py`, `encryption.py`, `registry.py`, `manifest.py`, `README.md`. No config key.

### References

- [Source: epics.md#Story-4.11] · [Source: prd.md#FR-43] (the pin) + [Source: prd.md#FR-25] (override,
  mandatory reason) + Glossary §239 (Pin) / §249 (Override). · UX:
  `EXPERIENCE-EPIC4.md#The-pin`, `DESIGN.md {components.pin-marker}`. · Sibling: Story 4.7 (Pin +
  derive_triage_sets), Story 4.5 (the append-only ledger + port/app seam + rekey), Story 4.8/4.9 (the
  line + its ledger — the pin does NOT move the line).

## Dev Agent Record

### Agent Model Used

claude-opus-4-8 (dev-story)

### Debug Log References

- Gate green: ruff clean · **70 structural checks** (incl. new `pin-ledger-append-only`,
  `pin-not-a-ranking-input`) · import-linter 3/0 · **1257 passed / 12 skipped**. The rekey /
  encryption / backup suites pass with `pin_entry` (both encrypted columns registered).

### Completion Notes List

- The pin is an **append-only, version-independent** ledger (`pin_entry`, keyed by pièce): a pin
  **survives re-ranking structurally** (no copy step), and the current pin is a max-`seq` VIEW
  (`current_pins`; a `removed` action lifts it). It reuses the 4.7 `Pin`/`PinSide` and feeds
  `read_triage_sets(pins=...)`.
- **Exactly-one-moves / line-unmoved / order-unchanged** come from 4.7's `derive_triage_sets` + table
  separation (pinning writes only `pin_entry`); proven by composing `read_current_pins` into
  `read_triage_sets` and asserting `read_ranked_order` / `read_current_line` byte-identical (AC-1).
- A pin **requires a one-line reason** (`validate_pin_reason` → `MissingPinReason`) and is recorded as
  an **override** — a distinct `pin_override` audit action carrying the reason verbatim (FR-25).
  Removal is `pin_removed` — a reversible act, not an override.
- AD-4 seam: `core/ports/pin.py` + `core/app/pin.py`; the store is a structural `PinRecorder`.
- Rekey durability: `pin_entry.reason` AND `pin_entry.set_by` (EncryptedText) registered in
  `backfill.py::ENCRYPTED_COLUMNS`. Two structural checks: append-only ownership + the ranking order
  ignores the pin axis (a pin never reorders).

### File List

**New:** `apx/core/domain/pin.py` · `apx/core/ports/pin.py` · `apx/core/app/pin.py` ·
`apx/adapters/store_postgres/migrations/versions/0028_pin_entry.py` ·
`apx/checks/pin_ledger_ownership.py` · `apx/checks/pin_not_a_ranking_input.py` ·
`tests/domain/test_pin.py` · `tests/adapters/test_pin_store.py` ·
`tests/adapters/test_pin_entry_migration.py` · `tests/app/test_pin_use_case.py` ·
`tests/checks/test_pin_ledger_ownership.py` · `tests/checks/test_pin_not_a_ranking_input.py`

**Modified:** `apx/adapters/store_postgres/models.py` (+`PinEntry`) ·
`apx/adapters/store_postgres/store.py` (+`pin_piece`/`remove_pin`/`read_current_pins`/
`read_pin_change_log`/`_append_pin_entry`/`_current_pin_action`/`StalePin`/`PinChangeEntry`,
`_BACKUP_TABLES`, imports) · `apx/adapters/store_postgres/backfill.py` (ENCRYPTED_COLUMNS ×2) ·
`apx/checks/encryption.py` (allowlist) · `apx/checks/registry.py` · `apx/checks/manifest.py` ·
`README.md` (structural-properties)

## Change Log

| Date       | Version | Description                                   | Author |
|------------|---------|-----------------------------------------------|--------|
| 2026-08-05 | 0.1     | Story drafted (create-story inline), ready-for-dev | create-story |
| 2026-08-06 | 0.2     | Implemented; adversarial review 1 finding → 1 confirmed → fixed; done | dev-story |

## Senior Developer Review (AI)

**Reviewed:** 2026-08-06 · **Outcome:** Approve after fix · **Method:** adversarial Workflow — 3
parallel lenses (correctness, security/isolation, architecture/scope), each finding independently
skeptic-verified with a default-REFUTED bias, against baseline `48a875f`. (Verified against the
workflow `journal.jsonl`: correctness produced 1 finding, security + architecture 0; the one finding
was CONFIRMED.)

**Result: 1 finding → 1 confirmed → FIXED.**

- **CONFIRMED (correctness, medium) — a surviving pin on a pièce that becomes UNSCORED (or absent) on
  re-rank crashed the whole triage view.** `read_current_pins` is version-independent (correct — a pin
  survives re-ranking, FR-43), but the sanctioned composition
  `read_triage_sets(version_no=N, pins=read_current_pins(...))` handed `derive_triage_sets` a pin whose
  pièce may not be in version N's ranked (scored) set. `derive_triage_sets` guards a pin naming a pièce
  not in the order and raised `ValueError` — crashing the **entire** version's retained/discarded view,
  not just that pièce. UNSCORED is a first-class cascade outcome (a judge failure), so this is
  reachable, and the affected pièce is by definition a decisive one the lawyer flagged. **The AC-3 test
  masked it** by re-ranking with identical pairs (keeping the pinned pièce scored).
  - **Fix (confined to `read_triage_sets` + a new test, no change to the 4.7 `derive_triage_sets`):** at
    the composition boundary, filter the passed pins to the version's ranked set. A surviving pin whose
    pièce is unscored/absent in **this** version is **dormant** for this view — it stays in the ledger
    (still returned by `read_current_pins`), applies to any version where the pièce is scored, and never
    imputes an unscored pièce into the retained set (AD-19, nothing imputed). The pure
    `derive_triage_sets` keeps its loud guard for direct callers.
  - **Regression test added** (`test_a_surviving_pin_on_an_unscored_piece_is_dormant_not_a_crash`): pin
    a pièce, re-rank so the cascade marks it UNSCORED, and assert the triage read does **not** crash —
    the pièce lands honestly in the unscored tail, the pin dormant but surviving.

**Integrity manifest:** of the 19 snapshotted code files, **only** the two touched by the fix
(`store.py`, `test_pin_store.py`) changed since the pre-review snapshot — the review agents mutated no
code; the change is exactly the confirmed-finding fix. **Secret scan:** clean.

**Gate at done (post-fix):** ruff clean · **70 structural checks** · import-linter 3/0 · **1258 passed
/ 12 skipped**.

## Dev Questions / Assumptions (ratified by the delegate — do not block)

1. **Version-independent ledger** (keyed by *pièce*, like the 4.5 taxonomy label), so pins survive
   re-ranking structurally (FR-43) rather than by a copy step. The current pin is a max-`seq` VIEW.
2. **Override = the audit act** (FR-25): a distinct audit action `pin_override` + the reason verbatim
   (encrypted). No separate override table (none exists; the Glossary defines it as an audit-recorded
   category). Removal is `pin_removed` — a reversible act, not an override (it lifts a contradiction).
3. **exactly-one / line-unmoved / order-unchanged** are inherited from 4.7's `derive_triage_sets` +
   table separation (pinning writes only `pin_entry`); 4.11 proves them by composing `read_current_pins`
   into `read_triage_sets` and asserting `read_ranked_order`/`read_current_line` are byte-identical.
4. **Reason stored in the pin ledger AND the audit**: the ledger `reason` (encrypted) feeds the pin
   change-log; the audit carries it verbatim (FR-25). A one-line note duplicated encrypted, each with a
   distinct purpose (reversible pin state vs the immutable override trail).
