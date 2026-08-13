---
baseline_commit: 010a539
---

# Story 5.7: The audit drawer and its export

Status: ready-for-dev

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

- [ ] **Task 1 — The two missing history reads.** `read_line_history` (every placement: last
      retained *pièce*, *ranking version*, author, timestamp, priced statement) and `read_pin_log`
      (every ledger entry, not just the in-force view), both scope-checked, both through the
      existing ports pattern. The export cannot state "the position history" or "all pins" without
      them. (AC-5)
- [ ] **Task 2 — The drawer read.** One core read seam assembling the four bands for one *pièce*
      from what exists (`read_justification` with its show-time verification, the triage-table row's
      derived côté and confidence, the ranking version). API `GET /api/matters/{m}/pieces/{id}/drawer`.
      Non-disclosing: out of scope reads exactly like absent. (AC-1, AC-2)
- [ ] **Task 3 — The proposed entry, in the domain.** A pure `proposed_entry(act, actor, matter,
      …)` that renders the row an act *will* append — act verb in the lawyer's language, actor,
      chain (from the catalogue, never the caller), and for an override its ground + the fact that a
      reason is mandatory. No timestamp: the domain refuses to invent one. (AC-3)
- [ ] **Task 4 — The drawer's actions, wired.** The four shipped acts (relabel, reject/restore the
      assessment, pin/unpin) exposed with their reversal sentence; the validation act rendered
      disabled naming Story 5.8. Each already writes its own audit entry — this task adds no new
      write path. (AC-4)
- [ ] **Task 5 — The export document, as data.** A pure domain `MatterRecord` assembling the eight
      FR-26 sections from the reads, tier-aware, with the two pending sections carrying their story
      number. Pure: no clock, no store, no I/O — so the self-containment test can rebuild it. (AC-5,
      AC-6)
- [ ] **Task 6 — The cover.** Scope, tier, author, timestamp; the per-chain continuity verdict from
      `read_audit().slices`; the AD-35 truncation banner; `degraded` computed at read time from the
      extracts' show-time verdicts, with its count. (AC-9)
- [ ] **Task 7 — The egress act.** `export_matter_record(...)` — the tier is a required argument
      with no default at the boundary, the act is audited with tier/actor/matter/scope, a refusal
      writes nothing, and the whole thing is scope-checked. New catalogued act
      `ACT_EXPORT_MATTER_RECORD`. (AC-7, AC-10)
- [ ] **Task 8 — Self-containment, asserted.** A test that takes the produced document, starts a
      process with **no** store access, and recomputes every number in it. The Story 5.4
      `test_statement_roundtrip.py` is the precedent for the shape. (AC-8)
- [ ] **Task 9 — The surfaces.** The drawer panel (four bands, the contract's states and a11y) and
      the tier fork with its second confirmation; both against DESIGN.md tokens, both in French.
- [ ] **Task 10 — Structural checks + gate.** At minimum: the tier is never defaulted at a boundary
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
