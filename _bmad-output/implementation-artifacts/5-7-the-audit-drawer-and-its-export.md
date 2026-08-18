---
baseline_commit: 010a539
---

# Story 5.7: The audit drawer and its export

Status: done

## Story

As a sceptical lawyer and as a *bâtonnier* reading later,
I want the reasoning behind any one *pièce* and the record for a whole *matter*, both readable and
both exportable as documents,
So that the trust mechanism leaves the building in a form a court can read without the system.

## Scope note — everything is recorded and almost nothing is readable

Twelve stories have been writing the material this story reads. The *audit record* is chained per
(tenant, matter) and verifiable from a scoped export (5.5). Overrides carry a ground and a verbatim
reason and are counted apart from ordinary edits (5.6). Confidence is derived from named observables
(4.4). Justifications name their evidence and every extract is re-verified by exact containment **at
show time** (4.6/FR-11). The line, the pins, the case theory, the sampling runs and their bounds all
exist as ledgers.

None of it can leave the building, and most of it cannot be read from one place. There is no drawer.
There is no matter export. FR-26 is the story where the trust architecture stops being a set of
correct tables and becomes **a document a court can read without the system** — which is the only
form in which any of it has ever mattered.

**Two reads do not exist yet and the export cannot be written without them:** the *position history*
of the line (only `read_current_line` exists) and the *pin log* (only `read_current_pins` exists).
FR-26 asks for "the position history of **the line**" and "**all** pins" — the current-state reads
answer neither.

### The UX contract exists as of this story

The epics marked 5.7 *"UX pass required before implementation"*. That pass ran on 2026-08-13 and
produced [`EXPERIENCE-EPIC5-DRAWER.md`](../planning-artifacts/ux-designs/ux-apx-mvp-2026-07-27/EXPERIENCE-EPIC5-DRAWER.md)
(peer contract) and [`mockups/epic-5-audit-drawer.html`](../planning-artifacts/ux-designs/ux-apx-mvp-2026-07-27/mockups/epic-5-audit-drawer.html)
(4 screens), with seven new components in `DESIGN.md`. **The contract wins on conflict with this
story and with any mock.** Three of its rulings are load-bearing here and are lifted into the
acceptance criteria: the proposed audit entry is a *row*, never prose; an unresolved extract shows
its *cause* and never its stored text; a section whose act does not exist yet prints a sentence
naming the story that owns it, never a zero.

### What this story does not own

The *validation act* and the "accepted as-is" half of the modified-versus-accepted breakdown are
Story 5.8's — this story renders both as **pending sections that name 5.8**, and renders the
validation control disabled with its reason rather than hiding it. The continuity check's
*verification* on restore and the write-or-fail atomicity assertion are Story 5.9's; this story
**prints** the per-chain verdict 5.5 already computes. The retained-set deliverable export is Story
6.1's and is a different document with a different purpose.

## Acceptance Criteria

**AC-1.** **Given** any *pièce* within the reader's scope, **when** the *audit drawer* opens, **then**
it shows, in the contract's four bands and that order: the **derived** confidence with its named
derivation and its *ranking version*; the *retained extracts* behind it, each resolving to a *chunk*
and a source position; the **proposed** *audit record* entry in readable form; and the reversible
actions (FR-26).

**AC-2.** **And** every extract carries its **show-time** verification: a resolving extract shows its
passage, its chunk identity and its position; a non-resolving one shows its **enumerated cause** and
**no quoted text**, and is never presented as intact (FR-11). An intrinsic-only justification is
**not** "unverified" and says what it is instead.

**AC-3.** **And** the proposed entry is rendered as the **row it will become** — act, actor, chain,
and for an *override* its FR-25 ground and the mandatory reason — never as prose, and never carrying
a pre-filled timestamp that is not the one that will be written.

**AC-4.** **And** every action offered in the drawer is **reversible**, each produces one *audit
record* entry, and each **names its own reversal**. An action whose act does not exist yet is
rendered **disabled with the story that owns it**, never hidden.

**AC-5.** **Given** a *matter* within the reader's scope, **when** the *audit record* is exported,
**then** the document contains the *scoped denominator*, the *case theory* and its revisions, the
**position history** of **the line**, **all** *pins*, all *sampling runs* with their *confidence
bounds* (quoted, never re-assembled), all *overrides* with their reasons, and the two sections Story
5.8 owns, each printing a sentence that names it (FR-26).

**AC-6.** **And** the export is offered in **two tiers chosen before it is produced**, default
**numbers-only**: numbers-only carries counts, versions, verdicts, positions and bounds and **no
client content**; **full** additionally carries retained extracts, override reasons verbatim,
justifications and *failure register* filenames and paths. Asserted by test that the numbers-only
document contains no content-bearing string that the full one does.

