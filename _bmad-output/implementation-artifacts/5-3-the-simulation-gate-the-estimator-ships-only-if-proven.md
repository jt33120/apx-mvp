---
baseline_commit: 4045623
---

# Story 5.3: The simulation gate — the estimator ships only if proven

Status: done

## Story

As a firm that will say this number to a judge,
I want the estimator validated by simulation against populations whose truth is known, in CI,
So that an unsound estimator cannot ship — the exact discipline the false "1.5%" claim failed.

## Scope note — this is the story that can say no

Stories 5.1 and 5.2 both refused, in their own docstrings, to claim the number was trustworthy. 5.1:
*"Nothing here makes it newly trustworthy, and nothing here pretends it does."* 5.2: *"this story is
not where the number becomes proven."* **This is where it becomes proven, or does not.**

The failure this exists to prevent is recorded in the PRD's own §0.2: the *confidence bound* was
written into a brief, a glossary, three FRs and a north-star metric as *"risk of having missed a
relevant document below 1.5%"* — **and it was false**, and it survived every prior review on
editorial care alone. SM-1 names the lesson in one line: *"a test that recomputes a wrong number and
gets the same wrong number passes."*

So the gate is not a test that the estimator runs. It is a test that the estimator is **right**, run
against populations whose truth is known by construction, and a product that emits **counts only**
when it is not.

## Acceptance Criteria

**AC-1.** **Given** the estimator, **when** the simulation harness runs in CI, **then** it generates
populations at varying relevant-item prevalence and varying duplicate structure, runs the sampling
procedure many times, and asserts a stated C% bound holds in **at least** C% of runs (FR-23, SM-1).

**AC-2.** **And** SM-1 asserts **soundness**, not merely reproducibility of the number — and this
story adds the other half nobody wrote down: **not vacuity either.** A bound that always answers
*"at most all of them"* covers the truth 100 % of the time and says nothing. The gate has a floor
**and** a ceiling.

**AC-3.** **And** the harness records explicitly that it validates the estimator against its
**assumed model**, not the assumption that a real *discarded set* resembles the simulated ones —
which is what the *gold set* and calibration (SM-17) are for, and where the honest residual
uncertainty lives. The caveat is carried on the verdict the harness emits, not only in prose.

**AC-4.** *(failure path)* **And** where the estimator is not proven, the product emits the
**counts-only** fallback and no bound: *"200 familles tirées au hasard parmi les 1 400 écartées ; 3
pertinentes"* — no percentage, no projection, and it says why (FR-23, ties 5.4).

**AC-5.** **And** the gate is unbypassable: a structural check asserts the proven flag cannot be
true unless the harness exists, declares its coverage target, asserts **both** the floor and the
ceiling, and is exercised by a registered test — the `gold_gate` pattern, applied to the one number
this product exists to say.

**AC-6.** **And** the simulation is **deterministic**: seeded per scenario, so a CI run is
reproducible and a failure is a fact rather than a mood. *A strict rule on a noisy measure produces
flaky builds, and flaky builds get disabled — which is how a gold set stops running for the second
time (the PRD's own words at SM-2).*

---

## The design record

### Decision 1 — there are TWO coverage claims, and the second is the one this story is really for

The obvious claim is over families: **P(D_true ≤ `count_upper_families`) ≥ C**. That validates the
hypergeometric, and the hypergeometric is textbook — the simulation will pass it, and passing it
proves the implementation, not the mathematics.

The claim that is genuinely this build's own is the one Story 5.2 invented: **P(relevant *pièces* ≤
`count_upper_pieces`) ≥ C**, where `count_upper_pieces` is the sum of the `D` largest frozen family
sizes.

**This is where AC-1's *"varying duplicate structure"* actually bites.** Duplicate structure is
irrelevant to the family claim — the hypergeometric over families does not know that families have
sizes. It is entirely load-bearing for the *pièce* claim. A harness that varied duplicate structure
and only checked the family claim would be running an expensive no-op and reporting a green build.

*(The pièce claim is provable on paper: on the event `{D_true ≤ D_upper}`, the relevant pièces are at
most the sum of the `D_true` largest sizes, which is at most the sum of the `D_upper` largest, so it
inherits the family claim's coverage. The simulation is still worth running, because the proof is
about the estimator and the test is about the **implementation** — a `sorted()` without `reverse=True`
satisfies the proof and fails the test.)*

