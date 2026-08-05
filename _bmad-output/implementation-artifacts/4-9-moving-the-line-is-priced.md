---
baseline_commit: a3ca6b8
---

# Story 4.9: Moving the line is priced

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a lawyer deciding how much to read,
I want to see the cost and the benefit of moving **the line** before I move it, honestly labelled,
so that the recall/precision trade-off is a dial I control with a price shown, not a hidden default.

## Scope note — 4.9 OWNS the priced PROJECTION + the serialised human move; the line ledger exists

Story 4.8 (committed `a3ca6b8`) built the append-only, version-bound `line_placement` ledger
(`place_line` for the system recommendation, `read_current_line` for the view). Story 4.9 adds the
**human move** and its **price**: when a user considers a candidate line position, the interface
states **Δ pièces-to-read** and the **change in the estimated prevalence of relevant material in the
resulting discarded set** — a **projection from the ranking**, labelled as such, that must **never**
read as a sampling bound and must **never** be worded as a "risk of having missed a relevant
document" (FR-19, §0.2). The move itself is **serialised** (a move against a superseded line is
refused) and **audited with the priced statement that was shown**.

**The single most dangerous invariant here (FR-19/§0.2):** a *projection from the ranking* and a
*confidence bound from a completed sampling run* (Epic 5) are **different kinds of statement** and
are **never shown in the same visual register**. The projection is a model estimate where **nothing
has been sampled**; the bound is a hypergeometric statement from a **completed** random sample
(`apx/core/domain/confidence.py::prevalence_upper_bound`). Story 4.9 must keep them structurally
apart — the projection **never** uses the sampling-bound estimator.

**IN scope:**
1. A pure Domain `apx/core/domain/line_projection.py` — the ranking prevalence projection:
   `piece_relevance_projection(band, confidence) -> float | None` (P(relevant) per pièce, reusing the
   directional conversion the SM-17 confidence calibration already fixed: **relevant band → P=c,
   discard band → P=1−c**, uncertain → 0.5, no observable → None); `project_discarded_prevalence` (the
   mean over the projectable discarded pièces, `None` when none is projectable); a `PricedMove` value
   object; and `price_line_move(order, current_line, candidate_line) -> PricedMove` (pure). A named
   `PROJECTION_METHOD` constant (the method is named in the interface + reproducible from the audit).
2. The **SM-17 calibration gate for the projection** — a harness (extending `eval/harness.py`) that
   flags a **systematically OPTIMISTIC** projection (projected prevalence systematically **below** the
   observed relevant share — the dangerous direction: claiming the discarded set is cleaner than it
   is), with a build-gate test. (The full gold-corpus run defers, like `recall_at_the_line` /
   `confidence_calibration`; the MATH is exercised now.)
3. Store `price_line_move(...)` — a scope-pre-filtered, **non-disclosing**, **not-audited** preview:
   reads the ranked order + per-pièce `band`/`confidence`, resolves the **current** line (the ledger's
   current placement, else the system recommendation) and the **candidate** line (the passed pièce),
   and returns the `PricedMove`. Edge cases: retain-everything → **discarded set empty, no bound
   applies** (never a prevalence of 0%); projection unavailable → **counts-only** (Δ pièces-to-read
   still shown, prevalence flagged unavailable); candidate pièce not in the order → loud failure.
4. Store `move_line(...)` — the human move: append a `LinePlacement` at the chosen pièce (append-only,
   reusing 4.8's ledger), **CONDITIONAL on `expected_seq`** (a move against a superseded line raises
   `StaleLine` with the current position — the serialised-move concurrency rule, FR-19), **atomic**
   with one `line_moved` audit entry recording **old position, new position, author, ranking version
   and the priced statement that was shown** (FR-19). The order is never reordered.
5. Extend the **core port + use-case seam** (`core/ports/line.py` + `core/app/line.py`) with
   `price_line_move` + `move_line` (AD-4).
6. A **structural check** `line_projection_is_not_a_sampling_bound` — the FR-19 projection module (and
   the price path) never imports/calls `prevalence_upper_bound` (the hypergeometric sampling bound),
   so a projection can never be computed by the bound estimator (FR-19/§0.2). Registered in the
   lockstep (registry + manifest + README).

