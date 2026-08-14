---
baseline_commit: b7d27a7
---

# Story 5.8: The validation act

**Epic 5 — the record a *bâtonnier* can read** · **FR-45**, FR-44, FR-24 · Status: **done**

## Story

As a supervising partner,
I want *"a human read this"* to be a real per-*pièce* gesture that records whether the document was
actually opened, with no undetectable bulk acceptance,
So that a click-through cannot masquerade as review — the failure the whole trust architecture must
not end in.

---

## Scope note — the last gesture, and the one that can undo twelve stories

Epic 5 built a record that cannot be forged (5.5), cannot be silently truncated (5.5/AD-35), prices
its exceptions in written reasons (5.6) and leaves the building in a form a court can read without
the system (5.7). **All of it is worth nothing if the final gesture can be produced by a
click-through.** v1 sold *"this document was read by a human"* as one of its four claims and never
built it: the claim rested on a phrase — *validation act* — that no requirement created. FR-45
creates it.

The design problem is **not** how to make the gesture easy. It is **how to make the record of it
true when it was easy.** Bulk acceptance is therefore *permitted* and *made impossible to hide*
(`addendum.md` §180): a 1 700-row grid grows a select-all because every grid does, forbidding it
produces a workaround rather than compliance, and leaving it unspecified produces 1 400 *pièces*
marked *read by a human* in four minutes — documented consent that was never given.

### What this story found before it started

**FR-45's load-bearing field is not recorded anywhere readable.** *"Whether the pièce was opened in
the viewer before the act"* is the fact that distinguishes reading from clicking. Story 3.5 does
record the open — `audit_piece_open` — but it records it as **`f"piece={piece_id}"` inside an
application-encrypted audit detail string**. Answering *"did this lawyer open this pièce"* would
mean loading every `retrieval`-class entry of the *matter*, decrypting each, and string-parsing a
`piece=` fragment. **This is the exact defect 5.7 fixed for the priced statement**, and the rule it
established stands: *a record whose reading depends on parsing prose is not a record.* Migration
0036 gives the open its own append-only ledger, written in the same transaction as its audit entry.

**The two FR-24 classes are the two pending export sections are two verbs.** `PENDING_CLASSES`
already declares `validation_act` and `value_accepted` as owned by this story, and
`audit_catalogue_is_complete` leg 3 will fail the build if either is still declared pending once a
verb writes it. `matter_record.PENDING_SECTIONS` declares §7 and the accepted half of §8, owned by
this story. They are the same two facts seen from the record and from the document, and this story
discharges all four together or none.

**The 5.7 tripwires fire on contact.** `drawer._pending()` raises `AssertionError` the moment the
validation verb is catalogued — deliberate, so the disabled control cannot survive its own act
shipping. `matter_export.a_pending_section_is_not_a_zero` fails when `PENDING_SECTIONS` empties.
Both are handled here, and the second is **strengthened rather than deleted** (AC-10).

### What this story does not own

- **Atomicity of the act with its record** under a read-only audit store — Story 5.9 (FR-53). This
  story writes ledger and entry in one transaction, which is the established pattern, but the
  read-only-store assertion is 5.9's.
- **The retained-set export's *validated by whom* column** — Story 6.1 (FR-46).
- **SM-C2 in the content-free projection** — Story 6.2 (FR-32).
- **The viewer's and the table's layout.** Both surfaces exist; this story adds a control to them.

---

## Acceptance Criteria

**AC-1 — the sentence is the act, on three surfaces.** A *validation act* is available from the
triage table, the viewer and the *audit drawer*, and the control's own text is the full assertion
*« J'ai lu cette pièce et j'accepte l'appréciation de l'outil. »*, naming the *ranking version* it
accepts (AD-23). The same act, the same sentence, the same record from all three (FR-45).

**AC-2 — one entry, carrying the eight facts.** A *validation act* produces one *audit record*
entry carrying actor, timestamp, sequence number, *matter*, *pièce*, *ranking version*, the values
accepted, and **whether the *pièce* was opened in the viewer before the act** (FR-45, FR-44).

