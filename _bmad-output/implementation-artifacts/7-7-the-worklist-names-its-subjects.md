---
baseline_commit: 9899369
---

# Story 7.7: The worklist names its subjects, and its one unfitness line discharges

Status: done

## Story

**As** a lawyer reading the banner at the top of a *matter*,
**I want** each line to say what it is about, in French, and to stop asking once I have done what it
asked,
**so that** the one line FR-23 exists to produce stops printing a technical identifier and a false
statement about the *ranking version*'s status — and stops growing by one paragraph per act.

## Why this story exists

Retro action **C5**, part 1 — and it is a **precondition of 7.8** in exactly the sense 7.5 was of
7.6. Both defects below were harmless only while no re-rank control existed. Story 7.6 shipped that
control this afternoon.

### The FR-23 line renders as a lie

`STALE_SUBJECT` in `apx/web/src/triage.tsx` has four keys — `ranking`, `line`, `bound`,
`sampling_run`. `KIND_RANKING_UNFIT` is `"ranking_unfit"` and is **not** among them, so the fallback
`STALE_SUBJECT[line.kind] ?? line.kind` prints the raw constant. The template then appends
*« — périmé depuis : »* and the line's `changed_fr`. For this line `changed_fr` carries the FR-23
**finding**, not a staleness cause, and the *ranking version* is **not** stale: it is current, and
not ranking anything. What a lawyer sees is:

> **ranking_unfit** v3 — périmé depuis : Sur les 5 pièces tirées au hasard, 1 était pertinente —
> soit 20 %, au niveau ou au-dessus du seuil de 20 % configuré. Le classement v3 ne trie pas ce
> dossier : déplacer la ligne ne corrigerait rien ; il faut reclasser avec une théorie du cas
> révisée.

A technical identifier, a version appended by the client rather than carried by the line, and a
false claim about the artefact's status — on the one surface FR-23 exists to produce.

### The line has no discharge condition, and the module already says why that is wrong

`read_worklist` appends the unfitness line whenever `bound.unfitness_fr is not None`. Nothing
compares the finding's *ranking version* against the *matter*'s current one. `worklist.py`'s own
docstring states the rule it is breaking:

> a **superseded** [artefact] … must not generate an offer, or the offer never discharges: the user
> accepts the re-rank and the banner still demands one, growing by one paragraph per act until
> nobody reads it.

That rule is applied to every line except the one whose offer is hardest to satisfy. The lawyer
accepts *« Reclasser avec une théorie du cas révisée »*, gets version 4, and the banner goes on
accusing — because the *bound* still records version 3's finding and no new *sampling run* has
measured version 4.

**Silence afterwards is honest, and it is not silence.** Unfitness is a **measured** finding over a
drawn sample; version 4 has not been measured, and declaring it unfit would be a verdict nobody
computed. Meanwhile the *bound* itself has gone stale — `ranking_version_no` moved — so the worklist
already emits *« La borne de confiance — périmé depuis : un nouveau classement. Ré-échantillonner… »*,
which is exactly the next act. The discharge hands her the right offer rather than nothing.

## Acceptance Criteria

- **AC1 (FR-23/AD-23).** Every `WorklistLine` carries `subject_fr`, composed where the kind is
  minted, and version-qualified where the artefact belongs to a *ranking version*. No raw kind
  constant can reach a surface.
- **AC2 (FR-58).** Every `WorklistLine` carries `reason_fr` composed beside its subject: *« périmé
  depuis : … »* for a staleness line, and the FR-23 declaration **quoted verbatim** for the
  unfitness line — never re-cut, never prefixed with a staleness phrase.
- **AC3.** `STALE_SUBJECT` and the client's *« — périmé depuis : »* template are **deleted**, not
  extended, and the client no longer appends a version of its own to a line.
- **AC4 (FR-23).** The unfitness line is emitted only while the *bound*'s `ranking_version_no` is
  the *matter*'s current one. A re-rank discharges it.
