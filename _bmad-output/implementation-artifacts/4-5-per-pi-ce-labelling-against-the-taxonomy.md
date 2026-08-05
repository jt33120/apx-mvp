---
baseline_commit: 95f37d3
---

# Story 4.5: Per-pièce labelling against the taxonomy

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a lawyer,
I want every *pièce* to carry exactly one label from my firm's taxonomy, changeable without moving it
in the ranking,
so that classifying a document and ranking it are two acts, not one.

## Scope note — the per-*pièce* TAXONOMY label (FR-40); a third axis, not the relevance verdict

There are already **two** label concepts in the codebase; Story 4.5 adds a **third, orthogonal** one and
must not conflate them:

- the **relevance verdict** — `triage.Label` (`relevant|uncertain|discard`), persisted in `piece_label`
  (`LabelRecord`) and carried as the nullable `RankedEntry.label` / `RankedRow.label`. This is the
  cascade's own judgement (FR-38), **not** a taxonomy;
- the **`taxonomy` config key** — a `str_list` of the *tenant*'s classification labels, already
  configuration-as-data (FR-30) seeded at provisioning (`config.py` `PROVISIONED_KEYS`). The *vocabulary*
  exists; it is **not yet attached to any pièce**;
- **what 4.5 adds** — a per-*pièce* assignment of **exactly one** member of that taxonomy, or the explicit
  enumerated `unlabelled`, held in a **new append-only ledger** and reversible from it.

FR-40's load-bearing promise (`prd.md:827-836`): *triage is ranking **and** labelling, and this is the
labelling.* A label is a *label*, not a rank — **changing it never moves a pièce or the line** — and a
label change is an ordinary, audited, reversible cell edit that **survives re-ranking marked human-set**;
a **taxonomy change never silently remaps** existing labels.

**IN scope:** (1) a Domain `taxonomy_label.py` — the `unlabelled` sentinel (spine Absent-values
convention `:1354`), a `LabelSource` (`human` used; `machine` reserved), label validation against the
*tenant*'s taxonomy ∪ `{unlabelled}` (loud failure — the "out-of-taxonomy can never leak" guardrail,
`epics.md:421`), and the pure **current-label view** over the ledger (latest entry, else `unlabelled`);
(2) a **new append-only per-pièce ledger** `taxonomy_label_entry` (migration 0026) keyed by
`(tenant, matter, piece_id)`, **version-independent** — one row per assignment or reversal, each carrying
a server-assigned **monotonic seq** (AD-49), actor, timestamp and source; (3) the **one owning use case**
(AD-37) `assign_taxonomy_label` — scope pre-filtered (AD-12/13), validating, appending one ledger entry
**atomic with one audit entry** (AD-22), never overwriting (AD-7); reversal is a **new entry**; (4) reads
— the current label per pièce (a VIEW, never null), the per-pièce change log, and the **SM-19 coverage
figures** (`unlabelled` share; zero-without-a-label; zero-silently-remapped); (5) a `valid=` predicate on
the `taxonomy` config key rejecting blanks and the reserved `unlabelled`; (6) **two structural checks**
(lockstep registry + manifest + README) — the ledger is append-only & single-owner, and the **ranked
order has no dependency on the label axis** (FR-43 / AD-39).

**OUT of scope (do NOT build):** **the line** as a committed ordinal cut (4.8 / FR-17) and the
retained/discarded **views** (4.7 / FR-16) — so "never moves across **the line**" is delivered as "never
changes order / position / version", the crossing act itself being the *pin* (4.11 / FR-43); the **FR-20
editable cell-by-cell table with a live change log** UI and a *generic* multi-column change log (4.10) —
4.5 delivers only the **label axis's** ledger, on the existing audit substrate; a **machine
classifier** that auto-assigns taxonomy labels (`source=machine` is reserved, like 4.4's
`repeated-judgement` signal — no classifier runs in 4.5, so the default state is `unlabelled`, never a
guessed label); the **worklist** surface that lists out-of-taxonomy labels (4.5 emits the *datum* — the
`in_current_taxonomy` flag — that drives it); the *justification* (4.6); any UX surface (needs a UX pass,
like 4.1–4.4). **Do NOT** hardcode the nine French default categories in code — they are adopted **as
data, not as code** (AD-24; `epics.md:425`), supplied at provisioning; and the salvaged
`DEFAULT_LABEL="Autre"` fallback is **dropped** (FR-40 forbids a default label; absence is `unlabelled`).