**AC-3 — the opened fact is read, never asserted.** Whether the *pièce* was opened is resolved from
the **open ledger**, for **the acting actor**, from opens **strictly before the act** — never
supplied by the caller, never a literal at a call site, and never inherited from another lawyer's
open. It is stored as the **timestamp of that open**, not a boolean: *"opened"* alone is true of an
open six months and three rankings ago (FR-45, FR-44).

**AC-4 — "accepted as-is" exists only where a validation act occurred.** No default, no elapsed
time, no scroll position, no screen visit produces it. Asserted by test: a *matter* left open for an
arbitrary period, scrolled end to end, with every read surface exercised, yields **zero** accepted
entries (FR-45).

**AC-5 — bulk is permitted and never undetectable.** A bulk *validation act* over a selected set
(a) requires an explicit confirmation naming the count; (b) produces one entry **per *pièce***, each
marked `bulk`, each carrying the size of the set and a **shared batch identifier**; (c) records for
each *pièce* that it was **not** opened in the viewer **unless it was** — resolved per *pièce*, never
blanket-stamped over the batch; and (d) is counted separately in the export (FR-45).

**AC-6 — the reversal is a new entry.** A *validation act* is reversible and the reversal is an
append, never an erasure. Both remain readable, and the in-force state is the max-`seq` view over
the append-only ledger — the *pin* precedent (FR-45, AD-7).

**AC-7 — the acceptance names the version it accepted.** What was accepted is a **named ranking
version's** assessment. After a re-rank, the surface and the export state which version the
acceptance referred to and which is current — nothing is erased and nothing is invalidated
(AD-23).

**AC-8 — the export's two sections become real.** §7 (*les actes de validation*) and the accepted
half of §8 print **counts**, split by register: validated-after-reading versus accepted-from-the-
list, individually versus in a batch, plus withdrawals. The two registers are never pooled. A **0**
in §7 is now a finding about the firm, which it was not yesterday (FR-26, FR-45, §13 q.5).

**AC-9 — the drawer's disabled row is retired.** `PENDING_ACTS` loses its entry and `OFFERED_ACTS`
gains the act with its reversal sentence; `propose()` answers for the validation verb, so the panel
that says where the entry lands and the writer that files it there still cannot disagree (FR-26).

**AC-10 — three structural checks, and one strengthened.** `only_the_validation_act_accepts` (the
`value_accepted` verb has exactly one writer, and that writer is the validation use case);
`the_opened_fact_is_never_a_literal` (no call site hands the provenance a constant — the shape of
FR-45(c)'s blanket stamp); `acceptance_is_never_manufactured` (no runtime symbol or French string by
which dwell, scroll or a screen visit could mint one, and **one home** for the assertion sentence —
a second spelling is a second control whose words are not the ones the record will carry). And
`a_pending_section_is_not_a_zero` gains a
**biconditional** leg — a section is declared pending **iff** its act is uncatalogued — so 5.7's
one-shot tripwire becomes a permanent invariant instead of a check that fails on success.

---

## Tasks / Subtasks

- [x] **T1 — the catalogue (AC-2, AC-9).** Three verbs on `CHAIN_MATTER`: `validate_piece` and
      `validation_withdrawn` on `CLASS_VALIDATION`, `values_accepted` on `CLASS_VALUE_ACCEPTED`.
      Remove both classes from `PENDING_CLASSES`. French in `proposed_entry.ACT_FR` for the two
      offered gestures only.
- [x] **T2 — the open ledger (AC-3).** Migration 0036: `piece_open`, append-only, actor
      application-encrypted (AD-31 — never a SQL predicate; the actor is matched in the
      application over a per-*pièce* bounded set). `audit_piece_open` writes the row and its audit
      entry in one transaction. Backfill is **not** attempted: pre-0036 opens live only in encrypted
      prose, and a validation act over one of them records *not opened*, which is the honest answer
      — stated in the docstring, not silently.
