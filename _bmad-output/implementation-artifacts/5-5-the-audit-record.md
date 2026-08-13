---
baseline_commit: ddd50d6
---

# Story 5.5: The audit record

Status: done

## Story

As a firm that may have to defend every decision,
I want an append-only record of everything that matters, each entry sequenced and attributed,
So that "auditability is non-negotiable" — the one named client requirement — becomes a mechanism
rather than a slide.

## Scope note — the record already exists; this story is where it becomes evidence

Slice A (Story 1.1) created `audit_record` with a per-**tenant** sequence and a chain over the
previous entry, and thirty-five call sites across eleven stories have been writing to it since.
Twenty-five distinct act verbs are already recorded. Read naively, FR-24 looks nearly discharged.

It is not, and the gap is a single sentence in FR-53 that the current shape cannot satisfy:

> *a gap, a reordering or a truncation is detectable by a reader **holding only the export**.*

The chain is one chain **per tenant**. An export is **per matter** (FR-26). So the export of a
matter is a set of entries whose sequence numbers have holes in them wherever another matter of the
same tenant wrote an entry in between — and whose chain values cannot be recomputed at all, because
each link is taken over the previous entry *of the tenant*, which is not in the export and which the
reader is not entitled to see (FR-24: *"a user reading it sees only entries for matters within their
scope"*). The *bâtonnier* holding the export today cannot verify anything. Worse, the holes are
indistinguishable from the truncation the chain exists to reveal — the artefact reports tampering on
an untampered record, every time.

AD-43 decided this before any of it was built: **the chain is scoped per (tenant, matter), plus one
matterless tenant chain**, and the sequence is allocated **inside the entry's own transaction from a
chained head row under `SELECT … FOR UPDATE`, never from a sequence generator**. Neither half is
implemented. This story implements both, closes FR-24's remaining coverage, and makes the catalogue
of recordable acts a build gate rather than a list in a requirements document.

**What this story does not own.** FR-53's continuity check on the export's face, the atomicity
assertion with the audit store made read-only mid-action, and verification on restore are Story
5.9's. The *override* classification is 5.6's, the *audit drawer* and the export document are 5.7's,
the *validation act* is 5.8's. This story owns the record's **structure, identity and coverage** —
the substrate all four rest on.

## Acceptance Criteria

**AC-1.** **Given** the *audit record*, **when** any recordable act occurs, **then** it appends an
entry and never edits or removes one — a correction is a new entry (FR-24), and the prohibition is
**structural**: no runtime path issues an `UPDATE` or `DELETE` against an evidential table.

**AC-2.** **And** the record captures at minimum the thirteen act classes FR-24 enumerates, and the
catalogue is a **mechanism**: every audit verb written by the runtime is a catalogued act, and every
act the catalogue declares covered has a real writer — an act class declared covered whose writer
does not exist fails the build, and an uncatalogued verb fails the build. Classes owned by a later
story are declared **pending with the story that owns them**, on the fitness-driver precedent, so a
hole is named rather than invisible.

**AC-3.** **And** every entry carries an actor, a wall-clock timestamp, a **monotonic sequence
number from a single authority**, and a *matter* — **or names the tenant chain explicitly** (FR-24
as amended by AD-43); system-initiated entries name the **system component** as actor and never a
user, and no entry is ever attributed to `"unknown"`.

**AC-4.** *(AD-43, the sequence authority)* **And** the sequence number is allocated inside the
entry's own transaction from a chained head row taken under `SELECT … FOR UPDATE` — never from a
sequence generator, so a gap is impossible **by construction** rather than detectable after the
fact; `nextval` and any `Sequence`-backed column on an evidential table **fail the build** as a
structural property.

**AC-5.** *(AD-43, the chain's scope)* **And** chains are scoped per (*tenant*, *matter*) with one
additional matterless *tenant* chain per *tenant*, so that a reader holding **only** one matter's
entries can recompute that matter's chain end to end; a matter chain's first entry is anchored to
the *tenant* chain's head at the moment the chain opened, and the opening is itself an entry.

**AC-6.** *(failure path)* **And** nothing already written is rewritten: the migration re-chains no
existing entry — a re-chaining would be detected as forgery by the head journal of Story 1.11, which
holds the old chain values outside the restorable store — and `read_audit` states which slice of a
matter's history is verifiable in isolation and which predates the matter's own chain, rather than
reporting a confidence the reader cannot reproduce.

## Design decisions

**D1 — the chain is named on the entry, never inferred from `matter IS NULL`.** A new
`chain_scope` column carries the matter identity, or the empty string for the tenant chain. FR-24 as
amended requires the entry to *name* its chain; deriving it from a nullable column means a future
entry with a forgotten matter silently joins the tenant chain and the reader cannot tell an act that
belongs to no matter from an act whose matter was dropped on the floor.

**D2 — the sequence comes from a head row, locked.** `audit_chain_head (tenant, chain_scope) → seq,
chain` is read `FOR UPDATE` inside the acting transaction. Today's `SELECT … ORDER BY seq DESC LIMIT
1` is unlocked: two concurrent acts read the same `prev_seq`, both compute seq n+1, and the second
one dies on the unique constraint. That is not a gap — the constraint holds — but it is a **refused
legitimate act** under ordinary concurrency, and AD-22 makes a refused audit write a refused act.
The lock serialises the two writers instead of killing one. AD-43's ban on `nextval` is not
performance advice: a burned `nextval` after a worker crash manufactures a permanent, unrepairable
tamper alarm that AD-22 forbids anyone to repair.

**D3 — nothing is rewritten, and the head journal is why.** Story 1.11 records every chain head
(tenant, seq, chain value) to an append-only file outside the restorable database. Re-chaining the
existing entries would leave every journalled chain value unmatched by the live record — the exact
signature of forgery, produced by our own migration. So the existing entries stay on the tenant
chain, at their existing sequence numbers, with their existing chain values, whatever matter they
name. The constraint was already mechanised before this story looked at it.

**D4 — a matter chain is anchored, and opening one is an act.** The first entry of a matter's chain
takes as its `prev_chain` the chain value of a `chain_opened` entry written on the **tenant** chain.
What that buys: the first link of a matter chain has a predecessor like every other link, the
tenant chain carries a complete list of every chain ever opened — so a reader can tell a matter
with no entries from a matter whose chain was removed wholesale — and taking the tenant head lock
to write the opening entry is what serialises two concurrent openers of the same chain.

> **Corrected after review.** This decision first claimed that anchoring meant *"a matter chain
> cannot be fabricated after the fact without the tenant head as it then stood"*. That is false,
> and two skeptics refuted it by reproduction: the chain is an unkeyed SHA-256 and the anchor is a
> plaintext column, so anyone who can rewrite the entries can re-chain them **from the true anchor**
> and leave every internal check satisfied — including the cross-check this story was about to add
> in response. The added check would have closed nothing while looking like a defence, which is
> worse than not adding it. Currency against an attacker with database write access comes from the
> head journal (AD-35), which lives outside the restorable store; nothing inside the store can
> supply it.

**D5 — the chained content is versioned.** The entry gains the application and payload-schema
versions (FR-24 requires both recorded), and they enter the chained content. Every entry written
before this story chained a five-field content string; recomputing those with the new recipe would
turn the entire existing record unverifiable in one commit. The entry therefore carries a
`content_version`, and the verifier picks the recipe from the entry rather than from the code's
current opinion.

**D6 — the system actor is a named component, not a default.** `SqlStore.save(actor="unknown")` is
today's default and it is the one attribution the record must never carry: an entry naming no one is
worse than no entry, because it is countable, filterable and defensible-looking. System-initiated
acts name their component (`system:import-worker`, `system:cascade`, …) from a closed set, and the
default disappears.

**D7 — `read_audit` reports what the reader can check.** The trail returns both slices — the
matter's own chain, and the pre-migration entries for that matter that live on the tenant chain —
and marks the second as *not verifiable in isolation*. A reader holding the export can verify the
first end to end. Reporting one `verified` boolean over both would assert a property of bytes the
reader does not hold.

## Tasks / Subtasks

- [x] **T1** — the domain: `apx/core/domain/audit.py` — the chain identity, the recordable-act
      catalogue (verb → FR-24 class, chain kind, actor kind, covered/pending + owning story), the
      system-actor set, the versioned chained-content recipe. Pure, no adapter import.
- [x] **T2** — the store: `audit_chain_head` table + migration `0033`, `_append_audit` rewritten to
      allocate from the locked head row, `chain_opened` anchoring, the version columns.
- [x] **T3** — the read seam: `read_audit` returns the two slices with an honest verification
      verdict per slice; scope-checked as today.
- [x] **T4** — the call sites: every `_append_audit` verb becomes a catalogue constant; the system
      actors get named; `actor="unknown"` is removed.
- [x] **T5** — the structural checks: `audit_catalogue_is_complete`, `audit_sequence_is_not_generated`,
      `audit_record_is_append_only` — registry + manifest + README, 89 → 92.
- [x] **T6** — the API: the audit endpoint carries the chain identity, the two slices and the per-
      slice verdict.
- [x] **T7** — tests: domain, adapter (concurrency, anchoring, migration continuity), checks, API.
- [x] **T8** — the gate: ruff · import-linter · structural checks · pytest · offline fitness ·
      typecheck · build.

## Dev Notes

- **Lockstep, three sites.** A structural check lives in `apx/checks/registry.py` (import +
  `CHECKS`), `apx/checks/manifest.py` (`_p(key, fr, ad, name, callable, inspects)`), and the
  `<!-- structural-properties -->` block of `README.md`. `manifest_matches_readme` compares the
  first five cells only.
- **`_RUNTIME_EXCLUDE = {"checks", "fitness", "timedrun", "__pycache__"}`** — `apx/checks/` is
  outside the scanned runtime and may name what it forbids. `apx/eval/` **is** scanned.
- **The evidential tables** for AC-4's ban: `audit_record`, `audit_chain_head`, and the append-only
  ledgers that carry legal weight — `case_theory_version`, `line_placement`, `pin_entry`,
  `taxonomy_label_entry`, `sampling_run`. All already use deterministic or application-computed
  identities; the check makes that irreversible.
- **Chain scope for tenant-level acts.** `grant_scope`, `revoke_scope`, `config_changed`,
  `tenant_provisioned`, `key_rotated`, `truncation_override`, `create_user`, and the corpus-wide
  query audit belong to the tenant chain — they name no matter and must not invent one.
  `rescope_matter` names a matter *and* is a tenant-authority act; it goes on the **matter** chain
  because the matter is its subject, and the tenant chain carries the authority in the detail.
- **AD-44 is not in scope.** Per-worker partition ledgers for high-volume machine events are a
  separate decision; today's high-volume writers (`ingest`, the register) already collapse to one
  entry per job by AD-6, so the contention AD-44 exists to prevent does not yet bite. Named here so
  the omission is deliberate.

## Dev Agent Record

### Completion Notes

The record existed before this story and looked nearly finished: one chain per *tenant*, thirty-five
call sites, twenty-five verbs. What it could not do was the one sentence FR-53 turns on — *a gap, a
reordering or a truncation is detectable by a reader holding **only the export***. An export is per
*matter*; the chain was per *tenant*; so the *bâtonnier*'s copy had a hole wherever a sibling matter
had written, and its links ran through entries that reader is not entitled to see. The artefact
reported tampering on an untampered record, every time. AD-43 had decided both halves of the fix
before anything was built, and neither had been implemented.

**What the record is now.** Chains are scoped per (*tenant*, *matter*) plus one matterless *tenant*
chain. A sequence number is allocated inside the acting transaction from a head row taken under
`SELECT … FOR UPDATE` — never a generator, because a burned `nextval` after an ordinary crash
manufactures a permanent tamper alarm AD-22 forbids anyone to repair. The chained content is
versioned, so entries written under the old recipe keep verifying under it. Forty verbs are
catalogued with their FR-24 class and their chain; three structural checks make the catalogue, the
allocator and the append-only prohibition build gates rather than intentions. Nothing already
written was re-chained, renumbered or moved: the head journal holds those chain values outside the
restorable store, and a migration that rewrote them would have produced the exact signature of
forgery with our own hands.

**What it refuses.** An uncatalogued verb at a call site. A literal verb string. An FR-24 class
claimed as covered with no writer, or claimed as pending while a writer exists. `nextval`, a
`Sequence` column on an evidential table, and an allocation that does not take the row lock. A
statement that removes or bulk-updates an evidential row, and an in-place edit of one. The actor
`"unknown"` — the one attribution the record must never carry, because an entry naming no one is
countable, filterable and defensible-looking.

### Debug Log

- **Three defects surfaced before the review, from reading the seams rather than the diff**: the
  backup did not carry `audit_chain_head`, so a restore produced a tenant with a record and no
  allocator; the head journal folded every chain of a tenant under one scope, so per-chain
  reconciliation compared unrelated sequence numbers; and `save(actor="unknown")` was a default.
- **Removing that default broke sixty-five tests.** Scripted the `actor="Me Dupont"` insertion
  across eight files, then reflowed twenty-five E501 lines by hand — accented characters push a
  line past a hundred columns where the formatter's arithmetic does not.
- **The `nextval` check fired on its own migration's docstring**, which explains at length why
  `nextval` is banned. Story 5.3's precedent: exempt docstrings **subtractively**, so raw SQL beside
  such a docstring still fails. `_docstrings(tree)` returns `id()` values, not text — wrote
  `_docstring_text`.
- **The strengthened append-only leg fired on `SamplingRun`'s lifecycle transitions.** A run is an
  entity that opens and then completes or is abandoned, and each transition writes its own audit
  entry; its history lives on the chain, which is append-only in the strict sense. Split
  `APPEND_ONLY_MODELS` (no in-place edit) from `EVIDENTIAL_MODELS` (no statement removal or bulk
  update) rather than forbidding a legitimate state machine.
- **The encryption check demanded a decision on `TruncationMarker.chains`** and got one: plaintext,
  by the same reasoning as the `matter` column beside it, written into the allowlist with the
  reason it rests on and the reason it does **not** rest on.
- **The offline fitness frame still listed *produce an audit record* as PENDING 5.5** while 5.5 was
  being built. The frame's own rule — asserted with something behind it, or pending with a name on
  it, never both — makes that a defect the moment the story lands. The stage now asserts the half
  the frame can reach: the chain recomputes from the entries alone, a rewrite, a gap and a
  reordering each break it at the named link, and two chains of one tenant verify independently. A
  **tail** truncation is deliberately not claimed — a shorter chain recomputes perfectly and no
  reader can tell from the export alone; that is the head journal's job (AD-35) and Story 5.9's.

## File List

**New** — `apx/core/domain/audit.py` · `apx/checks/audit_record.py` ·
`apx/adapters/store_postgres/migrations/versions/0033_audit_chain_scope.py` ·
`tests/domain/test_audit_catalogue.py` · `tests/adapters/test_audit_chains.py` ·
`tests/adapters/test_audit_chain_migration.py` · `tests/checks/test_audit_record_checks.py` ·
`tests/api/test_audit_api.py` · `tests/_fixtures/audit_violations/` (12 fixtures)

**Updated** — `apx/adapters/store_postgres/{models,store}.py` · `apx/api/app.py` ·
`apx/checks/{registry,manifest,encryption}.py` · `apx/core/domain/head_journal.py` ·
`apx/fitness/driver.py` · `apx/web/src/{App.tsx,api.ts}` · `README.md` (89 → 92) ·
`tests/adapters/{test_backup_restore,test_case_theory,test_failure_register,test_idempotent_ingest,test_inventory_denominator,test_ranking_store,test_store,test_store_postgres}.py` ·
`tests/api/test_register_api.py` · `tests/probe/test_never_hard_delete.py` ·
`tests/security/test_out_of_scope_adversarial.py`

---

## Senior Developer Review (AI)

**Six lenses** — the chain, the allocator, the catalogue and its checks, the migration and its
continuity, the read seam, the regression surface. Every finding adjudicated by **two independent
skeptics** defaulting to REFUTED, one attacking the mechanism and one the consequence.

### Coverage

| | |
|---|---|
| Lenses run / planned | **6 / 6** (one re-run after an outage) |
| Findings | **23** |
| Skeptic verdicts | **45 / 45** |
| Confirmed | **9** |
| Refuted | **14** (61 %) |
| **Unadjudicated** | **0** |
| Agents lost | **25**, to a network outage in the first run — recovered, not written off |

The outage is worth recording, because the first script classified a verdict-less finding as
*refuted*. A lost agent and an agent that examined a claim and rejected it are not the same thing,
and the difference falls entirely on the flattering side. The recovery script added an explicit
`unadjudicated` status, re-ran the lens that died, and re-adjudicated everything; the table above is
from that run.

### The nine confirmed, and what each was

1. **The append-only check promised a leg it did not implement** [HIGH]. Its docstring said an
   in-place edit of a loaded row was forbidden; the implementation inspected only `delete()` and
   `update()` statement builders. `row = session.scalars(...).one(); row.detail = "corrected"`
   passed a green build — the plainest way to rewrite the record, and five sibling checks already
   implemented exactly the idiom that catches it.
2. **`SELECT … FOR UPDATE` does not lock a row that does not exist** [HIGH]. Two concurrent first
   acts on a new matter both found no head, both opened the chain, and the second died on the
   unique constraint. AD-22 makes a refused audit write a refused act, so ordinary concurrency
   refused legitimate work on exactly the acts that open a matter. → the head is re-read under the
   *tenant* head lock after opening, which turns the race into a wait.
3. **A backup restored into an empty store left the tenant permanently unable to write** [HIGH].
   `audit_chain_head` was outside `_BACKUP_TABLES`, so the restore produced entries with no
   allocator; the next act allocated seq 1 and collided with the entry it was meant to follow —
   for ever, since AD-22 forbids repairing it. This one touched **every backup the deployment holds
   today**. → the table is in the backup, and the allocator is rebuilt from the entries on restore.
4. **Restore never compared the allocator against the entries it shipped with** [HIGH]. A backup
   whose head disagreed with its own record was accepted into an unrepairable state. → the
   disagreement refuses the restore.
5. **The backup read the allocator and the entries in different moments** [MED]. Under READ
   COMMITTED a backup taken during an ingest could capture `audit_chain_head` after a commit that
   `audit_record` was read before — an allocator ahead of its own record, restored as a permanent
   hole. → `REPEATABLE READ` on PostgreSQL, in an extracted, tested decision.
6. **The truncation marker is one row per tenant, and the per-chain loop overwrote it** [MED].
   Two matters truncated; the firm was told whichever scope sorted last, understating the loss and
   naming no matter. Reproduced at 20 entries lost, 1 reported. → the total, every chain named, and
   the surviving pair describes the **worst**-hit chain.
7. **The tenant slice was built only when entries remained on it** [MED]. Deleting a matter's
   pre-5.5 history made the slice vanish, and the trail read clean and shorter with nothing saying a
   slice had ever existed. → the slice is always reported.
8. **`verified` was `all([])`** [MED] — true on a trail with no chain at all. A register with
   nothing in it is not an intact register; it has nothing to check.
9. **The client said nothing about the no-slice state** [LOW] — a blank panel where the honest
   answer is a sentence.

### Refuted, and the one that mattered

The anchor cross-check I was about to add. D4 claimed anchoring meant a matter chain *"cannot be
fabricated after the fact without the tenant head as it then stood"*, and the natural response was a
check comparing the chain's anchor against the `chain_opened` entry. **Both skeptics reproduced the
forgery with the anchor left intact**: the chain is an unkeyed SHA-256 and the anchor is a plaintext
column, so anyone who can rewrite the entries re-chains them from the true anchor and satisfies
every internal check — including the one I was adding. It would have closed nothing while looking
like a defence, which is worse than not adding it.

So the **claim** was corrected rather than the code (see D4). Currency against an attacker with
database write access comes from the head journal (AD-35), outside the restorable store; nothing
inside the store can supply it, and a story that says otherwise teaches the next reader to trust the
wrong thing.

### Found after the review, by execution

**A chain that had gone quiet since an override could be erased wholesale, invisibly** [HIGH].
Clearing a truncation resets the reconciliation baseline to the heads recorded *after* the override.
A chain that had not written since had no such head, so its baseline was zero — and nothing is below
zero. Its entries and its head row could then be deleted entirely and `reconcile_heads` reported no
loss: a matter's whole history gone, no marker, no alarm. The *tenant* chain escaped only by
accident, the override entry being written on it.

Per-matter chains are what opened this, so it is 5.5's to close: under one chain per tenant the
override always supplied its own baseline. → the override now **writes down what it accepted**
(`_journal_acknowledged_heads`), which is what an override is. It is this project's recurring defect
once more — a comparison whose right-hand side was not the same thing as its left — and it was found
by running a throwaway script to the end rather than by reading the code, which is the lesson worth
keeping.

## Change Log

- **2026-08-13** — Story 5.5 implemented, reviewed and completed. The audit record became evidence:
  chains scoped per (tenant, matter) plus one tenant chain, sequence numbers allocated from a locked
  head row, a versioned chained content, a forty-verb catalogue enforced by three structural checks
  (89 → 92), and a read seam that states which slice of a matter's history a reader can verify for
  themselves. Nothing already written was re-chained. Nine review findings and one post-review
  defect fixed, each with the test that fails without it.
