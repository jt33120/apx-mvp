---
baseline_commit: 832a67f
---

# Story 4.3: The ranked order and the reproducible ranking version

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a lawyer who may have to defend a ranking in front of a court,
I want one ranked order per *matter* that reproduces exactly from its recorded version, with a specified tie-break,
so that "reconstructible from the *audit record* alone" is true, not aspirational.

## Scope note — the RANKING ACT: identity + deterministic order + persistence (wraps the 4.2 cascade)

Story 4.2 delivered the **pure cascade compute engine** (`apx/core/app/cascade.py::run_cascade` →
`CascadeResult`), which persists nothing. Story 4.3 **wraps** it into the *ranking act*: it turns a
`CascadeResult` into **exactly one deterministic ranked order**, records the complete **immutable
ranking-version identity** (AD-23) that produced it, and **persists** the version + the per-*pièce*
ranked rows atomically with one audit entry (AD-22/AD-37), against a *matter*.

**This story's spine is REPRODUCIBILITY, not a relevance policy.** The load-bearing guarantees are:
one order, a version identity that names every input, a **deterministic tie-break over the *pièce*
identity hash** (collation-independent), and a persisted order that reconstructs *pièce* for *pièce*.
The *relevance ordering* itself is the honest, minimal ladder derived from the cascade's own
bands/labels/scores — it is **not** the confidence derivation (4.4), the taxonomy label (4.5), the
evidence justification (4.6), **the line** (4.7/4.8) or re-ranking staleness (4.13).

