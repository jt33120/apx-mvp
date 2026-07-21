---
title: Adversarial Review — Architecture Spine, APX MVP First Increment
type: review-adversarial
target: ARCHITECTURE-SPINE.md (34 ADs) + WORK-BREAKDOWN.md (20 units)
lens: construct two units that each obey every AD to the letter and still build incompatibly
status: draft
created: 2026-07-21
---

# Adversarial Review — the Spine as a Contract Between Units

**Method.** Every finding below is a *pair*: unit A and unit B from `WORK-BREAKDOWN.md` (or two
plausible units inside one), the AD each is obeying, and the legitimate, defensible, in-scope
choice each can make that renders them incompatible. Nothing here requires a unit to disobey an
AD. Where the spine already closes an attack, it is recorded in one line at the end so that the
team does not re-litigate it.

**Verdict.** This is an unusually strong spine — the failure modes it names are the real ones, and
AD-33 is the right idea in the right place. Its weakness is uniform and structural: it governs the
*retrieval* path, the *write* path and the *record* with great care, and is close to silent on
**concurrency, ownership of state transitions, and every read that is not a search**. With one
non-hands-on lead and AI agents, an unstated concurrency contract is not a gap that a careful
engineer fills — it is a coin flip taken twenty times.

**Count: 24 incompatible-pair holes.** Plus 6 unenforceable AD clauses, 8 ADs carrying two or more
decisions under one ID, and 11 dimensions on which no AD speaks at all.

---

## Damage ranking

| # | Hole | Units | Class |
| --- | --- | --- | --- |
| **H-1** | AD-9 and AD-13 give opposite instructions about the same column | U5 × U9 | shared shape / silent leak |
| **H-2** | AD-14 governs *retrieval*; most reads of *tenant* data are not retrieval | U9 × U16/U18/U13 | single-path defeated |
| **H-3** | The audit chain has no concurrency contract; a crash forges a tamper alarm | U8 × U12 | audit chain |
| **H-4** | Restore is a sanctioned hard delete that passes the chain check | U4 × U8 | reversibility |
| **H-5** | The encryption-layer-split AD exists only in `.memlog.md`; AD-31 still says "unresolved" | U4 × U6 | missing AD |
| **H-6** | `ON DELETE CASCADE` defeats AD-7 without a call site | U4 × U5 | reversibility |
| **H-7** | An **exhaustive** set truncated by an AD-17 capacity bound, or computed during an ingestion | U9 × U12 | truth status |
| **H-8** | `chunk_id` omits the extraction version — evidence mutates under a citation | U5 × U10 | shared shape |
| **H-9** | Stage-1 exclusions leave the population the *confidence bound* reports on | U14 × U17 | two owners / silent leak |
| **H-10** | AD-2's stubbed endpoint requires the second Embedder AD-11 forbids | U1 × U11 | environment split |
| **H-11** | *Custodian* is a required scalar on the chunk and a set on the *pièce* | U5 × U12 | shared shape |
| **H-12** | `supersedes`: AD-9 says nothing writes it; FR-4 says ingestion must | U5 × U12 × U18 | two owners |
| **H-13** | *Failure register* entry has three writers and no compare-and-set | U12 × U16 | state mutation |
| **H-14** | **The line**, *pins* and a *sampling run* have three writers and no conditional commit | U15 × U17 | two owners |
| **H-15** | Queue state vs the application ledger; quarantine written inside the failing transaction | U12 × U16 | state mutation |
| **H-16** | The *denominator* has no arithmetic for cardinality `unknown` | U12 × U16 × U17 | shared shape |
| **H-17** | Near-duplicate family identity is not required to survive into the ranked order | U14 × U15 × U17 | shared shape |
| **H-18** | Database collation is unpinned; a restore changes the tie-break | U4 × U15 | reversibility |
| **H-19** | A dev-tier read replica or pooler is "the same PostgreSQL" | U4 × U9 | environment split |
| **H-20** | Nothing forbids HTTP caching; a cached response replays an **exhaustive** claim | U16 × U9 | truth status |
| **H-21** | A user-supplied document password has no lawful channel to a worker | U12 × U6 | state mutation |
| **H-22** | Extraction subprocess stderr carries *pièce* content into the worker log | U10 × U13 | egress |
| **H-23** | "Extent" / "reading burden" has no declared unit | U15 × U17 | shared shape |
| **H-24** | User-facing HTTP is not idempotent; a double-click doubles a bulk *validation act* | U16 × U8 | state mutation |

---

## H-1 — AD-9 and AD-13 give opposite instructions about the same column

**Unit A — U5, the payload and identity kernel**, obeying **AD-9**: *"exactly one function writes a
chunk. It takes tenant, matter, **RBAC scope** and custodian as **required arguments with no default
value anywhere in the source**."* Reinforced by **AD-5**: *"chunk row + its vector + its RBAC scope
is one transactional object."* U5 therefore declares `chunk.rbac_scope NOT NULL` and requires it at
the writer. This is the letter of two ADs.

**Unit B — U9, the single retrieval path**, obeying **AD-13**: *"authorisation state lives in
exactly one place and is joined into every retrieval query as a pre-filter … **never denormalised
onto indexed rows** … **no re-stamping operation exists in the system**."* U9 therefore joins the
grant store and ignores `chunk.rbac_scope` entirely.

**The incompatibility.** The wall now has two representations: a column written at index time that
nothing may ever re-stamp, and a join resolved at query time. AD-13 exists precisely to forbid the
first. Both units are correct. The moment any third code path — an export enumerator, a bulk retry,
the AD-18 stage-2 filter, a capacity report, a projector — reads `chunk.rbac_scope` because it is
right there and it is `NOT NULL`, it enforces the **stale** wall permanently and correctly against
the wrong material. That is AD-13's stated failure mode, reached without disobeying AD-13.

