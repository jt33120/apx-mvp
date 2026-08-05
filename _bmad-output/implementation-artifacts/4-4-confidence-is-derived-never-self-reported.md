---
baseline_commit: a598a9f
---

# Story 4.4: Confidence is derived, never self-reported

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a lawyer whose *confidence bound* must mean something,
I want the per-*pièce* confidence derived from observable quantities and never from a number the model
made up about itself,
so that a statistical statement does not rest on the model's own opinion of its certainty.

## Scope note — the DERIVATION of the confidence value (FR-42); not the justification, not the line

Story 4.2 gave the cascade its observable outputs (`PieceJudgement`: band, score, label, stage_reached,
outcome). Story 4.3 persisted them per *pièce* against a *ranking version*. Story 4.4 **derives one
confidence value per *pièce* from those observables** — score margin and cross-stage agreement — records
the **derivation method in the ranking-version identity** (AD-23), marks confidence **not derived** where
it cannot be derived (AD-19, never imputed), and lands the **calibration harness (SM-17)** the gold set
will exercise. FR-42's load-bearing promise: *a confidence never comes from a figure the language model
states about itself.*

**IN scope:** (1) a pure Domain `confidence.py` — `derive_confidence(judgement, config) -> Confidence |
None`, from **observable cascade quantities only**, with a versioned `CONFIDENCE_METHOD`; (2) the method
recorded in `RankingIdentity` (AD-23 — a method change is a new version); (3) the confidence carried on
`RankedRow` and persisted on `RankedEntry` (migration 0025, nullable — NULL == not derived, AD-19); (4)
the static gate — the existing `no_model_reported_confidence` check made **non-vacuous and kept green**,
plus a new **one-implementation** check (FR-42/FR-56: the derivation has exactly one implementation);
(5) the **SM-17 calibration** harness (`eval/harness.py`) + a build-gate property test that a
**systematically overconfident derivation fails the build** (the full gold-corpus measurement defers like
`recall_at_the_line`).

**OUT of scope (do NOT build):** the one-line justification derived from named evidence (4.6); **the
line** and the above/below-the-line generation policy + on-demand backfill (4.7/4.8 — the backfill
*depends on the line*); the *audit drawer* expansion and the reversible-in-one-action UI act (later,
needs a UX pass); the *confidence bound* sentence (Epic 5). The **repeated-judgement agreement** signal
is DECLARED in the method but currently absent (the cascade judges each *pièce* once — no repeats are
produced yet); the derivation uses the two signals that exist (score margin + cross-stage agreement) and
names the third as reserved.

## Acceptance Criteria