- **AC5.** A re-rank that discharges the unfitness line leaves the lawyer a **stale-bound** line
  offering `re-sample` — the discharge is not a disappearance.
- **AC6.** `_SUBJECT_FR` covers exactly the kinds a line can carry; a kind added without a subject
  fails a test rather than reaching a screen.

## Tasks / Subtasks

- [x] T1 — `Freshness.version_no`, carried from the artefact (AC1).
- [x] T2 — `WorklistLine.subject_fr` / `.reason_fr` and `_SUBJECT_FR` (AC1, AC2, AC6).
- [x] T3 — the unfitness line's discharge condition in `read_worklist` (AC4, AC5).
- [x] T4 — the wire (`WorklistLineOut`) and the client (`api.ts`, `triage.tsx`) (AC3).
- [x] T5 — the regressions, each proven against the pre-story code.

## Dev Agent Record

### Found while building, not fixed here

- **C19 — the product names one artefact two ways on one screen.** The worklist subject composed
  here says *« Le classement n° 3 »* (the convention `BatchSplit.sentence_fr` and `manage rank`
  already use); `unfitness_statement_fr` says *« Le classement v3 »*, and the two now sit on the
  same banner line. Not changed here on purpose: that sentence is quoted into an exported record, so
  its wording is spec surface and a story about a banner is the wrong place to move it.

### Review

**The discharge condition reads the comparison this module already computes.** The bound's own
freshness reports `ranking_version_no` among its changed inputs exactly when the ranking has moved
since the bound was drawn — so the gate uses that rather than fetching the current version a second
time. One referent for one fact, which is the failure mode this project keeps meeting. An
**unstamped** bound emits nothing, which is the stance `BoundReading` already takes: an absence of
evidence is not evidence of validity.

**Two fixes proven by reverting them:**

| The plausible move | What it breaks | Test that goes red |
|---|---|---|
| append the unfitness line whenever the bound carries a finding | the banner accuses a version the lawyer has already replaced, for ever | `test_a_re_rank_discharges_the_unfitness_line` |
| `_SUBJECT_FR.get(kind, kind)` — the client's `??` fallback, moved server-side | a missing translation renders as content instead of failing; this is exactly how `ranking_unfit` reached a screen | `test_an_unknown_kind_raises_rather_than_rendering_itself` |

**Four existing tests had to change, and the change is the finding.** `tests/domain/test_worklist.py`
built `Freshness` objects with no `version_no`, and `worklist_line` now raises on a version-bound
kind that cannot name its version. `FreshnessStamp.ranking_version_no` is an `int`, never `None`, so
those fixtures were constructing an artefact that cannot exist. They now carry one.

**Coverage lost: none.** No lens or reader errored; this story was scoped from 7.6's reconnaissance
and every claim in it was read directly from the source before being written down.

### File List

- `apx/core/domain/freshness.py` — `Freshness.version_no`, threaded through `assess_freshness`.
- `apx/core/app/read/freshness.py` — the version carried into each assessment; `_RANKING_VERSION_MOVED`
  and the unfitness line's discharge condition.
- `apx/core/domain/worklist.py` — `_SUBJECT_FR`, `subject_fr`, `subjects_are_total`, and
  `WorklistLine.subject_fr` / `.reason_fr`.
- `apx/api/app.py` — the two fields on `WorklistLineOut` and its route.
- `apx/web/src/api.ts` — the two fields on the client type, neither optional.
- `apx/web/src/triage.tsx` — renders what it is given; `STALE_SUBJECT`, the *« — périmé depuis : »*
  template and the `version` prop **deleted**.
- `tests/domain/test_worklist.py`, `tests/domain/test_freshness.py` — fixtures carry a version.
- `tests/api/test_worklist_says_what_it_is_about.py` — **new** (11).

### Change Log

| When | What |
|---|---|
| 2026-08-18 | C5 part 1, extracted as 7.8's precondition. Built; two fixes proven red. |