There is a defensible reading in which AD-9's scope argument is a *write-time authorisation check*
and not a stored value. The spine never says so, AD-5 says the opposite, and nothing distinguishes
*tenant* and *matter* (immutable, safe to denormalise) from *RBAC scope* (mutable configuration
under FR-49, unsafe by AD-13's own argument).

**Tightening — amend AD-9, third sentence:**

> The one chunk writer takes *tenant*, *matter*, *RBAC scope* and *custodian* as required arguments
> with no default value anywhere in the source. *Tenant* and *matter* are **persisted on the row**;
> they are immutable for the life of the *chunk*. The *RBAC scope* argument is a **write-time
> authorisation check against the *matter*'s current scope and is not persisted** — no column named
> or aliased as a scope exists on `chunk`, `piece` or `full_text`, and no read path derives
> authorisation from an indexed row. Enforced as a *structural property*: a schema check over the
> migration files asserts the absence of the column, and the import-graph check asserts that the
> grant store is imported only by the AD-14 query constructor.

And amend **AD-5**'s parenthetical to read *"chunk row + its vector + its* matter *is one
transactional object"*, so the two ADs stop contradicting each other in print.

---

## H-2 — AD-14 governs *retrieval*; most reads of *tenant* data are not retrieval

This is the structural claim the brief asks to be attacked, and it is defeated by four separate
pieces of entirely legitimate code.

**AD-14's letter:** *"Retrieval has one entry point. It requires a scope argument. No result-set
post-processing function accepts a scope, and none exists."* The noun is **retrieval** — the search
of a *corpus* returning a ranked or complete match set. Nothing in AD-14 binds a read that is not a
search.

**AD-12 does not close it.** AD-12 says *"every read is constrained by tenant before RBAC scope is
applied"*, which makes a hand-written scope check in a viewer route **obligatory** — it does not make
it **centralised**. The wall is then enforced in N places, correctly per AD-12, with no single path
and no structural check over any of them. That is precisely AD-14's own stated Prevents clause —
*"the join of AD-13 being bypassed by a second query path written in good faith"* — arriving through
the noun AD-14 chose.

**Pair A — U9 × U16 (the viewer, FR-44).** U16 must render `.msg`, PDF, scanned PDF with an OCR
layer, `.docx`, `.xlsx` and images, and open the source *pièce* **at the passage**. That is a
primary-key fetch of an original artefact and of AD-10's stored full text. U16 legitimately writes
`GET /api/pieces/{id}/original` → `SELECT … FROM piece WHERE id = :id AND tenant = :t`, plus an
explicit scope check written by hand in the route or the use case. AD-12 is satisfied (tenant first,
then scope). AD-14 is not engaged, because this is not retrieval. **A second place where the wall
can be wrong now exists, in the unit with the most surface and the least adversarial testing.**

**Pair B — U9 × U18 (the export, FR-46).** AD-7 makes the *retained set* a **view over one ranked
order plus pins** — and a view is computed by a query, whose owner AD-7 does not name. U18
legitimately calls a domain-level `ranked_order(matter, ranking_version)`, applies pins in
`core/domain`, then hydrates title, date, *custodian*, label, rank, confidence and justification
per *pièce* by identifier. Every hydration is a Pair-A read. The one query constructor was used for
nothing, and the artefact that leaves the building was assembled entirely outside it.

**Pair C — U9 × U13/U14 (aggregates).** AD-18 requires *"the share of pièces reaching stage 3 is
recorded per run"*; FR-3 requires *"a corpus-wide OCR figure … per matter and per tenant"*; AD-20
requires that figure on the face of every **exhaustive** claim. These are aggregate queries run by a
worker with **no user**. AD-12 says *"a user with no scope receives an empty corpus — and this
applies identically to administrative and system identities. There is no implicit superuser."* A
system identity with no scope must therefore compute a corpus-wide figure over nothing. The only
implementation that ships is a fourth query path with no scope argument at all.

**Pair D — U9 × U16 (every non-search screen).** FR-27's *worklist*, FR-28's *denominator*,
FR-60's *matters* zone, FR-7's completion summary, FR-52's backup status. Each returns *tenant* data.
None is retrieval. AD-29 closes the *frontend* side (static, HTTP to one API) and says nothing about
the API having one data-access family.

**Tightening — amend AD-14's rule, replacing "retrieval" with the full read surface:**

> **Every read of *tenant*-owned data has one entry point** — not only ranked or exhaustive search.
> This includes: reads by identifier; streams of original bytes, OCR images and stored full text;
> render and thumbnail requests; counts, aggregates and derived statistics; the *failure register*;
> the *worklist*, the *denominator*, the *matters* zone and the completion summary; and every
> enumeration performed while producing an export. The read port exposes **no method that accepts an
> identifier without a *tenant* and a scope argument**. Enforced as a *structural property*: no SQL
> text and no ORM query naming a *tenant*-owned table appears outside `core/app/read/`, asserted by
> a grep over `adapters/`, `api/`, `worker/` and `eval/`; and the AD-33 registry of user-reachable
> actions carries, per action, the read entry point it uses — an action with none fails the build.
>
> Aggregate and derived-statistic computation is a first-class use case executed through the same
> entry point under an explicit **maintenance principal** (see H-4's tightening), is recorded in the
> *audit record* as a system-actor read, and any figure displayed to a user is either recomputed
> within that user's scope or is labelled on its face as a *matter*-level quantity the user is
> authorised to see (the FR-6 two-names rule, extended from the *denominator* to every derived
> figure).

**Note on U9's estimate.** `WORK-BREAKDOWN.md` already calls U9 `UNDERESTIMATED` and says the
adversarial suite "must be extended every time any surface is added, forever". That is a statement
of intent that relies on a human noticing. The amendment above converts it into a check.

---

## H-3 — The audit chain has no concurrency contract, and a crash forges a tamper alarm

**Unit A — U8, the audit spine**, obeying **AD-22**: entries carry *"a monotonic sequence number
from a single authority and a chain value over the previous entry, so that a gap, a reordering or a
truncation is detectable by a reader holding **only the export**."*

**Unit B — U12, the ingestion pipeline**, obeying **AD-6** (*"state advances only by a worker
committing a unit of work"*, many workers) and **AD-17** (one unit of work per *pièce*, each
producing register entries and completion records). At the *design target* U12 appends continuously
from N concurrent workers.

**Three incompatibilities, all legitimate:**

**(a) The sequence source.** U8 can implement "monotonic from a single authority" as a PostgreSQL
`SEQUENCE`. `nextval` is **non-transactional**: a worker that takes number 41 209 and then crashes
or rolls back burns it forever. The chain then has a permanent gap, AD-22's continuity check reports
it on every future export, and AD-22 forbids repair: *"a failed verification is surfaced, never
silently repaired."* **An ordinary worker crash manufactures a permanent, unrepairable tamper alarm
on a record of asserted legal weight, on a machine APX reaches only by telephone.** U8 can equally
implement it as an in-transaction `audit_head` row under `SELECT … FOR UPDATE`, which is gapless and
serialises every append. Both satisfy AD-22's words. They are not interchangeable and the second
unit to ship discovers it.

**(b) The chain's scope.** Open Question 3 records that per-*tenant* versus per-*matter* is
undecided. It is worse than undecided: **AD-22 binds *tenant*-level actions** — *"granting or
revoking a scope, changing configuration"* — while **FR-24 requires every entry to carry a
*matter***. A scope grant belongs to no *matter*. U8 legitimately invents a sentinel *matter*; U7
legitimately writes configuration changes to a separate *tenant* chain; U6 legitimately writes grants
to neither. Three chains, or one chain with a lie in it.

**(c) Contention as a correctness problem, not a performance one.** AD-14 requires **every
retrieval** to be recorded, and AD-22 requires the action to **fail** if its entry cannot be written.
Read-path availability is therefore bounded by write contention on the chain head, during an
ingestion writing register entries continuously. AD-22's escape (*"read-only functions may
continue"*) applies only where the store *cannot be written at all* — not to a lock timeout.

**Tightening — split AD-22 and add the missing contract:**

> **AD-22a (atomicity)** — unchanged.
>
> **AD-22b (sequence and chain).** The sequence is allocated **inside the entry's own transaction**
> from a chained head row, never from a non-transactional sequence generator; a gap is therefore
> impossible by construction rather than detectable after the fact. `nextval` and any
> `Sequence`-backed column on an evidential table fail the build (*structural property*). The chain
> is scoped **per (*tenant*, *matter*)**, and each *tenant* additionally carries **one matterless
> chain** for *tenant*-level acts — provisioning, scope grants and revocations, configuration
> changes, backups, restores. FR-24's "every entry carries a *matter*" is amended to "every entry
> carries a *matter*, or names the *tenant* chain explicitly."
>
> **AD-22c (volume).** High-volume machine-generated events — *failure register* entries, retrieval
> records, per-unit ingestion commits — are appended to a **per-worker partition ledger** that is
> not chained per entry. Each partition is sealed at a configured interval and its digest is
> appended to the *matter* or *tenant* chain as one entry. The chain therefore carries O(intervals),
> not O(*pièces*), and the tamper-evidence property is preserved over the digests. The interval and
> the partition count are configuration-as-data with a defined default, and the sealing act is
> itself an entry.

This also removes Open Question 3's contention risk from the critical path, which the U2 timed run
would otherwise have to answer before U8 can be built.

---

## H-4 — Restore is a sanctioned hard delete that passes the chain check

**Unit A — U4, the one store**, obeying **AD-30**: *"Rollback is dump restore plus re-tagging
recorded image digests — **never** `alembic downgrade`."* And **AD-32**: *"a restore into an empty
installation reproduces a tenant whose denominator, ranked orders, audit sequence and confidence
bounds are identical … with the AD-22 chain re-verified on restore."*

**Unit B — U8, the audit spine**, obeying **AD-7**: *"the audit record, the change log and the
register are append-only"*, and **AD-22**: truncation is detectable *"by a reader holding only the
export."*

**The incompatibility.** A restore replaces the live database with an earlier dump. Every entry
written after the dump is **destroyed** — a hard delete of the evidential record, executed by the
documented, single, blessed operation, with both units perfectly obedient. Worse, it is
**undetectable by design**: a truncation to an earlier *consistent* point produces a chain whose
every link verifies. AD-22's check detects a hole in the middle; it cannot detect that the record
now ends earlier than it did, because **nothing outside the restorable database records where the
head was.** The chain proves internal consistency, not currency.

This is the cleanest instance in the spine of "never hard-delete defeated with no unit disobeying".
It is also the operation most likely to be run on a bad day, by a support call, at a firm.

**Tightening — new AD:**

> **AD-35 — The chain head is recorded outside the restorable store; a restore that moves it
> backwards is named as a truncation.**
> - **Binds:** the audit spine, backup, restore, `upgrade.sh`, the support procedure.
> - **Prevents:** the one operation the spine blesses silently destroying the record the spine
>   exists to protect, in a way AD-22's own check cannot see.
> - **Rule:** on every chain seal (AD-22c) the head — chain scope, sequence number, chain value,
>   wall-clock and monotonic timestamps, application and schema versions — is appended to a
>   **head journal** held outside the restorable database: at minimum an append-only file on a
>   volume not covered by the dump, and a copy on every backup target. `upgrade.sh` records the head
>   at which its pre-migration `pg_dump` was taken. On start-up and on restore the application
>   compares the live head with the journal's latest: **a live head behind the journal is a
>   truncation**, is surfaced in the interface and in the *worklist* in the lawyer's language, is
>   named on the face of every subsequent export, and clears only by a recorded human *override*
>   with a reason (AD-25, AD-22). It is never repaired. A missing or unwritable head journal fails
>   start-up, on the same gate as AD-31's key.

---

## H-5 — The encryption-layer-split AD exists only in `.memlog.md`

Not a pair between two units so much as a pair between two readers of the same document — but it
blocks the schema, which is the irreversible decision, so it ranks here.

`.memlog.md` line 35 records a user decision of 21 July 2026 (the encryption layer split), and
**Open Question 1 in the spine is struck through as RESOLVED, pointing at "the encryption-layer-split
AD"**. There is no such AD. The spine has AD-1…AD-34 and no more. **AD-31 still reads:
*"Unresolved and recorded, not smoothed … Which layer carries at-rest encryption for the two
searchable surfaces is an open question below."*** FR-47 in the PRD *was* amended and carries the
answer; the spine's own binding text was not.

**Unit A — U4, the one store**, whose card says *"Blocked on Open Question 1 before the schema is
written"*, reads the struck-through question, finds it resolved, and needs the rule — which is not
in any AD it binds.

**Unit B — U6, identity, sessions and keys**, binds **AD-31** and reads the live AD-31 text, which
says the question is open. U6 legitimately builds the startup gate for **one** layer (the application
key), because the second layer is, in the AD it binds, undecided. The volume-encryption half of the
fail-closed gate — the half that protects the *vector column and the deterministic text index*,
i.e. the two surfaces that hold every embedding and every word of every *pièce* — is then owned by
nobody.

**Tightening — write the decision into the spine as AD-31's rule, and delete the "unresolved"
paragraph:**

> **AD-31 (amended).** … Two surfaces are **named exceptions to application-layer encryption**: the
> `halfvec` vector column and the deterministic text index, neither of which can be indexed as
> ciphertext. They are protected by **volume- or cluster-level encryption on a machine the operator
> controls** — never a third party's volume service — so that a stolen disk or a restored backup
> yields nothing while both indexes remain buildable. Everything else — original *pièces*, extracted
> full text, OCR images, the *audit record*, the *failure register*, configuration, staged exports,
> the head journal (AD-35) and every backup artefact — is encrypted by the application's storage
> adapters. **Start-up fails closed on both layers**: a missing or unreadable application key, or a
> data volume the application cannot verify as encrypted, refuses to start with no
> warning-and-continue. The AD-26 seeded-token test runs against the raw stores excluding the two
> named surfaces, which are asserted by the start-up gate instead. Recorded so it is not
> re-litigated: this is the resolution of spine Open Question 1, decided 21 July 2026; FR-47 was
> amended the same day.

Then mark Open Question 1 as closed **by AD-31** rather than by an AD that does not exist.

---

## H-6 — `ON DELETE CASCADE` defeats AD-7 without a call site

**Unit A — U4, the one store**, owns migrations. **Unit B — U5, the payload kernel**, owns the entity
relations in the ER diagram. Both obey **AD-7**: *"Bulk deletion, truncation or recreation of a
tenant's indexed material is reachable from exactly one named administrative entry point … Enforced
as a structural property: **no other call site exists**."*

**The incompatibility.** `ON DELETE CASCADE` is **not a call site**. It is a schema property, and
PostgreSQL executes it. The ER diagram gives `MATTER ||--o{ AUDIT_ENTRY`, `MATTER ||--o{
FAILURE_ENTRY`, `MATTER ||--o{ PIECE`, `PIECE ||--o{ CHUNK`. U5 declares those relations; U4 writes
the migration; a `CASCADE` on any of them is idiomatic, is what an AI agent writes by default, and
passes every static check the spine names. Then the **one blessed administrative entry point** —
which AD-7 authorises, with a human act and a reason — issues its `DELETE`, and the cascade removes
the *audit record* entries, the *failure register* entries and the *change log* rows that AD-7
declares append-only, **including the audit entry recording the deletion itself**.

The operation the spine designed to be the only irreversible act destroys its own evidence, and the
grep for "no other call site" is green.

**Tightening — amend AD-7's rule and add the check:**

> No foreign key in any migration declares `ON DELETE CASCADE`, `ON DELETE SET NULL` or
> `ON DELETE SET DEFAULT`; every reference to an evidential ledger — the *audit record*, the *change
> log*, the *failure register*, the head journal — is `ON DELETE RESTRICT`. The named administrative
> entry point performs a **state transition to `retired`**, never a `DELETE`: retired material is
> excluded from every read by the AD-14 entry point, is excluded from every *denominator* with its
> retirement stated as its own named count, and remains restorable by the inverse transition. The
> tokens `DELETE FROM`, `TRUNCATE` and `DROP TABLE` appear in **no** runtime module and in migrations
> only under a reviewed, dated allow-list naming the migration and its reason. Enforced as a
> *structural property* over the migration files, **and re-asserted against the live schema by the
> AD-2 job** — a `CASCADE` that reached a firm's database through a hand-run migration is otherwise
> invisible to a source-level grep.

---

## H-7 — An **exhaustive** set truncated by a capacity bound, or computed over a moving population

Two attacks on the same invariant; both hold.

**(a) The `LIMIT` that wears the exhaustive label.**
**Unit A — U9**, obeying **AD-20**: **exhaustive** is *"the complete match set over the whole indexed
corpus within one scope"*, set at one construction site, a constant there. **Unit B — the same U9, or
U16 consuming it**, obeying **AD-17**: *"Capacity bounds — pièce size, container depth, expansion
ratio, attachments per message, matters per tenant, **rows per export** — are configuration with
defined defaults."* At the *design target*, a common French word matches 40 000 *pièces*. No API
returns 40 000 rows and no browser renders them. U9 legitimately applies the configured bound. The
result set is now a top-k set carrying the constant `exhaustive`, and **AD-20's guarantee — that no
threshold in any configuration can produce an exhaustive label — is defeated by a bound AD-17
requires to exist.** This is "a similarity threshold wearing the costume of a proof" arriving as a
`LIMIT` clause.

**(b) The moving population.** **U9** returns an **exhaustive** set with its four AD-20
qualifications (*scoped denominator*, open register entries, `container-unopenable` of unknown
cardinality, OCR share). Those are four separate reads. **U12** is concurrently ingesting — AD-6
makes that the normal case, and an ingestion at the design target runs for a weekend. The four
qualifications are read at four instants; the absence claim is made over a population that grew
while it was being made. FR-6's invariant (`submitted = in corpus + open register`) is asserted *by
a test that runs after every import job* — i.e. at quiescence — and displayed under concurrency.
AD-23 already lists *"every **exhaustive** result set"* among the artefacts that go stale on *"any
ingestion into the matter"* — but there is no rule that forbids **producing** one during an
ingestion, and AD-19 says the product must refuse rather than label a partial set.

**Tightening — amend AD-20's rule:**

> An **exhaustive** result set is **never truncated**. Where the match set exceeds the configured
> transport bound, the product returns the **count and the four qualifications** with status
> **exhaustive**, and the rows as an explicitly paginated cursor over **one stable snapshot**; a
> `LIMIT`, `top_k` or page size applied to a set constructed as exhaustive **downgrades its status
> to *suggestive* at the same construction site**, and no configuration can prevent the downgrade.
> Enforced as a *structural property*: the deterministic engine's constructor accepts no limit
> parameter.
>
> An **exhaustive** set and its four qualifications are computed **in one snapshot** — one
> repeatable-read transaction — and over a *matter* with **no open *import job***. Where an *import
> job* is open on the *matter*, the deterministic engine **refuses** and says so in the lawyer's
> language, naming the job and offering the *worklist* line; it never downgrades silently to
> **suggestive** and never returns a labelled partial set (AD-19).

---

## H-8 — `chunk_id` omits the extraction version: evidence mutates under a citation

**Unit A — U5**, obeying the Identity convention and **AD-9**: *"`chunk_id` = deterministic function
of (pièce_id, position, chunking configuration)."* The extractor is not in it.

**Unit B — U10, the extraction bench**, obeying **AD-28**: *"Every extracted pièce records the
extraction method **and the extractor version** … so a re-extraction under a new engine is
**detectable rather than suspected**."* AD-28 therefore makes re-extraction a first-class capability
— and it must be, because `pypdf` → Docling+Tesseract fallback, a Tesseract upgrade, or a
`password-protected` retry all re-extract.

**The incompatibility.** A re-extraction produces **different text at the same position** under **the
same `chunk_id`**. AD-17 makes the re-write idempotent-by-identity; AD-9's one writer upserts. The
*retained extract* that a *judgement* cites (`RETAINED_EXTRACT }o--|| CHUNK`) now resolves to
different words. AD-10 half-catches this — *"exact-containment verification resolves against the full
text at the moment an extract is shown, and a resolution that fails marks the containing export
degraded"* — but that catches only the case where the extract **no longer appears**. A re-extraction
that yields *better* text, containing the extract in a different place with different surroundings,
**resolves successfully and silently**, and the justification recorded in the *audit record* now
rests on evidence that changed after the fact. Note that AD-11 puts `model_id` and `model_version` on
every chunk for exactly this reason on the embedding side; the extraction side has no equivalent in
the identity function.

AD-10 already supplies the fix's raw material: *"extraction produces two artefacts with separate
identities **and versions**."*

**Tightening — amend the Identity convention and AD-9:**

> `chunk_id` = deterministic function of (`pièce_id`, **`full_text_version`**, `position`, chunking
> configuration), where `full_text_version` is AD-10's version identity of the stored full text —
> which itself includes the extraction method and the extractor version (AD-28). A re-extraction
> therefore produces **new chunks with new identities**; the previous chunks are retired by state,
> never deleted (AD-7); every *retained extract*, *judgement* and export citing a retired chunk is
> marked **stale** by AD-23's trigger list, to which "a re-extraction of a *pièce* in the *matter*"
> is added. Enforced by test: re-extract a *pièce* under a changed extractor version and assert that
> no `chunk_id` collides and that every citing artefact is stale.

---

## H-9 — Stage-1 exclusions leave the population the *confidence bound* reports on

**Unit A — U14, the relevance cascade**, obeying **AD-18**: stage 1 is *"deterministic filters and
near-duplicate grouping — content-hash dedup, document type, participant roles, **dates against the
case theory period**, obvious noise"*, and stage 3 runs *"only on the uncertain band that stages 1
and 2 could not separate."*

**Unit B — U17, the estimator**, obeying **AD-22/AD-23/FR-22**: the draw is *"random over the whole
discarded set within the user's RBAC scope"*, the population is frozen, the bound is hypergeometric
over M.

**The incompatibility.** AD-18 never says what stage 1 does with what it removes. Two legitimate
implementations:

- **(i)** stage-1 rejects are placed at the bottom of the ranked order → they are in the *discarded
  set* → they are in M → the bound covers them.
- **(ii)** stage-1 rejects are **excluded from the ranked order** → not in M → the bound is computed
  over a population that silently excludes every *pièce* the deterministic filters removed.

**AD-19 actively pushes toward (ii)**: *"**Unscored is not zero:** a pièce the model could not judge
is excluded from the ranked order and shown as unscored, not ranked last."* A stage-1 reject was
never judged by any model. Under (ii) the product produces exactly the failure AD-19 says it exists
to prevent — *"a pièce no model ever read, scored zero, sorted to the bottom, sitting inside the
population a confidence bound reports on"* — inverted: a *pièce* no model ever read, sitting
**outside** the population, with the sentence quoted to a court claiming a bound over "the
discarded". A `date-undetermined` *pièce* (an explicit enumerated value under the Absent-values
convention) failing a "date within the *case theory* period" filter is the concrete instance, and it
is the normal case for scanned material.

**Tightening — new AD:**

> **AD-36 — The cascade removes *pièces* from judgement, never from the population.**
> - **Binds:** the cascade, the ranked order, **the line**, the estimator, every *sampling run*,
>   every *confidence bound*, the *denominator*.
> - **Prevents:** the population a bound reports on being narrowed by a deterministic filter that
>   nobody reads as a filter, producing an honest-looking sentence about a set that excludes exactly
>   the material most likely to be wrongly excluded.
> - **Rule:** stages 1 and 2 decide **only** which *pièces* reach LLM judgement. Every *pièce* in the
>   *corpus* is, at all times, in exactly one of two sets: **the ranked order**, or the explicit
>   **unscored** set — and there is no third. A stage-1 or stage-2 rejection places the *pièce* in
>   the ranked order carrying its **rejection reason as an enumerated class**, never outside it.
>   The **unscored** set holds only *pièces* whose judgement failed (AD-19) and is displayed as its
>   own count wherever the sets are counted. A *sampling run*'s population is the *discarded set*
>   **plus** the unscored set, or the run's record states the exclusion and the AD-23 sentence
>   carries it in words. Asserted by test: a *pièce* with `date-undetermined` outside the *case
>   theory* period is drawable by a *sampling run*.

---

## H-10 — AD-2's stubbed endpoint requires the second Embedder that AD-11 forbids

**Unit A — U1, the fitness gates**, obeying **AD-2**: a CI job *"boots the whole application in a
network-isolated container with no outbound network **except a stubbed model endpoint**, and asserts
it starts, **ingests, indexes**, retrieves over both engines, ranks, places the line, writes an audit
record and exports."* Indexing requires embeddings. U1 stubs the endpoint. It runs **from week one**.

**Unit B — U11, the embedder**, obeying **AD-11**: *"**There is no fallback embedder at runtime**, in
any configuration **including test and development**: the port has exactly one **non-test**
implementation, no exception handler in the embedding path constructs an embedder, and **no
configuration key selects one outside the enumerated list**."*

**The incompatibility.** Note the asymmetry that makes this sharp: BGE-M3 is a **local** 568M model,
so unlike the language model it needs no network endpoint at all — AD-2's stub covers the *model
endpoint*, and the embedder is simply expected to be there. So AD-2's job, to "index", requires the
**real** embedder inside the network-isolated container. And AD-3 says *"exactly one artefact is built
and every installation runs it"*, so the CI container runs **the artefact**, and AD-16 forbids any
runtime module importing from the test tree — which is where AD-11's permitted "test implementation"
would live. Three consequences, none of which any AD decides:

- U11 wins strictly → **1.4 GB of model weights must be inside the CI image and inside the shipped
  `docker save` tarball**, and the AD-2 job's runtime is bounded by real embedding throughput from
  week one. That is a real packaging and CI-cost decision that nobody has made, and it is the correct
  one — but it must be *stated*, because the artefact's size and the "no model download step at
  install" property both follow from it.
- U1 takes the obvious shortcut → a stub embedder wired into the artefact. It cannot come from the
  test tree (AD-16), so it is a **non-test implementation selected by configuration** — exactly what
  AD-11 forbids, and U11's structural check fails the build, in week one, on the unit whose whole
  purpose is to fail the build.
- Somebody splits the difference with a configuration key that selects a stub embedder → **v1's exact
  defect** (a degenerate embedding selected by circumstance rather than by decision) reintroduced
  through the front door and blessed by a green build.

The collision lands in week one, on U1 and U11 — the first unit and one of the earliest.

**Tightening — amend AD-2 and AD-11 together. The decision to take is "the embedder is never
stubbed, anywhere":**

> **AD-2 (amended).** The network-isolated job runs the shipped artefact with **exactly one stubbed
> edge: the language-model endpoint.** The embedder is the real one, from weights **carried inside the
> artefact** — which is also what makes the on-premise install free of any model-download step, and is
> asserted as such: the AD-2 job fails if any embedder weight is fetched at start-up or at first use.
> The artefact's size and the job's wall-clock are therefore load-bearing and are recorded per run,
> alongside the AD-18 stage-3 share, as figures a regression would otherwise hide.
>
> **AD-11 (amended).** The `Embedder` port has exactly one implementation in the artefact, in every
> environment including CI and the hosted dev tier. **There is no stub embedder**, no
> configuration-as-data key and no wiring variable that selects one, and the test tree's fakes are
> unreachable from any runtime module (AD-16). Where a test needs to avoid the cost of real
> embedding, it substitutes at the **port boundary inside the test process** and never inside a
> running artefact. Enforced as a *structural property*: exactly one class implements `Embedder`
> under `adapters/`.

If the cost of real embedding in CI proves prohibitive after U2 measures it, the fallback is a
*second* AD-2 job tier — a fast job that skips indexing and a full job that does not — never a stub
inside the artefact. State that now, because the pressure will arrive in week one.

---

## H-11 — *Custodian* is a required scalar on the chunk and a set on the *pièce*

**Unit A — U5**, obeying **AD-9**: the one chunk writer takes *custodian* as a **required argument
with no default**, singular; and the Absent-values convention gives `custodian-undeclared` as the
explicit scalar absence.

**Unit B — U12**, obeying **FR-4** (bound to AD-8): *"Importing folder A then folder B, where B
contains a copy of a file in A, produces one pièce with two recorded provenance paths … **Every
custodian associated with either copy is retained on the pièce as a queryable set. Deduplication may
never collapse two custodians into one; in ordonnance 145 CPC work, who held a document is frequently
the fact in issue.**"* The ER diagram agrees: `PIECE ||--o{ CUSTODIAN_LINK`.

**The incompatibility, in three moves.** (1) The chunk carries one custodian; the *pièce* carries a
set. (2) On the second import, **AD-17 makes the unit a no-op** — *"Re-processing an already-committed
unit is a no-op that reports itself"* — so the chunk is never rewritten and **the second custodian
never reaches it**. (3) There is no re-stamp operation to fix it: AD-13 removed re-stamping from the
system, and while AD-13's text is about *scope*, its structural consequence (no rewrite path exists)
applies to every stamped attribute.

Result: a deterministic search filtered by *custodian* returns different answers depending on whether
the implementer joined `CUSTODIAN_LINK` (U12's model) or read `chunk.custodian` (U5's model), on the
question the spine itself names as *"frequently the fact in issue"*. Neither unit disobeys anything.

**Tightening — amend AD-9 and generalise AD-13:**

> **AD-9 (amended).** The one chunk writer takes *tenant*, *matter*, *RBAC scope* and *custodian* as
> required arguments. *Custodian*, like *RBAC scope* (H-1), is a **write-time required input and not
> a persisted chunk column**: custodianship is a set on the *pièce* (`CUSTODIAN_LINK`), is unioned —
> never replaced or collapsed — by every *import job* that admits the same content, and is resolved
> by join at read time through the AD-14 entry point. No column named or aliased as a custodian
> exists on `chunk`. Enforced as a *structural property*.
>
> **AD-13 (amended, one sentence).** The rule generalises: **no mutable attribute of a *pièce* or a
> *matter* is denormalised onto an indexed row.** The enumerated set of attributes that may appear on
> a `chunk` is exactly: `chunk_id`, `pièce_id`, `tenant`, `matter`, `position`, `full_text_version`,
> chunking configuration identity, schema version, `model_id`, `model_version`, the vector, the
> reserved external-authority reference. Any other column fails the build.

That enumeration is worth more than the rule that produces it: it is the one place an AI agent will
look before adding a field to the frozen schema.

---

## H-12 — `supersedes`: AD-9 says nothing writes it; FR-4 says ingestion must

**Unit A — U5**, obeying **AD-9**: *"Two extension points are reserved now and **written by nothing in
this increment**: an external-authority reference on a chunk … and a **`supersedes` relation between
pièces**."* U5 reserves an unvalidated, unindexed, semantics-free column.

**Unit B — U12**, obeying **FR-4** (U12's own FR): *"The same content at the same path with **changed**
content produces a new pièce carrying a `supersedes` relation to the previous one."*

**Unit C — U18**, obeying **FR-46**: *"Superseded pièces (FR-4) are marked as superseded and the
current version is named."* And **U17**, obeying FR-4's *"not counted as two independent draws by a
sampling run."*

**The incompatibility.** An AD states a falsehood about the increment's own scope, and three units
depend on the relation it says is unwritten. Because AD-9 declares it inert, U5 fixes no semantics,
and U12 then decides unilaterally: direction (new→old or old→new), chain versus tree, acyclicity,
and — the load-bearing ones — **whether a superseded *pièce* stays in the ranked order** (U15 needs
this), **whether it stays in the *discarded set* population** (U17 needs this: FR-4 says it must not
be double-drawn), and **whether it stays in the *denominator*** (U12 and U16 need this, and AD-7 says
nothing is removed).

**Compounding, H-12b — supersession is keyed on a fact AD-8 says is not identity.** FR-4's condition
is *"the same content **at the same path**"*. AD-8: *"**Provenance path is not part of identity**."*
So: `folderA/contrat.pdf` and later `folderB/contrat.pdf` with one byte changed → different content,
different path → **two independent *pièces*, no supersedes relation**, ranking independently, drawn
independently, exported as two rows. The mechanism FR-4 built to stop "a re-imported edited file
silently doubles" is defeated by the ordinary case, and AD-8 is why.

**Tightening — amend AD-9 and AD-8:**

> **AD-9 (amended).** One extension point is reserved and written by nothing in this increment: the
> external-authority reference on a *chunk*. **`supersedes` is not reserved — it is written in this
> increment**, by the ingestion use case only, and its semantics are fixed here: it points **from the
> newer *pièce* to the older**, is acyclic (enforced by constraint), forms a chain and not a tree,
> and both *pièces* remain in the *corpus*, readable and searchable (AD-7). A superseded *pièce*
> **remains in the *denominator***, is **excluded from the ranked order and from every *sampling
> run*'s population** (its current version stands for it), and is **marked as superseded on the face
> of every export** naming its current version.
>
> **AD-8 (amended).** Supersession is **never derived from a provenance path**, because path is not
> identity. A `supersedes` relation is created only by (i) an explicit user act with a recorded
> reason, or (ii) a declared, configured, audited rule whose output is a **worklist line offering the
> relation**, never a silent write during ingestion. Where no relation is created, two versions of one
> document are two *pièces* and every surface counting them says so.

---

## H-13 — The *failure register* entry has three writers and no compare-and-set

**Unit A — U12**, obeying **AD-7** and FR-5: owns `open → resolved` on a successful re-ingest, and
runs the **bulk retry** over a filtered set (2 800 entries, one audit entry for the set).

**Unit B — U16**, obeying **AD-7**'s state machine (`RegisterOpen --> RegisterOverridden`) and FR-25:
owns `open → overridden` via an *override* with a mandatory reason.

**Unit C — U10**, obeying **AD-28**: an extraction subprocess crash creates an entry.

**The incompatibility.** AD-7 says entries are *"resolved by state change and never removed"* and
AD-22 makes each write atomic with its audit entry. **Two atomic writes still race.** A bulk retry
runs in the queue (AD-6) while a lawyer overrides one of its entries in the SPA. Whichever commits
second wins, unconditionally, because nothing in the spine requires a transition to be conditional on
the observed prior state.

The damaging ordering is override-then-retry-succeeds: the *pièce* is in the *corpus*, and the
*audit record* permanently holds an *override* in which a named lawyer states a reason for
deliberately excluding a document that was in fact ingested. FR-5 explicitly calls that shape a
defect — *"it forces a lawyer to record in a permanent audit record that she deliberately excluded a
document she could in fact have opened"* — and AD-7 makes it unerasable.

**Tightening — new AD, which also closes H-14 and H-15:**

> **AD-37 — Every stateful entity has one owning use case per transition, and every transition is a
> conditional commit.**
> - **Binds:** the *failure register*, **the line**, *pins*, *validation acts*, *sampling runs*,
>   *import jobs*, grants, configuration rows, *ranking versions*, the *change log*.
> - **Prevents:** two obedient writers racing on one row; a retry mutating twice; a stale read used to
>   compute a write. None of these is visible to a code review, and none is decidable by a static
>   check over a single file.
> - **Rule:** the spine carries **one table naming, per entity, the owning use case of each state
>   transition**; a transition performed anywhere else fails the build (*structural property*: the
>   entity's state column is written by exactly one module). Every transition is a **conditional
>   commit**: the write names the state it observed, and a transition whose precondition no longer
>   holds **fails loudly** into the *failure register* or the *worklist* with an enumerated class —
>   it never overwrites and never silently no-ops. Every use case that computes a value from a read
>   and then writes it performs the read and the write **in one transaction at repeatable-read or
>   stronger**, and the isolation level is a declared property of the use case, not of the adapter.
> - **The ownership table is part of this spine** and every unit adds its entities to it before its
>   first write.

For the register specifically: `open → resolved` is owned by U12 and conditional on `open`;
`open → overridden` is owned by U16 and conditional on `open`; a retry that succeeds against an
`overridden` entry produces a *worklist* line offering to reverse the *override*, which is a new
audit entry (AD-7), not an erasure.

---

## H-14 — **The line**, *pins* and a *sampling run*: three writers, no conditional commit

**Unit A — U15**, obeying **AD-23** and FR-17/FR-43: owns `LINE_POSITION` and `PIN`.

**Unit B — U17**, obeying FR-22/FR-23: freezes the population (recording *ranking version*, line
position, scope and the **explicit identifier list**), and — in the same unit — *"offers to move **the
line** or to pin (FR-43)"* when K > 0.

**The incompatibility.** U17 both requires the line frozen and owns the surface that moves it, while
U15 owns the row. Two users, one *matter*: A completes a *sampling run*; B moves the line. FR-22 says
a line move during a run *"marks the run as invalidated-in-flight"* — but **nothing makes the run's
completion a conditional commit against the recorded line position.** AD-22 makes the completion
atomic with its **audit entry**; it does not serialise it against the line. AD-13 requires a
long-running job to re-resolve **scope** at every unit of work and says nothing about re-resolving the
**population's** other recorded inputs.

So the *confidence bound* — the north star, copyable as text, quoted to a court — is computed and
committed over a population whose defining cut moved. Both units obeyed every AD.

The same shape holds for *pins* (U15 writes; U16's triage table writes; both change the
retained/discarded views and therefore M) and for a second *sampling run* started while a first is
open.

**Tightening — AD-37 above, plus one clause in AD-23:**

> **AD-23 (added clause).** An action that produces an artefact carrying a version identity **commits
> only if every input recorded in that identity is unchanged at commit time**, verified in the same
> transaction as the write. A changed input fails the commit into the artefact's `invalidated` state
> with a *worklist* line naming which input changed — never into a produced artefact. This applies to
> a *ranking version*, a position of **the line**, a *sampling run*'s completion, a *confidence
> bound*, an **exhaustive** result set and every export.

---

## H-15 — Queue state versus the application ledger, and quarantine inside the failing transaction

**Unit A — U12**, obeying **AD-17**: *"each pièce is one committed unit of work against an
**application-owned ledger** keyed by its identity"*, and *"a unit that kills the worker is
quarantined after a configured number of attempts as its own register entry and the job proceeds."*

**Unit B — U16**, obeying **AD-6**: *"A user-visible progress figure is read from committed state,
never held in a process."* Procrastinate's job table **is** committed state, in the same PostgreSQL
(AD-5), and is cheaper to query than the ledger.

**Incompatibility (a) — two authorities for one fact.** U12 counts committed ledger rows; U16 counts
Procrastinate rows. They disagree during retries and after quarantine: a poison unit is `failed` in
the queue and `open` in the register, an in-flight retry is `doing` in the queue and absent from the
ledger. FR-2's *"processed count against the submitted count"* has two values, and FR-7's
"newly indexed" versus "already present" counts become the racy quantity FR-7 exists to prevent.

**Incompatibility (b) — the quarantine write is inside the transaction it is quarantining.** AD-17
does not say where the register entry for a poison unit is committed. The natural implementation
writes it in the job's exception handler, i.e. **inside the failing unit's transaction**, which rolls
back with the failure. The unit is retried, fails, rolls back, is retried… **exactly the failure
AD-17 names in its Prevents clause** — *"a resume that resumes onto the unit that killed the worker
and never completes"* — reached through the letter of AD-17. Worse, if the worker is killed by the
OS (OOM on an oversized *pièce*, which AD-17 anticipates), no handler runs at all and there is no
attempt counter anywhere but the queue — the authority U12 was told not to use.

**Tightening — amend AD-17:**

> The **application-owned ledger is the single authority** for a unit's state and for every
> user-visible progress figure; the queue holds no state any read path consults, and no module outside
> `adapters/store_postgres/queue` may query a queue table (*structural property*). The attempt counter
> lives in the ledger, is incremented in a **separate transaction committed before the unit's work
> begins** — so that an OS-level kill still advances it — and the quarantine transition and its
> *failure register* entry are committed in a transaction **independent of the failing unit's**. A
> unit whose attempt counter exceeds its configured bound is never dispatched again. Asserted by test
> with an induced `SIGKILL` mid-unit, not only an induced exception.

---

## H-16 — The *denominator* has no arithmetic for cardinality `unknown`

**Unit A — U12**, obeying **AD-17** (*"the submitted set is frozen at the completion of
enumeration-and-expansion"*) and FR-6/FR-57.
**Unit B — U16**, obeying FR-6/FR-28: renders *"97 200 / 100 000 indexed · 2 800 not indexed"*
persistently.
**Unit C — U17**, obeying FR-22/FR-23: M is the size of the *discarded set*, and the sentence states
it out loud.

**The incompatibility.** FR-6 asserts an exact identity — `submitted = in corpus + open register` —
over a quantity that, by FR-57, **is not a number**: a `container-unopenable` entry *"stands for an
unknown number of pièces"* and carries cardinality `unknown`. FR-6 then adds a *fourth* named count
(filesystem noise, *"its own named line in the denominator"*) while forbidding a third bucket. And
FR-3 puts `extracted-empty` in the register and explicitly **not** in the corpus.

Three legitimate implementations of `submitted`: known *pièces* only; known + 1 per unopened
container; known + a configured expected-cardinality estimate. Three legitimate answers to whether
noise is inside the total. **Every one of them satisfies AD-17 and FR-6's words**, and they produce
different numbers on the home screen, in the completion summary, in the export's face and inside the
*confidence bound* sentence.

**Tightening — new AD (the *denominator* is a record, not an integer):**

> **AD-38 — The *denominator* is a named record of disjoint counts; `unknown` never enters an
> arithmetic total.**
> - **Binds:** ingestion, the *failure register*, the home screen, every **exhaustive** claim, every
>   export, the estimator, the capacity check.
> - **Rule:** the *denominator* is one record with exactly these fields, all disjoint, all displayed
>   with their own names wherever any of them is displayed: `submitted_pieces` (post-expansion,
>   frozen at enumeration); `in_corpus`; `open_register_entries`; `excluded_as_noise`;
>   `retired`; and **`unknown_cardinality_entries`** — the count of open entries standing for an
>   unknown number of *pièces*. The invariant is
>   `submitted_pieces = in_corpus + open_register_entries`, over **known** *pièces* only;
>   `excluded_as_noise` and `retired` are outside it and are stated separately;
>   `unknown_cardinality_entries` **is never summed into any total** and is rendered in words
>   (*"1 archive unopened, contents unknown"*) on every surface carrying a total. A *confidence
>   bound* whose population record has `unknown_cardinality_entries > 0` states that fact in the
>   sentence. Asserted by test at the *design target* and by a type: the *denominator* has no
>   `int` representation anywhere in the source.

---

## H-17 — Near-duplicate family identity is not required to survive into the ranked order

**Unit A — U14**, obeying **AD-18**: *"Near-duplicate families are judged as a family with one
representative; members keep their own identity, provenance and custodian."*
**Unit B — U15**, obeying AD-23: produces one ranked order with a deterministic recorded tie-break.
**Unit C — U17**, whose *"unit of the draw (pièce or near-duplicate family)"* is explicitly **deferred**
to the estimator unit.

**The incompatibility.** The deferral is honest, but it defers a decision **U15 has to have already
made**. If U15 fans the representative's judgement out to members and does not carry the family
identifier into the ranked order (nothing requires it), then U17 **cannot** draw by family even if it
decides to — the information is not there, and it is not cheaply recoverable at the design target.
U17 then draws 40 members of one family as 40 independent draws; the hypergeometric bound assumes
independence it does not have; **the bound is wrong in the unsafe direction** (the effective sample is
smaller than N). FR-4 anticipates exactly this hazard for *supersedes* — *"not counted as two
independent draws by a sampling run"* — and AD-18 legitimises the opposite for families by saying
members keep their own identity.

The fix is cheap now and expensive later, which is the definition of a spine decision.

**Tightening — amend AD-23's *ranking version* definition:**

> The ranked order's recorded output carries, per *pièce*: its rank, its score or its enumerated
> rejection class (AD-36), **its near-duplicate family identifier and whether it was the family's
> judged representative**, and its `supersedes` state. The near-duplicate **grouping itself is part
> of the *ranking version*'s identity** — a change to the grouping threshold produces a new version —
> so that whichever draw unit U17 validates, the information the estimator needs is present and
> immutable. The threshold's *value* remains deferred (Open Question / OQ-21); its *presence in the
> version identity* is not.

---

## H-18 — Database collation is unpinned; a restore changes the tie-break

**Unit A — U4**, obeying **AD-30**: rollback is a `pg_dump` restore, possibly onto a rebuilt machine.
**Unit B — U15**, obeying **AD-23**: *"Re-running a fixed ranking version over a fixed corpus
reproduces the same order, pièce for pièce … **The tie-break is deterministic and recorded in the
version** — never the order a store happened to return, because ties are the normal case for
near-duplicates and a tie spanning **the line** would otherwise reshuffle set membership with no
recorded event."*

**The incompatibility.** A deterministic tie-break over French legal material will, in any natural
implementation, break ties on a title, a filename or a *pièce* identifier — all text. Text ordering in
PostgreSQL depends on `LC_COLLATE`, the ICU version and the collation provider. **No AD pins any of
them.** A restore onto a machine with a different libc/ICU (AD-30's own rollback path, a
disaster-recovery restore onto new hardware, or a base-image bump inside the digest-pinned bundle)
silently changes the order of tied *pièces*. Set membership across **the line** changes with no
recorded event — the precise thing AD-23 says it prevents — and **AD-32's restore assertion
(*"ranked orders … identical"*) fails, or worse, passes at reduced scale and fails at the *design
target***.

The same unpinned collation also silently changes AD-21's declared normalisation semantics, which are
the honesty of every absence claim.

**Tightening — amend AD-5 and AD-23:**

> **AD-5 (added).** The database's collation is pinned as part of the artefact: `LC_COLLATE`,
> `LC_CTYPE`, the collation provider and the ICU version are declared, are asserted at start-up
> against the running cluster, and a mismatch **fails to start** rather than warning. The AD-30
> restore procedure asserts them before restoring. Enforced by the AD-2 job.
>
> **AD-23 (added).** The recorded tie-break is computed over a **byte-ordered, collation-independent**
> key — the *pièce* identity hash — never over collated text. Asserted by test: the same *ranking
> version* over the same *corpus* reproduces the same order under two different `LC_COLLATE`
> settings.

---

## H-19 — A dev-tier read replica or connection pooler is "the same PostgreSQL"

**Unit A — U4**, obeying **AD-5** (*"PostgreSQL 18.4 … No component may introduce a stateful service
beyond it"*) and **AD-3** (environments *"differ by configuration rows and by which adapter
implementations are wired, never by which code was built"*).
**Unit B — U9**, obeying AD-14/AD-21: needs the deterministic engine to be fast at the *design target*
and has Open Question 4 hanging over it (*"the deterministic engine has no benchmark"*).

**The incompatibility.** On the hosted dev tier, a read replica or a routing pooler is one
configuration row away and is unambiguously *the same PostgreSQL*. U9 legitimately points read traffic
at it — AD-5 satisfied, AD-3 satisfied, AD-1 satisfied. A replica is **asynchronously stale**, so:
the four AD-20 qualifications and the result set come from different LSNs (H-7b, now guaranteed
rather than possible); AD-13's scope join can be resolved against a replica that has not yet seen a
revocation, defeating FR-14's bounded-interval revocation; and if any audit read (the chain's previous
entry, AD-22) touches a replica, **the chain forks**. On-premise there is no replica, so the class of
bug exists only in the tier where it is developed, or arrives later when a firm's IT adds one.

**Tightening — amend AD-5:**

> Exactly one PostgreSQL **endpoint**, in every environment. No read replica, no hot standby, and no
> pooler that may route a statement to anything but the primary. The application refuses to start
> against a connection where `pg_is_in_recovery()` is true, and asserts at start-up that its
> configured endpoint is the same one the queue and the vector store use. This is a *configuration
> divergence the dev tier makes trivially available*, which is why it is stated as a start-up refusal
> rather than as a convention.

---

## H-20 — Nothing forbids HTTP caching; a cached response replays an **exhaustive** claim

**Unit A — U16/U9**: the API returns a result set carrying its *truth status*.
**Unit B — U4/`deploy/`**, obeying AD-29: *"served by the same reverse proxy that fronts the API"*.

**The incompatibility.** AD-29 removed Next's caching architecture *"a liability under a per-matter
wall"* — and then put a reverse proxy in front of the API and said nothing about its cache
directives. A `GET /api/search?q=…` response cached for 60 seconds by the proxy, by the browser, or
by a React Router loader, is replayed after the population changed: **an exhaustive absence claim,
with its status and its qualifications intact, over a corpus that has moved.** AD-23's staleness
machinery binds *"every exhaustive result set"* — but there is no mechanism by which a cached HTTP
response learns it is stale, and AD-23 only forbids staleness being *resolved* by time, not
*created* by a cache. A shared proxy cache keyed without the session is additionally a cross-scope
leak: two users, two scopes, one cache key.

**Tightening — amend AD-29:**

> No response carrying *tenant* data is cacheable by any intermediary, by the browser, or by the
> client's router: every such response sets `Cache-Control: no-store` and carries no `ETag`,
> asserted **by test over every registered route** (AD-33's action registry supplies the
> enumeration). The reverse-proxy configuration is **part of the signed artefact**, and the AD-2 job
> asserts that no cache directive in it applies to `/api`. Client-side result caching in the SPA is
> permitted only for the duration of one rendered view and is discarded on any mutation, on any
> *matter* change and on any session change.

---

## H-21 — A user-supplied document password has no lawful channel to a worker

**Unit A — U12**, obeying **AD-6** (*"the HTTP layer validates, authorises, enqueues and returns"*) and
FR-5 (*"a `password-protected` entry offers a credential-supply action; supplying the password re-runs
ingestion for that pièce"*).
**Unit B — U6**, obeying **AD-31**: secrets *"are held **outside the application's own data stores**,
are never written to a log, a diagnostic, an export or an audit entry"*, and **AD-5**: PostgreSQL is
the only stateful service.

**The incompatibility.** The password must travel from an HTTP request to a worker. The only channel
is the queue. The queue is a table in the one PostgreSQL — **the application's own data store**.
Three legitimate resolutions, and the spine picks none:
(i) put it in the job payload — violates AD-31's spirit and nothing's letter, because *"secret"* is
undefined and a document password supplied by a user is arguably not one;
(ii) extract in the request — violates AD-6;
(iii) hold it in the API process — there is no channel, and AD-6 forbids the API doing the work.

Whichever ships, a *pièce* password sits in a Procrastinate argument column, appears in the queue's
own diagnostics, and survives into `pg_dump` and every backup. AD-31's seeded-secret test runs
against *"the raw stores"* — and would catch this, in CI, after it is built, if anyone seeds a
document password as a token. Nobody will, because it is not on the list of things that are secrets.

**Tightening — amend AD-31:**

> A third class is named: a **transient user-supplied secret** (a document or archive password, a
> credential supplied to resolve a *failure register* entry). It is written **only** to a dedicated
> encrypted, single-use, TTL-bounded credential row keyed by the *failure register* entry; the worker
> consumes it and the row is **purged**, which is a named and audited exception to AD-7 recorded in
> AD-7's own text (the purge writes an audit entry naming the entry, never the value). It never
> appears in a job payload, in a log, in a diagnostic, in an export or in a backup — backups exclude
> the credential table by name. The AD-26/AD-31 seeded-token test seeds a document password among its
> tokens.

---

## H-22 — Extraction subprocess stderr carries *pièce* content into the worker log

**Unit A — U10**, obeying **AD-28**: each extraction engine *"runs in a subprocess with its own
resource bound; a crash is a failure register entry, never a worker death."* To produce a useful
register diagnostic, U10 captures the subprocess's stderr and puts it in the entry's *"redacted
diagnostic"* (the Error-shape convention).
**Unit B — U13**, obeying **AD-26**: *"Filenames, paths, matter names, user names, content and query
text never appear in any output"*, and the Logging convention: *"No pièce content, no chunk content,
no filename … Log the class and the opaque identifier."*

**The incompatibility.** `pdfplumber`, `pypdf`, Docling and `extract-msg` all emit warnings
containing document fragments, object streams and filenames on malformed input — and malformed input
is the normal case at the *design target*. U10 captures third-party stderr it does not control and
writes it into a *failure register* entry that FR-5 makes **exportable** and that AD-26 makes a
projector's potential input. The word *"redacted"* in the Error-shape convention is doing all the
work, and **no check decides whether a diagnostic is redacted**. AD-26's seeded-token test runs
against *registered projectors*, not against subprocess stderr.

**Tightening — amend AD-28:**

> A subprocess's `stdout` and `stderr` are **never** propagated verbatim into a *failure register*
> entry, a log, a diagnostic or an export. The extraction adapter maps them to an **enumerated error
> class** and discards the text; where a free-text diagnostic is genuinely needed it is truncated,
> passed through the same redaction function the *failure register* uses, and that function's output
> is included in AD-26's seeded-token test — which is extended to seed tokens **inside malformed
> documents fed to each extractor**, not only inside the *corpus*. A subprocess launched without
> captured-and-mapped streams fails the build (*structural property*: no `subprocess` call outside
> `adapters/extraction` and no `stderr=None` within it).

---

## H-23 — "Extent" and "reading burden" have no declared unit

**Unit A — U15**, obeying FR-39: emits a review-effort estimate for the *retained set*, *"derived from
their extent"*.
**Unit B — U17**, obeying FR-22: *"the estimated reading burden derived from their extent (**the same
quantity FR-39 emits for the retained set**)"*, stated to a senior lawyer before the first verdict.

**The incompatibility.** The PRD says explicitly that it is the same quantity, and **no AD and no
Consistency Convention declares its unit.** Pages? Characters? Extracted-text bytes? Tokens? Original
file bytes (which for a 40 MB scanned PDF of 6 pages is wildly wrong)? Minutes? Two units, one
number, two units of measure — the oldest interface bug there is, in the sentence the product uses to
ask a senior lawyer for an evening of his time.

The Consistency Conventions table covers naming, identity, dates, absent values, error shape, result
envelopes, mutation, configuration, logging, translation keys, versions and language. **It does not
have a row for units of measure**, and this is not the only quantity affected: *pièce* size bounds,
the expansion ratio, the OCR quality signal, the storage footprint and the capacity check all cross
unit boundaries as bare numbers.

**Tightening — add a Consistency Convention row:**

> | Units of measure | Every quantity crossing a module boundary carries its unit in its **type and
> its name** — `extent_pages`, `size_bytes`, `duration_seconds`, `burden_minutes`. A bare `int` or
> `float` for a physical quantity fails review. **Extent** is defined once, in `core/domain`, as
> **estimated pages** (`extracted characters ÷ a configured characters-per-page constant`, or the
> true page count where the format supplies one), and both FR-22 and FR-39 call the same function.
> Wall-clock and burden estimates are rendered with an explicit stated basis, never as a bare number. |

---

## H-24 — User-facing HTTP is not idempotent; a double-click doubles a bulk *validation act*

**Unit A — U16**, obeying **AD-6**: the HTTP layer *"validates, authorises, enqueues and returns"*, and
FR-45: a bulk *validation act* over a selected set produces **one audit entry per *pièce***, each
marked `bulk` with a shared batch identifier.
**Unit B — U8**, obeying **AD-22**: every entry is atomic with its action, appended, never removed.

**The incompatibility.** FR-7 closes this for *import jobs* only (*"only one import job may be open on
a matter at a time"*). Nothing closes it for a bulk *validation act*, a line move, a pin, an export, a
*sampling run* start, or a bulk retry. A double submission — a double-click, a retried fetch on a slow
link, an SPA remount — produces **2 800 audit entries instead of 1 400, in two batches**, permanently,
in an append-only record whose §13 reader must distinguish 180 individual judgements from one gesture
over 1 400. The record now says the gesture happened twice, and AD-7 forbids removing either batch.
A retried **export** job likewise writes the third egress path's audit entry twice, and a reader
concludes two exports left the building.

**Tightening — amend AD-6:**

> Every state-changing HTTP request carries a **client-generated idempotency key**; the API stores it
> with the resulting action in the same transaction and returns the original result for any repeat.
> An action registered in the AD-33 registry as state-changing and reachable without an idempotency
> key **fails the build**. The idempotency key of a unit of work **covers its audit entry**: a
> re-executed unit that is a no-op under AD-17 writes **no new entry** and reports itself against the
> existing one.

---

# Separately flagged

## A. Unenforceable AD clauses — intentions no test or static check can decide

AD-33 states the rule: *"a property with no check is not a property."* Applied honestly to the spine
itself, the following clauses are not properties. That does not make them wrong — it makes them
**citable cover**: a unit can decline any sentence with no named check and invoke AD-33 for it.

| Clause | Why undecidable | Do this instead |
| --- | --- | --- |
| **AD-3** — *"a capability available on the managed dev tier but not on-premise **may not be depended on** by the core"* | No check decides "depended on". Only the two named exclusions are checkable. | Make it a **package deny-list** in `checks/`, plus H-19's start-up refusals. State that the deny-list is the check and is extended by name. |
| **AD-24** — *"Tenant-specific **behaviour** is not a greppable property and is not claimed as one — it is covered by AD-3's single-artefact rule"* | Honest, but AD-3's rule is itself uncheckable (above), so the chain terminates in nothing. | Name the real check: no conditional anywhere in `core/` reads a *tenant* identifier. That **is** greppable and is most of what was wanted. |
| **AD-19** — *"never a plausible-looking wrong answer"* | Undecidable as stated. Its two checkable parts are named (no model-reported confidence field; one derivation implementation). | Keep the sentence as rationale; move the two checkable parts into the Rule and label the rest *asserted by review*. |
| **AD-26 (iii)** — a projector may emit only values *"attested across a configured minimum number of pièces and matters"* | Per-projector checkable **only** if every projector declares its attestation counts machine-readably — and it is **not composable**: two projectors each above the floor can jointly identify. | Require the declaration in the registry, and add: *"the seeded-token test runs against the **union** of all registered projectors' output for one tenant, not projector by projector."* |
| **AD-27** — *"the expected wall-clock for the chosen profile is **stated honestly to the firm** before the job starts"* | A sales act, not a system property. Nothing in the product enforces it. | Make it a screen: the pre-flight check of AD-32 already computes capacity; have it also state expected wall-clock for the configured profile, and record the statement in the *audit record* with the *import job*. Then it is a test. |
| **AD-18** — stage 3 runs *"only on the uncertain band"* | "Uncertain" is configuration-as-data, so a configuration widening the band to everything satisfies the letter. AD-24's "no default disables its guarantee" protects the default, not a *tenant*'s edit. | Add a **floor**: a configuration that would send more than a configured share of a *matter* to stage 3 requires an explicit override with a reason (AD-25), and the measured share (already required) generates a *worklist* line when it exceeds the floor. |

## B. ADs that are really two or more decisions wearing one ID

Each of these will be cited by a unit, ambiguously, and the second clause is the one that gets
dropped — because it binds a different unit than the first.

| AD | Decision 1 | Decision 2 (and 3…) | Why it matters |
| --- | --- | --- | --- |
| **AD-7** | Nothing hard-deleted; ledgers append-only (binds everyone) | The *retained*/*discarded* sets are **views**, not memberships (binds U15 only) | A unit citing "AD-7" is ambiguous; and H-6 shows clause 1 needs its own enforcement text. |
| **AD-9** | One chunk write boundary with required arguments | Schema frozen + versioned + migration rejection rules | + Decision 3, the reserved extension points, which is where H-12's falsehood hides. |
| **AD-12** | *Tenant* stamped at write | Scope fails closed at read, including system identities | + Decision 3 — *"the failure register is inside this guarantee"* — a genuinely separate and load-bearing rule buried as a third clause of a long AD. |
| **AD-15** | The session/hashing/2FA stack | The rejected-library record | Decision 2 is a memo, not an invariant. It belongs in `.memlog.md` or a Stack note. |
| **AD-20** | Two truth statuses, one constant construction site each (binds U9) | The qualifications an **exhaustive** set must carry (binds U16, U18) | Decision 2 is the droppable one and it is the honesty of the absence claim. It should be its own AD with its own check. |
| **AD-22** | Atomicity of action + entry | Monotonic sequence from one authority | + chaining/continuity + refusal-when-unwritable. Four decisions, three concurrency consequences (H-3), one ID. |
| **AD-26** | The projector registry and structural content-freedom (binds U13) | The enumeration of exactly three egress paths + the outbound-adapter static check (binds U14, U18, everyone) | **U13 is predicted to be dropped.** Dropping it drops decision 2 with it — the check that no fourth egress path exists. Split them so the egress enumeration survives U13's cut. |
| **AD-30** | Offline signed packaging | Upgrade fails closed | + rollback is dump-restore (H-4) + version readability. Four. |
| **AD-31** | The no-key-no-start gate | Secret handling and rotation | + a now-stale "unresolved" paragraph (H-5). |

## C. Whole dimensions on which no AD speaks

Two units can therefore diverge on each of these without either disobeying anything.

1. **Concurrency and isolation.** *The largest silence in the spine.* Not one AD names a transaction
   isolation level, a locking discipline, a conflict-resolution rule or a retry-safety contract — in a
   system whose central artefacts are a monotonic chain, an ordinal cut and a frozen population,
   built by agents. H-3, H-13, H-14, H-15, H-24 are all instances. **AD-37 is the single highest-value
   addition in this review.**
2. **The principal taxonomy for non-user work.** AD-12 forbids an implicit superuser and defines only
   users. The backup (AD-32), the migration (AD-30), the capacity check, the queue's own work, the
   aggregate statistics (H-2 pair C) and the CI job have no defined principal. Proposed: exactly three
   kinds — **user**, **matter-bound job** (created only by an audited user action, carrying the
   initiating user's identity, re-resolving that user's scope per unit of work per AD-13), and
   **tenant-bound maintenance** (may read whole *tenant* partitions; **may not produce a result set,
   may not render content to any surface, and may not emit through the AD-26 registry**). Any fourth
   kind fails the build.
3. **Reads that are not retrieval** — H-2. The dimension, not just the instances.
4. **Result-set transport: pagination, cursors, stability, maximum sizes** — H-7.
5. **HTTP caching semantics** — H-20.
6. **Deletion at the schema layer (`ON DELETE`, `TRUNCATE`, cascade)** — H-6.
7. **Subprocess I/O discipline** — H-22.
8. **Collation, locale and byte-ordering of the database itself** — H-18.
9. **Units of measure** — H-23.
10. **Time.** `Clock` is a port and nothing else is said. On an air-gapped machine with a user-settable
    clock: FR-48's absolute and idle session lifetimes, AD-22's wall-clock timestamps and AD-23's
    staleness comparisons all read a clock that can move backwards. An *audit record* whose timestamps
    go backwards is a tamper signal to its reader. **Proposed:** audit entries carry both the `Clock`
    wall-clock and a monotonic counter; a backward wall-clock movement between consecutive entries
    appends its own `clock-adjusted` entry rather than leaving a reader to interpret it.
11. **Chunking-configuration change over an existing *corpus*.** AD-11 says changing the *embedder* is
    *"a background migration, never a rebuild"*; nothing says the equivalent for the **chunker**,
    whose configuration is in `chunk_id`. AD-9's *"a migration that cannot preserve every mandatory
    field"* preserves fields, not rows. **Proposed:** chunking configuration is immutable for a
    *matter* once its first *chunk* is written; a change applies only to *matters* with no *corpus*, or
    by an explicit audited re-chunk that writes new *chunks*, retires the old by state, and marks every
    citing artefact stale (the same shape as H-8).

## D. One more, worth naming: the register entry that can only exit through a defect

FR-5 says an entry whose only exit is an *override* is **a defect of FR-5**. Yet an
`extracted-empty` or `corrupt-file` entry resolved by fixing the source file produces **different
content** → a **different *pièce*** under AD-8 → the original entry can never be resolved by
successful ingestion, and its only exit is the *override* FR-5 calls a defect. At the design target
this accumulates permanently in the "not indexed" count the home screen displays forever.
**Proposed:** a register entry is keyed by (submitted path, submitted content hash, *import job*), and
a **`superseded-by-reimport`** transition exists — offered in the interface, audited, naming the new
*pièce* — so that resolution by a replacement is a first-class state and not a lawyer's recorded
admission of deliberate exclusion.

---

# Attacks that failed — the spine already closes these

Recorded so a one-person team does not spend time re-deriving them.

- **Post-filtering the wall.** Closed by **AD-14**: *"No result-set post-processing function accepts a
  scope, and none exists"*, as a structural property.
- **Cross-*matter* identity and dedup ambiguity.** Closed by **AD-8** — identity is (content, *matter*),
  the predicate is an equality, cross-*matter* dedup is explicitly forfeited.
- **The half-migrated re-stamp window.** Closed by **AD-13**: no re-stamping operation exists, so the
  long-running rewrite cannot fail halfway.
- **The silent fallback embedder** (v1's 256-dim hash). Closed by **AD-11** — one non-test
  implementation, no exception handler constructs one, no configuration key selects one. (The CI stub
  is H-10, a different problem.)
- **The *failure register* outside the wall.** Closed by **AD-12**'s third clause and **AD-21** — the
  register is searched separately, within scope, is visibly distinct, and never counts inside an
  **exhaustive** set. Its no-*matter* entries are gated on the administrative grant.
- **Model-reported confidence.** Closed by **AD-19** — no field parsed from a model response is named
  or used as a confidence; the derivation has one implementation; both are static checks.
- **A server-rendering second query path.** Closed by **AD-29**.
- **A second vector store, a second queue, a second search service.** Closed by **AD-5** plus the named
  exclusion list, which records the reason so it is not reconsidered by accident.
- **A demo or fixture layer overriding the backend** (v1's worst shape). Closed by **AD-16**'s four
  structural properties, and the v1 layer is deleted rather than disabled.
- **Concurrent *import jobs* racing the *denominator*.** Closed by **FR-7** — one open *import job* per
  *matter*, refused with a *worklist* line. (Concurrent **retries** are not closed — H-13.)
- **`alembic downgrade` on an unreachable machine.** Closed by **AD-30** — rollback is dump restore
  plus recorded digests, never a downgrade.
- **Staleness resolved by time, by a background job, or by being viewed.** Closed by **AD-23**, with a
  complete enumerated trigger list including any ingestion into the *matter*.
- **The false "risk of having missed" phrasing reintroduced by a translator.** Closed by FR-23's
  structural check across every locale's string set.
- **Backup asserted rather than exercised.** Closed by **AD-32** — restore is asserted in CI at reduced
  scale with the chain re-verified. (The residual is that the *hosted dev tier* may not be able to run
  it; CI does, which is the environment that matters for the check.)
- **An unbounded *worklist* one line per *pièce*.** Closed by FR-27's aggregation key, cap and
  partial-completion semantics.
- **Cross-*tenant* configuration or an operator console.** Closed by **AD-25** — per-*tenant*, inside the
  boundary, never cross-*tenant*, not an operator console.

---

# What to do first

The three that block irreversible units and should be settled before U4 and U5 write a schema:

1. **H-1** — decide whether `chunk` carries a scope column. It is a `NOT NULL` column in one AD and a
   forbidden denormalisation in another, and it is the payload schema, which is the one irreversible
   decision in the increment.
2. **H-5** — write the encryption-layer-split decision into AD-31. U4's card says it is blocked on
   exactly this, and the answer currently exists only in `.memlog.md`.
3. **H-8 / H-11 / H-12** — fix the `chunk` column enumeration and the identity function together
   (`full_text_version` in, scope out, custodian out, `supersedes` written and specified). All four are
   the same edit to AD-9 and the Identity convention, and all four are un-fixable after the first
   installation.

Then, before U8 and U12:

4. **AD-37** (H-13/H-14/H-15/H-24) and **AD-22b/c** (H-3). The concurrency contract is the largest
   silence in the spine and it is the one an AI agent will not fill correctly by default.
5. **H-4 + H-6** — the head journal and the `ON DELETE` prohibition. Both are cheap now and both defeat
   AD-7 completely if left.