**AC-1 (FR-42 — derived from observable quantities, never self-reported).** A *pièce*'s confidence is
computed by **one** pure function from **observable cascade quantities only** — the **score margin**
(distance of the stage-2 score beyond its band's decision boundary) and **cross-stage agreement** (does
the stage-3 LLM label agree with the cheap band's direction) — and **never** from any figure the model
states about itself. The judge's `Verdict` carries only `label` + `rationale` (no confidence field); the
derivation reads `score`/`band`/`label`/`stage_reached`, never a model-response field.

**AC-2 (FR-56 — the static gate: no model-reported confidence + one implementation).** A structural
check asserts (a) no field parsed from a model response is named or used as a confidence
(`no_model_reported_confidence`, now **non-vacuous** because the confidence path exists, and **green**),
and (b) the confidence **derivation has exactly one implementation** (a new check, mirroring
`embedder_has_one_implementation`). Both are registered in the check registry + manifest + README block
(lockstep).

**AC-3 (AD-23 — the method recorded in the ranking version, reproducible).** The derivation method is a
versioned identifier (`CONFIDENCE_METHOD`) recorded in the `RankingIdentity` (so it is in the version
`fingerprint`/`identity_json` and the `version_id`); a **change to the method is a new ranking version**.
Given a fixed *ranking version* over a fixed *corpus*, the confidence reproduces (it is a pure function of
the recorded observables + the recorded method).

**AC-4 (AD-19 — never imputed; marked not-derived where it cannot be derived).** Where a confidence
cannot be derived — an **UNSCORED** *pièce* (no judgement), a **REJECTED** near-duplicate member (no
independent judgement of its own), or the intrinsic path with no numeric score — the confidence is
**`None`/NULL (not derived)**, never a default, a zero or an imputed number. The persisted `confidence`
column is nullable and NULL means exactly "not derived".

**AC-5 (SM-17 — calibrated against the gold set; overconfidence fails the build).** A calibration harness
(`eval/harness.py::confidence_calibration`) computes, per confidence band, the **observed relevant share**
from a gold observation and reports whether the derivation is **systematically overconfident** (the mean
claimed confidence in a band materially exceeds the observed relevant share). A build-gate **property
test** asserts the derivation is **not systematically overconfident** on a battery (a boundary *pièce*
gets a low confidence; a cross-stage conflict lowers it below agreement; confidence is monotone in the
margin). The **full gold-corpus measurement defers** (documented) exactly like `recall_at_the_line`, and
must not break the existing gold gate (AD-34).

**AC-6 (persistence + tenant isolation regression).** The confidence is persisted per *pièce* on
`RankedEntry` (migration 0025, append-only) and returned on the ranked-order read; all Story 4.3
guarantees (atomic record, scope pre-filter, non-disclosing reads, append-only, no retained/discarded
column) remain intact.

## Tasks / Subtasks

- [x] **Task 1 — Domain: the confidence vocabulary (`apx/core/domain/confidence.py`, NEW).** (AC-1, AC-4)
  - [x] `ConfidenceSignal(StrEnum)` — `SCORE_MARGIN`, `CROSS_STAGE_AGREEMENT`, and a **reserved**
    `REPEATED_JUDGEMENT` (declared for AD-36-style append-only stability; the cascade produces no repeats
    yet, so it is never emitted in 4.4). `CONFIDENCE_SIGNALS` tuple.
  - [x] `Confidence` frozen dataclass — `value: float` (asserted in `[0.0, 1.0]` in `__post_init__`),
    `signals: tuple[ConfidenceSignal, ...]` (which observables fed it — non-empty). It is a **domain**
    value object, not a model subject.
  - [x] `CONFIDENCE_METHOD = "margin-agreement-v1"` — the versioned derivation identity recorded in the
    ranking version (AD-23). Bump when the formula/weights change.
  - [x] `derive_confidence(judgement: PieceJudgement, config: CascadeConfig) -> Confidence | None` — the
    **one** pure implementation:
    - **Not derivable → `None`** (AD-19): `outcome is UNSCORED` (no judgement); `outcome is REJECTED`
      (a near-duplicate member, no independent judgement); a JUDGED *pièce* with `score is None`
      (intrinsic path — no numeric margin AND, if it also has no stage-3 label, no observable at all).
      (A JUDGED intrinsic *pièce* WITH a stage-3 label still has the agreement signal — derive from that
      alone; only when neither observable exists is it `None`.)
    - **score margin** (a JUDGED *pièce* with a score): normalise the distance beyond the band boundary —
      confident-relevant: `(score - high) / max(1.0 - high, ε)`; confident-discard: `(low - score) /
      max(low - (-1.0), ε)`; uncertain band: `0.0` (the ambiguous zone gives the score no confidence).
      Clamp `[0, 1]`. Document the score domain (`1.0 - min cosine distance`, so `[-1, 1]`).
    - **cross-stage agreement** (a *pièce* that reached stage 3 — has a `label`): the cheap band's
      direction is relevant (confident-relevant) / discard (confident-discard) / none (uncertain).
      `+1` when the LLM label agrees with the band direction (or, for the uncertain band, is a decisive
      `relevant`/`discard`); `-1` on a conflict (confident-relevant + `discard`, or confident-discard +
      `relevant`); a small negative for uncertain-band + `uncertain`; `0` when no stage-3 label (settled
      at stage 2 — only the margin speaks).
    - **combine** (documented v1 weights, deliberately conservative → never overconfident): a confident
      band's base is `0.5 + 0.5 * margin`; the uncertain band's base is a low constant; the agreement
      adjustment nudges up on agreement and **down more on conflict** (a conflict is a strong
      de-confidence signal). Clamp `[0, 1]`. The exact constants are **v1**, to be calibrated against the
      gold set (SM-17); the PROPERTIES (monotone in margin, conflict < agreement, boundary → low) are the
      tested contract.
    - It reads **only** `judgement.score/band/label/stage_reached/outcome` and `config` band boundaries —
      **never** a model-response field (FR-42). Add a module docstring stating this.

- [x] **Task 2 — Wire the confidence into the ranked order + the identity.** (AC-1, AC-3, AC-4)
  - [x] `apx/core/domain/ranking.py` — `RankedRow` gains `confidence: float | None = None` and
    `confidence_signals: tuple[ConfidenceSignal, ...] = ()`. `rank_cascade` takes `config: CascadeConfig`
    (needed for the margin boundaries), and for each row calls `derive_confidence(judgement, config)`,
    setting `confidence`/`confidence_signals` (None/empty when not derived). Keep the ordering unchanged
    (confidence does NOT affect rank — the order is 4.3's relevance ladder; a later story may use
    confidence, but not here). Update `_to_row` to accept the derived confidence.
  - [x] `RankingIdentity` gains `confidence_method: str`; `assemble_identity` stamps
    `CONFIDENCE_METHOD`; add it to `_canonical()` (so it is in the fingerprint + `identity_json`) and to
    the blank-field validation. `RankingIdentityInputs` does **not** carry it (it is a build constant like
    `grouping_identity`/`tie_break`).
  - [x] `apx/core/app/rank.py::produce_ranking` — pass `config` to `rank_cascade` (it already has it).

- [x] **Task 3 — Persistence: the confidence column + migration 0025.** (AC-4, AC-6)
  - [x] `apx/adapters/store_postgres/models.py` — `RankedEntry` gains `confidence: Mapped[float | None]
    = mapped_column(Float, nullable=True)` (**NULL == not derived**, AD-19) and, for transparency,
    `confidence_signals: Mapped[str | None]` (a compact comma-joined signal list, plaintext categorical
    — like `band`/`label`; NULL when not derived). Plaintext: a float + categorical enums, no content.
  - [x] Migration `0025_ranked_entry_confidence.py` — `down_revision = "0024_ranking_version"`;
    `op.add_column("ranked_entry", ...)` for both (nullable, **no backfill** — a pre-4.4 ranking had no
    derivation, so its confidence is genuinely unknown = NULL, honest per AD-19). `downgrade` drops them.
  - [x] `store.py::record_ranking` — write `confidence` + `confidence_signals` from each `RankedRow`;
    add them to `RankedEntryView` and the `read_ranked_order` projection. No other change (the version +
    audit + conditional-commit stay exactly as 4.3).

- [x] **Task 4 — Static gate: no-model-reported (kept green) + one-implementation (new).** (AC-2)
  - [x] Verify `no_model_reported_confidence` (`apx/checks/forward_looking.py`) stays **green** now that
    the confidence path exists (the derivation reads no model-response field). Extend `_MODEL_SUBJECTS`
    with the real judge-result name if warranted (`verdict`) — but ONLY if it does not false-positive on
    the legitimate domain `Verdict` (it is a domain value object; a `verdict.label`/`verdict.rationale`
    read is fine — the check flags `.confidence`/`.certainty`/… which `Verdict` does not have). Keep the
    check's own tests green.
  - [x] NEW `apx/checks/confidence_derivation.py` — `confidence_has_one_derivation`: the confidence is
    derived by exactly **one** function (`confidence.derive_confidence`); a second confidence-producing
    site (another function returning a `Confidence`, or a second `Confidence(...)` construction outside
    the one module) fails the build (mirror `forward_looking.embedder_has_one_implementation`'s shape and
    its fixture-proven failure path). Register in `registry.py` + `manifest.py` + the README block.

- [x] **Task 5 — SM-17: the calibration harness + the overconfidence build gate.** (AC-5)
  - [x] `eval/harness.py::confidence_calibration(observations)` — given per-band gold observations
    (`band -> (relevant_count, total_count)`) and the derivation's claimed per-band confidence, compute
    the **observed relevant share** per band and return a structured verdict: per-band (claimed_mean,
    observed_share, overconfidence_gap) + `systematically_overconfident: bool` (True when a band's claimed
    mean materially exceeds its observed share beyond a tolerance). The FULL gold-corpus run (ingest gold
    → cascade → derive → compare to `eval.gold_mapping.mapped_gold`) **defers** exactly like
    `recall_at_the_line` (document it); this function computes the calibration MATH from an injected
    observation so it is exercisable in CI now.
  - [x] A **build-gate property test** (`tests/domain/test_confidence.py` or a dedicated calibration
    test) that fails the build if the derivation is systematically overconfident on a synthetic battery:
    a boundary *pièce* (score == high) has LOW confidence; a cross-stage **conflict** yields a **lower**
    confidence than **agreement** at the same margin; confidence is **monotone non-decreasing** in the
    score margin within a confident band; and `confidence_calibration` on a hand-built overconfident
    observation returns `systematically_overconfident=True` (proving the gate can fire).
  - [x] Do NOT break the existing gold gate (AD-34): `recall_at_the_line` stays defined + invoked by a
    test; the gold gate must remain green.

- [x] **Task 6 — Tests (red→green; deterministic, no network/DB for domain).**
  - [x] `tests/domain/test_confidence.py` — `derive_confidence`: the None cases (UNSCORED, REJECTED,
    scoreless-and-labelless intrinsic); the value in `[0,1]`; monotonicity in margin; conflict <
    agreement; a boundary *pièce* is low; the signals recorded; a JUDGED intrinsic *pièce* with only a
    label derives from agreement alone. `Confidence.__post_init__` rejects an out-of-range value.
  - [x] `tests/domain/test_ranking.py` (extend) — `rank_cascade(result, config)` attaches confidence per
    row (None for unscored/rejected); the identity now carries `confidence_method` (fingerprint changes
    on a method change); the order is UNCHANGED by confidence.
  - [x] `tests/app/test_rank_run.py` (extend) — `produce_ranking` passes config; the recorded order's
    rows carry confidence.
  - [x] `tests/adapters/test_ranking_store.py` (extend) — `record_ranking` persists confidence +
    signals; `read_ranked_order` returns them; a not-derived *pièce* round-trips as NULL.
  - [x] `tests/adapters/test_ranking_confidence_migration.py` — 0025 adds both columns; downgrade drops
    them; head is `0025_ranked_entry_confidence` (mirror `test_ranking_migration.py`'s Operations-context
    approach).
  - [x] `tests/checks/test_confidence_derivation.py` — the one-implementation check passes the real tree,
    fires on a second `Confidence(...)` / second derivation function fixture, fails closed.
  - [x] `tests/eval/test_confidence_calibration.py` — `confidence_calibration` computes the per-band
    observed share and flags a systematically overconfident observation; a well-calibrated one passes.

## Dev Notes

### The observable quantities — and the one that isn't there yet
FR-42/AC-1 name three signals: **score margin**, **cross-stage agreement**, **agreement across repeated
judgements**. The first two are observable from a single `CascadeResult` (score vs band boundary; band
direction vs stage-3 label). The third needs the cascade to judge a *pièce* MORE THAN ONCE (repeated
sampling), which the current `run_cascade` does not do — it calls the judge once per representative. So
4.4 derives from the two available signals and **reserves** `REPEATED_JUDGEMENT` in the signal enum
(append-only, like `cascade.RejectionClass`) so a later story adds repeats without a schema churn. Do
NOT fabricate a repeated-judgement signal from a single call.

### FR-42 is a NAMING + SOURCING discipline, enforced by a live check
`apx/checks/forward_looking.py::no_model_reported_confidence` flags a `.confidence`/`.certainty`/
`.self_confidence`/`.confidence_score` read off a **model-response subject** (`response`, `resp`,
`completion`, `llm_response`, `answer`, `reply`, …). It is **vacuous today** ("until the judge/confidence
path lands"). 4.4 makes it non-vacuous — so the derivation must read ONLY `judgement.*` and `config.*`,
never a model-response field. The judge's `Verdict` (`apx/core/domain/triage.py`) is `{label, rationale}`
— it has **no** confidence field, so there is nothing to accidentally read; keep it that way. The check's
own comment says the "one implementation" half "lands with the confidence path (4.x)" — that is Task 4's
new `confidence_has_one_derivation` check.

### AD-19 — not-derived is a first-class state, never a zero
A confidence that cannot be derived is **NULL/None (not derived)** — never 0.0, never a default. AD-19:
"unscored is not zero". An UNSCORED *pièce* (its judgement failed) has no confidence; a REJECTED
near-duplicate member has no independent judgement (it was collapsed into its representative, so it
carries a rejection class, not a confidence); the intrinsic path with neither a score nor a stage-3 label
has no observable to derive from. Mark all of these NULL. A reader distinguishes "confidence 0.0" (a
derived low confidence) from NULL (not derived) — the column is nullable and the distinction is load-
bearing for the future *confidence bound*.

### AD-23 — the method is part of the version identity
The derivation method (`CONFIDENCE_METHOD`) joins `RankingIdentity` so it is in the `fingerprint`,
`identity_json` and `version_id`. A change to the formula/weights = a new `CONFIDENCE_METHOD` = a new
ranking version (a re-derivation is never silently the "same version"). This is exactly the AD-23 shape
4.3 built for `grouping_identity`/`tie_break` — a build constant stamped by `assemble_identity`, NOT a
caller input. The 4.3 fingerprint tests that assert equality/inequality still hold; a test asserts a
`confidence_method` change flips the fingerprint.

### SM-17 — calibration defers like recall, but the MATH + the gate are live now
`recall_at_the_line` (`eval/harness.py`) raises `NotImplementedError` pending *the line* (Epic 4.7/4.8);
the gold gate (AD-34) requires it to be defined + invoked by a test so it RUNS in CI. Mirror that:
`confidence_calibration` computes the per-band observed-share math from an injected gold observation (so
the calibration LOGIC is exercised in CI now), while the FULL gold-corpus derivation-vs-truth run defers
(documented) until the gold-ranking pipeline exists. The "systematically overconfident fails the build"
requirement is made real NOW by a **property test on the derivation** (boundary → low, conflict <
agreement, monotone in margin) — a derivation that claimed high confidence at the boundary would fail it.
Keep the gold gate green (do not touch `recall_at_the_line`'s deferral).

### Reuse, don't reinvent — the seams already in place
- **The substrate:** `cascade.PieceJudgement` (band/score/label/stage_reached/outcome), `CascadeResult`,
  `CascadeConfig.band_of`/boundaries (`core/domain/config.py`), and 4.3's `rank_cascade`/`RankedRow`/
  `RankingIdentity`/`assemble_identity` (`core/domain/ranking.py`) + `record_ranking`/`RankedEntry`/
  `RankedEntryView`/`read_ranked_order` (`store.py`). Extend, don't duplicate.
- **The one-implementation check:** mirror `forward_looking.embedder_has_one_implementation` (its
  AST shape + fixture-proven failure path) for `confidence_has_one_derivation`.
- **The migration test:** `tests/adapters/test_ranking_migration.py` shows the alembic-Operations-context
  approach for a DDL migration on SQLite (load by path, bind `op` to a connection). Mirror it for 0025.
- **The lockstep:** a new check needs THREE edits kept in sync by the meta-checks — `registry.py::CHECKS`,
  `manifest.py::PROPERTY_MANIFEST`, and the README `<!-- structural-properties:start -->` block.

### Testing standards
`uv`-managed: `export PATH="$PWD/.venv/bin:$PATH"` then `pytest` / `ruff check`. **NEVER `export
DATABASE_URL`.** ruff line-length 100 — accented prose ("pièce", "é", "→", "≥") pushes lines over; trim
manually. Domain tests are pure (no DB/net). Import-linter (AD-4/AD-27/AD-45) must stay green:
`core/domain/confidence.py` imports Domain only; it must NOT import any adapter or LLM SDK. No new
dependency expected (stdlib only) — use `uv add` if one is genuinely needed.

### Project Structure Notes
NEW: `apx/core/domain/confidence.py`, `apx/checks/confidence_derivation.py`,
`apx/adapters/store_postgres/migrations/versions/0025_ranked_entry_confidence.py`, the test files.
UPDATE: `apx/core/domain/ranking.py` (RankedRow + RankingIdentity + rank_cascade), `apx/core/app/rank.py`
(pass config), `apx/adapters/store_postgres/models.py` (2 columns), `apx/adapters/store_postgres/store.py`
(persist + read confidence), `apx/checks/registry.py`, `apx/checks/manifest.py`, `README.md`,
`eval/harness.py` (confidence_calibration), and possibly `apx/checks/forward_looking.py` (extend
`_MODEL_SUBJECTS` only if safe). No config-key change is expected (the cascade band keys already exist and
supply the margin boundaries). Commit on `master`, enumerate files explicitly, feat message, secret-scan
the staged diff, co-author trailer.

### References
- Story 4.4 + FR-42 (epics.md) — derived, never self-reported; method recorded; calibrated; never
  imputed. FR-18 (the confidence value; the justification + reversal are 4.6/UX).
- AD-19 (ARCHITECTURE-SPINE.md ≈ 559) — loud failure, nothing imputed. AD-23 (≈ 656) — the version
  identity includes the derivation method. AD-34 (≈ gold gate) — the gold merge gate stays green.
- Story 4.2 (`4-2-…-cascade-cheap-filters-first.md`) — the observable outputs. Story 4.3
  (`4-3-…-ranking-version.md`) — the identity + persistence this extends.
- `apx/checks/forward_looking.py` — the live `no_model_reported_confidence` gate + the
  `embedder_has_one_implementation` shape to mirror.

## Dev Agent Record

### Agent Model Used
claude-opus-4-8 (1M context) — BMAD dev-story.

### Debug Log References
Gate green: `ruff check` clean · 62 structural checks (incl. the new `confidence-one-derivation`; the
live `no_model_reported_confidence` stays GREEN now the confidence path exists; the gold gate AD-34
stays green; the encryption AD-31 allowlist widened for `RankedEntry.confidence_signals`) ·
import-linter 3 kept / 0 broken (AD-4/27/45) · pytest **1089 passed / 12 skipped** (20 new tests).

### Completion Notes List
- **Naming:** the per-*pièce* confidence lives in a NEW `apx/core/domain/piece_confidence.py` — the
  existing `confidence.py` is the Epic-5 hypergeometric *confidence bound* (a different thing); the two
  are kept distinct (same for the test files: `test_piece_confidence.py`).
- **Derivation (pure).** `derive_confidence(judgement, config)` from OBSERVABLES only — the confident-
  band **score margin** (0 at the boundary → 1 at the extreme), deflated by a stage-2/stage-3
  **conflict**; the uncertain band derives from the LLM label's decisiveness. It reads only
  `judgement.score/band/label/outcome` + config boundaries — never a model-response field (the
  `Verdict` has no confidence). v1 weights are **conservative** (never overconfident by construction);
  the tested contract is the PROPERTIES (monotone in margin, conflict < agreement, boundary → low),
  not the constants. Returns **None** (not derived) for UNSCORED / REJECTED / no-observable (AD-19).
- **Identity + persistence.** `CONFIDENCE_METHOD` is stamped into `RankingIdentity` (AD-23 — in the
  fingerprint/`identity_json`/`version_id`; a method change is a new version). `rank_cascade` now takes
  the `CascadeConfig` and attaches each row's confidence (never reorders — the order is 4.3's).
  `RankedEntry` gained `confidence` (Float, **NULL == not derived**) + `confidence_signals` (comma-
  joined categorical, plaintext) via migration 0025 (no backfill — a pre-4.4 ranking is honestly NULL).
- **Static gate.** `no_model_reported_confidence` (FR-42) is now non-vacuous and green; a NEW
  `confidence_has_one_derivation` check asserts `Confidence(...)` is constructed only in
  `piece_confidence.py` (one auditable derivation) — registered in registry + manifest + README.
- **SM-17 calibration.** `eval/harness.py::confidence_calibration(observations)` computes the per-band
  observed relevant share and flags a **systematically overconfident** derivation; exercised in CI by a
  test with a synthetic observation. The **build-gate property test** (boundary → low, conflict <
  agreement, monotone) makes "overconfidence fails the build" real NOW; the full gold-corpus run
  **defers** exactly like `recall_at_the_line` (the gold gate stays green, untouched).
- **Deferrals (assumed).** The `REPEATED_JUDGEMENT` signal is reserved but never emitted (the cascade
  judges once). The one-line justification (4.6), the line + on-demand backfill (4.7/4.8), the audit
  drawer + reversal UI, and the *confidence bound* sentence (Epic 5) are out of scope.

### File List
**New:** `apx/core/domain/piece_confidence.py` · `apx/checks/confidence_derivation.py` ·
`apx/adapters/store_postgres/migrations/versions/0025_ranked_entry_confidence.py` ·
`tests/domain/test_piece_confidence.py` · `tests/adapters/test_ranking_confidence_migration.py` ·
`tests/checks/test_confidence_derivation.py` · `tests/eval/test_confidence_calibration.py`
**Updated:** `apx/core/domain/ranking.py` (RankedRow +confidence; RankingIdentity +confidence_method;
`rank_cascade(result, config)`) · `apx/core/app/rank.py` (pass config) ·
`apx/adapters/store_postgres/models.py` (2 columns) · `apx/adapters/store_postgres/store.py` (persist +
read confidence; RankedEntryView) · `apx/checks/registry.py` · `apx/checks/manifest.py` ·
`apx/checks/encryption.py` (allowlist) · `README.md` · `eval/harness.py` (confidence_calibration) ·
`tests/domain/test_ranking.py` · `tests/app/test_rank_run.py` · `tests/adapters/test_ranking_store.py`

## Change Log

| Date       | Version | Description                         | Author |
| ---------- | ------- | ----------------------------------- | ------ |
| 2026-08-04 | 0.1     | Story context created (ready-for-dev) | Julian |
| 2026-08-05 | 1.0     | Implemented; adversarial review (3 lenses + skeptic-verify) → 3 findings, 0 confirmed / 3 refuted (all the same calibration-direction insight); addressed the refuted-but-convergent insight (SM-17 contract made direction-explicit); re-gated green; done | Julian |

## Senior Developer Review (AI)

Adversarial Workflow review (3 lenses — derivation correctness/AD-19, identity/persistence/FR-42,
SM-17/gold-gate/regression — each finding independently skeptic-verified, default REFUTED). **3
findings → 0 CONFIRMED / 3 refuted.** Integrity manifest verified: the review mutated nothing (only
the 2 SM-17-hardening files changed post-review). Re-gated green (ruff · 62 structural checks ·
import-linter 3/0 · 1090 passed).

**All three lenses independently converged on ONE insight** (a strong signal, though all refuted): the
SM-17 `confidence_calibration` compares the derivation's confidence — the certainty of the *assessment*
(symmetric: a deep confident-DISCARD pièce is HIGH confidence it is *irrelevant*) — against the
observed **relevant** share, which for the discard direction moves the opposite way. The verifiers
REFUTED it as a shipped defect: `confidence_calibration` is a standalone math primitive over an
INJECTED observation, not wired to any live build gate (the gold-corpus pipeline defers exactly like
`recall_at_the_line`); it implements AC-5 verbatim; and the shipped test fixture already passes the
discard band as a P(relevant) (0.10 = 1 − 0.9). No AD/AC violation, no reproducible current failure.

**Addressed anyway (the refuted-but-convergent insight, cheap + principled):** the SM-17 contract is
now **direction-explicit** — the observation's claim is documented and named `claimed_p_relevant` (a
probability of relevance, not a directionless confidence), with a `[0, 1]` guard that refuses a raw
directional confidence and a docstring stating the caller must convert (`p_relevant = c` for a
relevant band, `1 − c` for a discard band) before bucketing. A new test locks the convention. This
closes the latent trap the deferred gold pipeline could have fallen into, without building that
pipeline. The build-gate teeth stay the derivation property test (boundary → low, conflict <
agreement, monotone); the gold gate (AD-34) is untouched and green.
