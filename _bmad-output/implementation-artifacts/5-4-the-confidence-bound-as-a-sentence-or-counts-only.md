---
baseline_commit: 9f44f48
---

# Story 5.4: The confidence bound as a sentence, or counts only

Status: done

## Story

As a sceptical lawyer,
I want a completed run to give me a sentence I can say to a client or a court, or honest counts if
no defensible bound exists,
So that I am never handed a number nobody can defend.

## Scope note — this story owns the words, and the words are the product

5.1 drew the sample. 5.2 computed the number. 5.3 proved the number. **This story is where the
number becomes a thing a human says out loud** — and it is the only artefact in this product that
routinely leaves it. A bound rendered on screen is qualified by everything around it: the panel, the
chip, the version header, the staleness tone. A bound *pasted into an email* is qualified by
nothing except the characters inside it.

That asymmetry is the whole design problem. §0.2 is the proof it is not hypothetical: a false
sentence — *"risk of having missed a relevant document below 1.5%"* — travelled from a brainstorm
into a brief into a glossary into three FRs and into the north-star metric, and every reader along
the way was a careful one. **Editorial care already failed at this exact task, in this exact
document.** FR-23's answer is to make the correction mechanical (FR-56), and that is the largest
single piece of work here.

## Acceptance Criteria

**Given** a completed *sampling run* with a proven estimator,
**When** the sentence is produced,
**Then** it reads *"N pièces sampled at random from the M discarded; K relevant. With C% confidence,
at most X% of the discarded set — about Y pièces — is relevant."*, copyable as text, carrying its
*RBAC scope* and its staleness state in the copied string (FR-23, FR-58).
**And** where the estimator is not proven sound, the product emits **counts only** — *"200 pièces
sampled at random from the 1 400 discarded; none relevant"* — with no bound and no projected figure,
and says so (FR-23).
**And** the sentence is regenerable from the *audit record* with **no** model call — a statistical
claim never depends on the network (FR-55, FR-36).
**And** a static check asserts no banned phrasing — *"risk of having missed"*, or any wording
implying a probability that nothing remains — appears in any locale's string set (FR-23, FR-56).

### Adopted from FR-23, absent from the epics' AC list — the unfitness declaration

FR-23's seventh consequence:

> **Where K approaches N — the reviewer disagrees with most or all of the sample — the finding is
> that the ranking carries no signal, not that the line is misplaced.** At a configured threshold
> the system declares the *ranking version* unfit for this *matter*, says so in words, produces a
> *worklist* line offering a re-rank with a revised or newly written *case theory* (FR-37), and
> **does not offer a line move as the remedy**.

`grep -rn "unfit"` returns **zero hits** across `epics.md`, the architecture spine, and the whole
runtime tree. No story claims it. It is a consequence *of the sentence* — it is what the sentence
must say when the sample comes back mostly relevant — so 5.4 adopts it rather than leaving FR-23
partially built with nobody's name on the remainder. FR-56: a property with no check is not a
property; an FR consequence with no story is not a requirement.

### UX pass — discharged before implementation

The epics mark this story *"UX pass required before implementation. No UX design contract exists
yet. The sentence and its visual register — distinct from the priced projection of FR-19 — are the
product's most consequential text."*

Discharged: [`EXPERIENCE-EPIC5.md`](../planning-artifacts/ux-designs/ux-apx-mvp-2026-07-27/EXPERIENCE-EPIC5.md)
+ [`mockups/epic-5-the-sentence.html`](../planning-artifacts/ux-designs/ux-apx-mvp-2026-07-27/mockups/epic-5-the-sentence.html).
The contract's load-bearing decision is the **two-register separation** the epics' note asks for:
the priced projection (FR-19) and the confidence bound (FR-23) never share a container, a numeral
treatment, a verb mood, or a copy affordance — *"only a constat can be copied"*, because copying is
the act of taking a number somewhere its qualifications do not follow.

---

## The design record

### Decision 1 — the sentence gets exactly one owner, and it is the Domain

Before this story the four registers' words lived in **three** places: `census_statement_fr` and
`counts_only_statement_fr` in `core/domain/sampling.py`, the bound sentence composed inline inside
`BoundReading.copy_text` in `core/app/read/freshness.py`, and `no_population` with no sentence at
all. Two layers, three homes, one missing.

That split is not a tidiness complaint. FR-23 makes the banned-phrasing list a **structural
property**, and a structural check over *the words* is only as good as its knowledge of where the
words are. A check pointed at the Domain would have been green while the most-quoted sentence in
the product was composed one layer up. Worse, the register split is only as strong as its
least-careful composer: the read seam had to re-derive `kind` and re-branch, and the Story 5.2
review found that same duplicated branching wrong in three separate readers.