### Decision 2 — the adversarial scenario is mandatory, not optional

The *pièce* claim's worst case is **the relevant families are the largest ones**. A harness that
assigned relevance uniformly at random over families would sample that case with vanishing
probability at exactly the sizes where it matters. So one scenario family assigns relevance
**adversarially, to the largest families first**, and it is not optional.

### Decision 3 — soundness alone is satisfiable by a useless estimator, so the gate has a ceiling

`count_upper = N` always covers. It is perfectly sound and perfectly worthless, and it would pass
every assertion AC-1 asks for. So each scenario also asserts the bound is **materially below the
population** where the sampling fraction can support that — a *tightness floor*, stated per scenario
as a maximum acceptable `prevalence_upper` at zero found.

This is not in the AC. It is in this story because the AC is satisfiable without it, and a gate that
can be satisfied by breaking the thing it guards is not a gate.

### Decision 4 — deterministic, and the assertion is made on EVIDENCE, not on the observation

Seeded per scenario, so a CI failure is reproducible on a developer's machine rather than arriving
as a mood. The harness also asserts its own **shape** — a minimum trial count — so a future edit
cannot quietly reduce the draws and keep the green tick. A gate whose sample size nobody asserts is a
gate that can be turned off without being removed.

**Corrected during implementation, and the correction is the most important thing in this story.**
The first draft asserted the observed coverage directly, on the argument that a deterministic run
needs no Monte-Carlo tolerance because the exact hypergeometric bound over-covers anyway. Measured,
that argument was wrong where it mattered: at 500 trials the tightest scenario
(`flat-120-half-relevant`) cleared the target by **0.8 of a standard error** — an observed 0.9580
entirely consistent with a true coverage of 0.94.

Determinism is not evidence. A seeded run returns the same number every time; it does not make that
number a reliable estimate of the thing being measured. The gate would have passed, for ever,
deterministically, on evidence it did not have — which is SM-1's own failure wearing the costume of a
green build, inside the harness built to prevent it.

So `sound` is judged on a one-sided **Wilson lower confidence bound** on each coverage, at 8 000
trials, and it now states what it means: *at 95 % confidence, the true coverage is at least C.* The
tightest scenario's lower bound is 0.9525. The observed proportions are recorded beside the bounds so
a reader can see the slack rather than take the assertion's word for it.

### Decision 5 — "does not ship" is a fourth register, not a warning

When the estimator is not proven, `estimate_for_run` returns `KIND_COUNTS_ONLY`, carrying `N`, `n`
and `k` and **nothing else**: no `prevalence_upper`, no `count_upper`, no worst case. The register is
disjoint in the type, exactly as census and bound already are (Story 5.2, OQ-4 input 2), so no
surface can render a bound the product has not earned by consulting a flag it forgot to check.

`estimator_is_proven()` is consulted at the **one place a bound is born**. The structural check that
holds it is the `gold_gate` pattern: the flag may be true only if the harness exists, names its
target, asserts floor and ceiling, and is run by a registered test.

### What this story does NOT decide

- **The sentence.** Story 5.4 owns the words, the copyable text and the banned-phrasing check. This
  story produces the fourth `Estimate` register the counts-only sentence will render.
- **Whether a real discarded set resembles a simulated one.** It does not, necessarily, and nothing
  here claims otherwise — AC-3 exists to make that refusal explicit rather than implied.
- **Calibration (SM-17).** Different question, different evidence, and Story 5.2 already recorded
  that the only labelled corpus in the plan is not admissible for it.

---

## Tasks / Subtasks

- [x] **T1 — The verdict type and the caveat it carries.** `SimulationVerdict` in the domain:
  scenario name, trials, observed family coverage, observed pièce coverage, target, the tightness
  figure, and `validates_fr` / `does_not_validate_fr` — the AC-3 caveat as data. *(AC-3)*
- [x] **T2 — The population generator.** `apx/eval/estimator_simulation.py`: build a population of
  families with a given size distribution and a given relevant set, uniform **and** adversarial
  (largest-first). Seeded. *(AC-1, AC-2, AC-6)*