**IN scope:** (1) a pure Domain `ranking.py` — the `RankingVersion` identity value object + its
deterministic id/fingerprint, and `rank_cascade(result)` the pure deterministic ordering; (2) the
persistence — a `RankingVersion` table + a `RankedEntry` table (append-only, **no retained/discarded
column**, AD-39), migration 0024, and the ONE owning store use case `record_ranking` (AD-37); (3) a
thin `core/app` orchestrator `produce_ranking` (the *explicit act*, FR-39 "fails loudly rather than
producing an arbitrary order") wired to the cascade + a new `RankingRecorder` port; (4) two new
structural checks (append-only; no retained/discarded set column).

**OUT of scope (do NOT build):** **the line** and its priced move (4.7–4.9); the *retained/discarded
set* as anything storable (AD-39 forbids it — they are views, later); per-*pièce* confidence (4.4);
taxonomy labelling (4.5); justification/evidence extracts (4.6); the *pin* (4.11); re-rank triggers &
staleness materialisation (4.13); any UX surface (needs a UX pass). No `retained_extract_chunk_ids`
persistence (that is 4.6's evidence). The `supersedes` per-*pièce* state is recorded structurally but
is always `false` until the AD-8 superseding transition is built (documented deferral).

## Acceptance Criteria

**AC-1 (FR-39 / AD-23 — one order + the full version identity).** A ranking act produces **exactly
one** ranked order per *matter* plus a *ranking version* recording the complete immutable identity of
what produced it: *case theory* version id (or `None` + `basis="intrinsic"`), model identity (provider,
endpoint, name), prompt version, temperature **and every sampling parameter**, cascade configuration
(the four band/sample/ceiling numbers), embedder identity (model_id + model_version), chunking
configuration version, schema version, **and the near-duplicate grouping identity**. The version's
`version_id` is deterministic and referenceable; a `fingerprint` hash over the identity inputs alone
makes "the same ranking version" queryable.

**AC-2 (FR-39 / AD-23 — reproducible *pièce* for *pièce*).** Re-running a fixed *ranking version* over
a fixed *corpus* reproduces the same order, *pièce* for *pièce*, asserted by test. Because the model is
non-deterministic at the configured temperature, the *ranking version*'s ranked rows **record the
scores** (and the cascade label reached), so the order is reconstructible from the record even where
the judgement is not repeatable. `rank_cascade` is a **pure deterministic function** of the cascade
outputs + *pièce* identity hashes.

**AC-3 (FR-39 / AD-23 — the deterministic, recorded, collation-independent tie-break).** Ties are
broken by a **stable key recorded in the *ranking version*** — the *pièce* identity hash, compared in
**byte order**, never the order a store returned and never collated text. Asserted by test: the same
*ranking version* over the same *corpus* produces the **same order under two different `LC_COLLATE`
settings** (the order is computed in Python over the ASCII-hex *pièce* id and stored as an integer
rank; no read uses SQL collation to order).

**AC-4 (AD-23 recorded output + AD-36 — the two sets, never a third).** Each ranked row carries: its
**rank**; its **score OR** the enumerated **rejection class** that kept it out of judgement (AD-36);
its **near-duplicate family id and whether it was the family's judged representative**; its outcome;
its cascade band/label where judged; and its (always-`false`-for-now) `supersedes` state. The
**UNSCORED** set (AD-19 — the judgement *failed*) is recorded as its own named set, **carries no rank**,
is **never ranked last and never dropped** from the population, and near-duplicate **REJECTED** members
stay **in** the order carrying their class (AD-36). No row, column or table names a *retained* or
*discarded* set (AD-39).

**AC-5 (AD-22 / AD-37 — the owning act: atomic, append-only, conditional commit).** The version + its
ranked rows + **one** audit entry (`ranking_recorded`) are written by **exactly one** owning use case,
**atomic** (all commit or none). `version_no` is per-*matter* monotonic; a concurrent double-write
collides on `(tenant, matter, version_no)` and **fails loudly**, never a silent overwrite. A *ranking
version* is **never mutated after creation** (asserted by a structural append-only check). The commit
is **conditional** (AD-37/AD-23): it re-reads the *matter*'s latest *case-theory* version inside the
write transaction and **refuses to commit** (typed error, nothing written) if it differs from the one
recorded in the identity — a ranking is never silently committed over a case theory that changed under
it.

**AC-6 (AD-12/AD-13 — tenant isolation, scope pre-filter, non-disclosing).** Reads (`read_ranking`,
`list_ranking_versions`, `read_ranked_order`) resolve scope from `matter_scope` at query time and
pre-filter; an out-of-scope or absent *matter* returns `None`/empty **indistinguishably** (a
non-disclosing 404, FR-14), never a disclosure. Tenant is pinned on every query.

**AC-7 (FR-39 — fails loudly, never an arbitrary order).** A ranking that cannot be produced fails
loudly rather than emitting an arbitrary order: `produce_ranking` raises a typed error when there is
**no in-order *pièce*** to rank (an empty ranking is not a silent empty artefact) and when a required
identity input is missing. The failure names the reason.

## Tasks / Subtasks

- [x] **Task 1 — Domain: the ranking vocabulary (`apx/core/domain/ranking.py`, NEW).** (AC-1, AC-2, AC-3, AC-4)
  - [x] `RankingIdentity` frozen dataclass — every AD-23 input: `case_theory_version_id: str | None`,
    `basis: str`, `model_provider/model_endpoint/model_name: str`, `prompt_version: str`,
    `temperature: float`, `sampling: Mapping[str, float | int | str]` (top_p, max_tokens, seed, … —
    "every sampling parameter"), the four cascade numbers, `embedder_model_id/embedder_model_version`,
    `chunking_config_version`, `schema_version`, `grouping_identity`, `tie_break: str`. A canonical
    JSON (sorted keys, stable separators — reuse `config.dumps_value`'s shape) → `fingerprint =
    sha256(canonical_json)`. Validate no required field is blank (raise `ValueError` — AC-7).
  - [x] `RankingVersion.build(*, tenant, matter, version_no, identity, created_at)` → carries a
    `version_id = sha256(tenant \0 matter \0 version_no \0 fingerprint)` (the 4.1 id shape) — the
    referenceable, collision-free row identity; and exposes the `fingerprint` for "same version".
  - [x] `RankedRow` frozen dataclass — `piece_id, rank: int, family_id, is_representative: bool,
    outcome: Outcome, score: float | None, band: Band | None, label: str | None, rejection_class:
    RejectionClass | None, supersedes: bool = False`.
  - [x] `RankedOrder` frozen dataclass — `rows: tuple[RankedRow, ...]` (rank-ordered, judged+rejected
    only), `unscored: tuple[str, ...]`. Add `is_consistent()` (ranks are `1..len(rows)` contiguous;
    unscored disjoint from ranked; every family contiguous).
  - [x] `rank_cascade(result: CascadeResult) -> RankedOrder` — the PURE deterministic ordering:
    - Group by `family_id`; the **representative** carries the family's judgement (find it in
      `result.judgements` where `is_representative`).
    - Family anchor sort key = `(relevance_tier(rep), neg_score(rep), rep.piece_id)`. `relevance_tier`
      is the minimal honest ladder: band-first then label — confident-relevant(0) < uncertain-relevant(10)
      < uncertain-uncertain(11) < uncertain-discard(12) < confident-discard(21); a judged rep with no
      stage-3 label uses the neutral middle. `neg_score` = `-score` where a score exists, else a fixed
      sentinel so the intrinsic path (all `score=None`) falls through to the hash tie-break.
    - Order families by anchor; **within** a family the representative sorts first, then REJECTED
      members by `piece_id` (byte order). Flatten → assign `rank = 1..N`.
    - **UNSCORED** pièces are excluded from `rows` and collected into `unscored` (AC-4/AD-19).
    - **All comparisons that break ties use `piece_id` (ASCII hex) directly** — codepoint order ==
      byte order, locale-independent (AC-3). Never sort by any text that a collation could reorder.
  - [x] Constants: `PROMPT_VERSION` (the cascade question's version — bump when
    `cascade._INTRINSIC_QUESTION` or the case-theory question changes), `GROUPING_IDENTITY`
    (`"exact-text-key-v1"` — the `dedup.text_key` grouping; AD-23 "a change to the grouping threshold
    produces a new version"), `TIE_BREAK = "piece-id-hash"`.

- [x] **Task 2 — Persistence models + migration 0024.** (AC-1, AC-4, AC-5, AD-31, AD-7, AD-39)
  - [x] `apx/adapters/store_postgres/models.py` — `RankingVersion` table (`__tablename__ =
    "ranking_version"`): `id` (=version_id) PK; `tenant`/`matter` plaintext (query keys, AD-12);
    `version_no` Integer (per-matter, 1-based, monotonic — AD-49 ordering); `fingerprint` String(64);
    `identity_json` String (the canonical identity — **plaintext**: it is structural version metadata
    readable in the interface & the content-free projection per NFR-56, contains NO PII/content, like
    `schema_version`); `case_theory_version_id` String nullable (the referenced 4.1 identity, for the
    conditional-commit check); `created_at`. `UniqueConstraint(tenant, matter, version_no)`; composite
    `ForeignKeyConstraint((tenant, matter) → matter_scope)` **no ondelete** (AD-7). Model this on
    `CaseTheoryVersion` (Story 4.1) exactly.
  - [x] `RankedEntry` table (`__tablename__ = "ranked_entry"`): `id` PK = `sha256(ranking_version_id \0
    piece_id)`; `ranking_version_id` String(64) `ForeignKey("ranking_version.id")` **no ondelete**
    (AD-7), indexed; `tenant`/`matter` plaintext; `piece_id` String(64); `rank` Integer **nullable**
    (NULL == the unscored set — no rank, AC-4/AD-19); `outcome` String; `score` Float nullable;
    `band` String nullable; `label` String nullable; `rejection_class` String nullable; `family_id`
    String(64); `is_representative` Boolean; `supersedes` Boolean default False. **All plaintext**:
    none is content/PII (band/label/outcome/rejection_class are categorical, score is a float,
    family_id is a text_key hash) — like `LabelRecord` which encrypts only its rationale. **No
    `retained`/`discarded` column** (AD-39). `UniqueConstraint(ranking_version_id, piece_id)`.
  - [x] Migration `0024_ranking_version.py` (NEW) — `down_revision = "0023_case_theory_version"`;
    `create_table` both; **no backfill** (nothing to seed — ranking did not exist); `downgrade` drops
    both (child `ranked_entry` first). No re-index / no corpus mutation side effect (NFR-56).

- [x] **Task 3 — The owning store use case + reads (`store.py`).** (AC-5, AC-6, AC-2)
  - [x] `record_ranking(*, tenant, matter, actor, version: RankingVersion, order: RankedOrder) ->
    RankingVersionView` — the ONE owning use case (AD-37). Inside `_audited_tx`: (a) load `matter_scope`
    (unknown matter → `ValueError`); (b) **conditional commit** — re-read the matter's latest
    `CaseTheoryVersion.id`; if it differs from `version.identity.case_theory_version_id`, raise a typed
    `StaleRankingInput` (nothing written, AC-5); (c) compute `version_no = prev_max + 1`; (d) insert the
    `RankingVersion` row + all `RankedEntry` rows (ranked rows carry their integer rank; unscored rows
    carry `rank=NULL`); (e) write ONE audit entry `ranking_recorded` with detail
    `version={version_no} fingerprint={…} pieces={n} unscored={m} stage3_share=…` ATOMIC with the write
    (AD-22). The `(tenant, matter, version_no)` unique constraint makes a concurrent double-write fail
    loudly and retry, never overwrite (AD-37). NEVER updates/deletes an existing version (append-only).
  - [x] Persist the **whole** cascade population: ranked rows (`order.rows`) **and** the unscored set
    (one `RankedEntry` per unscored piece_id with `rank=NULL`, `outcome="unscored"`), so the record is
    the complete population (AD-36 — nothing dropped). Derive each unscored row's `family_id`/outcome
    from `result` via the `order`/version (pass enough through, or record unscored rows from the
    judgements — keep it faithful; unscored rows carry no score/band/label/rejection_class).
  - [x] Reads (scope pre-filtered, non-disclosing — copy the `read_case_theory` shape exactly, AC-6):
    `read_ranking(*, tenant, matter, scopes)` → latest `RankingVersionView | None`;
    `list_ranking_versions(...)` → ascending history or `None`; `read_ranked_order(*, tenant, matter,
    scopes, version_no=None)` → the ordered `RankedEntry` views for a version (latest if `None`) or
    `None`. `read_ranked_order` **ORDER BY rank** (the integer — collation-independent), unscored rows
    (rank NULL) returned in a named tail, never interleaved into the order.
  - [x] DTOs: `RankingVersionView` (version_no, version_id, fingerprint, basis, created_at, counts),
    `RankedEntryView`. Add `StaleRankingInput(Exception)` near `ScopeConflict`.

- [x] **Task 4 — The port + the orchestrator (the explicit act).** (AC-1, AC-2, AC-7, AD-4)
  - [x] `apx/core/ports/ranking.py` (NEW) — `RankingRecorder` Protocol: one method
    `record_ranking(*, tenant, matter, actor, version, order) -> RankingVersionView`. Ports are
    protocols only (AD-4); `SqlStore` provides the one implementation.
  - [x] `apx/core/app/rank.py` (NEW) — `produce_ranking(*, units, case_theory, scorer, judge, config,
    identity_inputs, tenant, matter, actor, scopes, recorder, now) -> RankingVersionView`. It: runs
    `run_cascade(...)` (4.2) → `CascadeResult`; **fails loudly** (`ValueError`) if `result.in_order` is
    empty (AC-7 — no arbitrary/empty order) or an identity input is blank; assembles the
    `RankingIdentity` (basis + case_theory_version_id from the cascade/inputs, the cascade config
    numbers, the model/embedder/chunking/schema/prompt/sampling inputs, `GROUPING_IDENTITY`,
    `TIE_BREAK`); builds the `RankingVersion` (version_no is the store's to assign — pass `version_no=0`
    placeholder or split the id-mint into the store; SIMPLEST: the store owns `version_no` + `version_id`
    mint, the orchestrator passes the `RankingIdentity` + `RankedOrder`, and `record_ranking` builds the
    `RankingVersion`). Computes `rank_cascade(result)`; calls `recorder.record_ranking(...)`. Imports
    Domain + Ports only (AD-4).
  - [x] **Decide the id-mint seam cleanly:** because `version_no` is a per-matter monotonic the STORE
    must assign inside its transaction (AD-37), have `record_ranking` accept `(identity: RankingIdentity,
    order: RankedOrder)` and build the `RankingVersion` (mint `version_no` + `version_id`) itself. The
    orchestrator then passes `identity` + `order`, not a pre-built `RankingVersion`. Update Task 1/3
    signatures accordingly during dev; keep `RankingVersion.build` as the pure minter the store calls.

- [x] **Task 5 — Structural checks (append-only + no retained/discarded column).** (AC-4, AC-5, AD-39)
  - [x] `apx/checks/ranking_ownership.py` (NEW) — `ranking_version_is_append_only`: the
    `RankingVersion`/`RankedEntry` rows are **construction-only** in the store adapter; no Core/bulk/
    raw-SQL UPDATE or DELETE, no `session.delete(instance)` of a loaded row, no attribute mutation of a
    loaded row. **Reuse the `case_theory_ownership.py` AST helpers verbatim** (`_loaded_instance_names`,
    `_mutates_a_loaded_instance`) — same residual-limit docstring honesty.
  - [x] `apx/checks/ranking_sets_are_views.py` (NEW) — `no_retained_or_discarded_set_column` (AD-39):
    scan `models.py` for any `__tablename__` or `mapped_column` name matching `retained`/`discarded`
    set-membership; fail if one exists. A greppable structural property that keeps AD-39 true.
  - [x] Register BOTH in `apx/checks/registry.py::CHECKS` **and** `apx/checks/manifest.py::
    PROPERTY_MANIFEST`, and add their rows to the README `<!-- structural-properties:start -->` block —
    the meta-checks keep these three in lockstep (a missing entry fails the suite).

- [x] **Task 6 — Tests (red→green; deterministic, no network/DB for domain).**
  - [x] `tests/domain/test_ranking.py` — identity fingerprint determinism + blank-field rejection;
    `rank_cascade` determinism (same input → same output), the ladder order (CR > uncertain-relevant >
    uncertain-discard > CD), family contiguity + representative-first, REJECTED members in order,
    UNSCORED excluded & collected, tie-break by `piece_id` bytes, **`is_consistent()`**, and the
    **`LC_COLLATE` independence** (compute order under two `locale` settings via a monkeypatched
    `os.environ["LC_COLLATE"]` / a sort that never touches collation → identical `piece_id` sequence).
  - [x] `tests/app/test_rank_run.py` — `produce_ranking` end-to-end with `FakeScorer`/`FixedJudge`
    (4.2's `tests/scoring_fakes.py`) + a `FakeRecorder`: asserts the recorder received the expected
    version identity + ranked order; the **empty-order loud failure** (AC-7); the case-theory vs
    intrinsic basis flows.
  - [x] `tests/adapters/test_ranking_store.py` — `record_ranking` persists version + entries + ONE
    audit atomically; monotonic `version_no`; **concurrent collision fails loudly**; **conditional
    commit rejects a stale case-theory-version** (append a new case theory between build and record →
    `StaleRankingInput`, nothing written); reads scope-gated + non-disclosing `None`; **AC-2
    reproduction** — record twice over the same corpus+identity and assert the two persisted orders are
    identical *pièce* for *pièce* (same ranks).
  - [x] `tests/adapters/test_ranking_migration.py` — 0024 upgrade creates both tables; downgrade drops
    them; head is `0024_ranking_version` (mirror `test_case_theory_migration.py`).
  - [x] `tests/checks/test_ranking_ownership.py` + `tests/checks/test_ranking_sets_are_views.py` — each
    with a **failure-path fixture that actually fires** (an injected UPDATE/DELETE; an injected
    `discarded_set` column) proving the check is not vacuous.

## Dev Notes

### The scope boundary — reproducibility is the spine, the relevance ladder is minimal
4.3 is **not** where relevance policy is decided. The order is the honest ladder over the cascade's own
signal (band → label → score), and its ONLY hard guarantees are: one order, a full recorded identity,
and a deterministic collation-independent tie-break that reconstructs the order *pièce* for *pièce*.
Confidence (4.4), taxonomy labels (4.5), evidence (4.6) and **the line** (4.7/4.8) all consume this
order later — do not anticipate them. In particular **do not store a retained/discarded set** — AD-39
makes them views over `order + line + pins`, and a structural check (Task 5) forbids a column that
names them.

### AD-23 is the whole story — read it verbatim
`ARCHITECTURE-SPINE.md` AD-23 (≈ line 656): a *ranking version* is *"the complete immutable identity of
what produced one order: case theory version, model identity, prompt version, temperature and every
sampling parameter, cascade configuration, embedder identity, chunking configuration, schema version,
and the near-duplicate grouping"*. Re-running it over a fixed corpus reproduces the order; where the
model is non-deterministic **the version records the scores themselves**. *"The tie-break is
deterministic and recorded in the version … computed over a byte-ordered, collation-independent key,
the pièce identity hash, never over collated text. Asserted by test: the same ranking version over the
same corpus reproduces the same order under two different `LC_COLLATE` settings."* The recorded
per-*pièce* output is *"rank; score OR the enumerated rejection class …; its near-duplicate family
identifier and whether it was the family's judged representative; and its `supersedes` state."* — this
is AC-1 + AC-4 verbatim; the family identifier's presence is **not** optional (the estimator needs it,
else it draws 40 members of one family as 40 independent draws and the bound is wrong in the unsafe
direction).

### The conditional commit (AD-37/AD-23) — what to enforce now, what to defer
AD-37's ownership table lists *"ranking version | created | the ranking use case | never mutated after
creation"* and AD-23's *"a version identity is a conditional commit — commits only if every input
recorded in that identity is unchanged at commit time, verified in the same transaction."* The FULL
input set (config, corpus, scope, every extraction) with an `invalidated` artefact state + a *worklist*
line is a large surface whose consumers (the line, the estimator) do not exist yet. **Enforce the
concrete, testable slice now:** (1) the `(tenant, matter, version_no)` unique constraint = the
row-level conditional commit (a racing second writer fails loudly, exactly like `append_case_theory_
version`); (2) re-read the *matter*'s latest `CaseTheoryVersion` inside the write transaction and refuse
to commit a ranking whose recorded `case_theory_version_id` no longer matches (the concrete "obedient
racing writers" hazard 4.1 makes real). **Defer** the `invalidated` state + *worklist* line + the
config/corpus/extraction staleness enforcement to the stories that consume the artefact (note it in the
completion notes; do not fake a no-op `invalidated` column).

### Reuse, don't reinvent — the seams already in place
- **Version+audit atomic, monotonic, append-only:** `store.append_case_theory_version` (Story 4.1,
  `store.py` ≈ 2603) is the EXACT pattern — `_audited_tx` retry on `(tenant, seq)` collision,
  `_append_audit`, `version_no = prev + 1`, the `(tenant, matter, version_no)` unique constraint, the
  composite matter FK with no ondelete. Copy its shape.
- **Append-only structural check:** `apx/checks/case_theory_ownership.py` — reuse its AST helpers
  (`_loaded_instance_names`, `_mutates_a_loaded_instance`) verbatim for `ranking_version_is_append_only`;
  keep the same honest docstring about residual AST limits (aliased import, cross-function).
- **Scope pre-filter + non-disclosing read:** `read_case_theory` / `list_case_theory_versions`
  (`store.py` ≈ 2647) — the `MatterScope.scope.in_(sorted(scopes))` guard returning `None`
  indistinguishably. Copy exactly (AC-6).
- **The cascade + its config + fakes:** `run_cascade` (`core/app/cascade.py`), `CascadeConfig`
  (`core/domain/config.py` ≈ 360), `tests/scoring_fakes.py` (`FakeScorer`, `FixedJudge`,
  `FailingJudge`). `CascadeResult.in_order` already gives judged+rejected (never unscored) — the exact
  input `rank_cascade` orders.
- **Deterministic id shape:** `case_theory_version_id` = `sha256(tenant \0 matter \0 version_no \0 …)`
  in `backfill.py`; mirror it for `version_id`. `dedup.text_key` is `family_id`. Every `piece.id` is a
  sha256 hex string — the ASCII tie-break key (str order == byte order).

### Identity inputs the orchestrator is GIVEN (not invented)
The `RankingIdentity` is assembled from explicitly-supplied inputs, not guessed: cascade numbers from
`CascadeConfig`; model identity from the tenant's config (`model_provider`/`model_endpoint`/
`model_name`, `config.py`); embedder identity from the embedder (`model_id`/`model_version`, the ONE
hardcoded `Bgem3Embedder`, AD-11 — the same values stamped on every `chunk`); chunking version from
`ChunkingConfig.version`; `schema_version` from `ingest.SCHEMA_VERSION` (`"slice-a"`); temperature +
sampling params from the judge's configured sampling (the live `LLMJudge` uses provider defaults today —
pass them explicitly so the identity is honest, never a silent default). For 4.3's tests these are
concrete fixture values; a later surface story reads them from the live tenant/config. Do NOT reach into
adapters from `core/app` to fetch them (AD-4) — they arrive as `identity_inputs`.

### `supersedes` — recorded structurally, always false for now (honest deferral)
AD-23's recorded output names a per-*pièce* `supersedes` state, but the AD-8 superseding transition
(`in-corpus → superseded`, AD-37's table) is not yet built — `Piece` carries no superseded marker. Carry
the `supersedes: bool` column/field (structurally present so the schema does not churn later) but always
`false`, and note the deferral in the completion notes. Do not invent a superseding source.

### AD-49 / AD-19 / AD-36 — the evidential shape
`version_no` (per-matter monotonic) + the audit `seq` are AD-49's wall-clock-plus-counter. AD-19: the
UNSCORED set is recorded, carries no rank, is never zero-scored/ranked-last/dropped. AD-36: REJECTED
near-duplicate members stay IN the order with their class; UNSCORED is the only "not in the order" set;
there is no third place. `CascadeResult.is_consistent()` already ties `unscored` to the UNSCORED
outcomes — assert `RankedOrder` preserves it.

### The gold gate (AD-34) stays green — do not touch the deferral
The `recall_at_the_line` gold-merge gate (Epic 2, SM-2) is already LIVE and green with a recall
deferral. 4.3 adds ranking but must **not** break that gate or its report. Run the full check suite
(`apx/checks`) and the gold gate after implementation; both stay green.

### Testing standards
`uv`-managed: `export PATH="$PWD/.venv/bin:$PATH"` then `pytest` / `ruff check` / `ruff format`.
**NEVER `export DATABASE_URL`** (tests set their own SQLite). ruff line-length 100 — accented prose
("pièce", "é", "→", "≥") pushes lines over; trim manually. Domain + app tests are pure (fakes, no
network, no DB); store/migration tests use the test SQLite. Import-linter (AD-4/AD-27/AD-45) must stay
green — `core/app/rank.py` imports Domain + Ports only; `core/domain/ranking.py` imports Domain only.
Add Python deps via `uv add` only (none expected — stdlib `hashlib`/`json` suffice).

### Project Structure Notes
NEW: `apx/core/domain/ranking.py`, `apx/core/ports/ranking.py`, `apx/core/app/rank.py`,
`apx/adapters/store_postgres/migrations/versions/0024_ranking_version.py`,
`apx/checks/ranking_ownership.py`, `apx/checks/ranking_sets_are_views.py`, and the six test files.
UPDATE: `apx/adapters/store_postgres/models.py` (two tables), `apx/adapters/store_postgres/store.py`
(the use case + reads + DTOs + `StaleRankingInput`), `apx/checks/registry.py`, `apx/checks/manifest.py`,
`README.md` (structural-properties block). No config-key change is required (the cascade keys exist);
therefore no README config-keys-block edit. Commit on `master`, enumerate files explicitly, feat
message, secret scan the staged diff, co-author trailer.

### References
- FR-39, FR-16 (epics.md ≈ lines 96, 50) — the ranked order + version; one order, nothing deleted.
- AD-23 (ARCHITECTURE-SPINE.md ≈ 656) — the version identity, reproducibility, the collation-independent
  tie-break, the recorded per-*pièce* output, the conditional commit.
- AD-37 (≈ 1029) — one owning use case; the ownership table row "ranking version | created | never
  mutated". AD-39 (≈ 1101) — retained/discarded are views, never a column. AD-22 (≈ 633) — audit atomic
  with the act. AD-49 (≈ 1328) — wall-clock + monotonic counter. AD-19 (≈ 559) / AD-36 (≈ 1007) — loud
  failure, two sets never a third.
- Story 4.1 (`4-1-the-optional-case-theory.md`) — the append-only versioned/audited model this mirrors.
- Story 4.2 (`4-2-…-cascade-cheap-filters-first.md`) — the `CascadeResult` this consumes.

## Dev Agent Record

### Agent Model Used
claude-opus-4-8 (1M context) — BMAD dev-story.

### Debug Log References
Gate green: `ruff check` clean · 61 structural checks pass (incl. the 2 new: `ranking-append-only`,
`no-retained-discarded-set`; the gold gate AD-34 stays live+green; the encryption AD-31 allowlist
widened for the plaintext structural-metadata columns) · import-linter 3 kept / 0 broken (AD-4/27/45)
· pytest **1067 passed / 12 skipped** (44 new tests). Domain + app tests are pure (fakes, no DB/net).

### Completion Notes List
- **Domain (`ranking.py`, pure).** `RankingIdentity` captures every AD-23 input + a canonical-JSON
  `fingerprint`; `RankingVersion.build` mints the referenceable `version_id`
  (`sha256(tenant\0matter\0version_no\0fingerprint)`). `rank_cascade` is the pure deterministic order:
  band→label relevance ladder, families contiguous (representative first), REJECTED members kept in
  the order (AD-36), UNSCORED excluded into their own set (AD-19), tie-break over the ASCII-hex pièce
  id (codepoint == byte order → collation-independent, AC-3). `RankedOrder.is_consistent()` asserts
  1..N contiguity + family contiguity + unscored disjointness.
- **Persistence.** `RankingVersion` + `RankedEntry` tables (migration 0024, append-only, no
  retained/discarded column — AD-39). The owning use case `record_ranking` (AD-37): mints a per-matter
  monotonic `version_no`, persists version + all rows (ranked + the unscored NULL-rank tail) + ONE
  `ranking_recorded` audit entry, ATOMIC (AD-22), via `_audited_tx`. The `(tenant,matter,version_no)`
  unique constraint makes a concurrent double-write fail loudly (AD-37). The **conditional commit**
  re-reads the matter's latest case-theory version id inside the tx and raises `StaleRankingInput`
  (nothing written) if it moved (AD-23/AD-37). Reads are scope pre-filtered + non-disclosing (AD-13).
- **The act.** `core/app/rank.py::produce_ranking` (imports Domain+Ports only, AD-4) runs the 4.2
  cascade → builds the identity → orders → records via the new `RankingRecorder` port; it **fails
  loudly** (never an arbitrary order) on an empty in-order set or a blank identity input (AC-7).
- **Deviations / deferrals (assumed).** (1) The conditional-commit slice enforced is the case-theory
  version input (the concrete hazard 4.1 makes real) + the row-level version_no collision; the FULL
  AD-23 `invalidated`-artefact state over config/corpus/extraction is deferred to the stories that
  consume the artefact (the line, the estimator) — no faked no-op column. (2) `supersedes` is recorded
  structurally but always `false` (the AD-8 superseding transition is not built). (3) No UX surface /
  endpoint (needs a UX pass; a later surface story reads the identity inputs from the live tenant).
- **AD-31.** The ranking columns are plaintext by conscious decision (added to the encryption
  allowlist): identity hashes + categorical enums + the content-free redacted `failure_reason`;
  `identity_json` is required plaintext by NFR-56 (readable in the interface + content-free projection)
  and carries no PII/client content.

### File List
**New:** `apx/core/domain/ranking.py` · `apx/core/ports/ranking.py` · `apx/core/app/rank.py` ·
`apx/adapters/store_postgres/migrations/versions/0024_ranking_version.py` ·
`apx/checks/ranking_ownership.py` · `apx/checks/ranking_sets_are_views.py` ·
`tests/domain/test_ranking.py` · `tests/app/test_rank_run.py` · `tests/adapters/test_ranking_store.py`
· `tests/adapters/test_ranking_migration.py` · `tests/checks/test_ranking_ownership.py` ·
`tests/checks/test_ranking_sets_are_views.py`
**Updated:** `apx/adapters/store_postgres/models.py` (RankingVersion + RankedEntry tables; +Float) ·
`apx/adapters/store_postgres/store.py` (record_ranking + reads + DTOs + StaleRankingInput) ·
`apx/checks/registry.py` · `apx/checks/manifest.py` · `apx/checks/encryption.py` (plaintext allowlist)
· `README.md` (structural-properties block: 2 new rows).

## Change Log

| Date       | Version | Description                         | Author |
| ---------- | ------- | ----------------------------------- | ------ |
| 2026-08-04 | 0.1     | Story context created (ready-for-dev) | Julian |
| 2026-08-04 | 1.0     | Implemented; adversarial review (3 lenses + skeptic-verify) → 5 findings, 1 confirmed / 4 refuted; confirmed fix (withdrawn-case-theory false staleness) + 2 principled hardenings (NaN tie-break guard; `fingerprint` allowlist qualified); re-gated green; done | Julian |

## Senior Developer Review (AI)

Adversarial Workflow review (3 lenses — correctness/fidelity, determinism/reproducibility,
security/regression — each finding independently skeptic-verified, default REFUTED). **5 findings → 1
CONFIRMED / 4 refuted.** Integrity manifest verified: the review mutated nothing (only the 5 fix files
changed post-review). Re-gated green (ruff · 61 structural checks · import-linter 3/0 · 1069 passed).

**CONFIRMED (high) — fixed.** The conditional commit compared the recorded `case_theory_version_id`
against the *raw latest* case-theory version row, which is non-None even for a **withdrawal** (text
NULL). An intrinsic ranking records `case_theory_version_id=None`, so a matter whose case theory had
been *withdrawn* was judged forever stale — **no ranking could ever be recorded on it**. Fixed:
`_operative_case_theory_version_id` returns None for a withdrawal/absent theory (mirroring
`_case_theory_state`), via a `text IS NULL` DB predicate (no decryption). Regression test added
(`test_an_intrinsic_ranking_commits_over_a_WITHDRAWN_case_theory`). The mirror staleness checks
(rewrite, withdrawal-under-a-case-theory-ranking, case-theory-appears-under-intrinsic) remain correct.

**Refuted — 2 addressed anyway (principled, cheap; the story's spine is determinism):** (1) a NaN
score would short-circuit the sort-key tie-break before the pièce-id and make the order
input-dependent — unreachable via the production scorer (the embedder never emits a zero-norm vector),
but `rank_cascade` is a pure function that must be robust to its inputs, so a non-finite score is now
neutralised to no-score (regression test added); (2) the bare `fingerprint` allowlist name is
table-qualified to `(RankingVersion, fingerprint)` to keep AD-31's encrypt-by-default posture tight.
**Refuted — no change (established non-defects):** the `\x00`-delimited `version_id` preimage (the
pervasive, already-reviewed store convention, tenant/matter are controlled identifiers); the unscored
tail ordered by the ASCII-hex `piece_id` in SQL (not part of *the order* — AC-3 scopes "no SQL
collation" to the ranked rows, which are ordered by the integer `rank`; hex collates stably).
