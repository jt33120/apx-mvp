# Epic 5 planning review — the population question (action item A1)

**Date:** 2026-08-07
**Discharges:** action item **A1** (blocking) from `epic-4-retro-2026-08-07.md`
**Decided by:** Julian delegated the three questions to the build ("aucune idée, ce que tu recommandes"). The
recommendations below are therefore the decisions. They bind Stories 5.1 → 5.4.
**Status:** decided — Story 5.1 may be created.

---

## The problem A1 named

Epic 5's north-star sentence — *"with C% confidence, at most X% of the **discarded set** is relevant"* — is
computed over a population. **There are two different discarded sets in this build**, and until now nothing
said which one the sentence means.

| | **Population #1 — the label pile** | **Population #2 — the derived view** |
|---|---|---|
| Where it lives | `label_record WHERE label = 'discard'` (a stored row per *pièce*) | `derive_triage_sets(ranked, unscored, line, pins).discarded` — computed at read time, **never stored** |
| Who owns it | Epic 2 — the cascade's relevance verdict | Epic 4, Story 4.7 (FR-16 / AD-39) |
| Built by | `sample_discards` / `record_recall_review` (Story 2.x) | `read_triage_sets` → the triage table the lawyer actually looks at |
| Knows about the ranking version | no | yes — it *is* a view over one version |
| Knows about **the line** | no | yes — the line is the cut that creates it |
| Knows about *pins* | no | yes |
| Watched by 4.13's `discard_population` observable | **yes** (today) | no |

FR-22 requires the *sampling run* to record *"the **ranking version**, the position of **the line**, the
*RBAC scope* and the explicit identifier list"*. **Recording the ranking version and the line is meaningless
for population #1** — the label pile has neither. The requirement only parses if the population is #2.

But every piece of machinery that exists today — including the *confidence bound* that Story 4.13 just made
stale-aware, refusable-at-export and copy-safe — is built on **#1**.

---

## Q1 — Which population does the *sampling run* draw over?

### Decision: **population #2, the Epic-4 derived discarded view.**

Four reasons, in decreasing order of force:

1. **FR-22's own freeze contract only parses over #2.** A run that records "the position of the line" over a
   population the line does not define is recording an irrelevant fact. The requirement is not decorative:
   it is what makes *invalidated-in-flight* possible.
2. **The sentence must describe the set the lawyer saw.** She reads the triage table: retained above the
   line, discarded below. If the sentence quantifies a *different* set — one assembled by the Epic-2
   cascade, before the ranking, before the line, before her pins — then the number she says to a *bâtonnier*
   describes a population that was never on her screen. This is the retro's recurring defect (*a comparison
   against a nearly-right referent*) promoted to the product's most consequential sentence.
3. **#1 is not closed under the acts the product offers.** A *pin* moves exactly one *pièce* across the line
   (FR-43). Under #1 a pinned-to-retained *pièce* stays in the sampled population — so the run can hand the
   lawyer a *pièce* she has already, explicitly, deliberately retained, and ask her whether it is relevant.
   Under #2 that cannot happen.
4. **The dependency statement already says so.** epics.md: *"Epic 5 on 4 (there must be a **discarded set**
   to audit)"*. The *discarded set* is a defined term, and Story 4.7 is where it is defined.

### What this costs

`sample_discards` and `record_recall_review` are re-pointed at `read_triage_sets(...).discarded` and take a
*ranking version* + a line + pins as inputs. That is not a tweak — it is the whole reason 5.1 is a large
story rather than a small one. Q2 is the consequence.

### The near-duplicate corollary (feeds A7 / Story 5.2)

Epic 4 already supplies `ranked_entry.family_id` and `ranked_entry.is_representative`. Under #2 the drawn
unit can therefore be the **family**, not the row — which is exactly OQ-4's first hard input and the reason
the estimator is not simply "n out of N". Under #1 that information does not exist on the population at all.
**Story 5.1 draws over representatives and freezes the family membership with the identifier list**; Story
5.2 owns what a family *counts as*.

---

## Q2 — Is the legacy `recall_review` / `sample_discards` pair superseded?

### Decision: **superseded, in Story 5.1, by supersession and not by deletion.**

- The **write** paths retire. `sample_discards` and `record_recall_review` stop being reachable as their own
  act; the *sampling run* becomes the one way to draw and the one way to record a verdict on a drawn
  *pièce*. No new `recall_review` row is ever written after 5.1.
- The **rows stay** (AD-7 — nothing is hard-deleted). Every historic `recall_review` remains readable, with
  its bound, its population, its reviewer and its date.
