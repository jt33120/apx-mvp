---
baseline_commit: d89f7ee
---

# Story 4.2: The relevance judgement — a cascade, cheap filters first

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a firm paying for inference,
I want relevance assessed by a staged cascade that reaches the language model only for the *pièces* cheap filters cannot separate,
so that cutting the model's workload ten-fold is cheaper than buying ten times the machine — the difference between the €2 000 box and the €20 000 one.

## Scope note — the CASCADE COMPUTE ENGINE (pure `core/app/`), scored; persistence + ranking version deferred to 4.3

The heart of the product and its most expensive capability (build, inference cost, egress). This story turns the **existing binary-label triage** into the **three-stage scored cascade** of FR-38/AD-18 — a pure computation in `core/app/` that a later story (4.3) wraps to produce the persisted, reproducible ranked order.

**What EXISTS today (verified first-hand — build on it, do not reinvent):**
- The `Judge` **port** ([core/ports/judge.py:17-23](../../apx/core/ports/judge.py#L17-L23)) returning a `Verdict` (`label` ∈ RELEVANT/UNCERTAIN/DISCARD + `rationale`) — **no score, no band, no confidence**.
- The **deterministic tier** `CriteriaJudge` ([adapters/judge/criteria.py](../../apx/adapters/judge/criteria.py)) and the **LLM tier** `LLMJudge` ([adapters/llm_openai_compat/judge.py](../../apx/adapters/llm_openai_compat/judge.py)) — OpenAI-compatible chat over stdlib `urllib` (no SDK, so the egress import-guard has nothing to forbid), Mistral-EU default, key from **env only** (`LLM_API_KEY`/`MISTRAL_API_KEY`, [app.py:657-676](../../apx/api/app.py#L657-L676)), and `CascadeJudge` (criteria→LLM fallback).
- `triage_pieces` ([core/app/triage.py:24-41](../../apx/core/app/triage.py#L24-L41)) → `LabelRecord` via `save_labels` + a `"judge"` audit entry; the `/api/matters/{matter}/judge` endpoint.
- **Exact-`text_key` dedup + families** ([core/domain/dedup.py](../../apx/core/domain/dedup.py) `cluster`/`text_key`; `store.representatives`), members keeping identity/provenance/custodian via the `PieceProvenance`/`PieceCustodian` SET tables.
- **Query-driven semantic NN** over `Chunk.vector` (halfvec `<=>`, Postgres-only) — [core/app/read/semantic.py](../../apx/core/app/read/semantic.py), [semantic_query.py](../../apx/adapters/store_postgres/semantic_query.py).
- Config-as-data: `cascade_stage3_max_share` (default 0.5, [config.py:238-249](../../apx/core/domain/config.py#L238-L249)), `similarity_threshold`, `taxonomy`; `get_config`/`set_config`; the `expansion_bounds(get)`/`chunking_config(get)` value-object-from-getter pattern.
- The 4.1 **`case_theory_version`** — the referenceable text the cascade judges relative to.

**What this story BUILDS (the gaps — pure compute, fully fake-tested; the semantic tier is Postgres-only so its behavioural run is pg-gated, its shape SQLite/fake-tested):**
- **New domain (`core/domain/cascade.py`)**: a `Stage` (1/2/3) enum; a `Band` (confident-relevant / uncertain / confident-discard) enum; an **AD-36 `RejectionClass` StrEnum** (append-only, mirroring `ErrorClass`); a **`PieceJudgement`** carrying `piece_id`, `family_id` + `is_representative`, `stage_reached`, and exactly one outcome — **judged** (a `score` + a `band` + optional stage-3 `label` + `retained_extract_chunk_ids`), **rejected** (a `rejection_class` + kept IN the order, AD-36), or **unscored** (judgement failed, AD-19 — held OUT of the order); and a **`CascadeResult`** (the per-pièce judgements, the `families`, the `unscored` set as its own named count, the **SM-18 `stage3_share`**, and an `over_stage3_floor` flag). Plus the enumerated **intrinsic-signals** set used where no case theory exists.
- **The cascade orchestrator (`core/app/cascade.py`)** — `run_cascade(units, case_theory, scorer, judge, config) -> CascadeResult`: **stage 1** groups near-duplicate families (one representative carries it) and applies the decidable deterministic filters, tagging rejects with an AD-36 class (kept in the order); **stage 2** scores every representative cheaply over the embeddings (cosine to the case-theory vector, or an intrinsic centroid where none) and assigns a band by the config thresholds; **stage 3** spends the LLM **only on the uncertain band** plus a **mandatory calibration sample** of the confident bands; **SM-18** = the measured stage-3 share; a share above `cascade_stage3_max_share` sets `over_stage3_floor`.
- **The AD-19 loud-failure seam** — a cascade-specific judge failure surfaces a *pièce* as **UNSCORED**, in its own named set, **excluded from the order, never imputed to zero, never sorted last** (distinct from the existing `CascadeJudge`, which degrades an outage to in-band UNCERTAIN — correct for the old binary label, wrong for FR-38). Stages 1–2 results survive a stage-3 outage intact.
- **A `SemanticScorer` port** (`core/ports/`) — score a set of *pièces* against a query vector (the case-theory embedding) over the corpus embeddings; a Postgres adapter (reusing the `<=>` + `matter_scope` pre-filter) and a **fake** for tests. Keeps the cascade pure (depends on a port, AD-4).
- **New config-as-data keys** — the stage-2 band thresholds (uncertain-band lower/upper) and the near-duplicate threshold (**value deferred, OQ-4**; the key + its use present), added to `CONFIG_SCHEMA` + the README config block (lockstep).

**What is DEFERRED (honestly — named, not stubbed):**
- **Persistence + the `ranking_version` + the ranked ORDER (FR-39)** — Story 4.3. This story returns a `CascadeResult`; it does **not** persist judgements, add an endpoint, or create a ranking-version entity. (AD-23 binds a `JUDGEMENT` to a `RANKING_VERSION`, which 4.3 creates; the `family_id`/score/rejection-class this story computes are exactly what 4.3 will record.)
- **Derived confidence (FR-42, Story 4.4)** — this story reads **no** model-reported confidence (the `no_model_reported_confidence` gate stays green); the confidence-derivation implementation is 4.4.
- **Taxonomy labels (FR-40, 4.5)**, the **justification surface (FR-41, 4.6)**, **the line (FR-17, 4.7/4.8)**, **pins/validation acts** — untouched.
- **The gold-set recall harness stays a DEFERRAL** — `eval.harness.recall_at_the_line` keeps raising `NotImplementedError` (it needs *the line*, 4.7/4.8); the `ranking_code_requires_the_gold_gate` gate is **already live and green** via *defined + invoked*, and this story keeps both halves intact (must not rename the harness fn or flip the deferral test). No recall figure is fabricated (PRD §7 SM-2).
- **Richer stage-1 filters that need structured metadata not extracted** — document type, participant roles, and **dates against the case theory's period** (the case theory is free text with no structured period; the pieces carry `piece_date` but there is no period to test it against). These defer with a note; the decidable stage-1 work (content-hash/`text_key` dedup + near-dup family grouping + obvious-noise) ships. The **fuzzy** near-duplicate primitive beyond exact `text_key` also defers with its threshold (OQ-4/OQ-21) — the family identifier + representative flag ship (via `text_key` clustering), which is the structural guarantee AD-23 needs; the fuzzy *value* is deferred.

## Acceptance Criteria

1. **The cascade has three stages with configuration-as-data boundaries; the LLM runs only on the uncertain band plus a mandatory calibration sample of the confident bands (FR-38, AD-18).** `run_cascade` gates deterministic filters + family grouping (stage 1) → cheap semantic scoring into bands (stage 2) → LLM judgement **only** on the uncertain band + a configured calibration sample of the confident bands (stage 3). The band thresholds and the calibration-sample size are config-as-data. *(tests: with a fake scorer placing pièces in each band and a spy judge, the judge is invoked on exactly the uncertain band + the calibration sample, never on the rest; moving the thresholds via config moves the band membership.)*

2. **The share of pièces reaching stage 3 is measured and recorded per run (SM-18), and a share above the configured ceiling is flagged (AD-18).** `CascadeResult.stage3_share` = (representatives reaching stage 3) / (all pièces of the matter) — the **cost/egress** share AD-18 defines, so near-duplicate collapsing counts as the saving it is, and a stage-3 call that then fails still counts (it reached the LLM and egressed); `over_stage3_floor` is set when it exceeds `cascade_stage3_max_share`. *(tests: the share is computed correctly across band splits; a wide uncertain band that pushes the share over the ceiling sets the flag; the default config keeps the cascade ON, i.e. share < 1.)*

3. **Near-duplicate families are grouped and judged as a family — one representative carries it, members retain their own identity, provenance and custodian — and the family identifier travels in the result (FR-38, AD-18, AD-23).** Stage 1 groups pièces into families; the representative is judged; each `PieceJudgement` carries its `family_id` and `is_representative`; members are neither re-judged nor counted as independent, and their identity/provenance/custodian are untouched. *(tests: forty near-copies of one thread form one family with one representative judged once; members carry the family id and are not sent to stage 3; the representative's outcome is the family's.)*

4. **Model-provider failure during judgement halts loudly and never imputes: an UNCERTAIN pièce whose sole judgement is the LLM becomes UNSCORED — in its own named set, excluded from the order, never scored zero, never sorted last — and stages 1–2 survive (FR-38, AD-19, AD-36).** A judge failure (timeout / unavailable / malformed) on an **uncertain** *pièce* places it in `CascadeResult.unscored` (its own count), **not** in the judged order and **not** at score zero; the stage-1/stage-2 outcomes of every other *pièce* are intact; a stage-1/stage-2 **rejection** (an AD-36 `rejection_class`) keeps the *pièce* IN the order, never in the unscored set. **A CONFIDENT pièce sampled only for calibration keeps its stage-2 judgement on a failure** — recall-first (a non-negotiable): a failed calibration call never drops a confidently-relevant *pièce* from the order (the outage still surfaces via the uncertain-band unscored set and SM-18). *(tests: a failing judge on an uncertain representative yields one unscored pièce and leaves the rest judged; a calibration-sampled confident pièce survives a judge failure as judged-at-stage-2, in the order; a stage-1 reject is in the order with its class, not unscored; no imputed/zero score is ever assigned on failure.)*

5. **Where a case theory exists the judgement is relative to it and the retained extracts are recorded; where none exists it is relative to an enumerated, named intrinsic-signal set, and the result says which (FR-38).** The cascade takes the 4.1 case theory (or its absence); stage 2/3 score relative to it and record the `retained_extract_chunk_ids` the judgement used; with no case theory the result is marked `intrinsic` and carries the named signal set. *(tests: with a case theory, the scorer is queried with its text and the judged pièces carry retained-extract chunk ids; with none, the result is flagged intrinsic and names the signals; the two are never conflated.)*

6. **The relevance judgement reads no model-reported confidence, and the gold-set merge gate stays green (FR-42, AD-34).** Stage 3 parses only the label/rationale (and derives the band from the cascade, never from a self-reported number); `python -m apx.checks` stays green — `no_model_reported_confidence` (FR-42) and `ranking_code_requires_the_gold_gate` (AD-34) both pass, the latter with `recall_at_the_line` still defined + invoked (the deferral intact). *(tests: the structural checks are green; a fixture reading a `confidence` field off a model response would fire `no_model_reported_confidence`; the recall deferral test is unchanged.)*

## Tasks / Subtasks

- [x] **Task 1 — The cascade domain (`core/domain/cascade.py`) (AC: 1, 3, 4, 5).**
  - [x] `Stage(IntEnum)` (STAGE_1/2/3); `Band(StrEnum)` (confident_relevant / uncertain / confident_discard); `RejectionClass(StrEnum)` — the AD-36 enumerated classes for what stage 1/2 can decide (e.g. `exact_duplicate_member`, `noise`, and a reserved set for the deferred filters), **append-only, mirroring `core/domain/failures.py::ErrorClass`**; an `IntrinsicSignal` enumeration (document-type / participant-roles / date-distribution / duplication / obvious-noise — the named set FR-38 requires where no case theory exists).
  - [x] Frozen dataclasses: `PieceJudgement` (`piece_id`, `family_id`, `is_representative`, `stage_reached`, and exactly one of: judged → `score: float` + `band` + `label: str | None` + `retained_extract_chunk_ids: tuple[str, ...]`; rejected → `rejection_class`; unscored → `failure_reason`); a small tagged shape (e.g. an `outcome` discriminant) so "judged / rejected / unscored" is exhaustive and mutually exclusive. `CascadeResult` (`judgements: tuple[PieceJudgement, ...]`, `families: Mapping[str, tuple[str, ...]]`, `unscored: tuple[str, ...]`, `stage3_share: float`, `over_stage3_floor: bool`, `basis: "case-theory" | "intrinsic"`).
  - [x] Tests (`tests/domain/`): the enums are stable/append-only; a `PieceJudgement` cannot be simultaneously judged and unscored; a rejected pièce is not in the unscored set.

- [x] **Task 2 — The `SemanticScorer` port + fake + Postgres adapter (AC: 1, 5).**
  - [x] `core/ports/` — a `SemanticScorer` protocol: `score(*, tenant, matter, scopes, query_text | query_vector, piece_ids) -> Mapping[str, float]` (a cosine-ish score per pièce over its chunks; higher = closer). Pure port; the cascade depends on it (AD-4).
  - [x] A Postgres adapter reusing the `<=>` operator + the `matter_scope` scope pre-filter (aggregate per pièce, e.g. max cosine over its chunks to the query vector). Postgres-only, like `semantic_query.py`; behavioural test pg-gated.
  - [x] A **fake** under `tests/` (mirroring `tests/embedding_fakes.py::FakeEmbedder`) returning canned per-pièce scores, so the cascade is tested deterministically without a DB.

- [x] **Task 3 — The cascade orchestrator (`core/app/cascade.py`) (AC: 1, 2, 3, 4, 5).**
  - [x] `run_cascade(units, *, case_theory, scorer, judge, config_get) -> CascadeResult`. **Stage 1**: group families (reuse `dedup.cluster`/`text_key`; representative = the cluster rep), tag decidable rejects with an AD-36 class (kept in the order); members inherit the family, are not judged. **Stage 2**: `scorer.score(...)` every representative vs the case-theory vector (or an intrinsic centroid where none); assign a `Band` by the config thresholds. **Stage 3**: send **only** the uncertain band + a config-sized **calibration sample** of the confident bands to `judge`; record the `retained_extract_chunk_ids` (the pièce's chunk ids — the judge reads the whole pièce text, so all its chunks are the extracts it used; a narrower highest-scoring subset is deferred with the richer-extract tier). Compute `stage3_share` (SM-18) and `over_stage3_floor` vs `cascade_stage3_max_share`. Set `basis` and, where intrinsic, the named signals.
  - [x] The AD-19 seam: a judge failure on a pièce → `unscored` (never a judged outcome, never score 0); stages 1–2 intact. Do **not** reuse `CascadeJudge` (it degrades to in-band UNCERTAIN); the cascade calls the raw `judge` and maps a failure/timeout/malformed verdict to unscored. Read only `label`/`rationale` from the verdict — never a confidence (FR-42).
  - [x] Tests (`tests/app/`): stage gating (spy judge sees only uncertain + sample); SM-18 share + over-floor; families (one rep judged, members carried); the failure path (one unscored, rest intact, no imputation); case-theory vs intrinsic basis; config thresholds move band membership.

- [x] **Task 4 — Config-as-data: the stage-boundary + near-duplicate keys (AC: 1, 2).**
  - [x] Add to `core/domain/config.py::CONFIG_SCHEMA`: the stage-2 band thresholds (`cascade_uncertain_low` / `cascade_uncertain_high`, floats, `affects_retrieval=True`, `preserves_guarantee` keeping stage 3 non-empty-and-not-everything), a `cascade_calibration_sample` size, and a `near_duplicate_threshold` (**value deferred, OQ-4** — a sensible default that reduces to exact `text_key` grouping, documented as deferred). Reuse `cascade_stage3_max_share`. Mirror the `expansion_bounds(get)` value-object pattern for reading them.
  - [x] Update the README config-keys reference block (the `documented_config_keys_exist` / `config_reference_is_complete` meta-checks require lockstep). Tests: each new key round-trips through `get_config`/`set_config` and its guarantee-preserving validator holds.

- [x] **Task 5 — Gate + regression + the gold-gate invariant (AC: 6).**
  - [x] `ruff check apx tests` clean (line-length 100); full `pytest` green (`export PATH="$PWD/.venv/bin:$PATH"`; **never** export `DATABASE_URL`); `python -m apx.checks` all green — specifically confirm `no_model_reported_confidence` (FR-42) and `ranking_code_requires_the_gold_gate` (AD-34) pass, with `eval.harness.recall_at_the_line` **unchanged** (still `NotImplementedError`) and its deferral test (`tests/eval/test_corpus_ingest.py`) **unchanged**. No new dependency (`uv add` only if truly needed — none expected; the cascade is stdlib + existing ports).
  - [x] Confirm no Postgres-only code runs on SQLite in tests (the scorer's behavioural run is pg-gated; its shape is fake-tested), and that the existing `/judge` endpoint + `triage_pieces` + `LabelRecord` are **untouched** (no regression to the current binary triage).

## Dev Notes

### The scope boundary with 4.3 — pure compute, no persistence

This story is the **algorithm**; Story 4.3 is the **persisted, reproducible ranked order + `ranking_version`**. Per the work breakdown (U15) and AD-23, a `JUDGEMENT` binds to a `RANKING_VERSION` that does not exist yet — so `run_cascade` **returns** a `CascadeResult` and persists nothing. Everything this story computes (`family_id`, `score`, `rejection_class`, `band`, `retained_extract_chunk_ids`, the unscored set, `stage3_share`) is exactly what 4.3 will record against a version. Do **not** create a ranking/judgement table, an endpoint, or a version entity here — that is the classic over-build, and AD-23's conditional-commit needs the version this story does not have.

### AD-36 — two sets, never a third; unscored ≠ zero (the correctness heart)

[ARCHITECTURE-SPINE AD-36:1007-1027](../../_bmad-output/planning-artifacts/architecture/architecture-apx-mvp-2026-07-21/ARCHITECTURE-SPINE.md#L1007-L1027) + [AD-19:559-578](../../_bmad-output/planning-artifacts/architecture/architecture-apx-mvp-2026-07-21/ARCHITECTURE-SPINE.md#L559-L578): every *pièce* is at all times in exactly **one of two** sets — **the ranked order** (carrying its rejection reason as an enumerated class if a cheap filter kept it out of judgement) or the explicit **UNSCORED** set (its judgement *failed*). **A stage-1/stage-2 rejection is NOT unscored** — it is in the order with its class. **UNSCORED holds only judgement failures.** A *pièce* the model could not judge is **never** scored zero, **never** ranked last, **never** dropped from the population a future *confidence bound* reports on. This is the single most important invariant: get the "rejected (in order, with class) vs unscored (out of order, failure)" distinction exactly right, and make it exhaustive + mutually exclusive in the domain type. The current `LLMJudge` returns UNCERTAIN on an outage ([judge.py:78-79](../../apx/adapters/llm_openai_compat/judge.py#L78)) — correct for the old in-band label, **wrong here**; the cascade must map a failure to unscored, not to a band member.

### The gold gate is ALREADY LIVE — do not break the deferral

[checks/gold_gate.py](../../apx/checks/gold_gate.py) `ranking_code_requires_the_gold_gate` is **not** vacuous (the manifest's "vacuous until Epic 4" note is stale): `apx/api/app.py` already imports the `Judge` port + `triage_pieces`, so a ranking site exists, and the gate passes only because [eval/harness.py](../../eval/harness.py) **defines** `recall_at_the_line` and a test **invokes** it. `recall_at_the_line` currently **raises `NotImplementedError("…ranker…")`** (it needs *the line*, 4.7/4.8), and `tests/eval/test_corpus_ingest.py` asserts that deferral. **Keep both.** This story adds cascade code (which stays a ranking site — no change to the trigger) but does **not** implement *the line*, so the harness stays deferred and the gate stays green. Do NOT rename `recall_at_the_line`, and do NOT fabricate a recall figure (PRD §7 SM-2: the metric that matters is that it *runs* — which happens when *the line* lands).

### FR-42 — never read a self-reported confidence

[checks/forward_looking.py](../../apx/checks/forward_looking.py) `no_model_reported_confidence` fires on reading a `confidence`/`certainty`/… field off a subject named `response`/`verdict`/`judgment`/`completion`/… . The current `_parse` reads only `label`/`rationale` ([judge.py:38-46](../../apx/adapters/llm_openai_compat/judge.py#L38-L46)) — keep it that way. The band/score are the cascade's own (stage-2 cosine + thresholds), never a number the model states about itself. Confidence derivation is 4.4.

### Reuse, don't reinvent — the existing seams

- Families: `core/domain/dedup.py::cluster` + `text_key` ([dedup.py:38-103](../../apx/core/domain/dedup.py)); members keep provenance/custodian via the SET tables (already true). The **fuzzy** tier is explicitly deferred by that module's own docstring; keep the exact-`text_key` family with a config threshold whose value is deferred (OQ-4).
- Semantic: the `<=>` cosine + `matter_scope` pre-filter in [semantic_query.py:42-64](../../apx/adapters/store_postgres/semantic_query.py#L42-L64); Postgres-only. The new per-pièce scorer aggregates chunk cosines to the case-theory vector — new code, same operator.
- Judge: the `Judge` port + `LLMJudge` transport seam (inject a `transport` in tests) + the `_judge(store, tenant)` composition ([app.py:657-676](../../apx/api/app.py#L657-L676)). The LLM key is **env-only** (`LLM_API_KEY`/`MISTRAL_API_KEY`) — NEVER written to the repo; `model_endpoint`/`model_name` are config-as-data, `model_provider` recorded-not-branched (AD-27).
- Config: mirror `expansion_bounds(get)` / `chunking_config(get)` ([config.py:294-323](../../apx/core/domain/config.py#L294-L323)) — a value object built from a per-key getter.

### The case theory's period problem (an honest deferral)

FR-38 stage 1 lists "dates against the *case theory* period." The 4.1 case theory is **free text** with no structured period, and there is no period-extraction. So the date-vs-period filter, document-type and participant-role filters **defer** (they need structured metadata not extracted). Stage 1 ships the decidable filters (dedup/families + obvious-noise). Record this in the `RejectionClass` enum as reserved-for-later classes, so 4.x can add them without a schema change.

### Testing standards

pytest; `tests/` mirrors the package. Fake the judge (a `_FixedJudge`/`_Spy` per [tests/app/test_triage.py](../../tests/app/test_triage.py) + a **failing** judge for the unscored path) and the scorer (mirror `tests/embedding_fakes.py`), plus an in-memory config getter — the cascade is tested deterministically with **no network and no DB**. The Postgres scorer's behavioural run is pg-gated (like the semantic tests). Run: `export PATH="$PWD/.venv/bin:$PATH"; pytest`; **never** export `DATABASE_URL`. `ruff` line-length 100. Structural checks: `python -m apx.checks`.

### Project Structure Notes

- New: `apx/core/domain/cascade.py`, `apx/core/app/cascade.py`, `apx/core/ports/` scorer port, an `apx/adapters/store_postgres/` scorer adapter, tests under `tests/domain/`, `tests/app/`, `tests/adapters/`, a scorer fake under `tests/`.
- Updated: `apx/core/domain/config.py` (+ README config block, lockstep).
- Untouched (no regression): `core/app/triage.py`, the `/judge` endpoint, `LabelRecord`/`save_labels`, `eval/harness.py`, the gold-gate deferral test.
- Naming: glossary terms only (*pièce*, *matter*, *case theory*, *cascade*, *unscored*, *family*). Communication French; code/docs/commits English; French legal terms of art stay French.

### References

- [epics.md:1110-1124](../../_bmad-output/planning-artifacts/epics.md#L1110-L1124) — Story 4.2 ACs; [1085-1108](../../_bmad-output/planning-artifacts/epics.md#L1085-L1108) 4.1 (done); [1126-1152](../../_bmad-output/planning-artifacts/epics.md#L1126-L1152) 4.3/4.4 (the deferred boundary).
- PRD: [FR-38 (803-813)](../../_bmad-output/planning-artifacts/prds/prd-apx-mvp-2026-07-20/prd.md#L803-L813), [FR-39 (815-825)](../../_bmad-output/planning-artifacts/prds/prd-apx-mvp-2026-07-20/prd.md#L815-L825) (deferred), [FR-42 (849-857)](../../_bmad-output/planning-artifacts/prds/prd-apx-mvp-2026-07-20/prd.md#L849-L857) (deferred).
- ARCHITECTURE-SPINE: AD-18 [530-557](../../_bmad-output/planning-artifacts/architecture/architecture-apx-mvp-2026-07-21/ARCHITECTURE-SPINE.md#L530-L557), AD-19 [559-578](../../_bmad-output/planning-artifacts/architecture/architecture-apx-mvp-2026-07-21/ARCHITECTURE-SPINE.md#L559-L578), AD-36 [1007-1027](../../_bmad-output/planning-artifacts/architecture/architecture-apx-mvp-2026-07-21/ARCHITECTURE-SPINE.md#L1007-L1027), AD-34 [966-980](../../_bmad-output/planning-artifacts/architecture/architecture-apx-mvp-2026-07-21/ARCHITECTURE-SPINE.md#L966-L980), AD-27 [758+](../../_bmad-output/planning-artifacts/architecture/architecture-apx-mvp-2026-07-21/ARCHITECTURE-SPINE.md#L758), AD-11/AD-4/AD-45.
- Code: [core/ports/judge.py](../../apx/core/ports/judge.py), [core/domain/triage.py](../../apx/core/domain/triage.py), [core/app/triage.py](../../apx/core/app/triage.py), [adapters/judge/criteria.py](../../apx/adapters/judge/criteria.py), [adapters/llm_openai_compat/judge.py](../../apx/adapters/llm_openai_compat/judge.py), [core/domain/dedup.py](../../apx/core/domain/dedup.py), [core/domain/failures.py](../../apx/core/domain/failures.py) (the `ErrorClass` StrEnum pattern), [semantic_query.py](../../apx/adapters/store_postgres/semantic_query.py), [config.py](../../apx/core/domain/config.py), [checks/gold_gate.py](../../apx/checks/gold_gate.py), [eval/harness.py](../../eval/harness.py), [tests/embedding_fakes.py](../../tests/embedding_fakes.py).

## Dev Agent Record

### Agent Model Used

claude-opus-4-8 (1M context)

### Debug Log References

- Gate green: `ruff check apx tests` clean · `python -m apx.checks` → **59** checks pass (the gold-gate `ranking_code_requires_the_gold_gate` and `no_model_reported_confidence` both green, config-key lockstep green) · full `pytest` → **1022 passed, 12 skipped** (+20 new, no regressions).
- New tests: `tests/domain/test_cascade.py` (5), `tests/domain/test_cascade_config.py` (5), `tests/app/test_cascade_run.py` (8), `tests/adapters/test_scorer.py` (2).

### Completion Notes List

- **Pure compute engine delivered**: `core/domain/cascade.py` (the `Stage`/`Band`/`RejectionClass`/`IntrinsicSignal`/`Outcome` enums + the tagged `PieceJudgement` with exhaustive/mutually-exclusive `__post_init__` validation + `CascadeResult`), `core/app/cascade.py::run_cascade` (three stages, SM-18, the AD-19 failure seam), the `SemanticScorer` port + its Postgres adapter + a fake. **No persistence, no endpoint, no ranking_version** — 4.3's concern. The existing `/judge` endpoint, `triage_pieces`, `LabelRecord`, and `eval/harness.py` are untouched (no regression; the gold-gate deferral test is unchanged).
- **AD-36/AD-19 exactly**: a stage-1 family member is **REJECTED** (`exact-duplicate-member`) and stays IN the order; a judge **failure** (any exception) makes the pièce **UNSCORED** — out of the order, never scored zero, never sorted last, never imputed. The domain type makes judged/rejected/unscored exhaustive + mutually exclusive.
- **AD-19 failure seam decision**: `run_cascade` treats a judge **exception** as unscored — it does NOT reuse `CascadeJudge` (which degrades an outage to in-band UNCERTAIN, correct for the old binary label but wrong for FR-38). The real *raising* judge adapter is 4.3's wiring; the existing `LLMJudge`'s swallow-to-UNCERTAIN is left untouched (no regression to the current triage). Tested with a `FailingJudge` fake.
- **FR-42 honoured**: stage 3 reads only the verdict `label` — never a self-reported confidence; the `no_model_reported_confidence` gate stays green. Confidence derivation is 4.4.
- **SM-18 denominator = all pièces** (`len(units)`), not just eligible representatives — so near-duplicate collapsing counts as the cost saving it is (40 near-copies judged once → a low share). `over_stage3_floor` = share > `cascade_stage3_max_share`.
- **DEVIATION from Task 4 (documented)**: the `near_duplicate_threshold` config key was **NOT added**. The fuzzy near-duplicate primitive is deferred (OQ-4), so a threshold key would be a knob that does nothing (any value below 1.0 would still do exact `text_key` grouping) — a misleading "configurable" surface. Family grouping is exact-`text_key` (the structural guarantee AD-23 needs — family id + representative flag ship); the fuzzy tier + its key land together in a later story. The three keys that ARE used shipped: `cascade_uncertain_low`/`_high` (band boundaries) + `cascade_calibration_sample` (mandatory, default 20).
- **Intrinsic path (no case theory)**: no cheap relevance query exists, so every representative is UNCERTAIN and judged (up to the ceiling), and the result is marked `basis="intrinsic"` naming the signal set — honest (a matter with no case theory legitimately needs more LLM judgement, and the ranking says so).
- **Reserved `RejectionClass` values** (`out-of-period`, `non-matching-type`, `non-participant`, `obvious-noise`) are declared now (append-only) so the deferred stage-1 filters — which need structured metadata not extracted — add without a schema change.

### File List

- `apx/core/domain/cascade.py` (NEW) — the cascade vocabulary (enums + `PieceJudgement` + `CascadeResult` + `CascadeUnit`).
- `apx/core/app/cascade.py` (NEW) — `run_cascade`, the three-stage orchestrator.
- `apx/core/ports/scorer.py` (NEW) — the `SemanticScorer` port.
- `apx/adapters/store_postgres/scorer.py` (NEW) — `piece_scores_stmt` + `PgSemanticScorer` (Postgres max-cosine).
- `apx/core/domain/config.py` (UPDATE) — the three cascade band/calibration keys + `CascadeConfig` value object + `cascade_config(get)`.
- `README.md` (UPDATE) — the three new config-keys rows (lockstep).
- `tests/scoring_fakes.py` (NEW), `tests/domain/test_cascade.py` (NEW), `tests/domain/test_cascade_config.py` (NEW), `tests/app/test_cascade_run.py` (NEW), `tests/adapters/test_scorer.py` (NEW).
- `_bmad-output/implementation-artifacts/sprint-status.yaml` (UPDATE) — 4-2 status.

## Change Log

| Date | Change |
| --- | --- |
| 2026-08-04 | Story 4.2 created (ready-for-dev) — the three-stage scored cascade compute engine. |
| 2026-08-04 | Implemented: the cascade domain (AD-36/AD-19 tagged outcome), the `run_cascade` orchestrator (family grouping → cheap scoring → LLM on the uncertain band + calibration sample), SM-18 share, the unscored failure seam, the `SemanticScorer` port + pg adapter + fake, the stage-boundary config keys. Pure compute (no persistence/endpoint/ranking_version — 4.3). `near_duplicate_threshold` key deferred (fuzzy tier deferred). Gate green (ruff · 59 checks incl. gold-gate + FR-42 · 1022 passed/12 skipped). Status → review. |
| 2026-08-04 | Adversarial Workflow review (3 lenses + per-finding skeptic-verify): **10 findings → 0 confirmed / 10 refuted** (the code was found faithful to AD-18/19/36/34 + FR-42, the gold-gate deferral intact, no regression). One refuted finding surfaced a genuine tension with the **recall-first non-negotiable** — I made the stronger design anyway: a stage-3 **calibration** failure on a **confident** pièce now keeps its stage-2 judgement (only an *uncertain* pièce, whose sole judge is the LLM, goes unscored), so a transient outage never drops a confidently-relevant pièce from the order. Aligned three doc-vs-code wording nits the review surfaced (SM-18 denominator = all pièces per AD-18; retained-extracts = the whole pièce's chunks). Re-gate green (ruff · 59 checks · 1023 passed/12 skipped). |