- [x] **T3 — The trial loop.** Draw without replacement through the product's own
  `draw_families`, compute through the product's own `estimate_for_run`, count coverage of both
  claims. Memoise the estimator per `(N, n, k, c)` in the HARNESS — never in the domain. *(AC-1)*
- [x] **T4 — The scenario set.** Prevalence 0 / 1 / 5 / 20 / 50 %, populations 40 / 120 / 1 400,
  duplicate structure singletons / few-large / heavy-tailed, sample sizes small / medium /
  near-census / census, and the adversarial relevance assignment. *(AC-1, AC-2)*
- [x] **T5 — `estimator_is_proven()` and the fourth register.** `KIND_COUNTS_ONLY`; the predicate
  consulted where the estimate is born; disjointness extended. *(AC-4)*
- [x] **T6 — The gate check** `estimator-simulation-gate`, plus the disjointness check extended to
  the third register. Both proven live. *(AC-5)*
- [x] **T7 — CI + the fitness driver** run the simulation; the API and the client render the
  counts-only register honestly. *(AC-1, AC-4)*
- [x] **T8 — Gate:** ruff · import-linter · harness · pytest · tsc · vite build.

## Dev Notes

- The estimator is **not** modified. If the simulation fails, the correct response is the
  counts-only fallback, not an adjustment to the statistic until it passes — that is how the false
  1.5 % happened.
- `_iter_py`, `_parse`, `_is_call_to` in `apx/checks/payload_schema.py` are the shared check
  primitives; `apx/checks/gold_gate.py` is the pattern for T6.
- Lockstep remains three sites: `checks/registry.py`, `checks/manifest.py`, `README.md`.
- Accented characters push lines past ruff's 100; reflow by hand.

## Dev Agent Record

### Completion Notes

**The result.** All 14 scenarios cover, at 8 000 trials each. The tightest is
`flat-120-half-relevant`: observed family coverage 0.9564, one-sided lower bound **0.9525**, against
a target of 0.95. Computed exactly — no simulation — the true coverage of that scenario is
**0.959637**, and the harness's draw lands 0.0033 from it. `ESTIMATOR_PROVEN = True` is therefore a
claim with a proof behind it, and the proof runs in CI, in the offline fitness frame, and in pytest.

**Three things this story found in itself, before any reviewer did.**

1. **The gate was asserting a pass it had not earned.** The first draft ran 500 trials and asserted
   the observed proportion. At 500 trials the tightest scenario cleared the target by 0.8 of a
   Monte-Carlo standard error — an observed 0.9580 wholly consistent with a true coverage of 0.94.
   Determinism had been mistaken for evidence: a seeded run returns the same number every time, and
   that does not make the number a reliable estimate of anything. Now judged on a one-sided Wilson
   lower bound at 8 000 trials. **This is SM-1's own failure, found inside the harness built to
   prevent it**, and it is the reason this story exists rather than a footnote to it.
2. **The harness was validating a path the product does not take.** It called
   `prevalence_upper_bound` directly; `complete_sampling_run` calls `bound_for_run`. Caught by the
   Story-5.2 check `estimator-one-run-one-bound`, which fired on the new module — a check written
   for a different reason, catching this one. What is simulated must be what ships.
3. **The tightness ceiling was asserted on a trials-dependent number.** `worst_prevalence_upper` is
   the loosest bound *observed*, and it grows as trials rise, so raising the trial count — a good
   change — would have reddened the build. The ceiling now sits on the deterministic bound at zero
   found. 13 of 14 scenarios carry one; the fourteenth is `tiny-4-one-drawn`, where one draw from
   four buys a bound of 0.75 and the honest report is that the draw is not worth making.

**The design decision that surprised me.** A **census survives an unproven estimator**. It makes no
statistical claim at all — every unit was read, and the count is a fact about what the lawyer saw.
Withholding it because the *estimator* is unproven would suppress a true statement on the grounds
that a different, absent statement is untrustworthy. So the register order is census → counts-only →
bound, in `estimate_for_run` and in `BoundReading.kind` alike.