**OUT of scope (do NOT build):** the **sampling run**, the **confidence bound**, the hypergeometric
estimator and its OQ-4 simulation gate (Epic 5) — 4.9 only stays structurally APART from them; the
**pin** (4.11); the **editable table / change-log UI** and any surface (the UX contract is
`EXPERIENCE-EPIC4.md`, but this story is backend + structural); the priced statement's on-screen
rendering (the store returns the numbers + the availability flags; the sentence is composed at the
edge). Do NOT wire the projection into the ranking-version record beyond naming its method (the
scores it needs are already in `ranking_version.identity_json`, FR-39).

## Acceptance Criteria

**AC-1** — **Given** a user repositioning the line, **When** she considers a candidate position,
**Then** the interface can state, for that position: the **change in the number of pièces to read**,
and the **change in the estimated prevalence of relevant material in the resulting discarded set** —
in the form "400 more pièces to read; the estimated share of the discarded set that is relevant falls
from about 3% to about 0.4%". It **never** states a "risk of having missed a relevant document"
(FR-19, §0.2 — the store returns Δ counts + both prevalences; the barred phrasing is not producible
because no such quantity is computed).
- *Testable:* `price_line_move` returns `pieces_to_read_delta` and `current_prevalence` /
  `candidate_prevalence` (each a float or None); moving down increases pièces-to-read and lowers the
  candidate discarded-prevalence vs the current.

**AC-2 (projection, not a bound)** — The priced figure is a **projection from the ranking**, never a
sampling bound: it is a model estimate where nothing has been sampled, computed by
`PROJECTION_METHOD`, and it is **structurally impossible** for the projection to be the hypergeometric
bound (`line_projection` never calls `prevalence_upper_bound`; asserted by
`line_projection_is_not_a_sampling_bound`).

**AC-3 (calibration, SM-17)** — The projection is calibration-tested: a **systematically optimistic**
projection (projected prevalence systematically below the observed relevant share) fails the build.
- *Testable:* the projection-calibration harness flags an optimistic projection and passes a
  well-calibrated one.

**AC-4 (retain-everything edge)** — Moving the line to retain everything states the **discarded set is
empty and no bound applies** — it **never** reports a prevalence of 0%.
- *Testable:* `price_line_move` with a candidate that retains all pièces returns `discarded_empty=True`
  and `candidate_prevalence=None` (not 0.0).

**AC-5 (failure path — counts-only)** — Where the prevalence projection cannot be produced (no
projectable discarded pièce), the move **still shows the change in pièces to read**, and says the
prevalence projection is **unavailable** rather than inventing one.
- *Testable:* a discarded set with no projectable pièce → `pieces_to_read_delta` present,
  `prevalence_available=False`, `candidate_prevalence=None`.

**AC-6 (the serialised move + audit)** — The line is a single per-matter parameter: a move is
serialised — a move made against a **superseded** position is **refused** with the current position
shown (`StaleLine`) — and every move is recorded in the audit with **old position, new position,
author, ranking version and the priced statement that was shown**. The move never reorders the order.
- *Testable:* `move_line(expected_seq=stale)` raises `StaleLine`; a fresh move appends a placement,
  writes one `line_moved` audit entry carrying the priced statement, and leaves `read_ranked_order`
  byte-identical.

## Tasks / Subtasks