- [x] **T3 — the validation ledger (AC-2, AC-6, AC-7).** Migration 0036: `validation_act` —
      per-*pièce* monotonic `seq` (AD-49), `action` ∈ {validated, withdrawn}, `ranking_version_id`,
      `opened_at` nullable, `batch_id`/`batch_size` nullable, the accepted values as categorical
      columns, actor encrypted. Tenant-qualified `sha256` id, FK to `matter_scope`, no cascade
      (AD-7).
- [x] **T4 — the domain (AC-1..AC-7).** `core/domain/validation.py`: the assertion sentence and its
      French, `Provenance` (read / from-the-list, derived from `opened_at`), `AcceptedValues`,
      `ValidationEntry`, the in-force view over an append-only sequence, and the staleness
      comparison against a current version. Pure core, no clock, no store.
- [x] **T5 — the use case (AC-2..AC-6).** One owning use case per transition (AD-37): validate
      (single and batch) and withdraw, each a conditional commit under a row lock, each atomic with
      its entries. The provenance is resolved **inside** the use case from the open ledger, per
      *pièce*, for the acting actor, strictly before the act.
- [x] **T6 — the export (AC-8).** Real §7 and §8 sections in `matter_record.py`; retire both
      `PENDING_SECTIONS` entries; the counts computed from the ledger and split by register, never
      pooled and never derived from the audit entries' prose.
- [x] **T7 — the drawer (AC-9).** `OFFERED_ACTS` gains the act and its reversal sentence;
      `PENDING_ACTS` empties; `_pending()`'s assertion is satisfied by removal, not by weakening.
      The drawer carries the provenance the act *would* record.
- [x] **T8 — the API and the client (AC-1, AC-5).** Endpoints for the act, the batch and the
      withdrawal; the batch refuses without an explicit count that matches the selection. React:
      the control with its full sentence as accessible name, the provenance line as
      `aria-describedby`, the bulk confirmation with the count-and-split and a non-focused
      confirming verb, and the badge's four facts.
- [x] **T9 — the checks (AC-10).** `apx/checks/validation.py` with three checks; strengthen
      `a_pending_section_is_not_a_zero`. Lockstep across `registry.py`, `manifest.py` and the
      README `<!-- structural-properties -->` block. **97 → 100.**
- [x] **T10 — the tests (AC-4, AC-5).** The FR-45 assertion test (a matter scrolled end to end
      yields zero acceptances); the bulk split test (a batch containing one opened *pièce* records
      that one as opened); the reversal test; the staleness test; the API non-disclosure test; and
      the export's two real sections.

---

## Dev Notes

### Where the material already is

| Need | Lives at | Note |
|---|---|---|
| the open, as an audited act | `store.audit_piece_open` | **prose only** — the fix is T2 |
| the values the tool asserts | `core/domain/triage_table.TriageRow` | side, band, confidence, label |
| the current ranking version | `store.read_ranking` / `list_ranking_versions` | AD-23 |
| the append-only ledger idiom | `models.PinEntry`, `models.TaxonomyLabelEntry` | seq, encrypted actor, sha256 id |
| the all-entries read idiom | `store.read_pin_log` | **all** entries, not the in-force view |
| the pending machinery | `audit.PENDING_CLASSES`, `matter_record.PENDING_SECTIONS`, `drawer.PENDING_ACTS` | all three retire here |
| the UX contract | `EXPERIENCE-EPIC5-VALIDATION.md` + `mockups/epic-5-validation-act.html` | committed `b7d27a7` |

### Constraints

- **AD-31.** The actor stays application-encrypted and is **never a SQL predicate**. The
  *"did you open it"* question is answered by loading the *pièce*'s opens and comparing in the
  application — bounded, because opens per *pièce* are human gestures behind a session. No blind
  index is introduced; a digest over the tenant's user list adds no protection an attacker holding
  the dump does not already have from `user_account.display_name`.
- **AD-7 / AD-39.** Nothing is overwritten and nothing is a stored membership. The in-force
  validation is a **view** over the ledger, exactly as the pin is.
