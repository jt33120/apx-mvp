---
baseline_commit: 5723674
---

# Story 5.1: Random draw from the discarded set, population frozen

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a sceptical senior lawyer,
I want a verifiably random sample from the whole *discarded set*, frozen for the duration,
So that an hour of my verdicts cannot silently become worthless because the population moved
underneath me.

## Scope note — the first story of Epic 5, and the one that fixes the referent

Epic 5's north-star sentence quantifies **the discarded set**. Until the planning review of
2026-08-07 (`epic-5-planning-2026-08-07.md`, action item **A1**), this build contained two of them:
the Story-2.x label pile (`label_record WHERE label='discard'`) and the Epic-4 derived **view**
(`derive_triage_sets(order, line, pins).discarded`). Everything that samples today reads the first;
everything the lawyer looks at is the second.

**A1 decided: the *sampling run* draws over the derived view, and the legacy pair is superseded.**
This story executes that decision. It is therefore not only "add a sampling run" — it is a
re-pointing of the product's most consequential population, and the reason it is large.

**Why the derived view (short form — the argument is in the planning artefact):** FR-22 requires the
run to record *"the ranking version, the position of the line, the RBAC scope and the explicit
identifier list"*. A population that has no ranking version and no line cannot record either. And a
*pin* (FR-43) that the lawyer deliberately pulled back across the line would still be handed to her
to review under the label pile — the tool asking her whether a *pièce* she just retained is
relevant.

**The load-bearing design decision — invalidated-in-flight is Story 4.13's comparison, not new
machinery.** FR-22's *"ingestion, re-ranking or a line move during a run marks it
invalidated-in-flight and tells the user immediately"* is exactly *"an artefact whose recorded input
stamp differs from the current one"*. So a *sampling run* is a **stamped derived artefact** of a new
kind, `KIND_SAMPLING_RUN`, observing all nine enumerated inputs. Invalidation is derived, never
stored — a stored `invalidated` flag must be *set* by every writer, and a writer that forgets leaves
the run **falsely valid**, which is the same failure AD-23 names for staleness and the same failure
the Epic 4 retrospective identified as this build's single recurring defect.

**The second design decision — the unit of the draw is the near-duplicate family.** epics.md 5.2:
*"the near-duplicate grouping of FR-38 feeds the unit of the draw, so a family counts as it should
rather than as its member count."* Forty copies of one email are not forty independent draws.
`ranked_entry` already carries `family_id` and `is_representative` (Epic 4). This story draws
**families** and freezes each drawn family's full member list; **Story 5.2 owns what a family
*counts as*** in the estimator and how a family-level bound is stated over *pièces*.

**What 5.1 must NOT do:**
- must not build the new estimator, the simulation gate or the north-star sentence — 5.2, 5.3, 5.4.
  The bound recorded at completion is the **existing** `prevalence_upper_bound` (already
  hypergeometric, already finite-population, already exact at census), unchanged;
- must not hard-delete a `recall_review` row, a route's history or anything else (AD-7 / FR-21);
- must not introduce a clock into validity — a run is never invalidated by elapsed time;
- must not sample the **unscored tail** (AD-19/AD-36: a *pièce* the cascade could not score was not
  discarded, and a bound over it would be a bound over a different claim);
- must not build the audit chain value or the audit drawer — 5.5, 5.7, 5.9. The run's acts append to
  the **existing** audit trail.

**IN scope:**

1. `apx/core/domain/sampling.py` — the pure vocabulary: the draw over families, the sizing search
   for a target bound, the census crossover, the frozen population, the run's derived state.
2. `apx/core/ports/sampling.py` — `SamplingRunStore` / `SamplingRunReader` protocols.
3. `apx/core/app/sampling.py` — the owning use cases (start, record verdicts, complete, abandon).
4. `apx/core/app/read/sampling.py` — the read seams, fail-closed on an empty scope set.
5. Migration `0031_sampling_run.py` + the `SamplingRun` / `SamplingRunItem` models.
6. Store: the run's write and read methods, drawing over `read_triage_sets(...).discarded`; the
   `discard_population` observable re-pointed at the derived view; the run's stamp written inside
   the starting transaction.