- [x] **Task 1 — Domain: the ranking prevalence projection** (AC: 1, 2, 4, 5)
  - [x] Create `apx/core/domain/line_projection.py`. `piece_relevance_projection(band: str | None,
        confidence: float | None) -> float | None`: **confident-relevant → confidence**,
        **confident-discard → 1 − confidence**, **uncertain → 0.5**, band None or confidence None →
        None (no observable — excluded from the mean, AD-19). (Import `Band` from
        `apx.core.domain.cascade`; the directional conversion matches
        `tests/eval/test_confidence_calibration.py`.)
  - [x] `project_discarded_prevalence(probs: Sequence[float]) -> float | None`: the arithmetic mean;
        `None` for an empty input (no projectable pièce — the AC-5 unavailable signal).
  - [x] Frozen `PricedMove(pieces_to_read_delta: int, current_prevalence: float | None,
        candidate_prevalence: float | None, discarded_empty: bool, prevalence_available: bool)`.
  - [x] `price_line_move(order: Sequence[tuple[str, str | None, float | None]], current_line: Line |
        None, candidate_line: Line | None) -> PricedMove`: `order` is `(piece_id, band, confidence)`
        in rank order (ranked pièces only). Retained(line) = up to & incl. last_retained; discarded =
        below. `pieces_to_read_delta = len(retained(candidate)) − len(retained(current))`. Prevalences
        = `project_discarded_prevalence` over each discarded set's projectable P(relevant).
        `discarded_empty` = candidate retains all; `prevalence_available` = candidate prevalence
        computable (and not discarded_empty). A `Line` naming a pièce not in the order fails loudly.
  - [x] `PROJECTION_METHOD = "ranking-prevalence-projection-v1"` (named in the audit + interface).
  - [x] Tests `tests/domain/test_line_projection.py`: the directional conversion; the mean; moving
        down raises pièces-to-read and lowers candidate prevalence; retain-everything →
        discarded_empty + None (never 0.0); no projectable → unavailable + None; a pièce-not-in-order
        fails loudly.

- [x] **Task 2 — SM-17 calibration gate for the projection** (AC: 3)
  - [x] Extend `eval/harness.py` with `projection_calibration(bands: dict[str, tuple[float, int,
        int]], *, tolerance=…) -> …` mirroring `confidence_calibration`, but flagging
        `systematically_optimistic` = projected prevalence systematically **below** observed relevant
        share (the dangerous direction). Reuse the input contract (claimed P(relevant), relevant
        count, total).
  - [x] Tests `tests/eval/test_projection_calibration.py`: a well-calibrated projection is not
        flagged; a systematically optimistic one IS flagged; a degenerate observation is rejected.

- [x] **Task 3 — Store: the priced preview** (AC: 1, 4, 5) — AD-13
  - [x] `price_line_move(*, tenant, matter, scopes, candidate_last_retained_piece_id, version_no=None)
        -> PricedMove | None`: scope-check (None when out of scope/absent/no ranking — non-disclosing);
        resolve the version; read `(piece_id, rank, band, confidence)` for ranked rows in rank order;
        resolve the **current** line (`read_current_line` placement, else `recommend_line`); build the
        candidate `Line(candidate_last_retained_piece_id)`; call `price_line_move`. **Not audited** (a
        preview).
  - [x] Tests `tests/adapters/test_line_move_store.py` (part 1): the preview against a seeded ranking
        (Δ pièces + both prevalences); retain-everything edge; the counts-only failure path;
        scope-gated non-disclosing.

- [x] **Task 4 — Store: the serialised human move + audit** (AC: 6) — AD-7/AD-22/AD-37/AD-49
  - [x] Add `StaleLine(Exception)` (mirror `StaleLabel`). `move_line(*, tenant, matter, actor,
        scopes, last_retained_piece_id, expected_seq, priced_statement, version_no=None) ->
        LinePlacementView` inside `_audited_tx`: scope-check; resolve the version; **validate the
        candidate pièce is in the version's ranked order** (loud `ValueError` otherwise); read the
        current max-`seq`; if `expected_seq != current_max` raise `StaleLine` (the serialised rule —
        nothing written); append a `LinePlacement` at the chosen pièce (basis inherited from the
        version via `_line_basis`, `seq = max+1`) **atomic** with one `line_moved` audit entry
        carrying `old=<current last_retained>` / `new=<chosen>` / `version` / the `priced_statement`
        shown. Return the new `LinePlacementView`. Touches only `line_placement` (never
        `ranked_entry`).
  - [x] Tests (part 2): a fresh move appends (seq+1) + one `line_moved` audit carrying the priced
        statement; a stale `expected_seq` raises `StaleLine` (nothing written); the order is
        byte-identical before/after; a candidate not in the order fails loudly.

- [x] **Task 5 — Core port + use-case seam** (AC: 1, 6) — AD-4
  - [x] Extend `core/ports/line.py::LinePlacementRecorder` with `price_line_move(...) -> PricedMove |
        None` and `move_line(...) -> LinePlacementView`. (Import `PricedMove` from
        `core/domain/line_projection.py`.)
  - [x] Extend `core/app/line.py` with thin `price_line_move` / `move_line` forwarders.
  - [x] Tests `tests/app/test_line_use_case.py` (extend): the two new seams forward to a fake recorder.