**What the simulation does not prove, restated because it will be quoted.** It validates the
estimator against its assumed model: a finite population of exchangeable units drawn without
replacement. It says nothing about whether a real *discarded set* resembles the simulated ones. That
is the *gold set* and SM-17, and it is where the honest residual uncertainty lives — carried on every
`SimulationVerdict` as data, not left in a docstring.

### Debug Log

- The banned-phrasing check (FR-23) fired on this story's own module docstring, which quoted the
  false §0.2 sentence verbatim to explain what it forbids. The check was **not** weakened: the
  docstring now names the error without spelling it, because a comment is one copy-paste from a
  string and that string set is the one a translator edits.
- The secret scanner (FR-51/AD-47) fired on the scenario name `few-large-120-ADVERSARIAL` — 25
  characters, mixed case, reads as a token. The names changed; the scanner did not.
- The gate check reported the harness's own `SCENARIOS` missing: `SCENARIOS: tuple[...] = (...)` is
  an `ast.AnnAssign`, not an `ast.Assign`. Fail-closed behaviour working as designed.

## File List

**New** — `apx/eval/estimator_simulation.py`; `tests/eval/test_estimator_simulation.py`;
`_bmad-output/implementation-artifacts/5-3-…md`.

**Updated** — `apx/core/domain/confidence.py` (`ESTIMATOR_PROVEN`, `estimator_is_proven`);
`apx/core/domain/sampling.py` (`KIND_COUNTS_ONLY`, `counts_only_statement_fr`, the fourth branch);
`apx/core/app/read/freshness.py` (`BoundReading.kind` three-way, the counts-only sentence);
`apx/api/app.py` (the register allow-list); `apx/checks/estimator.py`
(`the_simulation_gate_is_wired`, disjointness extended to the third register, the percent guard
extended to the second sentence); `apx/checks/registry.py`; `apx/checks/manifest.py`; `README.md`;
`apx/fitness/driver.py`; `.github/workflows/ci.yml`; `apx/web/src/api.ts`; `apx/web/src/triage.tsx`;
`tests/domain/test_sampling_estimate.py`; `tests/checks/test_estimator_checks.py`;
`_bmad-output/implementation-artifacts/sprint-status.yaml`.

## Senior Developer Review (AI)

**Date:** 2026-08-11 · **Outcome:** changes requested, all applied.

### Coverage (action item A2)

| | |
|---|---|
| Lenses planned / returned | 4 / **4** — soundness · wrong-referent (A3) · **seams (A4)** · the new gates |
| Findings raised | 27 |
| Skeptic verdicts returned | **54 of 54** |
| Confirmed | **8** · Refuted 19 (70 %) |
| Lenses lost · skeptics lost · unadjudicated | **0 · 0 · 0** |

**Full coverage, for the first time in this epic.** The seams lens (A4) — which died on a usage
limit during the Story 5.2 review and left that dimension unreviewed — ran here and produced three
of the eight confirmed defects. Every finding was adjudicated by two independent skeptics.

**The reviewers were working against a moving tree.** Several findings were refuted with the words
*"fixed before I looked"*: I was repairing confirmed defects while later skeptics ran. Those are
counted as confirmed below, because they were real when filed.

### What the statistics lens proved, independently

Worth recording because it is the evidence the product's right to state a number rests on. The lens
did not merely fail to find defects — it verified the claims:

- **The estimand is correct.** `P(D_true ≤ count_upper) ≥ C` at fixed *(N, D, n)* is the right
  frequentist notion for a one-sided upper bound, and it holds **exactly**: coverage = `P(K ≥ k*)`
  with `k* = min{k : P(X ≤ k | D_true) ≥ α}`, so coverage exceeds `1 − α` by construction and
  discreteness makes it strictly conservative.
- **The *pièce* monotonicity argument is sound and could not be broken.** No population and draw
  exist where family-covered fails to imply pièce-covered.
- **The sampler is not biased.** An independent exact-coverage computation agreed with the
  simulation within |z| ≤ 2.5 across all scenarios; a chi-square of the observed `found`
  distribution against the exact hypergeometric came in at 38.2 on ~16 bins, and all 8 000 drawn
  subsets were distinct.
- **The gate has real discriminating power.** Injecting `count_upper − 1`, `− 2`, `× 0.95` and
  `× 0.90` each turned 4–5 of 14 scenarios red.