`apx/core/domain/statement.py` owns all four registers. The read seam delegates and adds nothing.
The API serialises what the Domain composed. The client renders it verbatim.

### Decision 2 — the sentence states the draw, then the bound; one declared deviation from §0.2

The shipped bound sentence stated the bound and **not the draw**: it opened at *"Avec une confiance
de 95 %…"*. §0.2's corrected form opens with what was drawn, and it opens there for a reason — *"200
pièces sampled at random from the 1 400 discarded; none relevant"* is the evidence, and the bound is
the inference. A sentence that states an inference without its evidence is asking to be believed
rather than checked.

**Declared deviation.** §0.2 reads *"— about Y pièces —"* and says the corrected sentence is *"used
verbatim from this revision onward"*. This build says **« soit au plus Y pièces au pire »**, not
*« environ »*. Story 5.2 established that the *pièce* figure is a **worst case** — the sum of the
`D` largest frozen family sizes — precisely because `prevalence × pièces` understates whenever the
large thread-families are the relevant ones. *« Environ »* on a worst case understates it again, in
the flattering direction, which is the one direction §0.2 exists to forbid. The deviation makes the
sentence *more* conservative than the PRD's wording, never less.

### Decision 3 — the RBAC scope is named unconditionally, because the conditional's referent does not exist

FR-23: *"The scope is stated in the sentence itself **where the scope is narrower than the
matter**"* — the failure named is a lawyer saying *"1 400"* to a court about a *matter* holding
2 100.

In this build a *matter* sits behind **exactly one** wall (`matter_scope`), and a *pièce* carries no
scope column at all (`no_custodian_or_scope_column_on_piece`, Story 1.3). A reader either holds the
matter's wall and sees all of it, or does not see the matter. **There is no state in which the
population is narrower than the matter**, so a check of "is the scope narrower?" would be a
comparison whose right-hand side does not exist — this project's recurring defect, the nearly-right
referent, written deliberately.

So: the sentence **always** names the wall the number was computed under. Unconditional inclusion
satisfies a conditional requirement and cannot be wrong. And it is not vacuous, because a matter
*can* be re-scoped (`admin_rescope`, Story 1.6): a bound drawn under wall A and read after the
matter moved to wall B names A, and the surface says the two differ. That is the real version of
the failure FR-23 describes, and naming the wall is what catches it.

### Decision 4 — "regenerable without a model call" is proven by REGENERATING, not by asserting an absence

FR-55 requires the sentence to render offline; FR-23 requires *"every number in the sentence is
reconstructible from the audit record alone. **Asserted by test: recompute from the exported audit
record and compare.**"*

A check that the statement module imports no LLM adapter is a check on an **absence** — it passes on
an empty file, it passes on a module that never composes anything, and it would keep passing the day
someone reached the network through a seam it does not enumerate. Absence-checks are how a green
build gets built around a hole.

The positive proof is the round trip: take the **exported** audit record for a completed run,
reconstruct the statement inputs from it and nothing else, regenerate the sentence, and compare it
**character for character** against the live one. It fails if any number in the sentence is not in
the record — which is FR-23's requirement stated as an executable rather than as an intention. The
absence-check ships too (it is cheap and it catches the obvious regression), but it is the
belt, not the braces.

### Decision 5 — the banned list has been looking for the false claim in a language this product does not speak

`no_banned_confidence_phrasing` has been in the registry and **green** since Story 1.12. Its list:

```
"risk of having missed a relevant document", "probability that nothing was missed",
"probability that nothing relevant was missed", "chance that nothing was missed",
"chance that nothing relevant was missed"
```

Five phrases, **all English**. Every user-facing string in this product is **French**. The check has
been passing for eleven stories because it was looking for the wrong-language version of a sentence
nobody was going to write in that language. It is the perfect specimen of this project's own named
defect: a comparison whose right-hand side is not the thing on its left, failing green.

Fixed three ways:

1. **The product's own language first.** French shapes — *risque d'avoir manqué*, *probabilité que
   rien*, *aucun risque d'avoir manqué*, *chance que rien*, *risque de passer à côté* — plus the
   Italian ones FR-23 names explicitly (*"so a translator cannot reintroduce the false claim in
   French or Italian"*).
2. **Shapes, not only literals.** A translator's near-miss (*"le risque de ne rien avoir manqué"*)
   is not on any literal list anyone would write. A small family of proximity patterns catches
   *risque|probabilité|chance* within a short window of *manqué|oublié|passé à côté|rien ne reste*,
   in each locale.
3. **It is no longer vacuous.** Story 5.4 ships the string set the check exists to police, and the
   check now scans the statement module's literals as its primary target rather than as a
   hypothetical future one.

### Decision 6 — the unfitness threshold refuses the remedy, it does not merely add a warning

FR-23 says the system *"does not offer a line move as the remedy"*. A greyed control still proposes
the act; a warning beside an enabled control is a warning nobody reads. The declaration **removes**
the line-move affordance and offers exactly one remedy: re-rank with a revised or newly written
*case theory*.

The threshold is *configuration-as-data* (`sampling.unfit_relevant_share`, default **0.5**). The
default is stated as a rule, not as a discovery: at or above half the sample coming back relevant,
the finding is about the order, not about where it was cut. The declaration **names the share it
crossed**, so the reader sees the rule that fired rather than only its verdict.

And it is a **qualification, not a replacement**: the bound is still stated beneath — wide and
unflattering — because FR-23 also says the product *"never suppresses or reframes an unfavourable
result"*.

### What this story does NOT decide

- **The audit record itself** is Story 5.5. This story consumes the *sampling run*'s own recorded
  row as the record for its round-trip proof, and says so; when 5.5 lands, the round trip moves to
  the real export and the assertion tightens rather than changing shape.
- **The locale mechanism.** There is one locale (French). `no_hardcoded_locale` and FR-36's
  language-to-the-model contract are Story 6.5's. What lands here is the banned list *as data*, in
  every language it currently knows, so 6.5 inherits a policed string set rather than an empty one.
- **The worklist line's plumbing.** `worklist.py` already derives lines from freshness assessments;
  the unfitness line is derived from the *estimate*, and this story adds that derivation. Whether a
  worklist line can be dismissed, snoozed or actioned in place is untouched.

---

## Tasks / Subtasks

- [x] **T1 — one owner for the sentence.** `apx/core/domain/statement.py`: the four registers'
      French text, composed from one frozen input, pure. `sampling.py`'s two statement functions
      move here; `BoundReading.copy_text` delegates.
- [x] **T2 — the §0.2 form.** The bound sentence gains its draw clause; K>0 says so; the *pièce*
      worst case keeps its « au pire » wording. `no_population` gains a sentence.
- [x] **T3 — the wall in the string.** The recorded bound carries the scope it was computed under;
      every register's sentence names it; the surface says so when it differs from the matter's
      current wall.
- [x] **T4 — regenerable, proven by the round trip.** Reconstruct from the recorded run and compare
      character for character; plus the offline structural check and a fitness stage.
- [x] **T5 — the banned list made live and multilingual.** French + Italian literals, the proximity
      shapes, and a fixture proving each fires.
- [x] **T6 — the unfitness declaration.** Threshold as configuration, the declaration in words, the
      worklist line, and the structural check that the unfit branch offers no line move.
- [x] **T7 — the surfaces.** `BoundOut` carries the accompanying record; the React panel renders the
      four registers, the record, the copy failure path and the unfit block.
- [x] **T8 — the gate.** ruff · import-linter · the structural harness · pytest · offline fitness ·
      `tsc` · `vite build`.

## Dev Notes

**The lockstep, three sites.** A new structural check needs `apx/checks/registry.py` (import +
`CHECKS`), `apx/checks/manifest.py` (`_p(key, fr, ad, name, callable, inspects)`), and the
`README.md` `<!-- structural-properties -->` block. `manifest_matches_readme` compares the first
five cells only. **86 → 89** expected.

**The recurring defect to hunt in review.** A nearly-right referent — a comparison whose right-hand
side is not the same thing as its left, always failing toward falsely-fresh or flattering. This
story already contains one specimen found before implementation (Decision 5, the English-only banned
list). The review should assume there is another.

---

## Dev Agent Record

### Completion Notes

The story shipped its six decisions and adopted FR-23's seventh consequence. Two defects were found
**before** the review — the English-only banned list (Decision 5) and the two unfitness denominators
— and the review found twenty-four more.

**What the sentence is now.** One Domain module composes all four registers; the two read seams and
the client render what it produced and add nothing. The bound register opens on the draw and closes
on the inference, names the wall and the freshness state **inside the string**, states the *pièce*
figure as a worst case or says it is not computable, and can be regenerated character-for-character
from the exported record with every socket refused.

**What it refuses.** A percentage that would round to zero from a non-zero count. A census carrying
any percentage at all. A bound the estimator has not earned. A line move where the ranking carries
no signal. And, across three languages, the sentence §0.2 recorded as false.

### Debug Log

- The **census check failed closed** the moment the sentence functions left `sampling.py` — which is
  what a fail-closed check is for. Repointed at `statement.py` rather than relaxed.
- The **banned-phrasing check fired on `line_projection.py`'s docstring**, which named the false
  claim in order to forbid it. Story 5.3's precedent applied: rewrite the prose, never the check.
- The **one-composer check fired on `confidence.prevalence_fr`'s own docstring**. Docstrings are now
  exempt from the *shapes* and from the fragment scan, and still held to the literals — a docstring
  is documentation, not a string set, and prose has to be able to quote what it explains.
- The offline fitness stage moved the confidence bound **off the model-degradation list**, which
  broke a driver test asserting it was on it. The test was strengthened, not relaxed: FR-55 names
  that exclusion in as many words, and the old assertion matched on the word *"confidence"* — so the
  test that enumerates what the model's absence costs was asserting it cost the one capability FR-55
  says it must not.

## File List

**New** — `apx/core/domain/statement.py` · `apx/checks/statement.py` ·
`tests/domain/test_statement.py` · `tests/checks/test_statement_checks.py` ·
`tests/api/test_statement_api.py` · `tests/api/test_statement_roundtrip.py` ·
`_bmad-output/planning-artifacts/ux-designs/ux-apx-mvp-2026-07-27/EXPERIENCE-EPIC5.md` ·
`…/mockups/epic-5-the-sentence.html`

**Updated** — `apx/core/domain/{confidence,sampling,worklist,config,line_projection}.py` ·
`apx/core/app/read/{freshness,sampling}.py` · `apx/adapters/store_postgres/store.py` ·
`apx/api/app.py` · `apx/checks/{forward_looking,estimator,registry,manifest}.py` ·
`apx/fitness/driver.py` · `apx/web/src/{App.tsx,triage.tsx,api.ts,tokens.css}` · `README.md` ·
`tests/domain/{test_sampling,test_sampling_estimate}.py` ·
`tests/checks/test_estimator_checks.py` · `tests/api/{test_sampling_api,test_sampling_estimator_api}.py` ·
`tests/fitness/test_driver.py`

---

## Senior Developer Review (AI)

**Five lenses** — the words, the seams, the checks, the unfitness declaration, the regression
surface. Every finding adjudicated by **two independent skeptics** defaulting to REFUTED, one
attacking the mechanism and one the consequence.

### Coverage (action item A2)

| | |
|---|---|
| Lenses run / planned | **5 / 5** |
| Findings | **33** |
| Skeptic verdicts | **66 / 66** |
| Confirmed | **24** |
| Refuted | **9** (27 %) |
| **Unadjudicated** | **0** |
| Lenses or skeptics lost | **0** (71 agents, 0 errors) |

Second epic-5 review with full coverage and no losses. The 24 confirmed findings reduce to **eleven
distinct defects**; five lenses independently found the same one, which is the strongest signal this
process produces.

### The eleven, and what each was

1. **A positive bound rendered as `prévalence ≤ 0.0%`** [HIGH, 2/2]. `{p:.1%}` prints zero for every
   share below 0.05 %, and the product's own planner *recommends* such draws —
   `size_for_target(8000, 0.0004)` returns a sample of 4 217 whose bound is *at most 3 of 8 000*, a
   prevalence of 0.0375 %. Two numbers in one parenthesis, one of them false and false in the
   flattering direction: a residual-prevalence bound of zero reads as *nothing relevant remains*.
   §0.2 re-created by a format specifier. → one renderer, `confidence.prevalence_fr`, shared with
   the sizing preview; precision widens until the figure is non-zero, and a genuine zero is spelled
   `0 %` because *"0.0 %"* and *"0 %"* are different claims.
2. **The unfitness declaration divided by the verdicts recorded so far** [HIGH, five lenses]. A
   200-family draw whose first verdict came back relevant declared the whole *ranking version* unfit
   at 1/1 — and then said *"sur les 1 familles tirées au hasard"* about a draw of two hundred. It
   also disagreed with the *matter*'s own constat, which divides by the draw: the same run read
   **unfit** on one surface and **fit** on the other. → the denominator is the sample, on both
   surfaces, and only a completed run has one.
3. **FR-23's worklist line was never built** [HIGH, three lenses]. The requirement has four clauses;
   three were built. A requirement two-thirds implemented reads, from the outside, exactly like one
   that is finished. → `worklist.unfitness_line`, its own offer (`re-rank-revised-theory`, never the
   plain re-rank a moved corpus asks for), and a structural leg that fails the build without it.
4. **The offline check failed open on `importlib` and on relative imports** [HIGH]. Adding
   `importlib.import_module("httpx").post(...)` to the composer left all 89 checks green while the
   sentence was being sent to a third party. → dynamic imports resolved, a runtime-named module
   reported as *unverifiable* rather than clean, relative imports resolved against the importing
   package, and packages resolved to their `__init__`.
5. **The banned-phrasing check was blind to the French apostrophe** [two lenses] — while the sibling
   check *this same story added* folds it, and its docstring names the hazard. The lesson was
   applied to the new check and not to the one it was learned from: the recurring defect, committed
   twice in one commit.
6. **The banned list still missed the natural French claims** — the residual family (*subsiste*,
   *résiduel*, *ne reste*), the claim made positively (*certitude*, *garantie*, *assurance*), the
   bare claim with no risk word at all, and the exact banned literal behind a long qualifying clause.
7. **The raw-text legs collapsed whole files into one string**, so ordinary French legal vocabulary
   — *risque de forclusion* beside *pièce manquante* — failed the build accusing the author of the
   §0.2 claim. → per-line scanning, and the MISS family now names the **act** (`manqué`) and not the
   adjective (`manquante`). A check that cries wolf on correct French is a check somebody widens
   until it says nothing.
8. **Plural verb on a singular count**, reintroduced twice — in the census claim and in the new
   declaration. The Story 5.3 review confirmed and fixed exactly this, eight lines away.
9. **The declaration claimed a random draw on a census**, contradicting the sentence printed
   directly above it, and said *"au-dessus du seuil"* where the rule fires at equality.
10. **The wall was named conditionally** while the decision said unconditionally — a legacy bound's
    copied sentence dropped the clause entirely. → *"périmètre non enregistré"*, exactly as an
    unstamped bound states its freshness.
11. **`estimator-census-no-bound`'s manifest row and README still named a function and a module that
    no longer hold the property**, and the unfit declaration rendered as an `apx-chip`, whose
    `white-space: nowrap` would put a 200-character sentence on one unwrappable line.

### Refuted, and worth recording

- **Anglophone typography** — `95%`, `1.4%`, `1400` where French wants `95 %`, `1,4 %`, `1 400`.
  Both skeptics reproduced it and both refuted it: the rendering predates this story
  (`git show 9f44f48:…/freshness.py` carries the identical format specifiers), nothing it produces
  is untrue, and the decimal separator is a **locale** decision that `no_hardcoded_locale` and FR-36
  own. **Recorded as an action item for Story 6.4**, because `unfitness_statement_fr` is a new
  string and the inconsistency will grow if nobody owns it.
- **The line-move offer exists in `worklist.py`, which the check never opened** — refuted on the
  consequence (no line-move affordance ships: there is no API route and no client call), and correct
  on the scope. **Fixed anyway**: an unfit ranking now strips `OFFER_REPLACE_LINE` from the
  worklist, and the check reads the seam that emits it. The guard exists before the surface does,
  which is what the check claimed to be for.
- **The uncomputable *pièce* worst case was silently omitted** — refuted as a regression (the
  expression is a verbatim carry-over from `9f44f48`), and correct that the client arm's refusal
  text was deleted with the arm, leaving zero occurrences repo-wide. **Fixed anyway**, in the one
  composer: the sentence now says the worst case is not computable rather than leaving a gap.
- **The bound is stated over FAMILIES while the pile is quoted in *pièces*** — refuted: the unit is
  named on both numbers and the *pièce* figure sits beside the bound as an explicit worst case,
  which is Story 5.2's decision and is stated in the sentence itself.
- **`unfit_relevant_share` names the configured threshold in the core and the observed share on the
  wire** — refuted: the payload carries `unfit_relevant_share` and `unfit_threshold` as two fields,
  and no code path confuses them.

### Accepted with reason

- **The client leg of `unfitness-offers-no-line-move` is vacuous** and says so. Story 4.9's
  line-move surface does not exist; the guard is written now so it is in place before the control,
  rather than after. Its fixture proves it fires.
- **A static check over natural language cannot be complete.** The banned-phrasing check is a
  tripwire over a closed, product-owned string set — not a classifier. Its value is that the known
  claim becomes un-rewritable and every phrasing anyone finds is added to a fixture that fails the
  build. Every phrasing the review produced is in that fixture.

## Change Log

- **2026-08-12** — Story 5.4 implemented, reviewed and completed. The confidence bound became a
  sentence with one owner; the banned-phrasing check became live, multilingual and precise; FR-23's
  unfitness declaration was adopted whole, including the worklist line no story had claimed. The
  harness went 86 → 89.
