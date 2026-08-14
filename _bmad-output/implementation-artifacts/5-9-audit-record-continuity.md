---
baseline_commit: da27cc6
---

# Story 5.9: Audit record continuity

**Epic 5 — the record a *bâtonnier* can read** · **FR-53**, FR-52, FR-24 · AD-22, AD-35, AD-43, AD-46 · Status: **done**

## Story

As a *bâtonnier* holding only the exported record,
I want an action whose entry cannot be written to fail, and any gap in the record to be detectable,
So that the blessed backup restore cannot quietly truncate the audit trail and still pass its own check.

---

## Scope note — every story before this one proved the record cannot be *altered*; this one has to prove it cannot be *shortened*

Stories 5.5 through 5.8 built a record whose every link is recomputable: a chain per *(tenant, matter)*, a sequence
number from a locked head row, an append-only ledger the build refuses to let anyone edit. All of it answers one
question — *was any of this changed?* — and answers it well.

None of it answers the other question: **is this all of it?**

A truncation to an earlier *consistent* point produces a chain whose every link verifies. `verify_chains` holds no
expected length and no expected head; a five-entry chain cut to three returns `verified=True, broken_at=None`. That is
not a defect of the verifier — it is the shape of the problem. Proving a record complete needs a witness the record
does not contain, and this build already has one: the head journal (AD-35), append-only, on a volume the dump does not
cover, written on every chain advance since Story 1.11.

**It records the chain value on every advance, and nothing has ever read it back.** `Reconciliation` compares sequence
numbers; `HeadEntry.chain` is written by four call sites and read by none. So the one defence the architecture blesses
against a forged restore — the only currency that exists outside the restorable store — is being collected and thrown
away.

### What this story found before it started

