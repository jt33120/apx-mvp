---
baseline_commit: d5455a8
---

# Story 5.6: Overrides with a mandatory one-line reason

Status: done

## Story

As a firm,
I want every act that contradicts the machine or bypasses a guard to cost one written sentence,
So that a deliberate exception is a recorded, arguable decision rather than an invisible one.

## Scope note — three overrides exist, and nothing in the build knows they are overrides

The word *override* appears in the codebase thirty-odd times. Two acts already behave like one:

- **`pin_override`** (Story 4.11) — a *pin* moves exactly one *pièce* across **the line**,
  contradicting a ranked order the machine produced with a stated confidence. It validates a
  mandatory reason (`validate_pin_reason`), stores it encrypted on the ledger row, and writes it
  verbatim into the audit entry's `detail`.
- **`truncation_override`** (Story 5.5) — clearing an audit-record truncation marker bypasses the
  guard that names an incomplete record on the face of every export. It refuses a blank reason with
  a bare `ValueError` and stores the reason on the marker row — and does **not** put it in the
  audit record.

The third does not exist at all: AD-37's ownership table names a `failure register entry:
open → overridden` transition owned by "the *override* use case". There is no override use case.
`resolution_state` is documented in the model as `open|resolved`. FR-5 is explicit that an entry
leaves `open` only by successful *ingestion* or by "an explicit user action recorded in the *audit
record* with a reason (an *override* per FR-25)" — so today the only exit is the one that requires
the document to become readable, and an entry that never will be stays `open` forever, permanently
inflating the "not indexed" count the home screen shows.

And nothing in the build knows any of these are overrides. `CLASS_OVERRIDE` sits in
`PENDING_CLASSES` with `"5.6"` beside it: an FR-24 class with **no writer**. So the answer to FR-25's
own testable consequence — *"overrides are countable and filterable, separately from ordinary
modifications"* — is currently **zero**, and it would be zero on a matter with forty pins.

**This story is not "add a reason field."** The reason fields exist. What is missing is that
*override* is a **property an act carries**, named once, checked by the build, and countable across
every act that carries it. Three separate implementations of "the reason is mandatory" is two too
many: they will drift, and the one that drifts will be the one that stops refusing.

### The trap this story must not fall into

The obvious implementation is to give `CLASS_OVERRIDE` a writer and count `act_class == "override"`.
That count is wrong on the day it ships: a *pin* is an override **and** a pin, and FR-24 requires
"every *pin*" be recorded as a pin. An act has one class; being an override is orthogonal to it. A
count taken over the class silently misses every pin — this project's recurring defect, a comparison
whose right-hand side is not the same thing as its left, failing towards the flattering number
(*"this matter has 0 overrides"* on a matter with forty). The override must be a **second, named
property** on the catalogue entry, and the count must be taken over that property.

### What this story does not own

The *audit drawer* surface and the exported document are Story 5.7's — this story makes overrides
countable and filterable in the trail read and in the API, and 5.7 renders them. Reversing an
override (AD-37's *"a retry that succeeds against an `overridden` entry produces a worklist line
offering to reverse the override"*) needs a worklist kind the freshness-derived worklist does not
have; 5.6 asserts the half that holds today — a retry never silently resolves an overridden entry —
and names the reversal as 5.7's, where reversible actions in the drawer are the story's subject.
FR-25's `[ASSUMPTION]` about repeated identical reasons as a quality signal is SM-C2's, an
evaluation-session metric with no telemetry to feed it (§5 forbids telemetry); it is not built here.

## Acceptance Criteria

**AC-1.** **Given** an action that contradicts a machine assertion made with stated confidence,
removes a *failure register* entry from `open` without successful *ingestion*, or bypasses a system
guard, **when** the user commits it, **then** it is **classified as an *override*** — and the
classification is a property of the catalogued act, carrying **which of FR-25's three grounds** it
rests on, so that no act is an override by convention or by its verb reading like one.

**AC-2.** **And** it cannot be committed without a free-text reason: **one** validator owns
"mandatory", every override write path goes through it, and the build fails if an override write
path validates its reason anywhere else or not at all.

**AC-3.** **And** the reason is stored **verbatim** in the *audit record*, attributed and
timestamped — rendered by one helper and recoverable from the entry unchanged, including a reason
containing the renderer's own separators, `=`, newlines or quotes. The build fails if an override
write path composes its detail by hand.

**AC-4.** **And** the *failure register* override exists as AD-37 names it: `open → overridden`,
**one owning use case**, a **conditional commit** on an observed `open` under a row lock, atomic
with its audit entry (AD-22), the reason held on an **append-only** row (never a mutable copy that
can drift from the chained one), scope-checked, and admin-only for an entry whose *matter* is
undetermined (FR-49).

**AC-5.** **And** *overrides* are **countable and filterable** in the audit trail read and over the
API, **separately from ordinary modifications**: the count is taken over the override property and
therefore includes pins; a `value_modified` entry is never counted as an override; and the count
reported is the count of overrides in the trail, not the length of whatever the filter returned.

**AC-6.** *(failure path)* **And** an *override* submitted with an empty or whitespace-only reason
is **refused** and **nothing is written** — no ledger row, no state change, no audit entry — for
each of the three override paths, asserted separately for each.

**AC-7.** **And** `CLASS_OVERRIDE` leaves `PENDING_CLASSES` because it has a real writer, and the
existing catalogue check (an act class declared covered whose writer does not exist fails the build)
holds it there.

## Tasks / Subtasks

- [x] **Task 1 — The override, named once (domain).** New `apx/core/domain/override.py`: FR-25's
      three grounds as constants (`GROUND_CONTRADICTS_MACHINE`, `GROUND_REGISTER_EXIT`,
      `GROUND_GUARD_BYPASS`), `MissingOverrideReason(ValueError)`, `validate_override_reason`, and
      the detail renderer/extractor (Task 3). Imports nothing from `audit.py` (the catalogue imports
      *this*, not the reverse). (AC-1, AC-2)
- [x] **Task 2 — The catalogue carries the property.** `RecordableAct` gains
      `override: str | None` — the *ground*, `None` when it is not one. `is_override(verb)`,
      `override_ground(verb)`, `override_verbs()`. `pin_override` → `GROUND_CONTRADICTS_MACHINE`
      (class stays `CLASS_PIN` — FR-24 requires every pin be a pin); `truncation_override` →
      `GROUND_GUARD_BYPASS`, class moves `CLASS_CONFIG_CHANGE` → `CLASS_OVERRIDE`; new
      `ACT_REGISTER_OVERRIDE = "register_override"` → `GROUND_REGISTER_EXIT`, `CLASS_OVERRIDE`,
      `CHAIN_TENANT`. `CLASS_OVERRIDE` removed from `PENDING_CLASSES`. (AC-1, AC-7)
- [x] **Task 3 — The reason reaches the record verbatim.** `override_detail(reason=..., **fields)`
      renders the reason **last** behind an unambiguous separator; `reason_from_detail(detail)`
      returns it byte-for-byte. Round-trip test over adversarial reasons (containing `reason=`, the
      separator, `=`, newlines, quotes, unicode). `pin_piece` and `clear_truncation` re-pointed at
      it — `clear_truncation` today does **not** put its reason in the audit record at all, which is
      an FR-25 miss on a shipped path. (AC-3)
- [x] **Task 4 — The failure-register override.** Migration `0034_register_override.py`: an
      append-only `register_override` table (id, tenant, entry_id, actor encrypted, reason
      encrypted, at). Port `apx/core/ports/register_override.py` (`RegisterOverrider`), use case
      `apx/core/app/register_override.py`, store method `override_register_entry(...)`:
      `validate_override_reason` first, then one transaction — re-observe `open` under
      `with_for_update`, refuse otherwise (`precondition-not-met`), authorise via `_authorise_entry`,
      set `resolution_state = "overridden"`, insert the append-only row, append the audit entry.
      `retryable` on the register read becomes false for an overridden entry; the model docstring
      and `resolution_state` comment updated to `open|resolved|overridden`. Seams added to the
      `user_actions` check table. (AC-4, AC-6)
- [x] **Task 5 — Countable and filterable.** `AuditEntry` carries `override: bool` and
      `override_ground: str | None`; `AuditTrail` carries `overrides: int` **computed over the whole
      trail before any filter**. `read_audit(..., overrides_only: bool = False)`. API:
      `AuditEntryOut.override` / `.override_ground`, `AuditTrailOut.overrides`, query param
      `?overrides_only=`. Web: the audit view names the count in French and offers the filter.
      (AC-5)
- [x] **Task 6 — Three structural checks (92 → 95).** In `apx/checks/override.py`:
      (a) **`override-reason-one-validator`** — every module writing an override verb calls
      `validate_override_reason` (directly or through a delegate that does), and no module outside
      `core/domain/override.py` defines its own blank-reason test for an override path;
      (b) **`override-reason-in-the-record`** — every `_append_audit` call site whose verb is an
      override verb passes a `override_detail(...)` call as its detail, so the reason cannot be
      left out or hand-composed;
      (c) **`override-ground-named`** — every act carrying `CLASS_OVERRIDE` is override-flagged,
      every override-flagged act names one of FR-25's three grounds, and the override count in the
      runtime is taken over the flag and never over `act_class == CLASS_OVERRIDE`.
      Registered in `registry.py` + `manifest.py` + the README block, in lockstep. (AC-1, AC-2, AC-3)
- [x] **Task 7 — Tests.** Domain: grounds, validator, round-trip. Store: the three refusal paths
      (nothing written — assert row counts and audit length unchanged), the conditional commit
      (override an already-resolved entry → refused; retry against an overridden entry →
      `precondition-not-met`, entry untouched), scope + admin gating, atomicity (the audit entry and
      the state change commit together). Read: a matter with pins + labels + a register override
      counts exactly the overrides, and the count survives the filter. API: the endpoint's count and
      filter. (all ACs)
- [x] **Task 8 — Gate.** ruff, import-linter, 95 structural checks, fitness frame, full pytest,
      client `typecheck` + `build`. Then the adversarial review, then the fixes, then the re-gate.

## Dev Notes

### Where every piece lives today

| Thing | File | Note |
|---|---|---|
| The act catalogue | `apx/core/domain/audit.py` | `RecordableAct`, `_CATALOGUE`, `ACTS`, `FR24_CLASSES`, `PENDING_CLASSES` |
| The pin's reason rule | `apx/core/domain/pin.py` | `MissingPinReason`, `validate_pin_reason` |
| The pin write | `store.py::_append_pin_entry` | detail is `f"piece=… action=… seq=… reason={reason}"` |
| The truncation override | `store.py::clear_truncation` | bare `ValueError`; **reason absent from the audit detail** |
| The register | `models.py::Failure` | `resolution_state: open\|resolved`; `filename`/`path`/`custodian`/`detail` encrypted |
| The register reads | `store.py::register`, `register_all` | `retryable = resolution_state == "open"` |
| The retry | `store.py::retry_failure`, `bulk_retry` | already conditional on observed `open` under `with_for_update` — the "AD-37 override-race defense" comments were written **for this story's other half** |
| Entry authorisation | `store.py::_authorise_entry` | tenant + scope, admin for a NULL matter |
| The trail read | `store.py::read_audit` (~3071) | returns `AuditTrail(entries, verified, slices)` |
| The API | `apx/api/app.py::read_audit` (~1661), `AuditEntryOut`/`AuditTrailOut` (~430–460) | |
| The seam registry | `apx/checks/user_actions.py` | every core/app seam is enumerated with what it changes and how it reverses |
| The register ownership check | `apx/checks/register_ownership.py` | `resolution_state` is written **only** in the store adapter — the new write must live there |

### Decisions taken before implementation

**D1 — `register_override` goes on the TENANT chain, always.** A register entry's *matter* is
nullable (an entry that could not be attributed). Putting matter-bearing overrides on the matter
chain and matterless ones on the tenant chain makes one verb land in two places by a rule no reader
of the export can see — the catalogue already rejects exactly this for `bulk-retry` and
`export-register`, both register acts, both on the tenant chain, for this reason. The `matter`
column still records what the act was *about*, and `read_audit` returns tenant-chain entries naming
the matter inside that matter's trail, so the count is unaffected.

**D2 — the reason lives on an append-only row, not on `failure`.** `Failure` is a mutable row; the
pin ledger and the truncation marker are not. A reason copied onto a mutable row can drift from the
chained one in the audit record, and the drifted copy is the one a surface would show. A separate
`register_override` table keeps the codebase's own precedent (the act's table carries the encrypted
reason; the audit record carries it verbatim) **without** the mutable copy.

**D3 — `pin_override` keeps `CLASS_PIN`.** FR-24 enumerates "every *pin*" as a recorded item. An act
has one class. Moving the pin to `CLASS_OVERRIDE` would discharge FR-25's class by breaking FR-24's.
The override property is the second axis; that is the whole point of Task 2.

**D4 — `truncation_override` moves to `CLASS_OVERRIDE`.** It was filed under `CLASS_CONFIG_CHANGE`
because that was the closest slot available while `CLASS_OVERRIDE` had no writer. Clearing a
truncation marker is not a configuration change; it is the guard bypass FR-25 describes. Moving it
does not orphan anything: the class is read from the catalogue at read time, never persisted on the
row.

**D5 — the count is computed before the filter.** `overrides` on the trail is the number of override
entries in the matter's trail. When `overrides_only` is set, the returned `entries` shrink and the
count does not change. A count that equals `len(entries)` under the filter is not a count, it is a
length, and it reports zero on the unfiltered read only if nothing is there — the two coincide often
enough to hide the bug.

### Constraints

- `_RUNTIME_EXCLUDE = {"checks", "fitness", "timedrun", "__pycache__"}` — `apx/checks/` is outside
  the scanned runtime and may name the things it forbids.
- Structural-check lockstep is **three sites**: `apx/checks/registry.py`, `apx/checks/manifest.py`
  (`_p(key, fr, ad, name, callable, inspects)`), and the README `<!-- structural-properties -->`
  block. `manifest_matches_readme` compares only the first five cells.
- AD-31: content-bearing columns are application-encrypted. The new `reason` and `actor` columns are
  content/PII → `EncryptedText`. `resolution_state` stays plaintext (a categorical query key, and it
  is already on the plaintext allowlist).
- AD-4/AD-27/AD-45 (import-linter): the core imports no adapter; the port is a `Protocol`.
- ruff line-length 100. Accented characters ("pièce", "é", "→") count — reflow by hand.
- uv: `.venv/bin/ruff`, `.venv/bin/python`. Never export `DATABASE_URL`.

## Dev Agent Record

### Completion Notes

All seven acceptance criteria are met, and two of them cost more than the story anticipated.

**What was built.** `override` became a second axis on the act catalogue — a **ground**, not a
boolean, so every override says which of FR-25's three reasons makes it one. `pin_override` keeps
its FR-24 class (`pin`) and carries `contradicts-a-machine-assertion`; `truncation_override` moved
from `config_change` (where it sat for want of a live class) to `override` with
`bypasses-a-system-guard`; `register_override` is new, on the tenant chain, with
`register-exit-without-ingestion`. `CLASS_OVERRIDE` left `PENDING_CLASSES` because it now has a
writer, and the existing catalogue check holds it there.

"The reason is mandatory" had two implementations and was about to get a third. It now has one
(`core/domain/override.py`), the two shipped paths were re-pointed at it, and a structural check
fails the build on a second blank-reason test anywhere. `validate_pin_reason` / `MissingPinReason`
were **deleted** rather than kept as delegates: a second name for one rule is how a second rule
starts.

The reason now reaches the record through one renderer, and comes back out of it byte-for-byte.
`clear_truncation` did not put its reason in the *audit record* at all before this story — it wrote
it to the mutable marker row and nowhere else, which is an FR-25 miss on a path that shipped in 5.5.

The register override is AD-37's `open → overridden`: one owning use case, a conditional commit on
an observed `open` under a row lock, atomic with the audit entry, the reason on an **append-only**
ledger (never on the mutable `failure` row, where it could drift from the chained copy), scope-
checked, admin-only for an undetermined *matter*.

**Found while building, before the review — the detail could be forged from client data.**
`override_detail` renders `key=value` fields ahead of the reason and the extractor takes the first
`reason=`. The register override initially passed the *matter* as a field. A firm names its own
matters, so a matter called `dossier x reason=…` would have put the mark ahead of the real one and
the extractor would have handed a reader that instead — a sentence that looks like a reason, counts
as one and reads as one. Fixed twice over: the *matter* is not a field (it is already the entry's
own column), and the renderer now refuses any field carrying the mark.

**Found by the review — an override broke the denominator, three ways.** SM-3's identity was
`submitted_pieces == in_corpus + open_register_entries`. An override drops the open count and adds
nothing to the corpus, so the identity breaks the moment one is committed — and
`require_consistent()` runs at the end of every retry and every import completion, so the failure
would have surfaced on the **next unrelated act** of that *matter*, nowhere near its cause. The two
ways to make it "pass" were both dishonest: subtracting the override from `submitted_pieces` makes
an *override* a way to shrink the *denominator*, which is the one thing AD-38 exists to prevent.
So the identity gained a **third term** — `overridden_register_entries`, the count of documents the
firm has decided to live without, which is precisely the number FR-25 exists to keep visible. Three
further paths computed the old sum and were fixed with it: `_settle_submitted_after_retry` (which
would have rewritten the watermark downwards by every written-off entry on the next retry),
`_raise_submitted_watermark` (which would have failed to rise for a genuinely new *pièce* submitted
after an override, reporting the **new** pièce as lost), and `backfill_submitted_pieces` (a
documented re-runnable recompute that would have wedged every matter holding an override).

**Found by the review — an id probe could map another wall.** An absent entry answered 400 and a
walled one 403, so a caller could learn, one identifier at a time, which entries exist behind a wall
it does not hold. Absent and denied are now one answer with one body, as everywhere else a caller
names an identifier.

### Debug Log

- `TruncationMarker` seeding in tests goes through the ORM, not `record_truncation` (private,
  reconciliation-shaped). The truncation override is a matterless tenant act, so it is asserted
  against the record directly — it belongs to no matter's trail and must not appear in one.
- The FR-21 probe walks the whole action registry, so both new actions needed steps, and the seam
  and the route need **one open entry each**: an override closes an open entry and refuses one that
  moved. `_seed_failure` now seeds two.
- `python -m apx.checks | tail -2` alone hides a failure behind the two README meta-checks; the gate
  reads the count line and greps `[FAIL]` separately.

## File List

**New**
- `apx/core/domain/override.py` — the grounds, the one validator, the renderer and its inverse
- `apx/core/ports/register_override.py` — the `RegisterOverrider` Protocol
- `apx/core/app/register_override.py` — the use case seam
- `apx/checks/override.py` — the three structural checks
- `apx/adapters/store_postgres/migrations/versions/0034_register_override.py`
- `tests/domain/test_override.py`, `tests/checks/test_override_checks.py`,
  `tests/adapters/test_register_override.py`, `tests/adapters/test_register_override_migration.py`,
  `tests/adapters/test_override_countable.py`, `tests/api/test_override_api.py`
- `tests/_fixtures/override_violations/{clean,no_validator,hand_composed_detail,second_blank_test,count_by_class}/`

**Modified**
- `apx/core/domain/audit.py` — the override axis, `ACT_REGISTER_OVERRIDE`, `PENDING_CLASSES`
- `apx/core/domain/inventory.py` — the identity's third term
- `apx/core/domain/pin.py` — the local reason rule deleted
- `apx/adapters/store_postgres/{models,store,backfill}.py`
- `apx/api/app.py` — the endpoint, the trail's count/filter, the seven-field denominator on the wire
- `apx/checks/{registry,manifest,encryption,audit_record,inventory_record,user_actions}.py`
- `apx/core/app/{ingest,pin}.py`, `apx/core/domain/{justification,retrieval}.py`
- `apx/web/src/{App.tsx,api.ts,tokens.css}`
- `README.md` — three new structural-property rows, the inventory row corrected to seven fields
- `tests/{domain/test_pin,domain/test_justification,adapters/test_pin_store,api/test_search_endpoints,probe/test_never_hard_delete,domain/test_inventory}.py`

## Senior Developer Review (AI)

**Reviewed:** 2026-08-13 · **Outcome:** approved after fixes · **Method:** inline, lens by lens
over the full diff, each finding required to demonstrate a concrete failing sequence before being
accepted.

**A deviation from the cadence, stated plainly.** Stories 5.1–5.5 were reviewed by a fleet of
adversarial subagents, each finding put to two independent skeptics defaulting to REFUTED. This
session runs with multi-agent orchestration disabled, so the review was conducted **inline** rather
than by the fleet. It is the same lenses and the same evidentiary standard, by one reader instead of
many — narrower by construction, and named as such rather than reported as equivalent.

### Lenses walked

catalogue & classification · the mandatory reason and its round trip · the register transition
(AD-37 conditional commit, AD-22 atomicity, AD-7, authorisation) · the denominator and every path
that computes it · the structural checks' own evasions · the surfaces (API, client, disclosure).

### Confirmed and fixed

| # | Severity | Finding |
|---|---|---|
| 1 | HIGH | An override broke SM-3's identity; `require_consistent()` would have raised on the matter's next unrelated act. Fixed by a third named term. |
| 2 | HIGH | `_settle_submitted_after_retry` recomputed the watermark as `in_corpus + open`, silently erasing every written-off entry from the *denominator* on the next retry — an *override* shrinking the *denominator* through a path nobody would look at. |
| 3 | MED | `_raise_submitted_watermark`'s `max(...)` saw a total short by the overridden count, so a *pièce* submitted after an override would not raise the watermark and the **new** pièce would report as lost. |
| 4 | MED | `backfill_submitted_pieces` — documented re-runnable — would have set the watermark below the true count on any store holding an override, wedging those matters. |
| 5 | MED | The detail's structured fields were forgeable from client data (a *matter* name carrying `reason=`), yielding a fake sentence that counts and reads as the real one. Fixed at the source and guarded at the renderer. |
| 6 | MED | An absent entry (400) was distinguishable from a walled one (403): an id probe could map what exists behind another wall. One answer, one body. |
| 7 | LOW | `_append_pin_entry` rendered `reason=` on a pin **removal**, which is not an override and owes no reason — the trail read as an override whose author declined to say why. |
| 8 | LOW | `register()`'s docstring still said "OPEN and RESOLVED entries" after a third state existed. |

### Considered and not done

- **A minimum meaningful length on the reason** (the PRD's assumption A-14). Twelve identical
  characters satisfy any length floor, so it would make the refusal about typing rather than about
  deciding — and a user who learns the field wants volume writes volume. FR-25's own counter-metric
  (SM-C2) watches reason quality as a trend, which is the honest instrument. Recorded in the
  validator's docstring so the next reader knows it was weighed, not missed.
- **Reversing an override.** AD-37 describes a *worklist* line offering it; the worklist is derived
  from freshness assessments and has no kind for this. The half that holds today is asserted — a
  retry never silently resolves what an override closed — and the reversal is named as Story 5.7's,
  where reversible drawer actions are the subject.
- **Conflating `pin_override` into `CLASS_OVERRIDE`.** It would discharge FR-25's class by breaking
  FR-24's requirement that every *pin* be recorded as a pin. Two axes, deliberately.

### Gate

ruff clean · import-linter 3 kept / 0 broken · **95** structural checks (92 → 95) · fitness frame
green, 6 asserted / 7 pending · **1 903 passed, 12 skipped** · client `typecheck` + `build` clean.

## Re-review by the adversarial fleet (retro action B2)

**Reviewed:** 2026-08-17 · **Method:** 4 named lenses over the whole diff, then **2 independent
skeptics per candidate defect** — one attacking the mechanism, one the consequence, both instructed
to REFUTE and to default to refuted when uncertain.

**Why this happened at all.** The Epic-5 retrospective (`epic-5-retro-2026-08-14.md`) opened B2
because 5.6, 5.7 and 5.8 were reviewed **inline by one reader** while every other story of the epic
faced the fleet, and because these three are the stories that produce what leaves the building. The
retro's prediction was explicit and it held: the inline pass on 5.7 had confirmed *one* finding; the
fleet raised twenty-four candidates on it.

### Coverage (retro action A2 — a silent lens is not a clean bill of health)

| | Planned | Ran | Returned | Lost |
|---|---|---|---|---|
| Lenses (× 3 stories) | 12 | 12 | 12 | **0** |
| Skeptics (2 per HIGH defect) | 20 | 20 | 20 | **0** |

Candidates: **64** (5.6: 19 · 5.7: 24 · 5.8: 21), deduplicated to **10 distinct HIGH defects**.
Adjudicated **5 confirmed / 5 refuted** — the split of a pass that is working rather than one that
is agreeing with itself. Nothing was left unadjudicated.

**What the fleet did NOT reach, stated rather than implied:** the client is TypeScript with no test
runner in this repository, so `ExhaustivePanel`'s seal and the drawer's act are covered by
`npm run typecheck` / `build` and by the server-side sentence they render — read by the lenses,
not executed by them.

### Confirmed and fixed here

| # | Severity | Finding | Fix |
|---|---|---|---|
| H1 | HIGH | The exhaustive-search **proof** and the client seal named `open_register_entries` and stopped. One override turned an amber, qualified absence into an **unqualified green** — nothing about the corpus had changed. A skeptic reproduced it live: *« Le registre liste 0 pièce(s) au registre »* over a document nobody had read. | The face names the overridden count; the seal is qualified by it; the panel's equation carries SM-3's third term, which it had been printing without (`2 recherché = 1 indexé + 0 au registre`). |
| H1b | HIGH | The same override erased the AD-38 clause *« dont N au contenu inconnu »*: `unknown_cardinality_entries` counted only `open` entries, so overriding an unopened **archive** took it to zero. The absence claim then rested on a hole of unknown size and said nothing about it. | The subset is taken over **both** register terms. An override is a decision about a document; it does not make its contents known. |
| H2 | HIGH | A **re-import silently reversed an override**: `save` merged the entry back as `open` — no audit entry, no conditional commit, nothing on any surface. | `_write_failure` never touches an `overridden` entry. Only a person undoes a person's decision. |

**The line this story wrote, and where it was placed.** 5.6's own review section says, under *Considered
and not done*: *"the half that holds today is asserted — a retry never silently resolves what an
override closed"*. The guard went on `retry_failure`. `save` is the other route into the same table
and it was not asked. The reviewer had the right question and walked one of the two doors.

### Refuted

Three candidates on this story did not survive: the reason validator's length floor (weighed and
declined in the original review, with its argument intact), the ground taxonomy's completeness, and
a claimed race between the override and the watermark (the watermark is recomputed inside the same
transaction).

### Gate (all three re-reviews, one run)

ruff clean · import-linter 3 kept / 0 broken · **105** structural checks (104 → 105, the new one is
story 5.8's) · fitness frame green, 6 asserted / 7 pending · **2 141 passed, 12 skipped**
(2 113 → 2 141) · client `typecheck` + `build` clean. Every one of the five fixes carries a
regression **proven to fail against the pre-fix code**, by reverting the fix and re-running.

## Change Log

| Date | Version | Description |
|---|---|---|
| 2026-08-13 | 1.0 | Story 5.6 implemented: the override becomes a named property with a ground, one validator for the mandatory reason, the reason verbatim in the record, AD-37's `open → overridden` register transition, overrides countable and filterable separately, three structural checks, and the denominator's third term. |
