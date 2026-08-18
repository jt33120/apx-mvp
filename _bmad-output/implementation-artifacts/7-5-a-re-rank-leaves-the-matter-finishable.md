---
baseline_commit: a8e72d5
---

# Story 7.5: A re-rank leaves the *matter* finishable, and the record keeps every position of the line

Status: done

## Story

As **a lawyer who has committed to a cut and is about to re-rank**,
I want the second ranking to leave the *matter* at least as usable as the first did, and the record
to keep every position the line has held,
So that producing a ranking is an act I can be offered rather than one that quietly costs me the
triage I had.

## Why this story exists

Extracted from **C11** (the Epic-4 write surface) as its precondition. Story 7.3's own note said a
ranking route *"shipped alone would make the product worse"*; this is that sentence made false
before the route exists. Both defects are live **today**, on the operator path: two `manage rank`
runs are enough to produce each of them.

### The line vanished, and nothing said so

The line in force is read over the **latest** ranking version:

```python
        if placement is not None:
            live[KIND_LINE] = placement.id
```

When version 2 exists with no placement, `live` carries **no `KIND_LINE` key at all**, and
supersession is computed as `r.artefact_id != live.get(r.kind)` — a hex id is never equal to `None`,
so **every** line stamp in the *matter*, including version 1's committed placement, reads
`superseded=True`. And a superseded artefact deliberately emits nothing:

```python
def worklist_line(assessment: Freshness) -> WorklistLine | None:
    if assessment.fresh or assessment.superseded:
        return None
```

So `read_worklist` returned `()` — *read, and nothing to do* — over a *matter* where every ranked
*pièce* had fallen into the unsplit set, the *sampling run* refused to start, and no *confidence
bound* could exist. The strongest form of a silent failure: an empty list that means *nothing is
wrong*, over a *matter* that had just lost its triage.