## Acceptance Criteria

**AC-1 (FR-40 `:832` — exactly one label; no null, no default; the `unlabelled` sentinel).** Every
*pièce* carries **exactly one** taxonomy label: either a member of the *tenant*'s configured `taxonomy`
(FR-30) or the explicit enumerated value **`unlabelled`** where none was assigned. There is **no null and
no default label**. The current label per *pièce* is a **VIEW** — the latest ledger entry, or `unlabelled`
when the ledger holds none — so "exactly one, never null, never two" holds by construction.

**AC-2 (FR-40 `:832` / AD-19 — out-of-taxonomy can never leak; loud validation; the sentinel is
reserved).** Assigning a label that is **not** in the *tenant*'s current taxonomy ∪ `{unlabelled}` **fails
loudly and writes nothing** (the "out-of-taxonomy labels can never leak" acceptance floor,
`epics.md:421`). The `unlabelled` sentinel is **reserved**: a `valid=` predicate on the `taxonomy`
`ConfigKey` rejects a taxonomy that contains `unlabelled` or a blank/empty label, so the sentinel can
never collide with a real category.

**AC-3 (FR-40 `:833` / FR-43 / AD-39 — a label never moves a pièce or the line).** The taxonomy label is
**not an input to the ranked order**: it is absent from `RankingIdentity` and from `rank_cascade`, and the
ranked-order module has **no dependency** on the label axis. Assigning or changing a label leaves the
ranked order and the *ranking version* `fingerprint` **byte-identical**. (Because the label is not an
ordering input and **the line** — Story 4.8 — is an ordinal cut over that unchanged order, a label cannot
move a *pièce* across it; the crossing act is the *pin*, Story 4.11.) Enforced by a **structural check**
(the ranking module imports/reads nothing from the label axis) and a **behavioural invariance test**.

**AC-4 (FR-40 `:834` / FR-20 / AD-7 / AD-22 / AD-37 / AD-49 — an ordinary cell edit: change-log entry,
reversible).** A label assignment is an **append-only change-log entry** written through **one owning use
case** (AD-37): it records the *pièce*, the label, the actor, a **server-assigned monotonic sequence**
(AD-49) and a timestamp, and that it is **human-set**; it is **atomic with an audit entry** (AD-22); it
**never overwrites** (AD-7) — a change and its reversal are **both new entries**. The label is
**reversible from the change log** (a reversal appends a prior value). A write whose precondition no
longer holds (the observed seq moved) **fails loudly**, never silently no-ops (AD-37 conditional commit).

**AC-5 (FR-40 `:834` / AD-23 — survives re-ranking marked human-set).** Because the ledger is keyed by
*pièce* and is **version-independent**, re-ranking (a new *ranking version*, Story 4.3) **does not touch
labels**: a human-set label **persists across ranking versions** and stays marked `human`. A future
machine-classification path (`source=machine`, reserved here) must not overwrite a human-set entry; no
classifier exists in 4.5, so the invariant holds by construction and is asserted by test.

**AC-6 (FR-40 `:835` / SM-19 / AD-24 / AD-25 — a taxonomy change never silently remaps).** Changing the
*tenant*'s taxonomy (only through the one audited AD-25 surface — `set_config`) **touches only the config
row**; it does **not** invalidate, remap or null any existing label. A *pièce* whose current label is no
longer in the taxonomy **keeps that label** and is surfaced as **out-of-current-taxonomy** (the datum that
drives the FR-40 `:835` *worklist* line; the worklist surface itself is later). **Nothing is silently
remapped** (SM-19 target: zero).