- **The arithmetic holds at scale.** `bound_for_run` at N = 200 000, n = 800 runs in 14 ms with no
  overflow, so the scenario set's ceiling of 1 400 hides no failure.

It also confirmed, in its own words, that the 500-trial defect I found and fixed mid-story was real:
*"at 500 trials … an estimator with true coverage 0.94 passed with ~20 % probability"*.

### Confirmed and fixed

| # | Sev | The defect | The fix |
|---|---|---|---|
| 1 | HIGH | **`/sampling/runs` shipped `count_upper` and `prevalence_upper` beside `estimate_kind: "counts_only"`** — read straight off the frozen row, never consulting the register the same function had computed two lines earlier | the payload reads the register-aware **estimate**; the row is where numbers were recorded, the estimate is what the product may say |
| 2 | HIGH | **`/bound` and `/bound/export` shipped the worst-case *pièce* projection in the counts-only register.** The allow-list covered two of the four register-dependent fields — gating some of a register's fields is not gating the register | all four gated, `relevant_pieces` on census, the rest on bound |
| 3 | HIGH | **The gate never checked that `estimator_is_proven()` reads `ESTIMATOR_PROVEN`** — `return True` passed every leg, on the one seam the whole mechanism hangs from | `_reads_the_flag` |
| 4 | HIGH | **The anti-vacuity ceiling watched the *family* bound only**, so a *pièce* conversion returning the whole pile covered 100 % of the time and passed. No ceiling can fix it — with lumpy families the honest worst case really is 65 % of the pile — so the figure is now asserted **exactly**, against a computation the test does itself | `best_count_upper_pieces` + an exact assertion |
| 5 | MEDIUM | **The run panel rendered nothing at all in the counts-only register.** A lawyer who has just spent an evening on verdicts and is shown no outcome concludes the tool lost her work, not that it refused to state a number | a third arm, and `estimate_kind` became a typed union instead of `string` |
| 6 | MEDIUM | **The floor/ceiling legs were substring greps over the unparsed module** — `ast.unparse` keeps docstrings, so naming a marker in prose satisfied it — **and the floor used `any()`**, so asserting only the textbook family claim was enough | only `assert` statements are searched, and **both** claims are required |
| 7 | LOW | **A one-line `conftest.py` de-collected the gate** while the check reported it green; its only evidence of registration was that the file existed | conftests on the path are read; `pytestmark`, imperative `pytest.skip()` and class decorators are caught too |
| 8 | LOW | **`GET /sampling/sizing` promised a prevalence the unproven estimator would not be allowed to state.** A sizing is a plan, but it is a quantitative promise, and breaking it after an evening of verdicts is the cost | the plan carries `bound_will_be_stated` and a French caveat; the reading burden is unchanged, only the promise |

### Refuted, and worth recording

- *"The gate proves single-draw coverage; the product publishes the most recent of an unbounded
  number of draws"* — the arithmetic reproduces (it is `p^R`, the coverage of the **minimum** of R
  bounds), but `read_current_bound` orders by **recency**, not by favourability, so the product does
  not implement the selection rule the finding models. That refusal is Story 5.2's decision, and it
  is what makes this finding refutable rather than fatal.
- *"The harness bypasses `estimate_for_run`, so census scenarios certify a bound the product refuses
  at n == N"* — mechanism reproduced, consequence absent.

### Accepted with reason

- **The simulation validates the estimator against its assumed model, and nothing else.** Carried on
  every verdict as data. The *gold set* and SM-17 are where the residual uncertainty lives.
- **`_percent_reachable` follows one hop.** A two-hop helper chain to smuggle a percent sign into a
  court sentence is not an accident.
- **The web leg of `estimator-piece-worst-case` is source text, not an AST**, and says so.

## Change Log

| Date | Change |
|---|---|
| 2026-08-11 | Story created with its design record: two coverage claims, the adversarial scenario, the tightness ceiling, determinism, and counts-only as a fourth register. |
| 2026-08-11 | Implemented T1–T8. Simulation gate over 17 scenarios at 8 000 trials, judged on a Wilson lower bound; `estimator-simulation-gate` (85 → 86). Review: 4/4 lenses, 27 findings, 8 confirmed, all fixed, 0 lost. Status → done. |