- **AD-23.** No unqualified reference to a ranked figure, on any surface or in the document.
- **AD-37.** One owning use case per transition; every transition a conditional commit.
- **The project's recurring defect — a nearly-right referent.** Four live in this story, each
  failing toward the flattering answer: *opened by whom* (any actor vs. the acting one), *opened
  when* (ever vs. strictly before the act), *opened which* (blanket over a batch vs. per *pièce*),
  and *accepted what* (a timeless verdict vs. a named version's assessment). Each has an AC and a
  test.

---

## Dev Agent Record

### Completion Notes

**The two FR-24 classes turned out to be the two export sections turned out to be two verbs.** That
was not the plan; it fell out of taking FR-24 §611 literally. It enumerates two recorded things —
*"who validated what and when"* and *"which values were modified versus accepted as-is"* — and
`PENDING_CLASSES` had been carrying both since Story 5.5 with this story's number on them. So the
act writes **two entries in one transaction**: `validate_piece` (class `validation_act`) and
`values_accepted` (class `value_accepted`). One entry folding both would have made the acceptance a
property of the gesture rather than a fact with its own provenance — and the acceptance is the one
FR-24 §614 constrains. §7 and §8 of the export now count two different things because they *are*
two different things.

**FR-45's load-bearing fact was recorded only as prose.** `audit_piece_open` has faithfully recorded
every viewer open since Story 3.5 — as `piece=<id>` inside an application-encrypted audit detail.
Answering *"did this lawyer open this pièce"* meant decrypting every `retrieval`-class entry of the
*matter* and string-parsing a fragment. Migration 0036 gives the open its own append-only ledger,
written in the same transaction as the unchanged audit entry. **No backfill**, stated in three
places: pre-0036 opens exist only as encrypted prose, and reconstructing them would manufacture rows
indistinguishable from ones the ledger recorded itself, out of a detail format that was never a
contract. A validation over such a *pièce* records *not opened*, which is the honest answer from
what is readable.

**`opened_at` is a timestamp, not a boolean, and that is the design.** *"Opened"* alone is equally
true of an open six months and three rankings before the act. The flag is derived
(`Provenance.of`), and `Provenance` has **no constructor taking a boolean** — the only way to obtain
one is from a timestamp, so no call site can assert a provenance it did not read.

**Four nearly-right referents, each with a test.** *Opened by whom* (another lawyer's open is not
this lawyer's reading — `test_the_opened_fact_is_this_actors_and_never_another_lawyers`); *opened
when* (strictly before the act — `test_an_open_after_the_act_does_not_make_it_read`); *opened which*
(per *pièce*, never blanket over a batch — `test_a_batch_records_each_piece_s_own_provenance…`); and
*accepted what* (a named version's assessment — `test_a_re_rank_makes_the_acceptance_stale…`).

**The bulk path is permitted and made impossible to hide.** The confirmation states the count **and
the split**; the confirming verb names the count and is not the initially-focused control. Each
*pièce* gets its own entry with the shared batch identifier, the size, and **its own** opened-fact.

**The 5.7 tripwires fired on contact and were answered by removal, never by weakening.**
`drawer._pending()` raises the moment a listed verb is catalogued — so the disabled control could
not survive its own act shipping. `a_pending_section_is_not_a_zero`'s first leg required *at least
one* pending section, which was true until this story built both and would then have failed **on
success**; it was replaced by the **biconditional** — a section is declared pending exactly when its
act is uncatalogued — which fails in both directions and stays reachable forever.

### Found by the review, after the tests were green

Three defects, all in code this story wrote, all failing toward the flattering answer:

1. **The batch identifier was not unique per gesture.** It hashed (tenant, matter, actor, version,
   sorted *pièces*), so the same selection validated twice produced **one** identifier — and §13's
   question 5, *one gesture over how many*, would have answered "one batch" where a lawyer made two
   separate decisions. The moment of the act is now in the hash.
2. **`never_validated` was a subtraction across two different populations.** The numerator counted
   validations from a version-independent ledger; the denominator was the *current* ranked set. It
   could go negative, and `max(0, …)` would have rendered that as a flattering zero. It is a **set
   difference** now.
3. **`last_open_by` was unscoped**, resting on "the caller has already checked" — a guarantee that
   survives exactly as long as the one call site holding it. It checks `matter_is_held` itself.
4. **Neither new encrypted column was in the key-rotation registry** (`ENCRYPTED_COLUMNS`) — found
   by Story 1.8's `test_rekey_covers_every_encrypted_column`, which asserts the registry against the
   live model metadata. A rotation would have left `piece_open.actor` and `validation_act.actor`
   encrypted under the retired key, and the failure mode is the nastiest in this story: an
   unreadable `piece_open.actor` makes every later validation act record **not opened** — the
   flattering answer, arrived at silently, with nothing anywhere saying why. This is the check
   working exactly as designed, three stories after it was written.

### Known, named, and not fixed here

- **An actor is matched by display name.** `_opens_before` decrypts and compares `actor` strings, so
  two users sharing a display name would share an opened-fact. This is the product's existing
  identity model — the *audit record* attributes every entry the same way — and changing it is a
  cross-cutting decision, not this story's.
- **A concurrent re-rank between the table read and the commit** records the version the lawyer was
  looking at. That is deliberate and documented: what the record must carry is what she accepted.
- **`validate_pieces` reads the whole triage table** to obtain the derived `side`. That is the
  right source — AD-39 and `triage_sets_one_derivation` allow exactly one derivation path — but it
  couples the act to the table's FR-58 assertion, which is why two test fixtures had to grow a real
  corpus. In production the failing direction (corpus smaller than its own ranking) cannot arise.
- **A batch builds one `IN (…)` clause over its selection.** At the design target — a select-all
  over 1 700 rows — that is one large predicate and 1 700 ledger rows plus 3 400 audit entries in a
  single transaction. Correct, and deliberately not chunked: the whole point of FR-45(b) is that the
  batch is **one gesture**, and splitting the commit would let half of it land. Worth measuring
  against the 2.13 timed run before a firm ever does it.
- **Atomicity under a read-only audit store** is Story 5.9's (FR-53).

### Deviation

The **adversarial review was conducted inline**, as in Stories 5.6 and 5.7: multi-agent
orchestration is disabled in this session. The three findings above came from a manual pass over the
diff hunting the project's recurring defect shape.

## File List

**New:** `apx/core/domain/validation.py` · `apx/checks/validation.py` ·
`apx/adapters/store_postgres/migrations/versions/0036_validation_act.py` ·
`tests/domain/test_validation.py` · `tests/api/test_validation_api.py` ·
`tests/checks/test_validation_checks.py` · `tests/_fixtures/validation_violations/**` ·
`_bmad-output/planning-artifacts/ux-designs/…/EXPERIENCE-EPIC5-VALIDATION.md` ·
`…/mockups/epic-5-validation-act.html`

**Modified:** `apx/core/domain/audit.py` · `apx/core/domain/matter_record.py` ·
`apx/core/domain/proposed_entry.py` · `apx/core/app/read/drawer.py` ·
`apx/core/ports/justification.py` · `apx/adapters/store_postgres/models.py` ·
`apx/adapters/store_postgres/store.py` · `apx/api/app.py` · `apx/checks/registry.py` ·
`apx/checks/manifest.py` · `apx/checks/matter_export.py` · `apx/checks/encryption.py` ·
`apx/checks/user_actions.py` · `apx/web/src/api.ts` · `apx/web/src/drawer.tsx` ·
`apx/web/src/tokens.css` · `README.md` · `…/DESIGN.md` · four test files carrying the tripwires

## Change Log

| Date | Change |
|---|---|
| 2026-08-13 | Story created; UX gate discharged first (`b7d27a7`). |
| 2026-08-14 | Implemented; 97 → 100 structural checks; three review findings fixed. |