- Historic bounds read as **`fraîcheur invérifiable`** — the state Story 4.13 already built for a bound with
  no stamp. That is not a workaround; it is the honest verdict. A bound computed over population #1 cannot
  have its inputs verified against a product whose discarded set is population #2. `BoundReading` already
  refuses to export such a bound as current, and already refuses to call it fresh.

**Why not keep both.** Two live bound artefacts over two different populations, both named "the discarded
set", both rendered on the same surface, is the ambiguous-referent defect the retro identified as the
build's single recurring failure mode — installed deliberately, at the one place where being wrong is said
out loud to a court. One bound, one population, one referent.

**Why not defer the retirement to 5.4.** Because between 5.1 and 5.4 the product would draw its sample from
#2 and record its verdicts against #1. The draw and the review would disagree about what was drawn. A
transient incoherence in the middle of the estimator work is exactly where a defect hides.

**Consequence for the build's never-worse rule.** Story 5.1's run therefore completes with a bound, computed
by the existing `prevalence_upper_bound` (already hypergeometric, already finite-population, already exact at
census). The product is never left without a bound. What 5.2/5.3/5.4 add is not the number's existence: it is
the number's **five hard inputs answered explicitly** (5.2), its **soundness proven in CI** (5.3), and its
**sayable sentence with the counts-only fallback** (5.4). Until 5.3 passes, the number is what it is today —
no better, no worse, and not newly trusted.

---

## Q3 — Where does 4.13's `discard_population` observable point?

### Decision: **re-pointed at the derived view (#2), and kept — not deleted as redundant.**

The observable is currently a `sha256` over the *pièce* identities in `label_record WHERE label='discard'`.
It moves to a digest over `derive_triage_sets(...).discarded` for the version being stamped.

**The redundancy objection, and why it loses.** Under #2 the discarded set is a pure function of the ranked
order, the line and the pins — all three of which are *already* observables
(`ranking_version_no`, `line_seq`, `pin_ledger_seq`). So `discard_population` becomes formally redundant:
if none of the three moved, the derived set cannot have moved.

It is kept anyway, and the reason is the retro's headline lesson. Inferring *"no input we watch moved,
therefore the population is unchanged"* is a comparison against a **nearly-right referent** — right until
someone adds a fourth input to the derivation and forgets the fourth observable, at which point the bound
reads **falsely fresh**, which is the catastrophic direction. A direct digest over the population itself is
the **exact** referent, it costs one query the stamp is already making, and it cannot be defeated by a future
change to the derivation. Redundant evidence about the one artefact that gets quoted to a judge is not waste.

**Per-kind narrowing is unchanged in shape, changed in justification.** `INPUTS_BY_KIND` keeps excluding
`discard_population` from `KIND_RANKING` and `KIND_LINE` — but now because the discarded set is *derived
from* the ranking and the line, so making a ranking stale because its own consequence changed would be
circular. `KIND_BOUND` keeps all nine.

**One new kind.** The *sampling run* is itself a stamped derived artefact: `KIND_SAMPLING_RUN`, observing
**all nine** inputs. *Invalidated-in-flight* (FR-22) is then not a new mechanism — it is Story 4.13's
staleness comparison, read on a run that is still open. FR-22's *"tells the user immediately"* is the
worklist line the machinery already produces.

**One accepted false-stale.** A `recall_review` row stamped between 4.13 and 5.1 carries a #1-population
digest and will compare unequal against a #2 digest forever, so it reads **stale**. That is the safe
direction and it is also true: that bound's population is no longer this product's discarded set.

---

## What this binds

| Story | Bound by this decision |
|---|---|
| **5.1** | Draws over `read_triage_sets(...).discarded` for a named *ranking version*. Retires the legacy write paths. Freezes version + line identity + pins + scope + explicit id list + family membership. Invalidation-in-flight = `KIND_SAMPLING_RUN` staleness. |
| **5.2** | The family is the unit of the draw (`family_id` / `is_representative` are already on `ranked_entry`). Answers OQ-4's five inputs in the story file **before** implementation (action item **A7**). |
| **5.3** | Simulates populations shaped like #2 — varying prevalence **and varying duplicate structure**. |
| **5.4** | The sentence names the *ranking version* and the line, because its population is defined by them. |
| **5.5 / 5.7** | The *audit record* entry for a *sampling run* carries the version and the line position (FR-24 already says so — it is now satisfiable). |

## What this does not decide

- Whether a *sampling run* may be re-opened after invalidation, or must be abandoned and redrawn. Story 5.1
  decides; the recommendation is **abandoned and redrawn**, because a re-opened run's verdicts were formed
  against a population that no longer exists.
- Whether the unscored tail is ever sampled. It is **not** — AD-19/AD-36 keep it its own set; a *pièce* the
  cascade could not score was not discarded, and a bound over it would be a bound over a different claim.
  Story 5.1 asserts this by test.