**A worklist offer would have been the wrong remedy**, and it is worth saying why, because it is the
obvious one. `WorklistLine.artefact_id` is documented as *"the artefact the offer would supersede —
never the artefact it would produce, which does not exist yet"*, and a line that was never placed is
neither. The offer sentence would be false (*« Replacer la ligne produira une nouvelle position ;
l'ordre ne bouge pas »* — there is no line to replace). It is deleted outright whenever FR-23's
unfitness fires, so the one *matter* that most needs a cut would have its only remedy stripped. And
an offer is a promise to act later: between the re-rank and the click the product stays broken. The
worklist's own charter settles it — *"A line offers; it never acts"* — **a missing artefact is not
staleness, it is an incomplete act**.

### §3 of the exported record emptied

```python
        history = self.read_line_history(tenant=tenant, matter=matter, scopes=scopes) or ()
```

`read_line_history` is version-scoped and honest about it in its own docstring. The **call site**
passed no version, so it resolved the latest and read only its placements. On a *matter* with two
rankings, §3 of the document a *bâtonnier* receives was **empty** — not marked pending, just a
section with no rows — over a *matter* where a lawyer had moved the line and priced every move. An
empty §3 and *no line was ever placed* are the same bytes.

## Acceptance Criteria

**AC-1 — the ranking act draws the cut.** Producing a *ranking version* and drawing the tool's line
over it is one act. Drawing a first cut needs no consent — the codebase already records
`priced_statement=None` for it, because *a first placement is the tool drawing the cut, not a human
move*; the human act is **moving** the line, and it is priced (FR-19).

**AC-2 — over the version just minted, named.** The placement names the version explicitly rather
than resolving *the latest*, because the failure direction is the catastrophic one: a stamp whose
`line_seq` belongs to another version reads **fresh**.

**AC-3 — a failed placement does not lose the order.** Two transactions: an order that cost one
model call per uncertain *pièce* is not rolled back by a placement. `None` is a real answer — no
*pièce* in a retain band, and a line is never fabricated (AD-19).

**AC-4 — the record carries every position, of every version.** A second reader for the export;
the version-scoped one keeps its correct meaning for surfaces.

## Tasks / Subtasks

- [x] T1 — `core/app/rank.rank_and_draw_the_line`, the paired act (AC-1, AC-2, AC-3).
- [x] T2 — `manage rank` performs it.
- [x] T3 — `SqlStore.read_line_history_all_versions`; the export calls it (AC-4).
- [x] T4 — regressions, proven against the pre-story code.

## Dev Agent Record

### Completion Notes

**Two readers rather than a parameter**, because they answer different questions: a surface asks
*where is the line now, over this version*, and the record asks *what did she decide, ever*. A
default argument would have made the export's correctness depend on every future caller remembering
which question it was asking — which is exactly how it broke.

**Proven both ways.** Reverting the two changes turns **6 of the 7** new tests red. The seventh
(`the_all_versions_reader_refuses_a_matter_behind_a_wall`) passes either way because the reader is
new — recorded as a wall guard, not as a defect proof.

### Review

Run in-session across the three standing lenses, on a four-agent reconnaissance of the queue, the
route, the client and the blast radius. **Coverage stated**: the fleet mapped and gave a reasoned
scope judgement on each of the four blast-radius effects; one reviewer adjudicated.

**The wrong referent** — supersession compares an artefact id against `live.get(kind)`, and the
right-hand side is `None` when the kind has no live artefact at all. *Superseded by a newer one* and
*there is no current one* are not the same fact, and they produce the same silence. This story
removes the condition rather than the comparison; the comparison itself is noted below.

**The seams** — the export's call site versus the reader's docstring. The reader was correct and
said so; the seam registry's description of it (*"reads EVERY position the line has held … what the
matter export carries"*) was false the moment a *matter* had two versions. Registry prose is not
covered by any check.

**Which decision does this implement** — FR-17 (the tool draws the line and commits) and FR-24/FR-26
(*every* position, with its author and priced statement).

### Found while building, not fixed here

**C15 — `_validation_counts` is version-blind.** `in_force` never looks at `ranking_version_id`,
although `ValidationEntry` carries it, so after a re-rank an acceptance of version 1's assessment is
counted in §7 as a current judgement. The **denominator is already version-aware** while the
numerator is not. The domain even has the predicate — `is_stale(entry, current_ranking_version_id)`
— **with no caller**, which is the C5 family exactly. Deliberately not fixed here: the fix adds a
field to the exported `ValidationCounts` and a French label to §7's heading registry, and forces a
product decision about what a superseded acceptance means to a reader. That is spec surface, and
smuggling a schema change into a story about a cut is how one ships without a decision.

**C16 — a supersession that means *absent* is silent by construction.** `r.artefact_id !=
live.get(r.kind)` reports *superseded* for every artefact of a kind with no live member. This story
removes the one reachable condition; any new artefact kind, or any path that can leave a kind
unrepresented, inherits it. A `live` map that distinguished *no member* from *this member* would
close it for good.

**C17 — an open *sampling run* is invalidated with no warning.** `_guard_open_run` is a **write**
guard: a new *ranking version* moves `ranking_version_no`, every open run in the *matter* is
invalidated, and the lawyer discovers it on her *next* verdict as a 409. `abandon_sampling_run`
then audits `verdicts_kept=<the count of the hour just thrown away>`. Nothing warns before. The
confirmation shape exists (`check_confirmed_count` / `BatchSplit.sentence_fr`), and it belongs in
the **enqueue handler** of the gesture, not in the store — so it ships with C11's button, whose
arrival is what makes this reachable from the SPA at all.

### File List

- `apx/core/app/rank.py` — `rank_and_draw_the_line`.
- `apx/manage.py` — `rank` performs the paired act and names the cut.
- `apx/adapters/store_postgres/store.py` — `read_line_history_all_versions`; the export uses it.
- `apx/checks/user_actions.py` — the new seam registered; `user_action_registry_is_complete`
  fired on the unregistered act and was answered by registration, never by weakening.
- `tests/probe/test_never_hard_delete.py` — the paired act walked as its own probe step.
- `tests/test_rerank_leaves_the_matter_usable.py` — **new** (7).

### Change Log

| When | What |
|---|---|
| 2026-08-18 | Extracted from C11 as its precondition; implemented; gate green. |