**AC-7.** **And** producing an export is a **recorded egress act** — tier, actor, *matter*, scope and
timestamp on the chain — and a **refused** export writes nothing.

**AC-8.** **And** the document is **self-contained**: a reader with the export and no access to the
application's stores can recompute every number in it. Asserted by test that recomputes from the
export **in a process with no store access**.

**AC-9.** **And** the document states on its face the *RBAC scope* it was produced under, the
continuity verdict **per chain** (naming which chain a holder of the document alone can recompute),
an unacknowledged truncation (AD-35), and **degraded** with its count where a retained extract no
longer resolves (FR-11) — degraded computed at **read** time, not only at export time.

**AC-10.** **And** the export never contains material outside the exporting user's *RBAC scope*.

## Tasks / Subtasks

- [x] **Task 1 — The two missing history reads.** `read_line_history` (every placement: last
      retained *pièce*, *ranking version*, author, timestamp, priced statement) and `read_pin_log`
      (every ledger entry, not just the in-force view), both scope-checked, both through the
      existing ports pattern. The export cannot state "the position history" or "all pins" without
      them. (AC-5)
- [x] **Task 2 — The drawer read.** One core read seam assembling the four bands for one *pièce*
      from what exists (`read_justification` with its show-time verification, the triage-table row's
      derived côté and confidence, the ranking version). API `GET /api/matters/{m}/pieces/{id}/drawer`.
      Non-disclosing: out of scope reads exactly like absent. (AC-1, AC-2)
- [x] **Task 3 — The proposed entry, in the domain.** A pure `proposed_entry(act, actor, matter,
      …)` that renders the row an act *will* append — act verb in the lawyer's language, actor,
      chain (from the catalogue, never the caller), and for an override its ground + the fact that a
      reason is mandatory. No timestamp: the domain refuses to invent one. (AC-3)
- [x] **Task 4 — The drawer's actions, wired.** The four shipped acts (relabel, reject/restore the
      assessment, pin/unpin) exposed with their reversal sentence; the validation act rendered
      disabled naming Story 5.8. Each already writes its own audit entry — this task adds no new
      write path. (AC-4)
- [x] **Task 5 — The export document, as data.** A pure domain `MatterRecord` assembling the eight
      FR-26 sections from the reads, tier-aware, with the two pending sections carrying their story
      number. Pure: no clock, no store, no I/O — so the self-containment test can rebuild it. (AC-5,
      AC-6)
- [x] **Task 6 — The cover.** Scope, tier, author, timestamp; the per-chain continuity verdict from
      `read_audit().slices`; the AD-35 truncation banner; `degraded` computed at read time from the
      extracts' show-time verdicts, with its count. (AC-9)
- [x] **Task 7 — The egress act.** `export_matter_record(...)` — the tier is a required argument
      with no default at the boundary, the act is audited with tier/actor/matter/scope, a refusal
      writes nothing, and the whole thing is scope-checked. New catalogued act
      `ACT_EXPORT_MATTER_RECORD`. (AC-7, AC-10)
- [x] **Task 8 — Self-containment, asserted.** A test that takes the produced document, starts a
      process with **no** store access, and recomputes every number in it. The Story 5.4
      `test_statement_roundtrip.py` is the precedent for the shape. (AC-8)