7. `apx/core/domain/freshness.py` — `KIND_SAMPLING_RUN` + its `INPUTS_BY_KIND` row (all nine).
8. `apx/core/domain/worklist.py` — the new kind's offer.
9. `apx/api/app.py` — the sampling-run routes; the two legacy `recall/*` routes **retired**.
10. `apx/checks/user_actions.py` — the new routes and seams declared, the retired ones removed
    (4.12's registry turns the build red both ways).
11. **3 new structural checks** (77 → 80) + the `registry.py` / `manifest.py` / `README.md`
    lockstep.
12. `apx/web/src/` — the recall panel rewired onto the sampling run, showing the frozen population,
    the census label and the invalidated-in-flight state.

**OUT of scope, named with its reason (never silently dropped):**
- **The bound's *sentence*.** 5.4 owns the copyable text and the counts-only fallback. Until then the
  completed run exposes its numbers through the existing `BoundReading`, whose `copy_text` already
  carries the freshness state in the copied string (4.13).
- **Re-opening an invalidated run.** Decided against in the planning artefact: a re-opened run's
  verdicts were formed against a population that no longer exists. An invalidated run is
  **abandoned and redrawn**; its verdicts stay readable forever.
- **A family-to-*pièce* projection of the bound.** 5.2 owns it. 5.1 states the bound over the unit it
  drew and labels that unit explicitly, so no reader can mistake families for *pièces*.

## Acceptance Criteria

**AC1 — the draw is over the whole derived discarded set, within scope, without replacement.**
Given a *matter* with a ranked order and **the line** placed, when a *sampling run* is started, then
the population is `derive_triage_sets(order, line, pins).discarded` for a **named ranking version**,
grouped into near-duplicate families; the draw is uniform without replacement over those families;
and the run is refused (non-disclosing `None`/404) outside the caller's *RBAC scope* (FR-22, AD-13).
*Asserted:* a pinned-to-retained *pièce* never appears in a draw; a *pièce* in the unscored tail
never appears in a draw; a *pièce* discarded by the Story-2.x label ledger but **retained** by the
line never appears in a draw.

**AC2 — size by number, or by target bound, with the census crossover labelled.**
The caller either states a sample size, or states a target *confidence bound* and is given the
smallest size achieving it under the hypergeometric estimator. Where the required size equals the
population the run is a **census**, labelled as one, and produces the categorically stronger
statement ("every discarded *pièce* was reviewed; none was relevant") rather than a bound. Where the
target is unreachable at any size the tool says so and offers the best achievable.
*Asserted:* the sizing function is exercised over a target that lands strictly inside the
population, one that lands exactly on the census, and one that cannot be reached; the census run's
reading carries `is_census=True` and no bound is presented as if it were a sample estimate.

**AC3 — the population is frozen, by identifiers and not by a seed.**
The run records the *ranking version* (id and no), the position of **the line** (the identity of the
last retained *pièce*, never a bare integer), the *pin ledger* position, the *RBAC scope*, and the
**explicit identifier list** of every drawn family with its member *pièce* ids. A seed alone is
insufficient and a structural check says so.
*Asserted:* the frozen columns are non-nullable on the model; a run read back reproduces its exact
drawn identifier list without consulting the current discarded set; the structural check fails when
the item table is removed.

**AC4 — invalidated-in-flight, immediately, and never by a clock.**
An ingestion, a re-rank, a line move, a pin, a case-theory revision, a config change affecting
retrieval, a re-scope, a re-extraction, or a change to the discarded population **during** an open
run marks it invalidated and the read seam says so on the next read, naming the input that moved in
French. Passing time never invalidates a run.
*Asserted:* one test per trigger class exercising a real act (ingest / re-rank / move the line /
pin) and reading the run back as invalidated with the moved input named; a control asserting an
untouched run stays valid across an unrelated act.

**AC5 — verdicts are append-only, attributed, and survive invalidation.**
A verdict on a drawn family is recorded with actor and timestamp, appended never edited (a
correction is a new entry), and remains readable after the run is invalidated or abandoned — *"an
hour of my verdicts"* is never destroyed, only marked as no longer answering the question.
*Asserted:* a second verdict on the same family produces two rows and the later one is the view; the
verdicts of an abandoned run are still readable.

**AC6 — the legacy pair is superseded, not deleted.**
`sample_discards` and `record_recall_review` are retired as user-reachable acts and the two
`recall/*` routes are removed; existing `recall_review` rows stay readable forever with their
bounds, and a structural check asserts no code path constructs a new one.
*Asserted:* the probe registry no longer names the retired routes and the build is green (the 4.12
registry fails both on an undeclared action and on a declared action that no longer exists); a
historic bound reads back with its numbers intact; the check fails when a `RecallReview(...)`
construction is reintroduced.

**AC7 — the run completes atomically with its audit entry, and its bound is stamped.**
Completing a run writes the verdict tally, the bound over the unit drawn, and one audit entry, in
one transaction (AD-22/AD-37); the run carries the freshness stamp taken at the freeze, so the
completed bound is judged against the population it was drawn over, and a stale one cannot be
exported as current (4.13's `BoundReading`, unchanged).
*Asserted:* the audit store made read-only mid-completion leaves no run completed; `read_bound`
returns the run's numbers and its freshness verdict.

## Dev Notes

### The two populations, concretely

| | reads | today | after 5.1 |
|---|---|---|---|
| `sample_discards` | `label_record WHERE label='discard'` | the draw | **retired** |
| `record_recall_review` | same | the verdicts + bound | **retired** (rows stay) |
| `read_triage_sets(...).discarded` | order + line + pins | the lawyer's screen | **the population** |
| `discard_population` observable | `label_record` | 4.13's ninth trigger | the **derived** view |

### Family as the unit — the straddling case must be total, never excluded

`ranking.py` keeps a family **contiguous** in rank order (it raises if a family reappears), so at
most one family can straddle **the line**. Do not exclude it and do not impute:

- the population is the set of distinct `family_id`s having **at least one member in the discarded
  set**;
- a family's **proxy** — the *pièce* the lawyer actually reviews — is its **lowest-rank discarded
  member**, which is the representative whenever the representative is itself discarded;
- a family's frozen member list is its **discarded members only**. A retained member is not part of
  the discarded set and must not be counted into it.

A verdict on the proxy is a verdict on the family (that is what a near-duplicate family *is*). State
this in the docstring — a reader who does not know it will mistake the bound for a per-*pièce* one.

### The freshness wiring

- add `KIND_SAMPLING_RUN = "sampling_run"` beside `KIND_RANKING` / `KIND_LINE` / `KIND_BOUND`;
- `INPUTS_BY_KIND[KIND_SAMPLING_RUN] = _ALL` — a run is invalidated by **every** enumerated input,
  including `pin_ledger_seq` and `discard_population`, because all of them move the population it
  drew from. `staleness_triggers.py`'s `_per_kind_problems` currently asserts `bound == all`;
  extend it to assert `sampling_run == all` too;
- `_compute_stamp`'s `discard_population` moves from the `LabelRecord` query to a digest over
  `read_triage_sets(...).discarded` **for the version being stamped**. It is formally redundant
  (the derived set is a function of `ranking_version_no` + `line_seq` + `pin_ledger_seq`) and is
  kept anyway — see the planning artefact; the reason is that a direct digest is the exact referent
  and cannot be defeated by a future change to the derivation;
- `_compute_stamp` already takes a `version_no`; the derived digest must use it, or a run drawn over
  version 2 will be compared against version 3's discarded set — the exact defect 4.13's review
  found on the line;
- the run's stamp is written **inside the starting transaction**, keyed `(kind=sampling_run,
  artefact_id=run_id)`;
- the completed run **is** the current bound: `read_current_bound` returns
  `RecordedBound(artefact_id=<run_id>, ...)` from the latest **completed** run, falling back to the
  legacy `recall_review` rows only when no run exists. `BoundReading` matches the assessment by
  `artefact_id` and does not care about the kind — no change needed there.

**One accepted false-stale, stated so a reviewer does not report it as a defect:** a `recall_review`
row stamped between 4.13 and 5.1 carries a label-pile digest and will compare unequal against a
derived-view digest forever, so it reads **stale**. That is the safe direction and it is also true.

### Worklist

`_OFFER_BY_KIND` gains `KIND_SAMPLING_RUN: OFFER_RESAMPLE` — one offer covers both an open
invalidated run and a completed stale one, and the run's own reading carries
`invalidated_in_flight` for the immediate telling FR-22 requires. A **superseded** run (a newer run
exists) already produces no offer (4.13), which is what stops the banner growing a paragraph per
draw.

### Structural checks to add (77 → 80)

1. **`sampling-population-is-the-derived-view`** — the sampling run's write path never reads the
   label pile. AST over `apx/adapters/store_postgres/store.py`: inside the sampling-run methods, no
   reference to `LabelRecord`. Fails if someone re-points the draw at population #1.
2. **`sampling-run-freezes-identifiers`** — `SamplingRun` declares `ranking_version_id`,
   `last_retained_piece_id`, `pin_ledger_seq` and `scope` all `nullable=False`, and
   `SamplingRunItem` declares `proxy_piece_id` and `member_piece_ids`. Encodes FR-22's *"a seed
   alone is insufficient"* as a shape.
3. **`no-new-legacy-bound`** — zero `RecallReview(...)` constructions anywhere under `apx/`. The
   supersession cannot silently reverse.

Remember the **three-site lockstep**: `apx/checks/registry.py` (import + `CHECKS`),
`apx/checks/manifest.py` (import + `_p(...)` row), `README.md` `<!-- structural-properties -->`
block. `manifest_matches_readme` compares the first five cells only.

### The 4.12 registry will turn the build red — that is the design

New mutating routes and new `core/app` seams taking a Ports-typed parameter must be declared in
`apx/checks/user_actions.py::USER_ACTIONS`, and the retired routes' rows must be **removed** (a row
naming an action that no longer exists fails the same check). The bounded probe in
`tests/probe/test_never_hard_delete.py` must walk every new state-changing action; its existing
`_recall_review()` step and the `draw-recall-sample` step must be replaced by sampling-run steps,
and the arrangement that labels every *pièce* discarded must become an arrangement that **places
the line** (the population is now derived).

### Files

**NEW:** `apx/core/domain/sampling.py`, `apx/core/ports/sampling.py`, `apx/core/app/sampling.py`,
`apx/core/app/read/sampling.py`, `apx/checks/sampling_population.py`,
`apx/checks/sampling_freeze.py`, `apx/checks/no_legacy_bound.py`,
`migrations/versions/0031_sampling_run.py`, `tests/domain/test_sampling.py`,
`tests/app/test_sampling_run.py`, `tests/api/test_sampling_api.py`,
`tests/checks/test_sampling_checks.py`.

**UPDATE:** `apx/core/domain/freshness.py`, `apx/core/domain/worklist.py`,
`apx/core/app/read/freshness.py` (bound fallback), `apx/adapters/store_postgres/models.py`,
`apx/adapters/store_postgres/store.py`, `apx/api/app.py`, `apx/checks/user_actions.py`,
`apx/checks/staleness_triggers.py`, `apx/checks/registry.py`, `apx/checks/manifest.py`,
`README.md`, `apx/web/src/api.ts`, `apx/web/src/App.tsx`,
`tests/probe/test_never_hard_delete.py`, `tests/adapters/test_recall.py`,
`tests/api/test_freshness_api.py`.

### Encryption allow-list (NFR-56 / AD-31)

`sampling_run.scope`, `sampling_run_item.family_id`, `sampling_run_item.proxy_piece_id` and
`sampling_run_item.member_piece_ids` are identifiers and hashes, not content or PII. The existing
allow-list check requires a **table-qualified** plaintext entry with its argument — add them, or the
build goes red (this happened on `artefact_stamp` in 4.13).

## Tasks / Subtasks

- [x] **T1** — `apx/core/domain/sampling.py`: `SamplingUnit` (family + proxy + members), `group_discarded_families`, `draw_families` (uniform, without replacement, seeded, pure), `size_for_target` returning size / census / unreachable-with-best-achievable, `RunState` derivation (`open` / `invalidated` / `completed` / `abandoned`). Tests first (AC1, AC2).
- [x] **T2** — `apx/core/ports/sampling.py`: the reader/writer protocols, scoped, non-disclosing `None`.
- [x] **T3** — models + migration `0031_sampling_run.py`: `SamplingRun`, `SamplingRunItem`, `SamplingVerdict` (append-only), composite FK to `matter_scope`, no `ondelete`.
- [x] **T4** — store: `start_sampling_run` (draw over `read_triage_sets(...).discarded`, freeze, stamp, audit — one transaction), `record_sampling_verdict`, `complete_sampling_run`, `abandon_sampling_run`, `read_sampling_run`, `list_sampling_runs`, `size_for_target_bound`. (AC1, AC3, AC5, AC7)
- [x] **T5** — freshness: `KIND_SAMPLING_RUN`, `INPUTS_BY_KIND`, `discard_population` re-pointed at the derived view **per version**, `staleness_triggers` extended. (AC4)
- [x] **T6** — worklist offer + `read_current_bound` reading the latest completed run with the legacy fallback.
- [x] **T7** — `apx/core/app/sampling.py` + `apx/core/app/read/sampling.py`: the owning use cases and the fail-closed read seams.
- [x] **T8** — API: the sampling-run routes in; the two `recall/*` routes out; response models.
- [x] **T9** — `USER_ACTIONS`: declare the new routes and seams, remove the retired rows; update the probe's steps and its arrangement (place the line, not label-discard everything). (AC6)
- [x] **T10** — the 3 structural checks + the three-site lockstep (77 → 80) + `tests/checks/test_sampling_checks.py` proving each check is live by injecting a violation into a scratch copy of the tree.
- [x] **T11** — encryption allow-list entries for the new columns.
- [x] **T12** — web: `api.ts` + `App.tsx` rewired onto the sampling run; the panel shows the named ranking version, the frozen population size, the census label and the invalidated-in-flight banner.
- [x] **T13** — full gate: ruff, import-linter, the structural harness, pytest, `npm run typecheck`, `npm run build`.

## Dev Agent Record

### Implementation Plan

Built in the task order above. Two decisions shaped everything else:

1. **Invalidated-in-flight reuses Story 4.13.** A *sampling run* is a stamped artefact of a new
   kind (`KIND_SAMPLING_RUN`) observing all nine inputs. FR-22's failure path is then not new
   machinery — it is the stamp comparison read on a run that is still open, and the state is
   `derive_run_state(status, stamped, changed)` in the Domain. Nothing stores "invalidated".
2. **One derivation for the population and for the observable.** `_derived_discarded` is the single
   place the discarded set is computed; `_run_population` (the draw) and `_compute_stamp` (the
   `discard_population` observable) both go through it, and a structural check asserts they do. A
   run drawn over one set and invalidated against another is the falsely-fresh defect with a new
   cause, and this is the leg that makes it unspellable.

### Debug Log

- The 4.12 registry turned the build red twice, as designed — once for the 7 new routes and the 11
  new seams, once for the two retired `recall/*` rows. Declared and removed.
- The encryption allow-list failed twice (`SamplingRun.last_retained_piece_id`, then
  `SamplingRunItem.run_id`) and the re-key registry once (3 new `EncryptedText` columns). All three
  are the gates working.
- `test_freshness_api.py` needed a real discarded set: on a four-*pièce* corpus the tool's own
  recall-first placement retains everything, so the derived population is empty and a run is
  correctly refused. Added `_ensure_a_discarded_set` — the fixture now moves the line through the
  real priced act rather than pretending.
- `_IMPLIED_BY` had to become a map to a **tuple** of impliers: the derived discarded set has three
  causes (the order, the line, the pins), and saying *"le jeu écarté a changé"* beside *"un
  déplacement de la ligne"* would present one act as two.

### Completion Notes

**Self-found before the review** (each with a regression):
- the run's `pin_ledger_seq` was computed by a second arithmetic (a whole `_compute_stamp` call)
  instead of the observable's own — extracted `_pin_ledger_seq`, now shared, so the freeze and the
  comparison cannot drift;
- `SamplingRunReading.state_fr` compared against the literal `"open"` instead of `STATUS_OPEN`;
- `sample_size=0` was silently clamped to 1 — now refused;
- the run-history route re-read every run through the full seam (1 + 2n store calls).

### Senior Developer Review (AI) — adversarial workflow, 2026-08-07

**Shape.** Four lenses over the whole diff, each finding independently skeptic-verified with the
skeptic instructed to REFUTE and to default to refuted when uncertain. Lens 3 is the *wrong
referent* lens that action item **A3** asked for; lens 4 is the *seams* lens **A4** asked for.

| | count |
|---|---|
| lenses reporting | **4 / 4** |
| findings raised | **28** |
| skeptics returning a verdict | **26** |
| **confirmed** | **8** (≈ 6 distinct defects — `confidence` was found by three lenses) |
| refuted | 18 (**69 %**) |
| **skeptics lost to a transport error** | **2** — see coverage below |

**Coverage lost, stated per action item A2.** Two skeptics died with `API Error: ENOTFOUND` and
returned no verdict, so two findings went unadjudicated:
`store.py:4475` (*`box[0]` where every sibling reads `box[-1]`*) and `store.py:4398`
(*`size_for_target_bound` says "the discarded set is empty" for a matter that was never ranked*).
**Both were fixed anyway** rather than left on an absent verdict — an unadjudicated finding is not a
refuted one. Every other finding carries a verdict.

**Confirmed and fixed** (each with a named regression; the three marked ▸ were re-run with the fix
reverted and fail, and pass again with it restored):

| # | Sev | Defect | Fix |
|---|---|---|---|
| 1 ▸ | HIGH | A run started over an explicitly named **superseded** ranking version became the *matter*'s current bound, read **à jour** and exported — every observable it watches is the *matter*'s, not the old version's, so nothing could see it. | `start_sampling_run` refuses a version that is not the latest, naming both versions. |
| 2 ▸ | HIGH | The copied/exported bound sentence called a **family** count *"pièces écartées"* — the one sentence said to a judge, false about its own denominator. | `RecordedBound` gained `unit_fr` + `piece_count`; the sentence names the unit it was computed over and states the *pièce* count **beside** it, never substituted into it. |
| 3 | HIGH | The web mounted the whole sampling panel under `labels.discarded > 0` — the **Story-2.x label pile**, inherited verbatim from the retired panel. The audit was hidden exactly when the two populations disagree, which is the case decision A1 is about. | Ungated; the panel renders "aucun tirage" as its own state. |
| 4 | HIGH | An **invalidated** run could not be abandoned from the UI: the buttons gated on the derived `state`, and the banner told the lawyer to do the one thing she had no button for. | The buttons gate on the stored `status`; judging is additionally disabled while invalidated. |
| 5 | MED ×3 | `confidence` was validated only on the `target_prevalence` branch, so an out-of-range value was frozen onto the run and refused at **completion** — an hour of verdicts against a draw that could never produce a number. | Validated in the owning seam, where the run is born; the preview refuses what the draw refuses. |
| 6 | MED | The staleness banner rendered the new kind as the raw English `sampling_run`, stamped with a ranking version it does not have. | French subject added; the version suffix suppressed for this kind. |
| 7 ▸ | MED | An **abandoned** run stayed "in force" and put a permanently stale line on the worklist. Abandoning IS discharging the offer. | The live run is the latest **non-abandoned** one. |
| 8 | MED | The legacy `kind=bound` worklist line could never discharge: its label-pile digest compares unequal forever, and no code path can write another `recall_review`. | A legacy bound is live only while the *matter* has never had a run. |

**Also fixed, though their verdicts refuted them or never arrived** — each is one line and removes a
latent hazard rather than a live one:
`max_size=0` fell through an `or` idiom and drew a **census** (the opposite of the cap asked for);
`box[0]` instead of `box[-1]` after an `_audited_tx` retry; `POST /sampling/runs` answered a scope
refusal **403** where every peer route answers the non-disclosing **404** (FR-14); the
never-ranked-versus-nothing-discarded message; `no_legacy_bound` matched only the bare-name
construction (`models.RecallReview(...)` walked past); `sampling_population`'s label-pile leg was
defeated by one module-level alias; three probe steps did their own state-changing arrangement, so
the `changes_state` assertion could be satisfied by the arrangement — the cut is now its own step
declaring no action.

**Accepted with a reason, not silently dropped:**
- *`size_for_target` is a caller-controlled CPU cost inside the write transaction* (refuted). The
  binary search is ~log₂(N) bound evaluations over the **family** count of one *matter*'s discarded
  set. Real but bounded; revisit if 5.2's estimator changes the cost curve.
- *`GET /sampling/runs` is unpaginated and computes one freshness stamp per run.* Deliberate: the
  alternative is a reading carrying `stamped`/`changed` values that were never measured, and a
  reader with no way to tell a measured `()` from an unmeasured one — the nearly-right referent
  again. A *matter* has a handful of runs.
- *Verdict `seq` is a read-modify-write.* Guarded by `uq_sampling_verdict_seq` plus the `_audited_tx`
  retry: a race collides and retries, it does not overwrite.
- *The run "in force" and the run that IS the bound are chosen by different keys.* True and correct:
  the bound is the latest **completed** run; the work in flight is the latest non-abandoned one. A
  stale bound whose successor is already open offers nothing, because she is already re-sampling.

## File List

**NEW (14):** `apx/core/domain/sampling.py` · `apx/core/ports/sampling.py` ·
`apx/core/app/sampling.py` · `apx/core/app/read/sampling.py` · `apx/checks/sampling_population.py` ·
`apx/checks/sampling_freeze.py` · `apx/checks/no_legacy_bound.py` ·
`apx/adapters/store_postgres/migrations/versions/0031_sampling_run.py` ·
`tests/domain/test_sampling.py` · `tests/api/test_sampling_api.py` ·
`tests/checks/test_sampling_checks.py` · `tests/adapters/test_sampling_run_migration.py` ·
`_bmad-output/implementation-artifacts/epic-5-planning-2026-08-07.md` · this story file.

**UPDATED (22):** `apx/core/domain/freshness.py` · `apx/core/domain/worklist.py` ·
`apx/core/domain/confidence.py` · `apx/core/app/read/freshness.py` ·
`apx/adapters/store_postgres/models.py` · `apx/adapters/store_postgres/store.py` ·
`apx/adapters/store_postgres/backfill.py` · `apx/api/app.py` · `apx/checks/user_actions.py` ·
`apx/checks/staleness_triggers.py` · `apx/checks/encryption.py` · `apx/checks/registry.py` ·
`apx/checks/manifest.py` · `README.md` · `apx/web/src/api.ts` · `apx/web/src/App.tsx` ·
`apx/web/src/triage.tsx` · `tests/probe/test_never_hard_delete.py` ·
`tests/api/test_freshness_api.py` · `tests/api/test_ingest_api.py` ·
`tests/adapters/test_tenant_isolation.py` · `tests/adapters/test_encryption_at_rest.py` ·
`tests/domain/test_freshness.py` · `sprint-status.yaml`.

**DELETED (1):** `tests/adapters/test_recall.py` — the legacy pair's store test. The rows it
protected are covered by `test_sampling_run_migration.py` (nothing is migrated away) and
`test_sampling_api.py` (the legacy fallback still reads).

**Gate at close:** ruff clean · import-linter 3/3 · structural harness **80/80** ·
`pytest` **1 521 passed, 12 skipped** · `tsc -b --noEmit` clean · `vite build` clean.

## Change Log

| Date | Change |
|---|---|
| 2026-08-07 | Story created after the A1 planning review (`epic-5-planning-2026-08-07.md`). |
| 2026-08-07 | Implemented T1–T13. Adversarial review: 4 lenses, 28 findings, 8 confirmed, 2 skeptics lost to a transport error (both findings fixed anyway). All confirmed findings fixed with regressions; three verified by reverting the fix. Gate green. |