- **The witness is written and never read.** `HeadEntry.chain` (`head_journal.py:63`) is journalled on every head
  advance; `HeadJournal.reconcile()` takes `live_seq` only and `Reconciliation` has no chain field
  (`head_journal.py:137-143`, `store.py:2671-2684`). A backup that rewrites the record and re-chains it **to the same
  length** passes `_chain_verifies` (an unkeyed SHA-256 recomputed over the forger's own rows), passes
  `_reconcile_allocator` (head and entries agree, because the forger updated both — both inside the restorable store),
  and passes reconciliation (the sequence number never moved). Story 5.5 already recorded that two skeptics reproduced
  this forgery and that the anchor cross-check it was about to add would have closed nothing; it named the head journal
  as the answer. The data has been on disk ever since.
- **The export carries no entries at all.** `MatterRecord` has a cover, a denominator, the case theory, the line
  history, the pins, the sampling runs, the overrides, the validations and the breakdown — and not one audit entry, no
  chain value, no anchor, no content version. A reader holding the document receives *the producer's assertion that it
  verified* and nothing to check it with.
- **`recomputable_from_this_document` is a false claim printed on a court document.** It is set from `own.anchored`,
  which is true iff the tenant's `audit_chain_head` row **in the database** carried a non-empty anchor
  (`store.py:1957 ← :3464 ← audit.py:525 ← store.py:2914`). It is a fact about the server's own storage, printed under
  a name that asserts a property of the bytes in the reader's hands — and it is `True` on a document from which
  literally nothing can be recomputed. The test that guards it asserts the boolean and never attempts a recomputation
  (`tests/adapters/test_matter_record_export.py:190-199`); so does the self-containment probe, which copies the flag
  into its output (`tests/probe/test_export_self_contained.py:114-117`).
- **Half the record advances the head with no witness.** The import worker builds `SqlStore(make_session_factory())`
  with no journal (`queue/__init__.py:195`), and so do `manage provision` / `manage create-user`
  (`manage.py:194, 206`). Every act those write advances the live head with nothing recorded outside the store, so a
  truncation back to the last journalled head is undetectable — and `manage._open_store()` opens the journal with
  `required=False`, which means **the CLI restore, the one blessed destructive operation, performs no continuity check
  at all when the variable is unset, and says nothing about having skipped it**.
- **Nothing has ever failed an audit write.** A ripgrep for read-only across `tests/` returns no audit-store hit. Every
  test that says *atomic* asserts the happy path — the entry is there beside the write — which is the converse
  proposition and would pass on an implementation that committed the act and swallowed the audit failure. Stories 5.5
  and 5.8 both deferred the assertion here, by name.
- **No structural check looks at a transaction boundary.** The three audit checks cover the catalogue, the allocator and
  append-onlyness. `scope_mutations_are_audited` is lexical and says so in its own source; `only_the_validation_act_
  accepts` checks same-*function* co-occurrence. Same-function and same-file are strictly weaker than same-transaction,
  and every one of them is satisfiable by a two-step commit.
- **`journal_degraded` is an in-memory flag that clears on the next deploy.** A head we could not record means a later
  truncation to that point is undetectable — an alarm that must survive a restart, and today does not. That is a silent
  repair of exactly the condition AC3 says must never be silently repaired.

### What this story does not own

- **The rendered document.** The export is JSON and the client shows a toast; there is no HTML/PDF artefact. *On the
  export's face* is discharged here on the **cover** (the data every renderer will carry) and on the client's export
  panel. A paginated, printable *dossier* is Epic 6's (FR-46).
- **`upgrade.sh`, the pre-migration `pg_dump` and the recorded head before a migration** — AD-46's other half, deferred
  by Story 1.11 to deploy and still unbuilt. A migration is the second operation that can destroy the record; this
  story names the boundary rather than letting AC3 read as discharged over it.
- **The AD-49 monotonic counter.** A user-settable clock on an air-gapped machine can make timestamps go backwards,
  which reads as a tamper signal. Named by Story 1.11, still a later structural story.
- **AD-44's partition-and-seal.** Re-checked here rather than inherited: Story 5.8 added the first writer whose
  contention profile 5.5's justification did not cover (a batch over 1 700 *pièces*).
- **The deployment volume for `APX_HEAD_JOURNAL`.** *A volume the dump does not cover* is a README sentence, not a
  composed fact. Ops/Epic 6.

---

## Acceptance Criteria

**AC-1 — an act whose entry cannot be written does not happen, asserted by failing the write.** With the audit store
made unwritable mid-action, each of the six acts FR-53 names — moving **the line**, committing an *override*, completing
a *sampling run*, a *validation act*, granting a scope, changing configuration — raises, **and leaves no business row
behind**. The negative half is the assertion: the ledger row, the placement, the verdict, the scope grant and the
configuration value must each be absent afterwards, not merely unaccompanied (FR-53, AD-22).

**AC-2 — the refusal is a refusal, never an unaudited mode, and a lock wait is not the refusal.** Where the audit store
cannot be written at all, an affected write answers **503 with a sentence naming why**, and read paths keep answering
200. Contention — a lock wait on the head row, a concurrent `(tenant, chain_scope, seq)` collision — is **not** that
state: it retries and then fails as a conflict, and never puts the product into refusal (FR-53, AD-22's named trap).

**AC-3 — the verdict names what broke.** A chain's verdict distinguishes a **gap** (the sequence is not contiguous), a
**broken link** (a recomputed value does not match — a rewrite or a reorder), and an **unreadable field** (a value that
cannot be authenticated), instead of collapsing five different findings into one boolean and one integer. A
*bâtonnier* told *rupture au n° 7* must be able to tell which of those it was (FR-53).

**AC-4 — the document carries what a reader needs to recompute it.** The FULL-tier export carries, per entry of every
chain it holds: the chain scope, the sequence number, the timestamp **in the exact rendering the chain was taken over**,
the actor, the act, the detail, the content version, the application and payload-schema versions, and the chain value —
plus each chain's **anchor**. A numbers-only export carries none of it and **says so on its face**, in the lawyer's
language: what it holds is the producer's word, and the reader is told that is what it is (FR-53, FR-26).

**AC-5 — `recomputable_from_this_document` is derived from this document.** The flag is computed at assembly from the
document's own contents — a chain is recomputable exactly when the document carries its entries **and** its anchor — and
from nothing in the database. Asserted by a test that recomputes the chain in a process with no store, and by the
self-containment probe, which stops copying the flag and starts recomputing the links (FR-53).

**AC-6 — the continuity check runs on the export, and its result is on the export's face.** A pure-core reader takes the
document alone and returns, per chain: the recomputed verdict, its cause, and the comparison against the **journalled
head witness** the document carries. Its result appears on the cover, in French, and a disagreement between the
producer's printed verdict and the reader's recomputation is itself a finding (FR-53).

**AC-7 — a tail truncation is detectable from the export alone.** The document carries, per chain, the head recorded
**outside the restorable store** (scope, sequence, chain value, when it was recorded, application and schema versions).
A document whose last entry falls **behind** that witness is a truncation, named with the number of missing acts; a
document whose last entry runs **ahead** of it is an **unwitnessed tail**, named as such and never counted as clean
(FR-53, AD-35).

**AC-8 — the witness is compared, not counted.** Reconciliation compares the **chain value** the journal recorded at the
highest witnessed sequence against the value the live record carries at that sequence. A record rewritten and re-chained
to the same length is a **fork** — a distinct finding from a truncation, recorded as a persistent marker, named on the
export, and cleared only by an audited *override* with a reason (FR-53, AD-35).

**AC-9 — every store that writes is journalled, and the restore fails closed without the journal.** No runtime
construction of the store omits the head journal — the API, the import worker and the CLI all pass it, asserted by a
structural check — and the CLI opens it **required**, so a restore without the outside witness refuses rather than
silently skipping the continuity check. A head the journal could not record is **persisted**, survives a restart, and is
named on the disaster-recovery status (FR-53, FR-52, AD-35).

**AC-10 — the harness carries the properties, in lockstep.** Every new structural property is registered in the three
sites (`registry`, `manifest`, the README block), the offline fitness frame's audit stage widens to the claim this story
actually ships instead of carrying a disclaimer naming an unshipped story, and the count moves in step (AD-33, FR-56).

---

## Tasks / Subtasks

- [x] **T1 — the verifier names its cause, and gains a head comparison (AC-3, AC-7).** `ChainVerdict.cause`; a pure
      `HeadWitness` / `compare_to_witness` in the Domain producing *current* / *truncated(n)* / *unwitnessed(n)*. No
      store, no clock. Update `store`, `fitness/driver.py` and the React client to the widened verdict.
- [x] **T2 — migration 0037 (AC-8, AC-9).** `truncation_marker.kind` + `.forks` (the marker generalises from *a
      truncation* to *a discontinuity*, keeping one acknowledge-by-override path), and `journal_gap` — the heads the
      journal could not record, so the alarm survives a restart.
- [x] **T3 — read the witness (AC-8).** `Reconciliation` gains `forked`, `witnessed_seq` and both chain values;
      `reconcile_heads` compares the value at the highest witnessed sequence; a fork records a marker of kind `forked`.
      `_seed_journal_from_backup` validates the tail's types (a `"seq": "9999"` string currently poisons an append-only
      file and bricks every later boot) and never seeds a scope the live journal already witnesses.
- [x] **T4 — one store factory, journalled everywhere (AC-9).** API, worker and `manage` build the store through one
      function; `manage` opens the journal `required=True`; a structural check refuses an unjournalled construction in
      the runtime. Persist the journal gap; surface it on the DR status.
- [x] **T5 — the document carries the trail (AC-4, AC-5).** `ChainEntryLine`, the anchor and the head witness on the
      cover; FULL tier only, with the numbers-only sentence; `recomputable_from_this_document` re-derived in `assemble`
      from the document's own contents.
- [x] **T6 — the continuity check runs on the document (AC-6, AC-7).** `read_continuity(record)` in pure core; the
      cover carries the producer's verdict, the reader recomputes, and the disagreement is a finding. API + client.
- [x] **T7 — the refusal (AC-1, AC-2).** `AuditUnwritable`, a dialect-mapped lock-wait predicate, the 503 with its
      sentence, reads untouched.
- [x] **T8 — fault injection (AC-1).** A read-only-audit-store harness (the database refusing, not a Python mock) and
      the six acts, each asserting the business row is **absent** afterwards.
- [x] **T9 — structural checks + the three-site lockstep + the fitness frame (AC-10).**
- [x] **T10 — tests** — domain, adapters, API, checks, and the probe reader that recomputes instead of copying.

---

## Dev Notes

### Where the material already is

| Need | Lives at | Note |
|---|---|---|
| The chained recipe and the verifier | `apx/core/domain/audit.py:437-551` | pure core, versioned, one recipe per content version |
| The head journal | `apx/core/domain/head_journal.py` | append-only, per chain, `HeadEntry.chain` already written |
| The head write hook | `store.py:927-971` | `before_flush` captures, `after_commit` writes — post-commit by design |
| Reconciliation + the marker | `store.py:2644-2762` | seq only; the marker is per tenant and names every fallen chain |
| Restore-time verification | `store.py:2853-2867`, `:2919-2963` | inside the transaction; a refusal rolls back |
| The export assembly | `store.py:1920-2050` | where the cover is built |
| The document | `apx/core/domain/matter_record.py` | pure core, no clock, no store |
| The self-containment probe | `tests/probe/test_export_self_contained.py` | the one reader that runs with no store |
| The check lockstep | `apx/checks/registry.py`, `manifest.py`, `README.md` | 100 checks today; `manifest_matches_readme` compares the first five cells |

### Constraints

- **AD-22** — an entry is atomic with its act, and *a lock timeout or write contention is not "cannot be written at
  all"*. The escape the AD forbids is proceeding **without** the entry; refusing loudly is not that escape, but a
  contention must not be classified as the unwritable state or ordinary head-row queueing becomes a product-wide
  refusal — the inversion Story 5.5 introduced the lock to prevent.
- **AD-35** — the head is recorded outside the restorable store on every advance, and *currency against an attacker with
  database write access comes from the journal; nothing inside the store can supply it*. Any check this story adds must
  compare against the journal, never against another in-store value.
- **AD-43** — chains per *(tenant, matter)* plus one *tenant* chain, verified independently. The tenant chain is **not**
  recomputable from a scoped export and the cover must keep saying so.
- **AD-22 / AD-33** — a gap is never repaired, and a property with no check is not a property.
- **The boot sequencing trap** — `_lifespan` reconciles and then calls `record_current_heads()`, which appends the live
  head for every scope. Any fork check must read the journal's pre-existing witness **before** that advance, or it
  compares a forged value against a copy of itself.
- **The timestamp trap** — the chain is taken over `_audit_ts` (UTC, tz-naive, forced microseconds); the export prints
  `isoformat()` off the raw column (`+00:00`). Whatever the document carries per entry must be **byte-identical** to
  what `chained_content` consumed, or a reader recomputing it concludes tampering.
- **Two authorities in one printed list** — `read_audit` merges the matter chain with tenant-chain entries naming the
  matter; `OverrideLine` carries `seq` without `chain_scope`, so two authorities' numbering is interleaved unlabelled.
  Every sequence number the document prints must name its chain.
- **Four different `seq` columns** already appear in the document (`LineHistoryLine`, `PinLine`, `ValidationLine`, and
  the audit `seq` on `OverrideLine`). The chain's sequence must be unmistakable, and none of the others reused.
- **`detail` carries client content** for some verbs (a search query, a mail subject). The trail is therefore FULL-tier,
  and numbers-only says what it cannot prove rather than printing a flag it cannot support.

---

## Dev Agent Record

### Completion Notes

**Every story before this one proved the record cannot be altered. This one had to prove it cannot be shortened —
and that needs a value the record does not contain.** A truncation to an earlier consistent point recomputes
perfectly: every link holds, the allocator agrees with its entries, the length never moved. No cleverer verifier
closes it, because the entries do not know how many of them there should be. Completeness is only decidable against a
witness recorded somewhere the thing being checked cannot reach.

**The witness had been collected since Story 1.11 and read by nobody.** `HeadEntry.chain` is journalled on every head
advance, on a volume the database dump does not cover. `Reconciliation` compared sequence numbers. So a backup that
rewrote the record and re-chained it **from the true anchor to the same length** passed `_chain_verifies`, passed
`_reconcile_allocator`, and passed reconciliation — three checks whose left and right sides were both inside the
restorable store. Story 5.5 recorded that two skeptics had reproduced exactly this and named the journal as the
answer; the data was on disk the whole time. Reading it back is the story.

**And the comparison is taken at every witnessed point, not at the newest one.** Comparing only the latest journalled
head made the detection survive exactly one reconciliation: the forged record goes on writing, each commit journals a
head at a higher sequence, and the next comparison then takes a line the forgery itself produced — which matches.
Found by the review. The disagreement is now looked for at the earliest witnessed point, where a rewrite of history
shows up and nothing written afterwards can paper over it. A **missing** value there counts too: the guard that
skipped it justified itself by saying a removed entry "is reported as a truncation", and the truncation test compares
the head row's sequence, which deleting from the middle leaves exactly where it was.

**`recomputable_from_this_document` was a false claim printed on a court document.** It asserted a property of the
bytes in the reader's hands and was computed from whether a row in the *server's own database* carried an anchor — so
it printed **true** on a numbers-only export that carried no audit entries whatsoever. The test guarding it read the
boolean; the self-containment probe copied it into its output and reported which scopes had claimed it. Neither ever
attempted a recomputation. The flag is now derived in `assemble()` from what the document turns out to hold, the
adapter cannot set it (a structural check refuses the keyword anywhere else), and both tests now recompute.

**So the document carries the trail.** §9: every entry of the chains this *matter*'s export may hold, with each field
the chained value is taken over — including the timestamp **in the rendering the chain was actually taken over**,
which is not the rendering the rest of the document prints. A reader handed `+00:00` and asked to recompute a value
taken over `.000000` concludes tampering. FULL tier only: an entry's `detail` carries, for some verbs, what a lawyer
typed. A numbers-only document says on its face that what it holds is the producer's word.

**The witness is read before the entries, and only for the *matter*'s own chain.** Read afterwards, an ordinary act
landing between the two reads puts the journal ahead of the document and the document reports itself *truncated* — an
accusation of tampering produced by nothing but concurrency. Taken first, the same race can only leave the record
running past its witness, which is *unwitnessed*: honest, unalarming, and true. The *tenant* chain's witness is not
carried at all — it would tell the holder of one scoped export how many acts the whole firm has performed, and buy
them nothing, since they hold a slice of that chain either way.

**Four states, and none of them is "fine by default".** *Current* is the only one that establishes completeness.
*Truncated* names its count. *Unwitnessed* — the record running past the journal, which is ordinary, since the head
is written after the commit — is never counted as clean either: those are precisely the acts a later truncation could
remove without a trace. *Forked* is the finding no length and no link can show.

**FR-53's first consequence had never been tested, in any story.** Every test that said *atomic* asserted the happy
path — the entry is there beside the write — which is the converse proposition and passes on an implementation that
commits the act and swallows the audit failure. The harness now makes the audit store read-only **in the database**
(SQLite triggers raising ABORT: no application code patched, no method wrapped), drives the six acts FR-53 names, and
asserts the **negative** half: the placement, the ledger row, the verdict, the grant and the configuration value must
be **absent** afterwards.

**The refusal is a refusal, and a lock wait is not it.** `_append_audit` now flushes inside the acting transaction, so
the failure surfaces where it can be classified rather than at commit as a generic error about a transaction holding
several writes. A non-contention failure on an audit statement raises `AuditUnwritable`, which one exception handler —
registered once, for every route — turns into a **503 with a sentence**, while reads go on answering. Contention is
deliberately excluded: AD-22 names that trap in as many words, and Story 5.5 introduced the head-row lock precisely so
two writers queue instead of one dying.

**One door onto the store.** AD-35's invariant is *the head is recorded outside the store on every append*, and it was
true of the API and false of everything else: the import worker wrote the bulk of the record with no journal, and
`manage restore` — the one blessed operation that can hard-delete the record — opened it `required=False` and printed
its ordinary success line when the variable was unset. All three now build the store through `open_store()`, the CLI
fails closed, the container gates `APX_HEAD_JOURNAL` beside the encryption key, and a structural check refuses a
construction anywhere else.

**The alarm survives the restart that used to clear it.** A head the journal could not record is the exact point a
later truncation becomes undetectable, and it lived in a boolean in one process's memory — cleared by the next deploy,
unreachable by the worker, and clearable by nobody deciding anything. It is a row now.

**100 → 103 checks, and the fitness frame stopped disclaiming.** Its audit stage said in writing that a tail
truncation "is deliberately not claimed … that is what story 5.9 puts on the export's face". It now asserts it, in a
process with no store: the causes, the four witness states, the fork, and `read_continuity` over a whole document.

### Found by the review, after the tests were green

Six lenses, each finding verified by two independent skeptics instructed to refute. **35 candidate findings, 26
refuted, 9 confirmed and all 9 fixed.** The three that mattered:

1. **The comparison was taken at one point only** — the newest journalled head at or below the live one. One ordinary
   commit after a forgery, and the next reconciliation compared the forged record against a line the forgery had
   produced. Now compared at every witnessed point, earliest disagreement wins, with the post-override floor so a
   signed acknowledgement still settles.
2. **A chain removed *wholesale* left the document silent.** `read_audit` builds its slices from the entries it finds,
   so deleting every row of a *matter* chain produced no slice, no cover line, and nowhere for the comparison to run.
   The maximal truncation — the one that removes everything — was the only one the document said nothing about, and a
   silent document reads as a clean one. A chain the outside witness knows and the record no longer holds now gets its
   line, `verified=False`, and its comparison.
3. **The fork guard skipped a missing value on a justification that named a different table.** "An empty live value
   means the entry is gone, which is reported as a truncation" — except the truncation test reads `audit_chain_head`'s
   sequence, which deleting an entry from the middle does not move. The project's recurring defect, in the code
   written to close the project's recurring defect.

Also fixed: `manage restore` reported truncations only and printed the ordinary success line for a forked one; the
override that clears a fork recorded neither its kind nor its forks; the export read its witness *after* its entries,
so a concurrent act made a healthy document accuse itself of truncation; the tenant chain's witness was copied onto
every scoped export; `agrees_with_producer` printed **true** where no recomputation had happened; the store-door
exemption matched any file named `opening.py` anywhere; a refused export left the previous document's verdict on
screen beside the error; and the configuration act's negative assertion was a tautology whose second arm was the line
above it.

**Coverage lost, and stated as such (retro action A2):** one of the six lenses errored and returned nothing — the
atomicity-and-refusal lens. Its ground is covered by tests (`tests/adapters/test_audit_atomicity.py`, eleven of them)
but it received no adversarial reading. Every surviving lens also reported what it could not inspect; the material
one: the PostgreSQL SQLSTATE mapping in `_classify_audit_write` is read but not exercised, because the SQLite
harnesses surface a trigger ABORT as `IntegrityError` and therefore drive the *contention* path. The unwritable path
is driven by the second harness, at the DBAPI edge, on both the store and the HTTP boundary.

### Known, named, and not fixed here

- **A tail is only as witnessed as the journal is current.** The head is written after the commit, so the last acts of
  a live system have no outside witness and their removal would be undetectable. Named on the document rather than
  papered over; closing it would mean journalling inside the transaction, which a file append cannot be.
- **`upgrade.sh`, the pre-migration `pg_dump` and the head recorded before a migration** — AD-46's other half, deferred
  by Story 1.11 to deploy. A migration is the second operation that can destroy the record.
- **The AD-49 monotonic counter.** A user-settable clock can make timestamps go backwards, which reads as tampering.
- **AD-44's partition-and-seal**, re-checked rather than inherited: today's writers still collapse to one entry per
  job, and Story 5.8's 1 700-*pièce* batch is one transaction against one head row — to be measured against the 2.13
  timed run.
- **The rendered document.** *On the export's face* is discharged on the cover and the client panel; a paginated
  printable *dossier* is Epic 6's.
- **`witness_upto` is no longer used by the reconciliation** but is kept and tested — it is the single-point read a
  future compaction of the journal will want.
- **The journal is parsed once per reconciliation and grows one line per commit.** Compaction (retain the latest head
  per scope) stays deferred, as Story 1.11 left it; immaterial at the single-firm design target, and now bounded by
  one `IN (…)` per scope rather than one query per witnessed point.

## File List

**New:** `apx/adapters/store_postgres/opening.py` · `apx/adapters/store_postgres/migrations/versions/0037_chain_continuity.py` · `apx/checks/continuity.py` · `tests/domain/test_continuity.py` · `tests/adapters/test_audit_atomicity.py` · `tests/adapters/test_chain_fork.py` · `tests/adapters/test_chain_continuity_migration.py` · `tests/api/test_continuity_api.py` · `tests/checks/test_continuity_checks.py` · `tests/_fixtures/continuity_violations/{clean,unjournalled_store,claim_from_the_caller,swallowed_audit_write}/`

**Modified:** `apx/core/domain/audit.py` · `apx/core/domain/head_journal.py` · `apx/core/domain/matter_record.py` · `apx/adapters/store_postgres/store.py` · `apx/adapters/store_postgres/models.py` · `apx/adapters/store_postgres/queue/__init__.py` · `apx/api/app.py` · `apx/manage.py` · `apx/checks/registry.py` · `apx/checks/manifest.py` · `apx/checks/encryption.py` · `apx/fitness/driver.py` · `apx/web/src/{api.ts,drawer.tsx,tokens.css}` · `docker/entrypoint.sh` · `README.md` · `tests/adapters/test_matter_record_export.py` · `tests/probe/test_export_self_contained.py`

## Change Log

| Date | Change |
|---|---|
| 2026-08-14 | Story created from epics.md §5.9 + FR-53, after a six-reader survey of the existing substrate. |
| 2026-08-14 | Implemented T1–T10. Gate green: 103 structural checks, 3 contracts, fitness 6/7, client typecheck + build. |
| 2026-08-14 | Adversarial review (6 lenses, 2 skeptics per finding): 35 candidates, 26 refuted, 9 confirmed, 9 fixed. One lens errored — coverage loss stated above (retro A2). |
