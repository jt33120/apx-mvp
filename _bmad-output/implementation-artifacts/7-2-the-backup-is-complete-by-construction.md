---
baseline_commit: f5999c9
---

# Story 7.2: The backup is complete by construction

Status: done

## Story

As **a firm whose only copy of a matter is on one machine**,
I want a tenant backup to carry everything that is the tenant's — every table, and the original
documents — and to say so by construction rather than by a list somebody maintained,
So that a restore reproduces the matter rather than a plausible-looking subset of it.

## Why this story exists

The B3/B4 audit (`b3-b4-audit-2026-08-15.md`), action items **C2** and **C3**.

### C2 — nine tables are missing, and nobody could have noticed

`_BACKUP_TABLES` (`store.py:250`) is a hand-written tuple. The model has **35** mapped tables, **29**
of them tenant-scoped; the tuple names **20**. Absent:

    artefact_stamp   case_theory_version   import_job   piece_open   ranked_entry
    ranking_version  register_override     sampling_run  validation_act

Three more are absent one layer down, keyed by a parent rather than by *tenant* and therefore
invisible to the question the tuple was asking: `import_unit`, `sampling_run_item`,
`sampling_verdict`.

A restore therefore loses every *ranking version* and every ranked order, every *case theory*, every
*sampling run* with its drawn families and verdicts — and therefore every *confidence bound* — every
*validation act*, every recorded *piece-open*, every *override*, and every freshness stamp. And it
loses them **while the audit record survives**: the restored record attests a validation act whose
ledger is gone, a bound whose draw is gone, a ranking version nothing can reproduce. The
tamper-evident chain verifies perfectly over a matter that no longer exists.

AD-32's own success criterion is the sentence this breaks:

> a restore into an empty installation reproduces a *tenant* whose *denominator*, **ranked orders**,
> audit sequence and **confidence bounds** are identical

Two of those four are in the missing set.

**The list's history is the finding.** Story 5.5 added `audit_chain_head`; 5.9 added `journal_gap`;
retro action B2 independently found `register_override` missing while fixing something else. Three
separate stories each added the one table they were thinking about, and **not one of them asked
whether the list was complete.** A hand-maintained list of what to back up cannot be reviewed,
because reading it tells you what is in it and nothing about what is not.

### C3 — the originals are not in it at all

AD-32's Rule opens by naming them first:

> the product produces a complete restorable backup of a *tenant* — **originals**, extracted text,
> index, *audit record*, *failure register*, configuration — on a schedule and on demand,
> **encrypted**, inside the *tenant* boundary

`backup_tenant` runs `SELECT * FROM {tbl}` over `_BACKUP_TABLES` and nothing else. The string
`original` does not occur in the function. The originals live on the filesystem under
`FilesystemOriginalStore`, and no code path copies them. The *pièce* viewer renders documents, not
only extracted text (Story 3.5a is why they are retained at all); after a restore it renders
nothing, and FR-13's exhaustive search returns *pièces* whose source document is gone.

And the word **encrypted** in that Rule is not honoured either. `apx/manage.py` writes the payload as
plaintext JSON. Content-bearing columns are ciphertext inside it, but `chunk.full_text` is the one
column AD-31 deliberately leaves in the clear — *"you cannot index ciphertext"* — and its stated
protection is the encrypted **volume**. A backup file is the one artefact that leaves that volume by
design, and it carried the entire searchable corpus in clear.

## Acceptance Criteria

**AC-1 — the plan is total, or there is no backup.** Every table in the mapped model is classified
before a single row is read: captured by its own *tenant* column, captured as a child of a captured
table through its **declared foreign key**, captured by a written predicate, or excluded by name
with a written reason. A table matching none of the four makes `backup_tenant` **raise** — a new
model that nobody thought about stops the backup instead of being quietly dropped from it.

**AC-2 — the same statement at build time.** A structural check (AD-33) asserts the plan is total
over the live metadata, that every exclusion carries a non-empty reason, and that no exclusion names
a table the model no longer has. It fails closed.

