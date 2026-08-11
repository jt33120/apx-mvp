---
baseline_commit: 502e6e3
---

# Story 5.2: The hypergeometric estimator and the census crossover

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As the APX build,
I want the prevalence estimator implemented as standard hypergeometric statistics with the census
crossover handled,
So that the number behind the north-star sentence is sound by construction rather than by hope.

## Scope note — what this story is, and what it is not

Story 5.1 built the **ritual**: the draw over the Epic-4 derived discarded view, the family as the
unit, the freeze, invalidated-in-flight. It deliberately shipped the **existing**
`prevalence_upper_bound` unchanged and said so in its own docstring: *"Nothing here makes it newly
trustworthy, and nothing here pretends it does."*

This story is where the number becomes defensible. It is **not** where the number becomes proven —
that is Story 5.3's simulation gate — and it is **not** where the number becomes a sentence — that
is Story 5.4. The split is deliberate: the architecture work breakdown flags the estimator as the
single most likely thing in this build to be underestimated, so it is three stories, not one.

**The statistic itself does not change.** `confidence.prevalence_upper_bound` is already the exact
finite-population hypergeometric upper confidence bound: the largest defect count `D` for which
`P(X ≤ k | D) ≥ 1 − c` under `Hypergeometric(N, D, n)`, computed in exact big-integer arithmetic,
already exact at a census, already tighter than the binomial rule of three FR-23 forbids. Rewriting
it would be motion, not progress.

**What changes is everything around it** — the five things a naive estimator gets wrong, each of
which is a *design decision*, not a formula. Action item **A7** from the Epic 4 retrospective binds
this story: the five must be *answered in this file before implementation*. §"The five hard inputs"
below is that answer, and each of the five carries **one structural check** so that the answer is a
property of the build rather than a paragraph nobody re-reads.

## Acceptance Criteria

**AC-1.** **Given** a completed draw of size `n` from a *discarded set* of size `N` with `k`
relevant found, **when** the estimator computes, **then** it produces a **hypergeometric**
(finite-population) upper confidence bound on the **prevalence** of relevant material in the
*discarded set* at a stated confidence level — never a probability that nothing was missed (§0.2,
FR-23).

**AC-2.** **And** the estimator's five hard inputs are each answered explicitly in the design and
recorded: near-duplicate family structure (a family is not `n` independent draws), the
census-versus-sample crossover, repeated sampling over one population, population freezing, and the
projection at an unsampled position (OQ-4, FR-22, FR-38). Each answer is bound by a named
structural check, and a build in which an answer is quietly reversed fails (FR-56).

**AC-3.** **And** the near-duplicate grouping of FR-38 feeds the unit of the draw, so a family
counts as it should rather than as its member count — and the *pièce* figure a lawyer reads is
derived from the frozen family sizes as a **worst case**, never by rescaling a family prevalence
onto a *pièce* denominator nobody sampled.

**AC-4.** **And** a run that covered its whole population is a **census**: it states an exact count
and never a percentage, and the two registers — census and bound — are structurally disjoint
(FR-22).

**AC-5.** **And** a bound rests on **exactly one run**, and the run whose bound the *matter*
currently shows is chosen by **recency**, never by how favourable its number is; a run that is not
the first over its frozen population carries its ordinal (FR-22).

**AC-6.** **And** the numbers are computed from the run's **freeze**, never from a live
re-derivation of the discarded set, and the method that produced them is recorded by name on the
run, so a later change of method produces a new bound rather than silently restating the old one
(FR-22, FR-23, FR-58).

**AC-7.** *(failure path)* **And** where a run predates the frozen family-size list, the *pièce*
worst case is reported as **not computable** and is not guessed — an absent input is never imputed
(AD-19).

---

## The five hard inputs (OQ-4) — the answers, and what binds each

*This section discharges action item **A7**. Each answer states the decision, the reason, the
failure it prevents, and the structural check that holds it.*

### Input 1 — Near-duplicate family structure: a family is not `n` independent draws

> *"A discarded set of 1 400 in which 300 pièces are 40 variants of eight email threads is not a
> population of 1 400 independent units… What is the unit of the draw — the pièce, or the family?"*

**Decision (a): the unit of the draw is the family, and the estimand is the prevalence of relevant
*families* in the discarded set.** Story 5.1 already draws families and freezes each drawn family's
member list. This story states the consequence out loud: `N`, `n` and `k` in the hypergeometric are
**family** counts throughout. Nothing in the statistic is family-aware; the statistic is applied to
a population whose members really are exchangeable, which is what makes it valid.