**AC-7 (SM-19 — the measurable figures + the static gate).** A scope-pre-filtered read reports SM-19's
per-*matter* figures over the *pièces* of a ranking: **zero without exactly one label** (structural), the
**`unlabelled` share**, and the **out-of-current-taxonomy count** (the zero-silently-remapped evidence). A
new structural check asserts the label ledger is **append-only & single-owner**, and a second check
asserts the **ranked order ignores the label axis**; both are registered in the check **registry +
manifest + README** (lockstep) and each has a **failure-path fixture that actually fires**. The
`no_model_reported_confidence`/gold gates (AD-34) stay green.

## Tasks / Subtasks

- [x] **Task 1 — Domain: the label vocabulary, the sentinel, validation, the current-label view (AC-1,
  AC-2, AC-5)**
  - [x] Create `apx/core/domain/taxonomy_label.py`: `UNLABELLED = "unlabelled"`; `LabelSource(StrEnum)`
    with `HUMAN = "human"` used and `MACHINE = "machine"` **reserved** (documented, never emitted in 4.5,
    mirroring 4.4's reserved `REPEATED_JUDGEMENT`).
  - [x] `validate_label(label: str, taxonomy: Sequence[str]) -> str` — returns the label iff it is
    `UNLABELLED` or a member of `taxonomy`; else raises a loud `OutOfTaxonomyLabel` (AD-19). Reject a
    blank/whitespace label.
  - [x] A frozen `LabelEntry` domain value (piece_id, seq, label, source) and a pure
    `current_label(entries: Iterable[LabelEntry]) -> LabelView` returning `(label, source, seq)` = the
    max-seq entry, or `(UNLABELLED, None, None)` when empty — **never null**. Add `is_member(label,
    taxonomy) -> bool` for the out-of-current-taxonomy datum (AC-6). (The actor + timestamp of a label
    edit live on the store's `LabelChangeEntry` DTO, not on this pure Domain value.)
  - [x] Unit tests `tests/domain/test_taxonomy_label.py`: exactly-one/never-null view; `unlabelled` when
    empty; out-of-taxonomy raises; blank raises; `unlabelled` always valid; `current_label` picks max seq.

- [x] **Task 2 — Config: reserve the sentinel, forbid blanks on the `taxonomy` key (AC-2)**
  - [x] Add a `valid=` predicate to the `taxonomy` `ConfigKey` in `apx/core/domain/config.py`: every
    member is a non-blank string and **no member equals `UNLABELLED`**. Keep default `[]` and the
    provisioning seam unchanged.
  - [x] Verify the README `<!-- config-keys -->` block still matches (`configuration.py` diffs by key +
    default; adding `valid` must not desync it) — update only if the block records predicates.
  - [x] Tests: `coerce("taxonomy", [...])` rejects `["unlabelled"]` and `["", " "]`, accepts a real list.

- [x] **Task 3 — Persistence: the append-only ledger + migration 0026 (AC-1, AC-4, AC-5)**
  - [x] Add `TaxonomyLabelEntry` ORM model → table `taxonomy_label_entry` in
    `apx/adapters/store_postgres/models.py`: `id` (PK, sha256(piece_id \0 seq)), `tenant`, `matter`,
    `piece_id`, `seq` (Integer, monotonic per pièce), `label` (String — a taxonomy member or
    `unlabelled`), `source` (String — `human`/`machine`), `set_by` (**EncryptedText**, AD-31), `at`
    (DateTime(tz)). `UniqueConstraint(piece_id, seq)`; composite FK `(tenant, matter) → matter_scope`
    **no ondelete** (AD-7 RESTRICT); index on `(tenant, matter, piece_id)`.
  - [x] Migration `0026_taxonomy_label_entry.py`, `down_revision = "0025_ranked_entry_confidence"`,
    revision = full filename stem; create the table, **no backfill**.
  - [x] Allowlist the plaintext columns in `apx/checks/encryption.py` (label/source/seq/piece_id/etc. are
    non-content, like `band`/`rejection_class`); `set_by` is EncryptedText and needs none.
  - [x] Migration test `tests/adapters/test_taxonomy_label_migration.py` (Alembic Operations on SQLite,
    load by path — filename starts with a digit).

- [x] **Task 4 — The owning use case + reads: assign, revert, current label, change log, coverage (AC-1,
  AC-4, AC-6, AC-7)**
  - [x] Port `apx/core/ports/taxonomy_label.py`: `TaxonomyLabelRecorder` Protocol
    (`assign_label(*, tenant, matter, actor, piece_id, label, scopes, expected_seq=None) -> int` and
    `revert_label(*, ..., to_seq, scopes) -> int` — both return the new change-log `seq`). `SqlStore`
    satisfies it structurally, so the API depends on the core port, never the adapter (AD-4).
  - [x] App use case `apx/core/app/label.py::assign_taxonomy_label(recorder, ...)` /
    `revert_taxonomy_label(recorder, ...)` — the thin core seam that forwards to the recorder port;
    the recorder (the store) owns validation, the monotonic seq, the conditional commit and the
    atomic audit (the guarantee lives at the one write choke point, AD-37).
  - [x] `SqlStore.assign_label` (mirror `save_labels`/`record_ranking`): scope-check via `_matter_held`
    (non-disclosing 404, AD-12/13); mint `seq = (max seq for pièce)+1` **inside the tx** (AD-49); **conditional
    commit** on `expected_seq` when supplied (AD-37, `StaleLabel` on mismatch); insert one
    `TaxonomyLabelEntry` + one `_append_audit(... "piece_labelled" ...)` **atomic** (AD-22); never UPDATE.
  - [x] Reads (scope pre-filtered): `current_label(piece_id, ...)` → `(label, source, seq,
    in_current_taxonomy)`; `label_change_log(piece_id, ...)` → entries asc by seq; `label_coverage(matter,
    ...)` → SM-19 figures (total, labelled, `unlabelled` share, out_of_taxonomy count) over the latest
    ranking's pièces.
  - [x] Tests `tests/adapters/test_taxonomy_label_store.py`: assign happy path + audit written; reject
    out-of-taxonomy (nothing written); reversal is a new entry & restores value; `StaleLabel` on
    conditional-commit mismatch; scope isolation (non-disclosing 404); coverage figures.

- [x] **Task 5 — Invariance: a label never moves a pièce, the version, or across re-ranking (AC-3, AC-5,
  AC-6)**
  - [x] Behavioural test `tests/app/test_label_does_not_move_ranking.py`: record a ranking; assign/change
    a label; the ranked order **and** the `fingerprint`/`version_id` are byte-identical.
  - [x] Test: record ranking v1 → assign human label to pièce P → record ranking v2 (re-rank) → P's
    current label is still the human-set value, `source=human` (AC-5).
  - [x] Test: assign label X → remove X from the taxonomy via `set_config` → P's current label is still X
    with `in_current_taxonomy=False`; **nothing remapped/nulled**; the label ledger untouched (AC-6).

- [x] **Task 6 — Structural checks (lockstep) + registration (AC-3, AC-7)**
  - [x] `apx/checks/taxonomy_label_ownership.py::taxonomy_label_is_append_only` (FR-40 / AD-7, AD-37) —
    mirror `case_theory_ownership.py`/`ranking_ownership.py`: `TaxonomyLabelEntry` constructed only under
    `adapters/store_postgres`; no `UPDATE/DELETE taxonomy_label_entry`; no in-place attribute mutation of
    a loaded instance.
  - [x] `apx/checks/label_not_a_ranking_input.py::ranking_order_ignores_the_taxonomy_label` (FR-40 / FR-43
    / AD-39) — assert `apx/core/domain/ranking.py` (and the rank path) has **no import/reference** to the
    `taxonomy_label` module/table (the label provably cannot be an ordering input).
  - [x] Register **both** in `apx/checks/registry.py` (`CHECKS` + import) + `apx/checks/manifest.py`
    (`PROPERTY_MANIFEST` via `_p`) + `README.md` `<!-- structural-properties -->` block. Verify the
    meta-checks (`manifest_matches_readme`, `every_registered_check_is_in_the_manifest`, …) stay green.
  - [x] Failure-path fixtures `tests/checks/test_taxonomy_label_ownership.py` +
    `tests/checks/test_label_not_a_ranking_input.py` — each fires on a synthetic violation and passes on
    the real tree.

- [x] **Task 7 — Gate + close**
  - [x] `ruff check` clean (line-length 100 — accented category names risk E501); import-linter 3/0
    (core imports no adapter / no LLM SDK); full pytest green incl. the new checks; the gold gate (AD-34)
    stays green.
  - [x] Update the Change Log; fill Dev Agent Record (File List, Completion Notes).

## Dev Notes

### The load-bearing design decision — the label is a version-independent, append-only, per-*pièce* ledger

The three hard invariants of FR-40 all fall out of **one** structural choice: the taxonomy label lives in
its **own append-only ledger keyed by `(tenant, matter, piece_id)`, not on `ranked_entry` and not keyed
by any *ranking version*.**

- **"Never moves a pièce or the line" (FR-40 `:833`, AD-39 `:1110-1115`)** — the label is not on the
  ranking order at all; `rank_cascade`/`RankingIdentity` never read it. This is the AD-39 companion:
  sets/positions move only by order change, line move, or *pin* — never by a label.
- **"Survives re-ranking marked human-set" (FR-40 `:834`, AD-23)** — because the ledger is
  version-independent, a new *ranking version* simply doesn't touch it; the human's label persists
  automatically. (Contrast the relevance `LabelRecord`, which `session.merge`-overwrites in place — that
  design is wrong for taxonomy, which needs append-only history + reversibility.)
- **"Reversible from the change log" (FR-40 `:834`, AD-7 `:237-248`, FR-20 `:547`)** — AD-7 names *the
  change log* as an append-only ledger; a change and its reversal are **both new entries**, so reversal
  is replay, never a destructive undo. The `ranking_ownership` check already **blocks** any in-place
  mutation of ranking rows, which is exactly why the label must be its own append-only table (a
  `entry.label = …` on a loaded row would fail the append-only check) — the check *validates* this shape.

The `taxonomy_label_entry` table **is** the change log for the label axis. Story 4.10 (FR-20) adds the
*editable cell-by-cell table* UI and generalises the change log across columns; 4.5 delivers the label
column's ledger on the **already-present** audit substrate (U8) — do not build the 4.10 surface.

### The seq is server-assigned and monotonic (AD-49 / FR-20 `:549`)

Mint `seq` inside the transaction as `(max seq for that pièce) + 1`, exactly as `record_ranking` mints
`version_no` and `_append_audit` mints the audit `seq`. Ordering and staleness use this monotonic value,
never a workstation clock. The **conditional commit** (AD-37 `:1043-1052`): a caller may pass the
`expected_seq` it observed; if the ledger moved, the write **fails loudly** (`StaleLabel`) — it never
overwrites and never silently no-ops.

### The `unlabelled` sentinel — absence is an explicit enumerated value (spine `:1354`, FR-40 `:832`)

`unlabelled` joins the spine's Absent-values family (`custodian-undeclared`, **`unlabelled`**,
`date-undetermined`, cardinality `unknown`). It is **never null and never a default category**. The
current-label view returns `unlabelled` when the ledger is empty. The sentinel is **reserved** — the
`taxonomy` config `valid=` predicate forbids a tenant from configuring it as a real label.

### The nine default categories — adopt as DATA, drop the `Autre` default (AD-24; `epics.md:425`; OQ-16)

The salvaged v1 `domain/classification/labels.py` (nine flat French legal categories: *Contrats,
Jurisprudence, Doctrine, Pièces de procédure, Correspondance, Pièces comptables, Réglementaire, Note
juridique, Autre*) is adopted **"as the default taxonomy row set, not as code"**. **Do NOT** hardcode
them in `core/` (AD-24: no configured vocabulary in source; and shipping the v1 set unexamined is exactly
OQ-16's caution). They are supplied at provisioning as data; 4.5's mechanism is correct even with an
empty taxonomy (every pièce is then `unlabelled`, which is valid). **Critically, drop the salvage file's
`DEFAULT_LABEL = "Autre"` fallback** — FR-40 `:832` forbids a default label; a *pièce* the (future) model
cannot place is `unlabelled`, not "Autre".

### Existing seams to reuse (do not reinvent)

- Config-as-data: `TenantSetting` `(tenant, key)` JSON rows; the `taxonomy` `ConfigKey` (`config.py`);
  `set_config`/`_apply_config_change` (the one AD-25 audited write path); `provision_tenant`
  (`store.py:2389`) already seeds `taxonomy`.
- Audit (AD-22): `_append_audit(session, tenant, matter, actor, action, detail, ts)` inside the caller's
  tx; `_audited_tx` wrapper with `(tenant, seq)` retry. Action strings are plaintext (`"ranking_recorded"`,
  `"judge"`); use `"piece_labelled"`.
- Scope pre-filter (AD-12/13): `_matter_held(...)` → non-disclosing 404, as in the ranking reads.
- Ownership-check template: `case_theory_ownership.py` / `ranking_ownership.py` (`_iter_py`/`_parse`/AST
  walk, `CheckResult`, `_fail_closed`, `run()`); registration lockstep documented below.
- Migration-by-digit-filename: load via `importlib.util.spec_from_file_location` (path derived from
  `store_postgres.__file__`), as `0024`/`0025` tests do.

### Structural-check registration — the lockstep sites

Add each new check in **three** places (meta-checks fail the build on drift): (1) import + append to
`CHECKS` in `apx/checks/registry.py`; (2) a `_p(key, fr, ad, name, check, inspects)` row in
`apx/checks/manifest.py` `PROPERTY_MANIFEST` (the `check` is the **callable**); (3) a matching row in the
`README.md` `<!-- structural-properties -->` block (columns `key | FR | AD | verb | check-fn | inspects`).
No config-keys-block change is expected (the `taxonomy` key's presence/default are unchanged) — verify.

### Test / lint conventions (house rules)

uv-managed venv (`.venv/bin/ruff`, `.venv/bin/python`; no pip). `ruff check` (line-length 100) is the
gate — **not** `ruff format`. Run pytest with `export PATH="$PWD/.venv/bin:$PATH"`; **never export
`DATABASE_URL`** (tests set their own SQLite). Accented category names (*pièce*, *procédure*, *é*, *→*,
*≥*) push lines over 100 — keep comments short and reflow **by hand** (the E501 auto-reflow corrupts code
lines with trailing comments).

### Project Structure Notes

- New: `apx/core/domain/taxonomy_label.py`, `apx/core/ports/taxonomy_label.py`, `apx/core/app/label.py`,
  `apx/adapters/store_postgres/migrations/versions/0026_taxonomy_label_entry.py`,
  `apx/checks/taxonomy_label_ownership.py`, `apx/checks/label_not_a_ranking_input.py`, and their tests.
- Modified: `apx/core/domain/config.py` (taxonomy `valid=`), `apx/adapters/store_postgres/models.py`
  (`TaxonomyLabelEntry`), `apx/adapters/store_postgres/store.py` (`assign_label` + reads + `StaleLabel`),
  `apx/checks/encryption.py` (allowlist), `apx/checks/registry.py`, `apx/checks/manifest.py`, `README.md`.
- No change to `ranking.py`/`rank.py`/`ranked_entry` — the orthogonality is the point (AC-3).

### References

- [Source: prd.md#FR-40] `:827-836` — the four consequences; `:1354` Absent-values (`unlabelled`); `:1260`
  SM-19; `:1552` OQ-16 (label accuracy unmeasured; nine categories unvalidated).
- [Source: prd.md#FR-30/FR-50] configuration-as-data; the one audited provisioning/settings surface.
- [Source: prd.md#FR-20] `:547-549` the change log — append-only, server-assigned monotonic sequence.
- [Source: ARCHITECTURE-SPINE.md] AD-24 `:699-716`, AD-25 `:718-731`, AD-7 `:226-258`, AD-22 `:633-654`,
  AD-37 `:1029-1074`, AD-39 `:1101-1115`, AD-49 `:1328-1342`, AD-23 `:656-697`; Consistency Conventions
  `:1348-1361`.
- [Source: WORK-BREAKDOWN.md] U15 delivers FR-40 with FR-16/17/39/43 (labelling built with the line/pin at
  unit level; the BMAD epic split them — 4.5 ahead of 4.7/4.8/4.11); U16 (depends on U15) delivers the
  FR-20 editable-cell-table UI; U8 (the audit ledger substrate) is present.
- [Source: epics.md] Story 4.5 `:1154-1166`; the acceptance floor & nine-categories salvage `:421`, `:425`.

## Dev Agent Record

### Agent Model Used

claude-opus-4-8 (Opus 4.8, 1M context)

### Debug Log References

- Full gate green: `ruff check` clean · 64 structural checks pass (incl. the 2 new + all meta-checks
  lockstep) · import-linter 3/0 · **1130 passed / 12 skipped**.
- One regression caught + fixed: the key-rotation registry `ENCRYPTED_COLUMNS` (backfill.py) must
  list every `EncryptedText` column — `taxonomy_label_entry.set_by` was added (single-PK `id`, so a
  rotation addresses it directly). A rotation would otherwise have silently skipped it (durability
  bug). `test_rekey_covers_every_encrypted_column` re-green.

### Completion Notes List

- **The load-bearing choice:** the taxonomy label lives in its OWN append-only ledger
  (`taxonomy_label_entry`) keyed by `(tenant, matter, piece_id)`, **version-independent** — not on
  `ranked_entry`. This makes FR-40's three hard invariants structural rather than promised:
  "never moves a pièce/the line" (the label is not an ordering input — a new check proves
  `ranking.py`/`rank.py` have no dependency on the label axis), "survives re-ranking marked
  human-set" (re-ranking never touches the pièce-keyed ledger), "reversible from the change log"
  (append-only — a reversal is a new entry). The existing `ranking_ownership` check would have
  blocked any in-place mutation of `ranked_entry`, which validated the separate-table choice.
- **The current label is a VIEW** (`current_label` — the max-`seq` entry, else `unlabelled`), never
  null, never a default (AD-19). `unlabelled` joins the spine Absent-values family; the `taxonomy`
  config `valid=` predicate reserves it (and rejects blanks), so a real category can't collide.
- **Out-of-taxonomy can never leak:** validated at the single write choke point
  (`_append_label_entry` → `validate_label`) on BOTH `assign_label` and `revert_label`, so a
  reversion cannot re-introduce a category the taxonomy has since dropped.
- **The hexagonal seam (`core/ports/taxonomy_label.py` + `core/app/label.py`).** Initially I built
  the write path store-only (the `save_labels` precedent) and deferred the port. The adversarial
  review CONFIRMED that skipping it diverged from the `RankingRecorder`/`produce_ranking` sibling
  (4.3) the story promised to mirror, and would force a future consumer to import the adapter
  (violating AD-4). So the port `TaxonomyLabelRecorder` (`assign_label`/`revert_label` → the new
  `seq`) + the thin core seam `assign_taxonomy_label`/`revert_taxonomy_label` were added: `SqlStore`
  satisfies the Protocol structurally, so the API/UI depends on **core**, never the adapter. The
  **guarantee still lives at the one store choke point** (`_append_label_entry` → `validate_label`,
  the monotonic seq, the conditional commit, the atomic audit) — the seam only forwards, so there is
  no second writer (AD-37 preserved). Reads stay on the store, named `read_current_label` /
  `read_label_change_log` / `read_label_coverage` (house `read_*` convention).
- **SM-19** is exposed as `read_label_coverage` (per-matter figures over the latest ranking's pièces:
  `without_label` == 0 by construction, the `unlabelled` share, and the out-of-current-taxonomy
  count) — the runtime reporting figures, no gold corpus needed.
- **Deferred / reserved:** the line (4.7/4.8), the pin (4.11), the FR-20 editable-cell-table +
  generic change log (4.10), a machine classifier (`LabelSource.MACHINE` reserved, never emitted —
  mirroring 4.4's reserved `repeated-judgement` signal). The nine French default categories are NOT
  hardcoded (data, not code — AD-24); the salvage `DEFAULT_LABEL="Autre"` fallback is dropped
  (FR-40 forbids a default label).

### File List

**Created:** `apx/core/domain/taxonomy_label.py` · `apx/core/ports/taxonomy_label.py` ·
`apx/core/app/label.py` ·
`apx/adapters/store_postgres/migrations/versions/0026_taxonomy_label_entry.py` ·
`apx/checks/taxonomy_label_ownership.py` · `apx/checks/label_not_a_ranking_input.py` ·
`tests/domain/test_taxonomy_label.py` · `tests/domain/test_config_taxonomy.py` ·
`tests/adapters/test_taxonomy_label_migration.py` · `tests/adapters/test_taxonomy_label_store.py` ·
`tests/app/test_label_does_not_move_ranking.py` · `tests/app/test_label_use_case.py` ·
`tests/checks/test_taxonomy_label_ownership.py` · `tests/checks/test_label_not_a_ranking_input.py`

**Modified:** `apx/core/domain/config.py` · `apx/adapters/store_postgres/models.py` ·
`apx/adapters/store_postgres/store.py` · `apx/adapters/store_postgres/backfill.py` ·
`apx/checks/encryption.py` · `apx/checks/registry.py` · `apx/checks/manifest.py` · `README.md` ·
`_bmad-output/implementation-artifacts/sprint-status.yaml`

## Senior Developer Review (AI)

**Date:** 2026-08-05 · **Outcome:** Changes Requested → applied. Adversarial Workflow review, 3
parallel lenses (correctness · security/isolation · architecture/scope) → each finding independently
skeptic-verified (default REFUTED). Result: **2 findings → 1 CONFIRMED (fixed) / 1 REFUTED**. The
correctness and security lenses found **zero** defects; both findings came from the architecture lens
and concerned the same drift — the drafted Tasks over-claimed deliverables the leaner code did not
build. Integrity manifest verified: the review mutated no code file (all 19 snapshotted files
byte-identical).

**Action Items:**

- [x] **[Confirmed · med] The named owning use-case + port for label writes did not exist** — Task 4
  marked `core/ports/taxonomy_label.py` + `core/app/label.py` `[x]` but the write path was store-only,
  diverging from the `RankingRecorder`/`produce_ranking` sibling (4.3) and leaving a future consumer
  no core-side contract (AD-4). **Fix:** built the port `TaxonomyLabelRecorder` (`assign_label` /
  `revert_label` → the new `seq`) + the thin core seam `assign_taxonomy_label` /
  `revert_taxonomy_label`; `SqlStore` satisfies the Protocol structurally; the guarantee stays at the
  one store choke point (no second writer). Added `tests/app/test_label_use_case.py` (forwarding +
  a real-store end-to-end proof the store satisfies the port).
- [x] **[Refuted · low] Domain `LabelEntry` fields / `in_taxonomy` naming drift** — the story's Task-1
  wording claimed a `LabelEntry(…, actor, at)` and an `in_taxonomy()` helper; the actual (cleaner)
  code carries `LabelEntry(piece_id, seq, label, source)` (actor/at live on the store's DTO) and names
  the helper `is_member`. Refuted as documentation-only (no runtime path). **Addressed anyway**
  (convergent honesty): reconciled the Task-1 wording with the delivered code.

## Change Log

| Date       | Version | Description                                   | Author |
| ---------- | ------- | --------------------------------------------- | ------ |
| 2026-08-05 | 0.1     | Story drafted (create-story)                  | Claude |
| 2026-08-05 | 0.2     | Implemented (dev-story) — gate green          | Claude |
| 2026-08-05 | 0.3     | Adversarial review: 1 confirmed → fixed (port + use-case seam added) | Claude |