**AC-3 — every captured table round-trips, and the test is driven by the plan.** A seed populates
**every** captured table for one tenant; a backup, a wipe and a restore return each table's rows
byte-for-byte. The assertion iterates the plan, so a table added later is covered without the test
being edited — and a table the seed forgets is a failure, not a silent pass.

**AC-4 — AD-32's four named artefacts are reproduced through the read surfaces.** After the restore
the *denominator*, the ranked order with its *ranking version*, the audit sequence and the
*confidence bound* are identical **as read back through the product**, not merely as rows. A restore
that returns rows but leaves a read broken is not a restore.

**AC-5 — the originals travel, sealed, and the tenant boundary travels with them.** The bundle
carries every retained original for the tenant as the ciphertext it already is on disk — copied,
never decrypted, so taking a backup does not require the corpus key. After a restore, every retained
*pièce*'s original opens. A blob restored under another *tenant* fails authentication rather than
being served (the AAD binds it), so a mis-restored bundle cannot leak one firm's documents into
another's.

**AC-6 — the bundle is encrypted (AD-32's own word).** The tables payload is sealed with the
application cipher before it is written, so the deliberately-plaintext `chunk.full_text` does not
leave the volume in the clear. A bundle written without a usable key is refused; a bundle read
without one does not open.

**AC-7 — the recorded outcome states its coverage.** A backup that succeeded says how many tables
and how many originals it captured, so *"the backup succeeded"* stops being compatible with *"nine
tables were not in it"*.

## Tasks / Subtasks

- [x] T1 — `backup_plan.py`: the derivation, the written predicates, the exclusions with reasons,
      and `IncompleteBackupPlan` (AC-1).
- [x] T2 — the structural check `backup-plan-is-total`, registered in the three lockstep sites (AC-2).
- [x] T3 — `backup_tenant` / `restore_tenant` drive off the plan; `TenantBackup` loses its two
      special-case fields (AC-1, AC-3).
- [x] T4 — the originals: the `OriginalStore` port grows a sealed face; the bundle writer/reader
      (AC-5).
- [x] T5 — the bundle is sealed with the cipher; `manage backup|restore` speak bundles (AC-6).
- [x] T6 — coverage on the backup record (AC-7).
- [x] T7 — tests: the plan-driven round trip, the four artefacts through the read surfaces, the
      originals, the seal, the refusals.

## Dev Notes

The FK graph is already complete enough to derive the child captures — `import_unit → import_job`,
`sampling_run_item`/`sampling_verdict → sampling_run`, `piece_provenance`/`piece_custodian` → `piece`,
`chunk → piece`. Only `user_scope` has no declared foreign key, so it is the one written predicate.
`metadata.sorted_tables` is topologically ordered, which gives the restore a correct insert order for
free instead of the tuple's hand-ordering.

### References

- AD-32 (backup/restore are product features, exercised in CI), AD-31 (encryption at rest and its
  one named exception), AD-35 (the head journal), AD-40 (content addressing), AD-33 (structural
  properties).
- `b3-b4-audit-2026-08-15.md` — C2, C3.

## Dev Agent Record

### Completion Notes

**The plan replaces the list.** `apx/adapters/store_postgres/backup_plan.py` classifies every table
in `Base.metadata` by four rules — a `tenant` column, a declared foreign key to an already-captured
table, a written predicate, a written exclusion — and raises `IncompleteBackupPlan` naming every
table that matches none. Rules 1 and 2 run to a fixpoint over `metadata.sorted_tables`, which is
topological, so **the restore's insert order comes from the model** rather than from the order
somebody typed the old tuple in. The hand-written predicates of rule 3 are appended *after* that
fixpoint, because a link the model does not declare is a link `sorted_tables` cannot order.

There is exactly **one** rule-3 entry (`user_scope`, keyed by a globally-unique `user_id` with no
declared FK) and **zero** exclusions. The exclusion machinery exists anyway, with its own guards,
because it is the escape hatch: an unguarded one is how a table leaves a backup quietly.

**35 of 35, from 20.** The nine tenant-scoped tables C2 named, plus the three the audit's own
question could not see — `import_unit`, `sampling_run_item`, `sampling_verdict` are keyed by a
parent, not by *tenant*, so a sweep counting tenant columns did not reach them. Without
`sampling_run_item` and `sampling_verdict`, restoring `sampling_run` would have restored a draw with
no drawn families and no verdicts: the run's own numbers, and nothing that could produce them again.

**`TenantBackup` lost two fields.** `user_scopes` and `piece_links` were separate collections for
the tables the tuple could not express. Two representations of one fact is how a table could be in
the model, absent from the tuple *and* absent from the dataclass, with nothing anywhere saying so.
One `tables` collection now, derived.

**The originals travel sealed.** The `OriginalStore` port grew a backup face — `sealed_blobs`,
`read_sealed`, `put_sealed` — that never decrypts. Taking a backup therefore needs no encryption key
and never holds a firm's corpus in the clear, and a blob cannot be corrupted by re-encryption.
`sealed_blobs` enumerates the **store**, not a column: no table names the `ocr-layout` a *pièce* may
carry, so a list-driven backup would have left it behind while reporting that it had backed up the
originals.

**The bundle is sealed, and its inventory is inside the seal.** `chunk.full_text` is plaintext in the
database on purpose — you cannot index ciphertext — and volume encryption is what protects it. The
old backup file left that volume carrying the searchable corpus in clear. The payload is now
AES-256-GCM under the application key, and the `(content_hash, kind)` inventory is sealed with it, so
a restore puts back what the key attests rather than whatever is in the folder.

**An incomplete backup is recorded as a failure.** A retained *pièce* whose document is not on the
volume means the backup is not complete, and AD-32's subject is *the backup whose failure nobody
knew about*. The bundle is still written — a firm holding an incomplete backup is better off than
one holding none — and the *worklist* stops reading green over the hole.

**Two structural checks fired on this diff, and both were answered by strengthening.**
`filesystem-has-one-walk` (Story 7.1) caught two new enumerations:

- `restore_originals` read the bundle directory with `iterdir`. **Removed**, by sealing the blob
  inventory into the payload — which also closes a hole the check did not know about: a blob dropped
  into a bundle after it was written used to be restorable into the firm's own corpus.
- `sealed_blobs` enumerated the tenant's blob directory with `rglob`. **Routed through
  `walk_confined`**, so the tenant partition is a boundary there and not merely a naming convention:
  a symbolic link planted in that directory now refuses the enumeration instead of copying another
  firm's blobs into this tenant's backup.

Neither was answered with an entry on the permitted-walk list.

### Review

Run in-session across the three standing lenses rather than by a subagent fleet — stated rather than
implied, per action A2: **the coverage is one reviewer, not several**, and a defect a second
perspective would have found is not excluded by this section.

**The wrong referent** — six comparisons examined; three were wrong and are fixed:

1. `test_every_captured_table_returns_identically_after_a_restore` compared a backup of the source
   with a backup of the restore. Both denominators shrink with the defect, so it **passed on the
   pre-story code**. It now pins the set to the plan first, and fails.
2. `restore_originals` returned a `BundleCoverage` with `byte_size=0` — a zero under a name that
   means *how big the bundle is*. It has its own `RestoreCoverage` now.
3. Three tests asserted a literal `35`. Derived from `backup_plan()` / the metadata.

Checked and correct: `piece.content_hash` **is** the `OriginalStore` key (`core/app/ingest.py:239`),
so *retained pièces* and *blobs on the volume* are the same referent in the orphan count.

**The seams** — the check's fourth leg (`mapped - captured - excluded`) was **unreachable**, because
`backup_plan` raises rather than returning a subset. A leg that cannot fire is not a guard; removed,
and the totality statement is the `IncompleteBackupPlan` branch that is actually exercised.

**Which decision does this implement, and is every clause reachable** — AD-32's Rule, clause by
clause: originals ✓, extracted text ✓, index ✓, audit record ✓, failure register ✓, configuration ✓,
on demand ✓, encrypted ✓, inside the tenant boundary ✓, restore exercised in CI at reduced scale ✓,
chain re-verified on restore ✓, head reconciled ✓, a restore that moves the head backwards named ✓.
**Four clauses are not built**, none of them by this diff, all filed as **C10** below.

The asymmetry in `restore_tenant`'s table guard was examined and kept, with the reasoning written
into the code: a table the *backup* has and the plan does not is refused (its rows would be dropped
under a success), while a table the *plan* has and the backup does not is accepted (it is a table
added since, with no historical rows by definition — refusing it would make every schema upgrade
un-restorable from yesterday's bundle).

**Regressions proven against the pre-story store** (`git show HEAD:store.py`, run, restore): 3 of 5
in `test_backup_captures_every_table.py`, 3 of 5 in `test_restore_reproduces_the_matter.py`, 5 of 12
in `test_backup_bundle.py`. Recorded honestly: `test_the_denominator_is_identical` and
`test_the_audit_sequence_is_identical_and_still_verifies` pass **both ways** — those two tables were
in the old tuple — so they are regression guards on AD-32's other two named artefacts, not proofs.

### Found while building, not fixed here

**C10 — AD-32's four unbuilt clauses.** The Rule says more than this story implements, and each of
these is the Epic-5 retrospective's dominant shape (*a decision recorded and never implemented reads
exactly like one that was*):

- *"on a schedule"* — there is no scheduler. `backup_interval_hours` and `backup_status` can report
  a tenant overdue; nothing ever takes the backup that would clear it.
- *"the collation asserted before restoring (AD-5)"* — the string `collation` does not occur in
  `restore_tenant`, or anywhere in the store outside a docstring about integer ordering.
- *"a documented procedure at the design target"* — the reduced-scale restore is asserted in CI; the
  design-target procedure is not written down anywhere.
- *"Backup success or failure is a worklist line in the lawyer's language"* — `core/domain/worklist.py`
  emits freshness lines and FR-23's unfitness line and nothing else. This is the **C5 family**
  exactly: the mechanism is built and the half that tells the lawyer is not.

**A half-restore cannot be resumed.** The rows go back first (that transaction re-verifies the chain
and rolls back a corrupt bundle, so a rejected backup never leaves blobs on the volume); if the blob
copy then fails on a full disk, the tenant is no longer empty and a second `manage restore` is
refused. Named, not fixed: a resume flag is a decision about the operator's surface.

### File List

- `apx/adapters/store_postgres/backup_plan.py` — **new**: the derivation, the written predicate, the
  exclusions, `IncompleteBackupPlan`.
- `apx/adapters/store_postgres/store.py` — the tuple removed; `TenantBackup` collapsed to one
  `tables` collection; `backup_tenant` / `restore_tenant` driven by the plan.
- `apx/backup_bundle.py` — **new**: the sealed bundle format, the row codec (moved from `manage.py`),
  `Bundle` / `BundleCoverage` / `RestoreCoverage`.
- `apx/core/ports/originals.py` — the sealed face on the port.
- `apx/adapters/originals_fs/store.py` — `sealed_blobs` (through `walk_confined`), `read_sealed`,
  `put_sealed`; the atomic publish extracted.
- `apx/manage.py` — `backup` / `restore` speak bundles; `_originals()` refuses an unset
  `APX_DATA_PATH`; the outcome records its coverage.
- `apx/checks/backup_completeness.py` — **new**, registered in `registry.py`, `manifest.py`, `README.md`.
- `tests/adapters/test_backup_captures_every_table.py` — **new** (5).
- `tests/adapters/test_backup_bundle.py` — **new** (12).
- `tests/api/test_restore_reproduces_the_matter.py` — **new** (5).
- `tests/checks/test_backup_completeness.py` — **new** (7).
- `tests/adapters/test_backup_cli.py` — bundles + the coverage record (+3).
- `tests/adapters/test_backup_restore.py` — the wipe driven by the plan, in reverse order.
- `CLAUDE.md`, `README.md` — the gate numbers and the DR section.

### Change Log

| When | What |
|---|---|
| 2026-08-18 | Story written from C2 + C3; implemented; gate green at 106 checks / 2 173 tests. |
