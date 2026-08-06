---
baseline_commit: 0fcf71b
---

# Story 4.10: The editable cell-by-cell table with a live change log

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a lawyer correcting the tool,
I want to edit any cell without the tool undoing my other edits, with each change logged beside the row,
So that correcting the machine never costs me the correction I made a minute ago — the named requirement that turned out to be the architecture's invariant.

## Scope note — the substrate is complete; 4.10 gives it a face

Nine stories built the triage engine and left it **invisible**: there is no screen. Every guarantee
below already exists and is tested; 4.10 renders it and adds the one act the lawyer performs on it.

| Already built | Story | What 4.10 does with it |
|---|---|---|
| the ranked order + the reproducible **ranking version** | 4.3 | names it in the header (AD-23) |
| **confidence, derived** from observables | 4.4 | a read-only cell shaped *unlike* an editable one |
| the per-*pièce* **taxonomy label** ledger (append-only, version-independent) | 4.5 | **the editable cell** + **the change log** |
| retained / discarded / unscored as **VIEWS** | 4.7 | the *côté* chip and the three zones |
| **the line**, stored by the last-retained *pièce* identity | 4.8 | drawn as a cut **between** two rows, speaking |
| the **pin** | 4.11 | the pinned variant of the *côté* chip (read-only here) |
| the **justification** | 4.6 | not surfaced here (its drawer is 4.6's own surface) |

**The one new act is the label edit.** Everything else on the screen is a faithful rendering of a
derived view. The UX contract is `EXPERIENCE-EPIC4.md` (final) and the mockup
`mockups/epic-4-triage-table.html`; **the contract wins over the mock**.

**This story also opens the HTTP surface Story 4.12's registry explicitly deferred to it.** Label,
line, pin and justification are reachable today only at the `core/app` seam. 4.10 adds the routes
the table needs — and `user_action_registry_is_complete` will **fail the build** until each new
route is registered in `USER_ACTIONS`. That is the 4.12 harness working as designed, and honouring
it is part of this story.

**IN scope:**
1. **One read endpoint for the whole surface** — `GET /api/matters/{matter}/triage-table`: the
   ranking version identity, the three counts, the ranked rows (rank, *pièce* id + provenance name,
   derived confidence + its signals, current label + source + `in_current_taxonomy`, derived
   *côté*), the line (placed or not; the last-retained *pièce* and the basis), the unscored tail,
   `pins_in_force`, and the *tenant*'s taxonomy for the select. One request, because the table is
   one coherent read of one ranking version (AD-23) and N round-trips would let the parts drift.
2. **The edit endpoints**, both through the `core/app/label` seam (AD-4, never the adapter):
   `PUT  /api/matters/{matter}/pieces/{piece_id}/label` (assign; `409` on a stale `expected_seq`,
   `422` out-of-taxonomy) and
   `POST /api/matters/{matter}/pieces/{piece_id}/label/revert` (revert to a `seq` — a **new** entry).
3. **The change-log endpoints**: `GET …/pieces/{piece_id}/label/log` (one row's log, ascending) and
   `GET /api/matters/{matter}/change-log` (the matter-level log, newest first) — the latter needs a
   new store read (`read_matter_change_log`), scope pre-filtered with `matter` in the query (AD-13/
   AD-14).
4. **The registry lock-step** — the five new routes added to `apx/checks/user_actions.py`, each with
   its note, `changes_state`, and (for the revert) its `reads_as_deletion` + reversal.
5. **The React surface** — a `/matter/:matter/triage` route rendering the four zones of the contract:
   header (matter + **ranking version** + basis), the denominator **equation** under a **verdict**
   seal (*nothing has left the corpus*), the **honesty banner**, and the **table** with the line cut,
   the retained / discarded / **unscored** zones, the editable label `<select>`, the inline
   change-log entry on commit, and the matter-level change-log panel.
6. **The Epic-4 design tokens** in `tokens.css` (`triage-table`, `rank-cell`, `confidence-cell`,
   `label-cell`, `side-badge`, `the-line`, `change-log-entry`), derived from DESIGN.md — ink navy,
   one gold, warm paper; the kept/review/discard tier kept **distinct from gold**.

**OUT of scope (named so it is not smuggled in):**
- **Placing or moving the line** (Stories 4.8 / 4.9 surfaces) and **pinning** (4.11). The line and
  the pin marker are **rendered**, read-only — the contract's "line not yet placed" state is
  supported honestly. No control here changes a *côté*.
- **The justification drawer** (Story 4.6's surface).
- **A "Re-classer" button.** Re-ranking has no HTTP surface and inventing one here would put the
  LLM cascade behind a button without the staleness signals Story 4.13 owns. AC-2/AC-4 — *edits
  survive an explicit re-rank, marked human-set* — are therefore proven **at the seam by test**,
  which is where the property actually lives (the label ledger is version-INDEPENDENT, 4.5).
- Virtualisation of the table. The 5 000-*pièce* run is Story 2.13's gate; the surface renders the
  ranked order plainly and the bound is noted, not silently ignored.

## Acceptance Criteria

**AC-1 — an edit changes that cell and nothing else (FR-20, the architecture's invariant).**
Given the triage table over a ranking version,
When the lawyer commits a label on N different rows in turn,
Then **all N values hold** — asserted by test over N rows — no other row's label, rank, confidence or
*côté* changes, and every row keeps its position.

**AC-2 — no edit regenerates anything; re-ranking is separate, explicit, and never overwrites.**
Given rows carrying human-set labels,
When a new ranking version is produced by an explicit act,
Then every human-set value survives it and reads back `source = "human"`, and no edit ever triggered
a re-rank or re-classification of another row.

**AC-3 — each edit produces a change-log entry beside the row, immediately.**
Given a committed label edit,
When the row's change log is read,
Then it carries the entry with **previous value → new value, author, timestamp**, append-only and in
`seq` order; the surface shows it beside the row on commit without a reload.

**AC-4 — (failure path) a re-rank after edits preserves every human-set value and marks it as such**,
rather than replacing it with a fresh machine value.

**AC-5 — the surface tells the truth about what it is.**
Given the triage screen,
When it renders,
Then it names its **ranking version** (AD-23), shows *retenue + écartée + non-scorée = le corpus*
under a verdict seal, carries the honesty banner (*proposed order, revisable, nothing deleted*),
draws the line **between** rows named by the last retained *pièce* (never a bare integer), keeps the
**unscored** tail as its own zone, and offers **no control** that changes a *côté* — the *côté* chip
announces itself as a derived view.

**AC-6 — a write failure loses nothing (FR-20 extends to failure).**
Given an optimistic label commit that the server refuses (stale `seq`, out-of-taxonomy, out of
scope),
When the response arrives,
Then the cell **reverts to its previous value** and the failure is stated — never a silent loss, and
never a half-applied row.

**AC-7 — the harness stays honest.**
Given the five new routes,
When the structural harness runs,
Then `user_action_registry_is_complete` passes **because** each was registered (and demonstrably
fails when one is not), and the full gate is green.

## Tasks / Subtasks

- [x] **T1 — the store read for the matter-level change log**
  - [x] `read_matter_change_log(*, tenant, matter, scopes, limit)` in `store.py` — every
        `TaxonomyLabelEntry` of the matter, newest first, `matter` in the query (AD-13/AD-14),
        `None` when out of scope or absent.
- [x] **T2 — the API surface** (5 routes, all thin pass-throughs)
  - [x] `GET  /api/matters/{matter}/triage-table` — assembles the ranking version, counts, rows,
        line, taxonomy; non-disclosing `404` when out of scope / absent / no ranking.
  - [x] `PUT  /api/matters/{matter}/pieces/{piece_id}/label` → `label.assign_taxonomy_label`;
        `409` `StaleLabel`, `422` `OutOfTaxonomyLabel`, `404` non-disclosing.
  - [x] `POST /api/matters/{matter}/pieces/{piece_id}/label/revert` → `label.revert_taxonomy_label`.
  - [x] `GET  /api/matters/{matter}/pieces/{piece_id}/label/log`.
  - [x] `GET  /api/matters/{matter}/change-log`.
- [x] **T3 — the registry lock-step (AC-7)** — five `USER_ACTIONS` rows; the revert declares
      `reads_as_deletion` + its reversal (its name carries `revert`).
- [x] **T4 — the design tokens** — the Epic-4 block in `tokens.css`, from DESIGN.md.
- [x] **T5 — the React surface**
  - [x] `src/triage.tsx`: `TriageRoute` (route `/matter/:matter/triage`), the four zones, the table.
  - [x] The label cell: a real `<select>` (announced editable), optimistic-then-confirmed, reverting
        on failure with the message (AC-6); the change-log entry appears beside the row via a polite
        live region (AC-3, a11y floor).
  - [x] The confidence cell: read-only text + a `dérivée` marker, never an input (FR-42).
  - [x] The *côté* chip: accessible name includes *vue dérivée de la ligne*; not interactive.
  - [x] The line: `role="separator"`, drawn between rows, speaking its sentence + its basis eyebrow.
  - [x] The unscored zone, separately labelled and counted, never folded into *écartées*.
  - [x] The matter-level change-log panel.
  - [x] `main.tsx`: the route; a link from the matters list.
- [x] **T6 — tests**
  - [x] `tests/api/test_triage_table_api.py`: the read shape; **N edits across N rows all hold**
        (AC-1); the change-log entry carries previous→new, author, timestamp (AC-3); stale `seq` →
        409, out-of-taxonomy → 422, out-of-scope → the non-disclosing 404 (AC-6); the *côté* is
        derived and no route can set it (AC-5).
  - [x] `tests/app/test_labels_survive_a_rerank.py`: human-set labels survive a new ranking version
        and still read `source="human"` (AC-2/AC-4).
  - [x] `tests/checks/test_user_actions.py`: unchanged and still green (the registry grew).
- [x] **T7 — gate + bookkeeping** — ruff, 74 checks, import-linter 3/0, pytest green, `tsc -b` and
      `vite build` green; story → done; `sprint-status.yaml` 4-10 → done.

## Dev Notes

### The contract this screen must not break

From `EXPERIENCE-EPIC4.md` (final) — the load-bearing lines:

- **The editable/derived contrast is load-bearing.** The confidence cell and the label cell sit side
  by side "precisely so the lawyer sees, without being told, that scoring and classifying are
  different acts". Confidence is read-only text with a `dérivée` marker; the label is a real
  `<select>`. Not colour-only — a screen-reader user hears the difference.
- **Rows never reorder on an edit.** The order changes only on an explicit re-rank (new version).
- **The *côté* badge is never a toggle.** "The only way to change a side is to move the line (bulk)
  or pin a pièce (one)."
- **Barred:** a checkbox for retenue/écartée; an editable confidence; a sort-by-confidence; the word
  *supprimée* / *exclue*; folding *non-scorées* into *écartées*; a change log that can be edited.
- **Voice:** *"Écartée du jeu retenu de la version v3 — retrouvable par la recherche exhaustive."*
  Never *"Supprimée."*

### Where each number comes from (do not invent one)

| On screen | Source |
|---|---|
| `Classement v3 · <date> · théorie du cas v2` | `store.read_ranking(...)` → `RankingVersionView(version_no, basis, case_theory_version_id, created_at, ranked_count, unscored_count)` |
| the ranked rows | `store.read_ranked_order(...)` → `RankedEntryView(piece_id, rank, outcome, score, band, confidence, confidence_signals, …)` |
| retenue / écartée / non-scorée | `store.read_triage_sets(..., line=…, pins=…)` → `TriageSets(retained, discarded, unscored, pins_in_force, line_placed)` — **a view**, recomputed |
| the line | `store.read_current_line(...)` → `LinePlacementView(last_retained_piece_id, basis, seq, at, version_no)`; `None` = not placed |
| the pins | `store.read_current_pins(...)` → `tuple[Pin(piece_id, side)]` |
| the label per row | `store.read_current_label(...)` → `CurrentLabel(label, source, seq, in_current_taxonomy)` — **never null**, `unlabelled` is explicit |
| the change log | `store.read_label_change_log(...)` → `LabelChangeEntry(seq, label, source, set_by, at)` |
| the taxonomy for the select | the *tenant*'s `taxonomy` config (config-as-data, AD-24) |
| the *pièce* name | `Piece.provenance_path` |

**`confidence is None` means NOT DERIVED (AD-19) — render it as *non dérivée*, never as 0 or as
"faible".** The band wording (élevée / moyenne / faible) is a rendering of the derived number, never
a model self-report (FR-42), and the cell says `dérivée`.

**A previous value in a change-log entry** is the *preceding* entry's label in `seq` order — the
ledger stores the value each entry set, so the surface pairs entry *n−1* → *n*; the first entry's
previous value is `unlabelled` (the explicit sentinel, never null).

### Patterns to reuse (do not reinvent)

- **API**: `apx/api/app.py` — `Depends(current_identity)`, the non-disclosing `404 _MATTER_ABSENT`
  (`FR-14`: out-of-scope and absent are indistinguishable), `_require_store()`, a Pydantic `*Out`
  model per response. Follow `get_case_theory` / `put_case_theory` exactly.
- **The seam**: import from `apx.core.app.label`, never from the store adapter (AD-4; import-linter
  enforces).
- **Frontend**: `src/api.ts` typed wrappers + `ApiError(status)`; `src/viewer.tsx` is the model for a
  focused route (`useParams`, its own shell, honest states); `tokens.css` holds every visual value —
  no inline colour.
- **Untrusted text**: `provenance_path`, the label and the change-log author are **text nodes**,
  never `dangerouslySetInnerHTML` (the Epic-3 rule, `renders_sanitized`).

### Non-negotiables carried from the architecture

- **AD-23** — no unqualified reference: every count and set on screen names its ranking version.
- **AD-39/FR-16** — retained/discarded are derived views; the UI must offer no control that stores a
  membership.
- **AD-19** — never impute: a `None` confidence and an unscored *pièce* are shown as what they are.
- **AD-13/FR-14** — scope is a query pre-filter; out-of-scope and absent are the same 404.
- **AD-4** — the API depends on `core/app`, never on the store adapter.
- **FR-56** — the five new routes must be registered (Story 4.12), or the build fails.

### Testing standards

- `cd apx-mvp && export PATH="$PWD/.venv/bin:$PATH"` in the SAME shell call; never export
  `DATABASE_URL`. ruff line-length 100 — accented characters push lines over, reflow by hand.
- Frontend: `cd apx/web && npm run typecheck && npm run build` (no test runner ships in this repo;
  the surface's behaviour is asserted through the API tests + the type checker).
- Every new route gets a test for its **refusal** path, not only its happy path.

## Dev Agent Record

### Context Reference

- Epic 4, Story 4.10 (`_bmad-output/planning-artifacts/epics.md`)
- `EXPERIENCE-EPIC4.md` (final) + `mockups/epic-4-triage-table.html`; `DESIGN.md` for tokens
- FR-20 (the editable table + live change log), FR-16, FR-40, FR-42, FR-14, FR-56
- AD-4, AD-13, AD-19, AD-23, AD-24, AD-39

### Implementation Plan

Backend first, top-down through the layers the architecture already prescribes: the **domain view**
(`core/domain/triage_table.py`), the **port** (`core/ports/triage_table.py`), the **read seam**
(`core/app/read/triage_table.py`), the **adapter** (`store.py` implements the port), then the five
routes — so the API depends on `core` and never on the store (AD-4, import-linter-enforced). Then
the registry lock-step, then the tests, then the surface.

### Debug Log

- **The 4.12 harness did its job twice.** Adding the routes turned the build red
  (`5 HTTP route(s) exist but are not in USER_ACTIONS`), then red again for the three new
  `core/app/read` seams, then the 4.12 **probe** refused to pass until it walked all five new
  actions. Each was a real gap being named, not a nuisance: the registry is what bounds the
  never-hard-delete proof.
- **The partition invariant was wrong for a real state.** `TriageTable.__post_init__` demanded
  `retained + discarded + unscored == rows`, which is false before the line is drawn: with no cut
  nothing is retained or discarded. Calling those rows *écartées* would be exactly the lie FR-16
  forbids, so a **fourth honest side** was added — `unsplit` — and the invariant became: never
  exceed the matter, and partition it **once the line is placed**. Verified afterwards that a **pin**
  (which moves one *pièce* across the cut) preserves the partition: 2+1+0 → 3+0+0 over 3 rows.
- **`set_by` is the lawyer's name, not an email.** A test asserted the email; the product records
  `ident.actor`, the display name — which is the right thing to show in a change log. Test corrected,
  not the product.
- **N+1 removed before it shipped.** The first cut called `read_current_label` once per row — one
  query per *pièce* on a surface built for thousands (Story 2.13's 5 000-*pièce* run is the standing
  bound). Replaced by `_current_labels`, one query for the whole matter, reusing the same
  `current_label` domain view so the max-`seq` semantics are identical.
- **A refused edit was injecting a fake change-log entry.** The failure path called `onCommitted`
  with a synthesised "revert" entry, which prepended it to the visible matter-level log — a log
  showing an act that never happened. Removed: the `<select>` is *controlled by the row prop*, so a
  refusal needs no revert work at all (the committed value was never replaced), and nothing is
  appended. This is why the commit is **confirmed-then-applied** rather than the contract's
  "optimistic-then-confirmed": the cell never displays as committed a value the server has not
  accepted, which for this product is the stronger reading of the same promise.
- **The line was speaking a bare number.** It said *"jusqu'à la pièce n°142"* — but the contract bars
  the bare integer and writes the identity as `Pièce n°142 « Contrat de cession — 2019 »`. The
  sentence now carries the *pièce*'s **name** beside its number, in the accessible name too.

### Completion Notes

- **The surface exists.** Nine stories of triage engine had no screen; `/matter/:matter/triage`
  renders the four zones of the contract over the real substrate.
- **One act, and it is the label.** No control on this screen changes a rank, a confidence or a
  *côté* — and no route can: the côté is derived at read time from *(the order, the line, the pins)*
  and there is no endpoint that stores one (asserted by test, including that the route ignores a
  `side` field sent to it).
- **The editable/derived contrast is real, not decorative**: the label is a `<select>` (announced
  editable), the confidence is read-only text with a `dérivée` marker, and a *pièce* with no derived
  confidence reads *non dérivée* — never a zero (AD-19).
- **Five new routes, all registered** in `USER_ACTIONS`, all exercised by the 4.12 probe, all scope
  pre-filtered with the same non-disclosing 404 for out-of-scope and absent (FR-14).
- Gate: ruff clean · **74** structural checks · import-linter **3 kept / 0 broken** ·
  **1357 passed / 12 skipped** (1339 → 1357, +18 tests) · `tsc -b` and `vite build` clean.

## File List

| File | Change |
|---|---|
| `apx/core/domain/triage_table.py` | **NEW** — `TriageRow`, `LineView`, `TriageTable` (+ its partition invariant), `ChangeLogEntry`, `pair_change_log` |
| `apx/core/ports/triage_table.py` | **NEW** — the `TriageTableReader` Protocol |
| `apx/core/app/read/triage_table.py` | **NEW** — the three read seams (AD-14) |
| `apx/adapters/store_postgres/store.py` | UPDATED — `read_triage_table`, `read_label_change_log_paired`, `read_matter_change_log`, `_piece_names`, `_current_labels` |
| `apx/api/app.py` | UPDATED — 5 routes + their response models |
| `apx/checks/user_actions.py` | UPDATED — 8 registry rows (5 routes + 3 seams) |
| `apx/web/src/triage.tsx` | **NEW** — the triage surface |
| `apx/web/src/api.ts` | UPDATED — the typed client for the 5 routes |
| `apx/web/src/tokens.css` | UPDATED — the Epic-4 token block |
| `apx/web/src/main.tsx` | UPDATED — the `/matter/:matter/triage` route |
| `apx/web/src/App.tsx` | UPDATED — the link from a matter |
| `tests/api/test_triage_table_api.py` | **NEW** — 14 tests |
| `tests/app/test_labels_survive_a_rerank.py` | **NEW** — 4 tests |
| `tests/probe/test_never_hard_delete.py` | UPDATED — the probe walks the 5 new actions |

## Change Log

| Date | Change |
|---|---|
| 2026-08-06 | Story created (create-story). |
| 2026-08-06 | Implemented: 3 core layers + 5 routes + the React surface (dev-story). |
| 2026-08-06 | Adversarial review: 23 findings → 4 confirmed verdicts over 3 distinct defects; all fixed. |

## Senior Developer Review (AI)

**Reviewer:** adversarial 3-lens workflow (correctness · security-isolation · contract-architecture),
every finding independently skeptic-verified with the default set to REFUTED.
**Date:** 2026-08-06 · **Outcome:** Changes Requested → **all confirmed findings fixed** → Approve.

**23 findings → 4 CONFIRMED verdicts over 3 DISTINCT defects → all fixed · 19 refuted.**
(26 agents, ~2.2M tokens. Two defects were each filed twice by different lenses; one of those pairs
split — one skeptic confirmed it, the other refuted its sibling — and I fixed it.)

### The confirmed defects and their fixes

**1. (high) The concurrency guard was disarmed for the first edit of every row — a silent lost
update on the one act this story adds.** `commit()` forwarded `row.label_seq` as `expected_seq`, and
a never-labelled *pièce* reads back `label_seq: null`. The store applies its conditional commit only
`if expected_seq is not None`, so the client switched its own guard **off** for exactly the state
every row starts in. The skeptic reproduced it at both ends of the wire: two lawyers both holding the
pre-write view, Durand writes `Contrats` → 200, Autre writes `Jurisprudence` → 200, and Durand's
screen keeps showing `Contrats` with no 409 and no message — the failure AC-6 exists to prevent.
**Fixed:** the client sends `row.label_seq ?? 0`. Zero is this codebase's existing way of saying *"I
observed no entries"* (`test_taxonomy_label_store.py`, `test_line_move_store.py` both use it); the
React client was the single caller that departed from the convention. Regression test added: two
writers who both saw an unlabelled row → **200 then 409**, and the first writer's value stands.

**2. (medium) The label routes accepted any `piece_id`, writing permanent rows for *pièces* that do
not exist.** `taxonomy_label_entry` has no foreign key to `piece` — AD-7 forbids the cascade a FK
would invite — so nothing at the schema layer stopped it. Harmless while the act lived at the
internal seam, whose callers pass a *pièce* they just read; **4.10 put it behind an HTTP route**, and
there an unchecked identifier becomes an undeletable row (AD-7) in an evidential ledger, surfacing in
the matter's change log naming a *pièce* that never existed. The skeptic wrote six phantom entries
and read them back out of `/change-log`. **Fixed:** `store.piece_is_in_matter` (scope pre-filtered)
gates both writes at the **trust boundary**, refusing with the same non-disclosing 404 as an absent
matter (FR-14). The seam is deliberately left as it is: its contract is that the caller passes a
*pièce* of the matter, and validating untrusted input belongs where untrusted input arrives.

**3. (high) A failed change-log read was rendered as a verified absence.** `readMatterChangeLog(...)`
`.catch(() => [])` collapsed *"the read failed"* into *"there is nothing"*, and the panel then stated
**"Aucune modification pour l'instant."** Two skeptics reproduced it independently — one in a real
headless browser against the built bundle — and both found the fault state byte-identical to the
empty state, with no `role="alert"` anywhere on the page. For this product that is the cardinal sin:
it is the honest *"not in the corpus"* rule broken on the audit surface. **Fixed:** the log is
`ChangeLogEntry[] | null` — `null` means *not read*, `[]` means *read and empty* — and the panel
says so: *"Le journal n'a pas pu être lu — cet écran ne peut pas dire s'il y a eu des
modifications."* A commit no longer prepends to a log that was never read, either.

### Found and fixed before the review returned (during the same cycle)

- **A refused edit fabricated an entry in the change log.** The failure path called `onCommitted`
  with a synthesised "revert" entry, which prepended it to the visible matter-level log — a log
  showing an act that never happened. Removed: the `<select>` is *controlled by the row prop*, so a
  refusal needs no revert work at all. (Two lenses filed this; both skeptics then verified against
  the fixed file and refuted it, one noting *"`onCommitted` is NOT called from the failure
  branch"* — the fix landed first.)
- **N+1 label reads** — one query per *pièce* on a surface built for thousands — replaced by
  `_current_labels`, one query per matter, reusing the same `current_label` domain view.
- **The line spoke a bare number.** It now carries the *pièce*'s **name** beside its rank, in the
  accessible name too, which is what the contract's `Pièce n°142 « Contrat de cession — 2019 »`
  actually specifies.

### Notable refutations

- *"The line is rendered by rank, not by the identity of the last retained pièce."* Refuted on the
  contract's own evidence: in the mockup this contract is drawn from, the row the line names carries
  `rank 142`, and the walkthrough says *"drawn between pièce n°142 et n°143"* — so `n°142` **is** the
  rank. The barred form is *"Ligne à la position 180"*, a position with no pièce attached. The
  identity is what the line is **stored by** (verified by test), and the sentence now names it too.
- *"The denominator's total is the ranking version's population but is labelled 'pièces au
  dossier'"* — reproduced exactly, then refuted as **FR-58 / Story 4.13** (freshness and staleness of
  derived artefacts), which is allocated and not yet built. A real gap, in a named place.
- *"Neither AD-14 read-path check inspects this story's reads"* — refuted: a pre-existing gap in
  `checks/read_path.py` dating from Story 3.3, not something 4.10 introduced or made reachable.
- *"The /matter/:matter/triage route 404s on refresh"* — refuted: a pre-existing property of the
  deployment shell (`StaticFiles(html=True)` at `/`), unchanged by this story.
- *"Keyboard focus is destroyed on every label commit"*, *"the commit is pessimistic"*,
  *"with a pin in force the zone counts contradict the blocks"* — each driven in a real browser or
  through the real API by its skeptic, and each failed to reproduce.

### Integrity

All review work happened in `/tmp` and scratchpad copies. Ten of the fourteen snapshotted files were
**byte-identical** to their pre-review SHA-256 manifest when the review returned; the four that
differ are exactly the ones I edited to fix the findings above.