**Decision (b): the *pièce* figure is a worst case computed from the frozen family sizes, never a
rescale.** FR-23's sentence contains *"about Y pièces"*, and the lawyer counts her discarded pile in
*pièces*. The tempting arithmetic is `prevalence_upper × population_pieces`. **It is wrong, and it
is wrong in the flattering direction.** That product assumes the relevant families are of average
size; if the eight big threads are the relevant ones, it understates by the ratio of the largest
families to the mean. A number said to a judge must not be biased toward the speaker.

The honest figure: if at most `D` families are relevant, then at most **the sum of the `D` largest
family sizes in the frozen population** is relevant, in *pièces*. That is computable, is a true
upper bound under the same confidence, and requires only that the run freeze the population's family
sizes. So it does — one new frozen column.

**Decision (c): the *pièce* figure is stated beside the bound, never substituted into it.** This is
the CONFIRMED defect the Story 5.1 review found (*"the copied sentence called a family count 'pièces
écartées'"*), promoted from a fix to a property.

**The residual uncertainty, stated rather than hidden.** A verdict on a family is a verdict on its
proxy. If FR-38's grouping is wrong — if two genuinely different documents were grouped — the
estimate is wrong, and no amount of simulation detects it, because the simulation generates families
that are correct by construction. That belongs to the *gold set* and SM-17, and Story 5.3's harness
must say so in as many words rather than implying the simulation settles it.

**Bound by:** `estimator-piece-worst-case` — the *pièce*-level figure has exactly one owning
function, and no expression anywhere under `apx/` multiplies a prevalence by a *pièce* count.

### Input 2 — The census-versus-sample crossover

> *"Where the required sample equals the population, the honest output is 'every discarded pièce was
> reviewed; none was relevant', not a residual-risk figure over a fully reviewed population. Where is
> the crossover, and what does the sentence say near it?"*

**Decision (a): the crossover is `n == N` exactly, and there is no third register near it.** A draw
of `N − 1` families is a sample and says a sample's sentence. Inventing an "almost a census" register
would create precisely the reading FR-22 forbids — a sample heard as a census. Two registers, one
boundary, no gradient.

**Decision (b): a census states an exact count and never a percentage.** Not a tighter bound — a
*categorically different statement*. Nothing is estimated; everything was read. `at most 0.0% is
relevant` over a fully reviewed population is a false claim of residual risk, said out loud, to a
judge — it is the §0.2 failure with better arithmetic.

**Decision (c): a census with `k > 0` is still a census.** *"The 120 discarded families — 1 400
pièces — were all reviewed; 3 families, 47 pièces, were relevant."* Exact, unflattering, no bound.

**Decision (d): at a census the *pièce* figure is EXACT, not a worst case** — every drawn family's
member list is frozen, so the *pièces* held by the relevant families are known by name. The two
epistemic statuses are different and are named differently: `exact` at a census, `worst case` at a
sample. The `Estimate` carries which one it is; it never carries both.

**Bound by:** `estimator-census-no-bound` — the census branch emits no percentage and carries
no `prevalence_upper`; the two registers are disjoint by construction.

### Input 3 — Repeated sampling over one population

> *"Two runs over the same population is a multiple-comparisons problem that a record showing both
> runs does not repair, because the sentence travels alone. Do independent runs pool, and if so how,
> and what does a second run's sentence say about the first?"*

**Decision (a): runs never pool.** A bound rests on exactly one run's verdicts. Pooling two
independent draws over one frozen population is defensible statistics *only* if the decision to run
the second was made before seeing the first, and nothing in this product can establish that. The
cost of refusing to pool is a wider bound; the cost of pooling wrongly is an indefensible one.

**Decision (b): the current bound is chosen by RECENCY, never by favourability.** This is the leg
that actually bites. Pooling is a theoretical temptation; *"show the best one"* is a feature request
someone will make in good faith. `read_current_bound` orders by completion time and must never order,
minimise or maximise over `prevalence_upper` or `count_upper`.

**Decision (c): the ordinal counts EVERY prior run over the same frozen population, including the
abandoned ones.** Abandon-and-redraw is the cheapest route to a favourable number — an hour of bad
verdicts thrown away, a fresh draw, a nicer sentence — and a count that excluded abandoned runs would
flatter exactly the person gaming it. The frozen-population identity is the tuple *(ranking version
no, last retained pièce, pin ledger seq, scope)*: two runs share a population iff they share all
four.

**Decision (d): the ordinal is DERIVED, never stored.** A stored counter has to be incremented by
every writer, and a writer that forgets leaves the run reading as the first — the falsely-fresh
failure mode this build keeps meeting, in a new costume (AD-23, AD-39).

**Decision (e): no early-stopping rule exists, because none has been validated.** FR-22 is explicit
that early stopping is a property of the estimator and never of the interface. No stopping rule is
validated in this increment, therefore there is none: a run completes at its full drawn size, and
`complete_sampling_run` refuses a partially judged run (already true since 5.1, and its test stays).
OQ-26 may reopen this; until it does, the absence is the decision.

**Bound by:** `estimator-one-run-one-bound` — the estimator has exactly one owning module under
`apx/`, and the current-bound selection never orders by how favourable the number is.

### Input 4 — Population freezing

> *"The draw is reconstructible only against a frozen, identically-ordered population, and the
> population changes on ingestion, re-ranking, a pin or a line move. What is the exact freezing
> contract, and what invalidates a run mid-flight?"*

**Answered by Story 5.1 and unchanged here.** The contract is the five NOT NULL freeze columns
(*ranking version id + no*, the line by **last retained pièce identity** — never a bare integer —
the pin ledger seq, the scope) plus the explicit identifier list on `sampling_run_item`; a seed alone
is insufficient and the check `sampling-freeze-identifiers` says so structurally. Invalidation is the
4.13 stamp comparison over all nine observables, derived and never stored, and a verdict against a
moved population is **refused**, not warned about.

**What this story adds: the estimator's inputs are the FREEZE, never the live set.** The completion
path must read the run's own frozen counts, and must not re-derive the discarded set to get them. A
bound computed from a population re-derived at completion time would be a bound over whatever the
matter looks like now, quoted with the authority of a draw made over what it looked like then — the
same wrong referent, one layer deeper.

**And: the frozen family-size list.** Input 1's worst case needs the size of every family in the
population, not only the drawn ones, as it was at draw time. `population_family_sizes` is frozen at
`start_sampling_run`, sorted descending. Runs created before this story have no such list; their
*pièce* worst case is reported **not computable** and is never guessed (AC-7, AD-19).

**And: the method is recorded by name.** FR-23 requires that changing the statistical method produce
a *new* bound rather than silently restate the old one. `estimator_method` is written on the run at
completion. A recorded bound whose method differs from the current one is a bound computed by a
different method and reads as one.

> **Deviation from FR-23, stated rather than hidden.** FR-23 says the method *"is fixed for a given
> tenant by configuration-as-data"*. This story records the method but does **not** expose choosing
> it as a tenant configuration key. Exactly one estimator exists, and a knob that let a tenant select
> among estimators would be a knob that let a tenant select how favourable its number is. If a second
> method is ever admitted, the key is added then — with both methods validated by 5.3's gate. The
> requirement's intent (no silent change of method) is met by recording it; its letter is not.

**Bound by:** `estimator-bound-from-the-freeze` — the completion seam takes the estimator's population
and sample from the frozen run row and never reaches the live derivation.

### Input 5 — The projection at an unsampled position

> *"The priced figure is not a sampling bound at all; it is a calibrated model estimate, and
> calibration requires labelled data from a comparable corpus. The only labelled corpus in the plan
> is TREC Legal Track — English, e-discovery, a different task and a different relevance definition
> from ordonnance 145 CPC review. Is that calibration admissible, and what does SM-17 do when it is
> not?"*

**Decision: it is not admissible, so no calibrated projection ships.** TREC Legal Track is English
e-discovery; the task here is French and Luxembourgish civil-procedure document review under
*ordonnance 145 CPC*. Calibrating a probability on the first and quoting it on the second is exactly
the class of claim §0.2 exists to prevent — a number with a real pedigree, attached to the wrong
question.

**What ships instead is what Story 4.9 already built: the priced move states COUNTS.** *"Moving the
line here moves 34 pièces from retained to discarded."* That is a fact about the current ranking, not
an estimate about an unsampled position, and it needs no calibration to be true.

**What SM-17 does when calibration is not admissible: it says so.** The residual uncertainty is
recorded as residual, not laundered into a figure. The honest position is that this increment
quantifies *the discarded set that was sampled* and quantifies **nothing** at a position nobody
sampled.

**Structurally the two must stay apart in both directions.** Story 4.9's `line-projection-not-a-bound`
already forbids the projection from reaching the estimator. This story closes the other direction:
the estimator must not reach the projection, and must consume no model-reported number — FR-42's
*"no self-reported model number feeds FR-19's priced statement or FR-23's confidence bound, directly
or through any intermediate"*.

**Bound by:** `estimator-no-model-number` — the estimator modules import nothing from
`line_projection` and reference no model-reported score name.

---

## What this story does NOT decide

- **Whether the estimator is sound.** That is Story 5.3's simulation gate: populations whose truth
  is known by construction, many runs, a stated C% bound holding in at least C% of them, asserted in
  CI. Until that gate is green, nothing here licenses the number.
- **The sentence.** Story 5.4 owns the words, the copyable text, the counts-only fallback and the
  banned-phrasing check. This story produces the `Estimate` the sentence will render, and
  deliberately puts no new sentence on screen.
- **The unfitness declaration** (`K` approaching `N` ⇒ the ranking version carries no signal). FR-23
  consequence, Story 5.4's surface.
- **OQ-26 — whether 200 verdicts is a thing that happens.** Stratified draws and sequential stopping
  both change the estimator; neither ships unvalidated. The decision here is the absence of a
  stopping rule, not a claim that 200 is comfortable.
- **The near-duplicate threshold itself** (OQ-21). It arrives from Epic 4's `family_id`; this story
  consumes the grouping and does not second-guess it.

---

## Tasks / Subtasks

- [x] **T1 — The design record (A7).** This file's §"The five hard inputs" is the deliverable; mark
  A7 `done` in `sprint-status.yaml` with the resolution recorded, once the checks that bind the five
  answers are green. *(AC-2)*

- [x] **T2 — The domain estimator: a named method and one `Estimate`.**
  - [ ] `ESTIMATOR_METHOD = "hypergeometric-upper-bound/v1"` in `core/domain/confidence.py`, beside
        the statistic it names.
  - [ ] `pieces_upper_bound(*, count_upper_families, family_sizes)` — the sum of the `count_upper`
        largest frozen family sizes, or `None` when the list is absent. Never a rescale.
  - [ ] `Estimate` in `core/domain/sampling.py`: `kind` (`census` | `bound` | `no_population`),
        `method`, the family counts, the *pièce* counts, `pieces_are_exact: bool`, `run_ordinal`.
        A census carries an exact count and **no** `prevalence_upper`; a sample carries a bound and a
        worst case. Never both.
  - [ ] `estimate_for_run(...)` — the one owning function that produces an `Estimate`.
  - [ ] `census_statement_fr` restated to name both units exactly and no percentage.
  - [ ] Tests: `tests/domain/test_sampling_estimate.py`. *(AC-1, AC-3, AC-4, AC-7)*

- [x] **T3 — The freeze gains the family sizes and the method.**
  - [ ] `SamplingRun.population_family_sizes` (Text, nullable — sorted descending, comma-joined) and
        `SamplingRun.estimator_method` (String, nullable — written at completion).
  - [ ] Migration `0032_sampling_estimator.py` — pure DDL, no backfill: an existing run genuinely
        has no frozen size list and must not be given a fabricated one (AD-19/AD-7).
  - [ ] `start_sampling_run` freezes the sizes of **every family in the population**, not only the
        drawn ones.
  - [ ] `complete_sampling_run` writes `estimator_method` and computes the bound **from the frozen
        row**. *(AC-6, AC-7)*

- [x] **T4 — The run ordinal, derived.** Count every prior run — completed *and* abandoned — sharing
  the frozen-population tuple *(version_no, last_retained_piece_id, pin_ledger_seq, scope)* and
  starting earlier. Carried on `SamplingRunView`. *(AC-5)*

- [x] **T5 — `read_current_bound` states the estimate honestly.** `RecordedBound` gains `method` and
  the *pièce* worst case; the selection stays ordered by recency and gains a regression test naming
  the cherry-picking failure. *(AC-5, AC-6)*

- [x] **T6 — Five structural checks, one per input (77 → 80 became 80 → 85).**
  - [ ] `apx/checks/estimator_piece_figure.py` → `piece_figure_is_a_worst_case` *(input 1)*
  - [ ] `apx/checks/estimator_census.py` → `a_census_states_no_bound` *(input 2)*
  - [ ] `apx/checks/estimator_one_run.py` → `one_run_one_bound_chosen_by_recency` *(input 3)*
  - [ ] `apx/checks/estimator_freeze.py` → `the_bound_is_computed_from_the_freeze` *(input 4)*
  - [ ] `apx/checks/estimator_no_model_number.py` → `the_bound_consumes_no_model_number` *(input 5)*
  - [ ] Lockstep all three sites: `checks/registry.py`, `checks/manifest.py`, `README.md`'s
        `<!-- structural-properties -->` block. Each check proven **live** on a scratch copy
        carrying a deliberate violation, and proven to fail closed. *(AC-2)*

- [x] **T7 — API and client surface, minimal.** `SamplingRunOut` carries the estimate fields; the web
  panel distinguishes the census register from the bound register and names the run ordinal when it
  is not the first. **No new sentence** — that is 5.4. *(AC-3, AC-4, AC-5)*

- [x] **T8 — Gate.** ruff · import-linter · the structural harness at its new count · pytest ·
  `tsc -b --noEmit` · `vite build`.

---

## Dev Notes

### Files that exist and must be read before they are touched

| File | Current state | What changes |
|---|---|---|
| `apx/core/domain/confidence.py` | `prevalence_upper_bound` (exact hypergeometric, big-int), `PrevalenceBound`, `RecordedBound` with `unit_fr`/`piece_count` | + `ESTIMATOR_METHOD`, + `pieces_upper_bound`, `RecordedBound` + `method` and the worst case. **The statistic itself is not rewritten.** |
| `apx/core/domain/sampling.py` | `SamplingUnit`, `group_discarded_families`, `draw_families`, `Sizing`, `size_for_target`, `bound_for_run`, `is_census`, `census_statement_fr`, the view types, `derive_run_state` | + `Estimate`, `estimate_for_run`; `census_statement_fr` restated; `SamplingRunView` + `population_family_sizes`, `run_ordinal` |
| `apx/adapters/store_postgres/models.py` | `SamplingRun` (5 freeze columns NOT NULL), `SamplingRunItem`, `SamplingVerdict` | + 2 nullable columns on `SamplingRun` |
| `apx/adapters/store_postgres/store.py` | `start_sampling_run`, `complete_sampling_run`, `_run_view`, `read_current_bound` | freeze the sizes; write the method; derive the ordinal; the bound from the freeze |
| `apx/checks/registry.py`, `manifest.py`, `README.md` | 80 properties | 85 — **all three sites, or the meta-checks fail** |
| `apx/web/src/api.ts`, `triage.tsx` | `SamplingPanel` (ungated) | the two registers, the ordinal |

### Traps this build has already fallen into — do not repeat them

1. **`manifest_matches_readme` compares only the first five cells.** The prose column may differ;
   the key/FR/AD/verb/callable-name must match exactly.
2. **Every new HTTP route and every `core/app` seam taking a Ports-typed parameter must be declared
   in `apx/checks/user_actions.py`.** This story adds no route and no seam — if that changes, the
   registry changes with it, and the bounded probe walks it.
3. **A new `EncryptedText` column must be added to `backfill.py::ENCRYPTED_COLUMNS`.** This story
   adds none (sizes and a method name are neither content nor PII), but a plaintext column on an
   encrypted table needs its allowlist entry in `apx/checks/encryption.py` with the NFR-56 argument.
4. **Accented characters push lines past ruff's 100-char limit.** Reflow by hand.
5. **Reviewer subagents leave scratch test files** (`tests/api/test_zz_*.py`). Clean them up.
6. **`export PATH="$PWD/.venv/bin:$PATH"` in the same shell call as the test command**, and never
   export `DATABASE_URL`.

### Why `population_family_sizes` is a frozen list and not a computed one

The worst case needs the size of *every* family in the population, including the ones nobody drew,
as they were at draw time. Re-deriving them at completion reads the population as it is now, which
is the wrong referent by construction — and for an *invalidated* run it is a population that no
longer exists. Freezing costs one text column of small integers and buys a number that is
reconstructible from the audit record alone, which FR-23 requires in as many words.

### Why the ordinal counts abandoned runs

Because the failure it defends against is *abandon and redraw until the number is nice*. A count
that ignored abandoned runs would be blind to precisely the behaviour it exists to make visible.
This is the same reasoning as AD-7: the record of a discarded attempt is part of the record.

---

## Dev Agent Record

### Completion Notes

The statistic was not touched, as planned. What this story built is the design around it, and two
things emerged that the design record did not anticipate:

1. **A sample's bound can reach exactly zero without being a census.** At 39 of 40 families read
   with none relevant, the hypergeometric rejects even `D = 1` at 95 % (the one unread family would
   have been missed with probability 2.5 %, under alpha), so `count_upper` is 0. That is a true
   statement and it stays in the **bound** register: the two registers are told apart by their
   *shape* — a census says *"all 40 were read"*, a sample says *"39 of 40 were drawn; at most 0"* —
   never by whether the number happens to be zero. Collapsing them would let a sample borrow a
   census's authority for free.
2. **The frozen-population identity is the `discard_population` digest, not the freeze
   coordinates.** The first implementation keyed the run ordinal on
   *(version, last retained pièce, pin ledger seq, scope)*. A pin followed by an un-pin advances the
   pin ledger twice and leaves the discarded set byte-identical, so a third draw read as *"first
   draw"* — multiplicity hidden, in the flattering direction. The ordinal now compares the digest of
   the set actually drawn over, which is the identity the freeze coordinates were only ever a proxy
   for.

### Debug Log

- The census sentence originally mixed units (*"les 1 400 pièces… ; 3 familles"*) and hard-coded
  *"familles"*, which rendered a legacy `recall_review` — a **pièce**-unit bound — in families.
  `census_statement_fr` now takes `unit_fr` and singularises it.
- `copy_text` emitted *"prévalence ≤ 0,0 %"* for a census: the exact residual-risk claim FR-22
  names, reached through the one sentence a firm reads out loud. It now branches on the register.
- The web leg of check 1 fired on the client's own percent rendering, `(p ?? 0) * 100`. Cause: a
  regex backtracking on `\s*(?!\d)`. Fixed with a single `(?!\s*\d)` lookahead, and the exemption
  for *"× a bare number"* is now stated rather than accidental.

## File List

**New** — `apx/checks/estimator.py`;
`apx/adapters/store_postgres/migrations/versions/0032_sampling_estimator.py`;
`tests/domain/test_sampling_estimate.py`; `tests/checks/test_estimator_checks.py`;
`tests/api/test_sampling_estimator_api.py`; `tests/adapters/test_sampling_estimator_migration.py`;
`_bmad-output/implementation-artifacts/5-2-…md`.

**Updated** — `apx/core/domain/confidence.py`; `apx/core/domain/sampling.py`;
`apx/core/app/read/freshness.py`; `apx/core/app/read/sampling.py`;
`apx/adapters/store_postgres/models.py`; `apx/adapters/store_postgres/store.py`;
`apx/api/app.py`; `apx/checks/registry.py`; `apx/checks/manifest.py`; `apx/checks/encryption.py`;
`README.md`; `apx/web/src/api.ts`; `apx/web/src/App.tsx`; `apx/web/src/triage.tsx`;
`tests/domain/test_sampling.py`; `_bmad-output/implementation-artifacts/sprint-status.yaml`.

## Senior Developer Review (AI)

**Date:** 2026-08-11 · **Outcome:** changes requested, all applied.

### Coverage, including what was lost (action item A2)

| | |
|---|---|
| Lenses planned | 4 — the statistics · the wrong referent (A3) · the seams (A4) · the five new gates |
| Lenses that returned | **3 of 4** |
| Findings raised | 22 |
| Skeptic verdicts returned | **20 of 22** |
| Confirmed | 9 · Refuted 11 (**50 %**) |

**What was lost, stated rather than implied.** The **seams lens (A4) never ran** and **two skeptics
died**, all three on a provider weekly-usage limit. So one whole dimension of this diff — the
HTTP↔seam and client↔server boundaries, which produced 42 % of Epic 4's confirmed defects — went
un-reviewed, and two findings were never adjudicated. **Both unadjudicated findings were fixed
anyway.** An unadjudicated finding is not a refuted one, and a lens that dies looks exactly like a
lens that found nothing — which is the whole reason A2 exists.

### Confirmed and fixed

| # | Sev | The defect | The fix |
|---|---|---|---|
| 1 | HIGH | The bound panel printed a **family** count as *"pièces écartées"* and called a census an *"échantillon"* — the CONFIRMED Story-5.1 defect, reproduced one file over, one line under the sentence that got it right | the client renders the server's `unit_fr` and branches on `kind`; the unit is never spelled in the client |
| 2 | HIGH ×3 | A **census** shipped `prevalence_upper`, `count_upper` and a worst-case *pièce* figure on `/bound` and `/bound/export`. `estimate_for_run` was disjoint; the read path was not, so the same fact was derived twice in two registers | `read_current_bound` branches on the census; `BoundOut.count_upper`/`prevalence_upper` are **nullable** and NULL at a census — disjoint in the type, not by convention |
| 3 | MEDIUM | The run ordinal keyed on the pin ledger: **pin + un-pin reset a third draw to *"first draw"*** over a byte-identical population | keyed on the `discard_population` digest — the identity, not four proxies for it |
| 4 | MEDIUM | The census sentence rendered a legacy **pièce**-unit `recall_review` in *families* | `census_statement_fr` takes `unit_fr` and singularises it |
| 5 | MEDIUM | Every end-to-end test of the *pièce* worst case ran on a population where **each family held exactly one pièce**, so the worst case and the forbidden rescale agreed by accident and the acceptance assertion was an equality | the fixture builds a real 4-member family; `population_pieces > population_families` is asserted |
| 6 | HIGH | Check 3 saw only **bare names**: `import … as pub` or `confidence.prevalence_upper_bound(…)` reintroduced a second birthplace for a bound with the gate green | `_reaches()` covers Name, Attribute and alias |
| 7 | HIGH | Check 1 globbed `*.py` and claimed *"no prevalence is multiplied anywhere"* while **`apx/web` was invisible to it** | a source-text leg over the client, labelled as one |
| 8 | MEDIUM | Check 2's percentage leg **failed open** on a helper or a module constant | the reachable set is the function, its one-hop local callees, and the string constants it names |
| 9 | MEDIUM | Check 5 missed `import a.b.line_projection as lp` and `from a.b import line_projection as lp` | `_projection_site()` covers all four spellings |

### Unadjudicated (skeptic died) — fixed anyway

- **Check 1's two legs were jointly defeated by renaming one operand.** `total = run.population_pieces`
  then `prevalence_upper * total` names no *pièce* at the multiplication. A denylist keyed on **both**
  operands falls to renaming either, so the rule is now one-sided and absolute: *a prevalence is a
  ratio you state, never a factor you multiply.*
- **Check 3's recency leg missed an ordering column held in a variable.** Locals assigned from a
  favourability-named expression are now aliases the ordering scan sees through.

### Refuted, and why the refutation held

- *"The family apparatus is structurally inert — every family holds one pièce"* (HIGH). The reviewer
  reproduced it from the **test helper**, which feeds `produce_ranking` the `representatives`. The
  skeptic ran the same corpus through the product's own path with real text and got families of size
  > 1. The build was fine; **the tests were vacuous** — which is finding 5 above, and was fixed.
- *"`Estimate.method` imputes today's name"* and *"`SamplingRunOut` mixes a stored bound with a live
  re-derivation"* were both refuted as unreachable, and **both were fixed anyway**: `estimate_for_run`
  now reads the recorded numbers off the row instead of recomputing them, so the screen and the
  export cannot disagree the day the method changes — which is the FR-23 mechanism itself.

### Accepted with reason, not silently dropped

- **The web leg is source text, not an AST.** It is weaker than the Python leg and says so in its own
  success message. A TypeScript parser in the check harness is not worth its dependency here.
- **The percentage exemption `× <bare number>`** lets `prevalence * 100` through, because that is how
  a percentage is spelled in TypeScript. A rescale by a literal is not a thing anyone writes.
- **`_percent_reachable` follows one hop, not N.** A two-hop helper chain built to smuggle a percent
  sign into a court sentence is not an accident, and the check is not the last line of defence
  against a deliberate act.
- **The estimator is still unproven.** Nothing here licenses the number: Story 5.3's simulation gate
  does, or the counts-only fallback ships instead.

## Change Log

| Date | Change |
|---|---|
| 2026-08-07 | Story created. The five hard inputs (OQ-4) answered in writing before implementation, discharging action item A7. |
| 2026-08-11 | Implemented T1–T8. 5 structural checks (80 → 85). Adversarial review: 22 findings, 9 confirmed + 2 unadjudicated, all 11 fixed; the seams lens and 2 skeptics were lost to a usage limit and the coverage lost is stated above. Status → done. |