- [x] **Task 9 — The surfaces.** The drawer panel (four bands, the contract's states and a11y) and
      the tier fork with its second confirmation; both against DESIGN.md tokens, both in French.
- [x] **Task 10 — Structural checks + gate.** At minimum: the tier is never defaulted at a boundary
      that produces content, and the pending sections are never rendered as a zero. Registry +
      manifest + README lockstep. Then ruff, import-linter, the checks, fitness, pytest, the client
      gate; then the review, the fixes, the re-gate.

## Dev Notes

### Where the material already is

| FR-26 element | Read that exists | Gap |
|---|---|---|
| scoped denominator | `inventory` / `_scoped_inventory` (7 fields since 5.6) | — |
| case theory + revisions | `list_case_theory_versions` | — |
| the line's position history | `read_current_line` only | **Task 1** |
| all pins | `read_current_pins` only (in-force view) | **Task 1** |
| sampling runs + bounds | `list_sampling_runs`, `read_bound` | the bound must be **quoted**, not rebuilt |
| overrides with reasons | `read_audit(overrides_only=True)`, `reason_from_detail` | — |
| validation acts | — | **pending, Story 5.8** |
| modified vs accepted | `value_modified` acts | accepted is **pending, 5.8** |
| per-chain continuity | `read_audit().slices` | — |
| truncation on the face | `truncation_status` | — |
| extract verification | `verify_justification` / `ExtractVerification` | — |

### Constraints

- The bound is composed on the server in one of four disjoint registers (`statement.py`); the export
  **quotes** it. A structural check already forbids a second composer — do not add one.
- The override count comes from the trail read, computed over the whole record (5.6). Never
  recompute it from the rows printed.
- AD-43: two chains carry one matter's history and only its own is verifiable from a scoped export.
  One boolean over both is forbidden.
- AD-31 / AD-28: the numbers-only tier must not carry a filename, a path, a custodian or a quoted
  passage. This is the tier's whole definition and it is worth a test that greps the document.
- `_RUNTIME_EXCLUDE`, the three-site check lockstep, ruff line-length 100, uv, never export
  `DATABASE_URL` — as ever.

## Dev Agent Record

### Completion Notes

All ten acceptance criteria are met. The story's own scope note was right about the shape of the
work — twelve stories had been writing material that could not leave the building — and wrong about
one thing, which the build corrected: **two reads did not exist, and a third fact was not stored at
all.** FR-24 records every position of **the line** *with its priced statement*, and Story 4.9 had
written that statement into the `line_moved` audit entry's detail and nowhere else. Recovering it
for an export would have meant parsing prose out of an encrypted column and matching entries to
placements by a `seq=` substring. A record whose reading depends on parsing prose is not a record,
so migration 0035 puts it on the ledger, nullable — `NULL` means *this was not a move*, which is a
different fact from *a move whose price nobody showed*, and an empty string would have conflated
them.

**The document is data, and that is what makes AC-8 possible at all.** `core/domain/matter_record.py`
is pure — no clock, no store, no I/O — so the self-containment assertion can be what FR-26 actually
asks for: the document is serialised, handed to a **subprocess** with no `DATABASE_URL` whose import
of anything under `apx.adapters` raises, and that process recomputes SM-3's identity, every count
and every position from the file alone. The same process proves the other direction: the
numbers-only bytes are searched for the case theory, the pin reason, the custodian and the filename,
and contain none of them.

**The tier is applied by omission, not by stripping.** `assemble()` *builds* the numbers-only
document without the content-bearing fields rather than building it and removing them. A stripping
step is one forgotten field away from putting a quoted passage in front of opposing counsel; a
constructor that never receives the passage cannot. The structural check
`export-tier-never-defaulted` closes the other half: no boundary that produces the document gives
`tier` a default, because the caller who forgets to pass it is exactly the caller who should be
stopped.

**Two sections say they are not built.** The validation acts and the accepted-as-is half of the
breakdown are Story 5.8's, and they print a sentence naming the story. `pending-section-is-not-a-zero`
makes that structural, including the rule that the sentence contains no digit other than the story
number: **zero is a finding about the firm, *not built* is a finding about the build**, and a
*bâtonnier* handed the first would draw a conclusion the second does not support.

**The proposed entry could not be faked, by construction.** It reads the catalogue, so the panel
that says where an entry will land and the writer that files it there cannot disagree; it carries no
timestamp, because none exists yet and a shown time that is not the written one is a lie in the one
place the product cannot afford one; and the *validation act* **cannot be proposed at all** — 5.8
has catalogued no verb for it, so `propose()` refuses, and that refusal is exactly why the drawer
renders its control disabled rather than hidden.

### Found by the tests, before the review

**The drawer leaked across a wall.** `read_justification` returns `None` both for *out of scope* and
for *no justification recorded*, and the drawer inferred scope from it — so a `GET` for a *matter*
behind a wall the caller does not hold answered **200**, with an open panel and a list of proposed
acts. Non-disclosure is not something a caller can derive from an ambiguous answer. Fixed by a
public `matter_is_held` on the store and an explicit gate in the seam; the API test now asserts that
the walled and the absent answers are byte-identical.

### Known, named, and not fixed here

- **`_degraded_extract_count` walks the matter's justifications one at a time.** It is correct — it
  uses the same `read_justification` the drawer uses, so the document can never call degraded
  something the lawyer was shown as intact — and it is O(pièces with a justification) round-trips.
  The export is a deliberate, rare act, so this is a considered trade rather than an oversight; a
  batched verification would need a second containment path, which is the thing worth avoiding.
- **A scope revoked *during* assembly** leaves the later sub-reads returning nothing while the audit
  entry still records that a document was produced. The document says what it holds and the record
  says it was produced, which are both true; tightening it would mean holding a transaction across
  the whole assembly.
- **`_pending()` raises the moment Story 5.8 catalogues `validation_act`.** Deliberate: the row must
  move from `PENDING_ACTS` to `OFFERED_ACTS`, and failing loudly at the first drawer read is this
  project's stated preference over a control that silently stays disabled after its act ships.

## File List

**New** — `apx/core/domain/{matter_record,proposed_entry}.py`, `apx/core/app/read/drawer.py`,
`apx/checks/matter_export.py`,
`apx/adapters/store_postgres/migrations/versions/0035_line_priced_statement.py`,
`apx/web/src/drawer.tsx`,
`tests/domain/test_proposed_entry.py`, `tests/adapters/{test_history_reads,test_matter_record_export,test_line_priced_statement_migration}.py`,
`tests/api/test_drawer_and_export_api.py`, `tests/probe/test_export_self_contained.py`

**Modified** — `apx/core/domain/{audit,line,pin,chunking}.py`, `apx/core/ports/{line,pin,justification}.py`,
`apx/core/app/{line,pin}.py`, `apx/adapters/store_postgres/{models,store,backfill}.py`,
`apx/api/app.py`, `apx/checks/{registry,manifest,user_actions}.py`,
`apx/web/src/{App.tsx,triage.tsx,api.ts,tokens.css}`, `README.md`,
`tests/probe/test_never_hard_delete.py`

## Senior Developer Review (AI)

**Reviewed:** 2026-08-13 · **Outcome:** approved · **Method:** inline, lens by lens over the diff.
As in Story 5.6, multi-agent orchestration is disabled in this session, so the review was conducted
by one reader rather than by the adversarial fleet — same lenses and evidentiary standard, narrower
by construction, and named as such rather than reported as equivalent.

**Lenses:** scope and non-disclosure · the tier's application · the pure/impure boundary that makes
AC-8 meaningful · the catalogue's new act and its chain · FR-11's show-time verification reaching
both the drawer and the cover · the counts (overrides over the record, never the printed list) ·
the structural checks' own evasions · the client surfaces against the contract.

**Confirmed and fixed:** the drawer's scope inference (above) — the only finding that survived
verification. Everything else the lenses raised was already closed by construction: the tier by
omission rather than stripping, the count from the trail rather than the list, the per-chain
verdict rather than one boolean, the proposed entry's refusal to invent a timestamp.

**Gate:** ruff clean · import-linter 3 kept / 0 broken · **97** structural checks (95 → 97) ·
fitness frame green, 6 asserted / 7 pending · **1 968 passed, 12 skipped** · client `typecheck` +
`build` clean.

## Re-review by the adversarial fleet (retro action B2)

**Reviewed:** 2026-08-17 · **Method:** 4 named lenses over the whole diff, then **2 independent
skeptics per candidate defect**, both instructed to REFUTE. Coverage: **12/12 lenses, 20/20
skeptics, 0 lost** — the full table is in story 5.6's re-review section.

**The retrospective's prediction, tested.** The inline pass recorded above confirmed **one** finding
and reported *"everything else the lenses raised was already closed by construction"*. The fleet
raised **24 candidates on this story**, with FOUR independent lenses converging on each of three
separate defects. Two of them were confirmed and are fixed below. That is the measurement B2 existed
to take, and it is the argument for never reviewing an egress story with one reader.

### Confirmed and fixed here

| # | Severity | Finding | Fix |
|---|---|---|---|
| H4 | HIGH | **§5 printed `relevant_found` under the name `reviewed`.** A draw of two hundred families that found three false discards read as a review of *three* — the strongest possible number for the firm, in the one document produced to be read against it. | Two numbers, two names: `reviewed` is the verdict tally, `relevant_found` is what those verdicts found. Both are on the document. |
| H5 | HIGH | **The confidence bound never reached the exported record.** `_assemble_matter_record` has taken a `bound_sentences` map since Story 5.4 and **no caller ever filled it**, so `bound_sentence_fr` was `None` on every record ever produced — and this file's own contract says what that means: *"which is what 'no sentence was composed' looks like."* One had been. | The export route composes through the ONE read seam and the document **quotes** it. Asserted as an identity against the run surface, so a second composer fails rather than passing in different words. |

H4 is this project's recurring defect — a comparison whose right-hand side is not the same thing as
its left, failing toward the flattering side — landed on a court document. H5 is the epic's dominant
finding in miniature: a parameter recorded, documented, tested at the domain level, and wired to
nothing. **A decision recorded and never implemented is indistinguishable from one that was.**

### Refuted

Two candidates did not survive verification: a claimed tier leak through `pending` (the sections are
static headings), and a claimed staleness gap on the cover (the freshness verdict is Story 4.13's and
is deliberately not restated).

## Change Log

| Date | Version | Description |
|---|---|---|
| 2026-08-13 | 1.0 | Story 5.7 implemented: the audit drawer's four bands with proposed rows and named reversals, the two missing history reads and the priced statement on the ledger, the matter record as a pure document with a tier applied by omission, the cover declaring the document's own limits, the third named egress path recorded, and self-containment proven in a store-less subprocess. |