- [x] **Task 6 — Structural check: the projection is never the sampling bound** (AC: 2) — AD-33
  - [x] `apx/checks/line_projection_not_a_bound.py` (NEW): `line_projection_is_not_a_sampling_bound` —
        the FR-19 projection **module** `core/domain/line_projection.py` (where ALL the prevalence math
        lives; the store's price path only *delegates* to it) never imports or calls
        `prevalence_upper_bound` (the hypergeometric sampling bound). The store is deliberately NOT
        scanned: it legitimately imports the bound for the separate Epic-5 `record_recall_review`
        feature, so a module-level scan there would false-positive; guarding the pure domain module is
        the tractable static shadow (mirroring `ranking_order_ignores_the_taxonomy_label`). Mirror an
        import/call-scanning check (e.g. `label_not_a_ranking_input` / the `_is_call_to` +
        module-import inspection helpers). Fails closed on an unparseable file.
  - [x] Register in the three lockstep sites (registry + manifest + README); key
        `line-projection-not-a-bound`, FR-19, §0.2 → an AD (use AD-20 — the honest-truth-status
        family, or AD-38; pick the one the meta-checks accept). Failure-fixture test
        `tests/checks/test_line_projection_not_a_bound.py` that fires on a module calling
        `prevalence_upper_bound`.

- [x] **Task 7 — Full gate + reconcile** (all ACs)
  - [x] `cd apx-mvp && export PATH="$PWD/.venv/bin:$PATH"` then ruff (reflow accents by hand),
        the check harness (the new check green; the count rises 67 → 68), import-linter 3/0, pytest
        (all pass, no `apx-platform/` collection).

## Dev Notes

### The substrate 4.9 consumes (do NOT re-implement)

- **Story 4.8** (`apx/adapters/store_postgres/store.py`): `place_line`, `read_current_line`,
  `_line_basis`, `_line_retain_bands`, the `LinePlacement` model + `LinePlacementView`
  (`core/domain/line.py`). `move_line` reuses the SAME append path (server `seq`, conditional commit,
  atomic audit) — mirror `place_line`. [Source: store.py — the Story-4.8 section.]
- **Story 4.4** (`apx/core/domain/piece_confidence.py`): `derive_confidence` + `_band_direction`; the
  per-pièce `confidence` and `band` are persisted on `ranked_entry` (columns `confidence`, `band`).
  The **directional P(relevant) conversion** (relevant → c, discard → 1−c) is already fixed by
  `tests/eval/test_confidence_calibration.py` and `eval/harness.py::confidence_calibration` — reuse
  it verbatim so the projection and the confidence calibration agree. [Source: piece_confidence.py:88,
  tests/eval/test_confidence_calibration.py:16.]
- **The sampling bound to stay away from**: `apx/core/domain/confidence.py::prevalence_upper_bound`
  (hypergeometric, finite-population) is the Epic-5 CONFIDENCE BOUND. FR-19/§0.2: the projection is a
  DIFFERENT statement; `line_projection` must never call it (Task 6's check). [Source: confidence.py:49]
- **`_audited_tx` + `_append_audit`** (store.py) and the `expected_seq`/`StaleLabel` conditional-commit
  pattern (`_append_label_entry`) are the exact shapes `move_line` + `StaleLine` mirror. [Source:
  store.py::_append_label_entry.]

### The projection method (documented, single-implementation)

Per-pièce P(relevant): **confident-relevant → confidence**; **confident-discard → 1 − confidence**;
**uncertain → 0.5** (the tool could not decide — the honest, non-optimistic default, never derived
from a direction the uncertain band does not carry); no band / no confidence → **None** (excluded —
AD-19, nothing imputed). The discarded-set prevalence is the arithmetic mean over the projectable
pièces; `None` (unavailable) when none is projectable. Named `PROJECTION_METHOD`. This is a
**projection**, calibration-tested (SM-17, Task 2) for the optimistic direction — it can be wrong in a
way a completed sample cannot, which is exactly why it must never wear the bound's register (AC-2).

### FR-19 invariants to hold

- Never a "risk of having missed" quantity — it is simply **not computed**; the store returns Δ counts
  + prevalences only (AC-1, §0.2).
- Retain-everything → `discarded_empty`, prevalence None, **never 0%** (AC-4).
- The move is **serialised** (`expected_seq` conditional commit → `StaleLine`) and the audit records
  the **priced statement that was shown** (AC-6). The priced statement string is passed by the caller
  (what the user saw) and lands in the encrypted `audit_record.detail`.

### Testing standards

uv-managed (`.venv/bin/...`); **always `cd apx-mvp` first + `export PATH` in the same Bash call**;
**never `export DATABASE_URL`**; ruff line-length 100 (reflow accents by hand). Store tests use the
SQLite `_sf()` + `record_ranking` seeding (see `test_line_placement_store.py` /
`test_triage_sets_store.py`). Confidence must be persisted on `ranked_entry` for the projection — the
seeding via `record_ranking` populates `confidence` from `derive_confidence`.

### Project Structure Notes

- New: `apx/core/domain/line_projection.py`, `apx/checks/line_projection_not_a_bound.py`, their tests,
  `tests/adapters/test_line_move_store.py`, `tests/eval/test_projection_calibration.py`.
- Updated: `apx/adapters/store_postgres/store.py` (+`price_line_move`, `move_line`, `StaleLine`),
  `apx/core/ports/line.py` + `apx/core/app/line.py` (+2 seams), `eval/harness.py` (+projection
  calibration), `apx/checks/registry.py` + `apx/checks/manifest.py` + `README.md` (lockstep),
  `tests/app/test_line_use_case.py` (extend).
- No new model, no migration (the move reuses `line_placement`). No config key (the projection is
  parameter-free by design; calibration validates it).

### References

- [Source: epics.md#Story-4.9] · [Source: prd.md#FR-19] (lines 521–536) · [Source: prd.md §0.2]
  (the projection-vs-bound correction). · UX: `EXPERIENCE-EPIC4.md#Moving-the-line-is-priced`,
  `DESIGN.md {components.line-price}` (the projection register, deliberately not the verdict/absence
  seal). · Sibling: Story 4.8 (the line), Story 4.4 (confidence + calibration), Story 4.5
  (`expected_seq`/`StaleLabel` conditional commit).

## Dev Agent Record

### Agent Model Used

claude-opus-4-8 (dev-story)

### Debug Log References

- Gate green: ruff clean · **68 structural checks** (incl. new `line-projection-not-a-bound`) ·
  import-linter 3/0 · **1226 passed / 12 skipped**.
- Two regressions caught + fixed by the gate: (1) the shipped FR-23 check
  `no_banned_confidence_phrasing` fired on my `line_projection.py` docstring, which quoted the banned
  literal "risk of having missed a relevant document" verbatim (to explain what the projection never
  produces). Reworded to a paraphrase — the honest meaning kept, the barred literal removed. (2) The
  domain function `price_line_move` and the store method `price_line_move` share a name; imported the
  domain one aliased (`project_line_move`) to avoid shadowing.

### Completion Notes List

- The priced move is a **projection from the ranking** (`line_projection.py`): per-pièce P(relevant)
  reuses the directional conversion the 4.4 SM-17 confidence calibration already fixed (relevant → c,
  discard → 1−c, uncertain → 0.5, no observable → None), meaned over the projectable discarded set.
- **Projection ≠ bound is structural** (`line-projection-not-a-bound`): the projection module never
  imports/references `confidence.prevalence_upper_bound` (the Epic-5 hypergeometric bound) — a
  projection can never be computed by (or mistaken for) the sampling bound (§0.2).
- Edge cases held: retain-everything → `discarded_empty`, prevalence `None`, **never 0%** (AC-4);
  no projectable pièce → counts-only, prevalence unavailable (AC-5).
- The human move `move_line` is **serialised** (`expected_seq` conditional commit → `StaleLine` with
  the current position) and **audited** with old/new position + method + the **priced statement shown**
  (AC-6); it touches only `line_placement`, never the order.
- SM-17 projection calibration (`eval/harness.py::projection_calibration`) flags a systematically
  **optimistic** projection (the dangerous direction). AD-4 seam extended (`price_line_move`,
  `move_line`).

### File List

**New:** `apx/core/domain/line_projection.py` · `apx/checks/line_projection_not_a_bound.py` ·
`tests/domain/test_line_projection.py` · `tests/eval/test_projection_calibration.py` ·
`tests/adapters/test_line_move_store.py` · `tests/checks/test_line_projection_not_a_bound.py`

**Modified:** `apx/adapters/store_postgres/store.py` (+`price_line_move`, `move_line`, `StaleLine`,
imports) · `apx/core/ports/line.py` + `apx/core/app/line.py` (+2 seams) · `eval/harness.py`
(+`projection_calibration`) · `apx/checks/registry.py` · `apx/checks/manifest.py` · `README.md`
(structural-properties) · `tests/app/test_line_use_case.py` (extend)

## Change Log

| Date       | Version | Description                                   | Author |
|------------|---------|-----------------------------------------------|--------|
| 2026-08-05 | 0.1     | Story drafted (create-story inline), ready-for-dev | create-story |
| 2026-08-05 | 0.2     | Implemented; adversarial review 4 findings → 0 confirmed / 4 refuted; done | dev-story |

## Senior Developer Review (AI)

**Reviewed:** 2026-08-05 · **Outcome:** Approve · **Method:** adversarial Workflow — 3 parallel lenses
(correctness, security/isolation, architecture/scope), each finding independently skeptic-verified
with a default-REFUTED bias. Reviewers inspected the uncommitted working tree against baseline
`a3ca6b8`. (Verified against the workflow `journal.jsonl`: 3 lenses produced 1+1+2 = 4 findings, all
4 skeptic-verdicts REFUTED — no CONFIRMED verdict was dropped in aggregation.)

**Result: 4 findings → 0 confirmed / 4 refuted.**

- **3 findings (one per lens), same theme** — the `line-projection-not-a-bound` check scopes to
  `core/domain/line_projection.py` and does not scan the store, while the story's Task-6 prose said
  "+ the store's price path". **Refuted:** the runtime invariant genuinely holds — the store's
  `price_line_move` computes no prevalence, it *delegates* to the guarded domain function
  `project_line_move`, so every returned prevalence originates in the clean, scanned module; the
  store's `prevalence_upper_bound` import is **pre-existing** (Epic-5 `record_recall_review`), so a
  module-level scan of the store would false-positive on legitimate code; and the **binding AC-2** is
  satisfied exactly. The domain-module scope is the correct, tractable static shadow (mirroring
  `ranking_order_ignores_the_taxonomy_label`). **Doc tightening applied** (not a code change): Task-6
  wording corrected to state the check scopes to the domain module and why the store is not scanned.
- **1 finding** — the `line_moved` audit truncates old/new pièce ids to a 12-char prefix. **Refuted:**
  no data loss (the full id is in the append-only `LinePlacement` row), collision unreachable (a
  48-bit sha256 prefix over a few-thousand-pièce matter), and AC-6 is fully satisfied — the priced
  statement and the method are stored in **full**; it mirrors the pre-existing `place_line`
  convention.

**Integrity manifest:** all touched **code** files byte-identical since the pre-review snapshot — the
review mutated no code (the only post-review edit is this story's prose). **Secret scan:** clean.

**Gate at done:** ruff clean · **68 structural checks** (incl. new `line-projection-not-a-bound`) ·
import-linter 3/0 · **1226 passed / 12 skipped**.

## Dev Questions / Assumptions (ratified by the delegate — do not block)

1. **Projection method.** Assumed the directional P(relevant) conversion already fixed by the 4.4
   confidence calibration (relevant → c, discard → 1−c, uncertain → 0.5, no observable → None),
   arithmetic mean over projectable discarded pièces. Parameter-free; SM-17 validates the optimistic
   direction. A richer calibrated model defers (like the confidence derivation, it can be revised).
2. **The human move stores basis = the ranking basis** (unchanged by a move — it is *why the order
   is what it is*); the move's provenance (who moved it, old→new, the priced statement) lives in the
   `line_moved` audit entry. No new column.
3. **The priced statement is passed by the caller** (the sentence shown to the user) and recorded in
   the audit — FR-19 requires recording *the statement that was shown*, which only the edge knows.
4. **`price_line_move` is not audited** (a preview/hover); only the committed `move_line` is audited.
