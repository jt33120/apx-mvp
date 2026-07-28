---
baseline_commit: 480de8eeefe935da6d2a7179d401699b19a446ce
---

# Story 2.5: Idempotent ingestion with stable identity

Status: done

## Story

As a lawyer who might import overlapping folders,
I want re-submitting material to neither duplicate nor destroy it, and every *custodian* kept,
so that who held a document — often the fact in issue in *ordonnance 145 CPC* work — is never lost to deduplication.

## Acceptance Criteria

Sourced verbatim from `epics.md` §Story 2.5 (FR-4; AD-8 identity + supersession, AD-40 frozen schema, AD-9 `CUSTODIAN_LINK`, AD-7 no hard delete). Each is decomposed into the automatically-verifiable assertion the dev must make fire.

**AC1 — Identity is a deterministic function of (content, matter); path is not identity; never a counter.**
Given ingestion, when a *pièce* is identified, then its identifier is a deterministic function of **(content, *matter*)** — provenance path is not part of identity — stable across runs, processes and installations, never allocated from a restarting counter (per AD-8/AD-40, `(content, matter)` identity; *tenant* is inside identity per AD-12 because a *matter* is tenant-local).
- *Assert:* `piece_id(tenant, content_hash, matter)` is a pure function — same inputs ⇒ same id across two fresh processes / two `SqlStore` instances; the same bytes at two different paths ⇒ the same id; a different matter ⇒ a different id; no ingestion code path derives an id from a row count, sequence, `uuid4`, autoincrement or timestamp. (`identity.py` already provides this; the story's job is to prove stability by test and to make the persistence layer honour it.)

**AC2 — Re-import of the same folder into the same matter is a non-destructive no-op with a recognised-already-present line.**
Given a folder already ingested into a *matter*, when the same folder is imported again into that same *matter*, then the *corpus* count is unchanged, every prior *pièce* remains readable and **unmodified**, and the outcome **reports the recognised-already-present count as its own line** (the v1 defect was ids reused from 1, so a second upload overwrote the first — this AC exists to kill that).
- *Assert:* after a second `save()` of the same result, `inventory.in_corpus` is unchanged; a prior piece's row is byte-for-byte the same it was (id, `content_hash`, `full_text`, `text_identity`, `ingestion_timestamp`, first-seen representative `provenance_path` all unchanged — **no `merge`/overwrite**); and `SaveOutcome` exposes a distinct `pieces_already_present` count (≥ the number of re-recognised pieces) separate from `pieces_new`.

**AC3 — A file in two folders is one pièce with a set of provenance paths and a set of custodians; dedup never collapses custodians.**
Given the same content submitted from two provenance paths (in one job, or across two jobs, possibly under two custodians) into one *matter*, then it yields **one *pièce* with two recorded provenance paths** and **every *custodian* retained as a queryable set** — deduplication may never collapse two custodians into one (AD-9: custodianship is a set on the *pièce*, `CUSTODIAN_LINK`, **unioned — never replaced or collapsed — by every import job** admitting the same content).
- *Assert:* one piece row; `store.provenances(piece_id)` returns the set `{pathA, pathB}`; `store.custodians(piece_id)` returns the union `{custodianA, custodianB}` after two imports under different custodians; importing again under an already-seen custodian does not duplicate the set member.

**AC4 — The same file in two matters is two pièces (matter is in identity; no cross-matter dedup).**
Given the same file imported into two different *matters*, then it yields **two *pièces*** with separate identities — cross-*matter* deduplication is never performed (AD-8: the capability a Chinese wall exists to forbid).
- *Assert:* two distinct `piece_id`s, two rows, two independent provenance/custodian sets, one per matter; neither is visible from the other's matter.

**AC5 — (failure path) An induced write conflict yields exactly one copy and does not fail the job.**
Given the same *pièce* processed by two workers concurrently, when both persist, then the *corpus* contains **exactly one copy** and the job **does not fail** (idempotent, conflict-safe write — the second insert is absorbed, never a 500).
- *Assert:* a test that drives two `save()` calls for the same piece against the same store with an interleaving that forces a primary-key/unique collision (or directly simulates the `IntegrityError` on the piece insert) leaves exactly one piece row and raises nothing to the caller; the provenance/custodian union of both is present.

## Tasks / Subtasks

> Red-green-refactor, in order. Every task writes its failing test first. Gate after each with `export PATH="$PWD/.venv/bin:$PATH"` then `.venv/bin/ruff check .`, `.venv/bin/python -m pytest`, and `.venv/bin/python -m apx.checks`.

- [x] **Task 1 — Prove identity stability (AC1).** Add domain tests asserting `piece_id` / `content_hash` determinism across processes and path-independence, and matter/tenant sensitivity. No production change expected here beyond confirming `identity.py`; if any ingestion path is found allocating an id from anything but `(tenant, content_hash, matter)`, fix it. (Files: `tests/domain/test_identity.py` — extend or add.)

- [x] **Task 2 — The provenance set and the custodian set as link tables (AC3), schema (migration 0018).**
  - Add SQLAlchemy models `PieceProvenance` (`piece_provenance`) and `PieceCustodian` (`piece_custodian`) in `models.py`. Each: `id` `String(64)` PK = `sha256(piece_id \x00 value)` (deterministic set key — the same `_failure_id` pattern already in the store, so a repeated value is one row and a concurrent double-insert collides on the PK); `piece_id` FK → `piece.id` **`ON DELETE RESTRICT`** (AD-7, never CASCADE/SET NULL/SET DEFAULT), indexed; the value column `EncryptedText("piece_provenance.provenance_path")` / `EncryptedText("piece_custodian.custodian")` (AD-31 — a path/custodian is PII). **No unique constraint on the ciphertext column** — AES-GCM is randomised and cannot be matched/grouped in SQL (`crypto_types.py`); the deterministic `id` PK is the set key instead.
  - Write migration `0018_piece_provenance_and_custodian_sets.py` (`down_revision = "0017_import_job_ledger"`): create both tables; **backfill** each existing `piece` row's scalar `custodian` and `provenance_path` into the new link tables (compute the deterministic id from the row's `id` and the *decrypted* value, re-encrypt into the link column — reuse the cipher exactly as `encrypt_backfill` does); **then drop the `piece.custodian` column** (AD-9: *no* custodian column may exist on `piece`). Keep `piece.provenance_path` as the first-seen **representative** (AD-8 permits one recorded attribute; four readers use it — see Dev Notes). `DROP COLUMN` is not one of AD-7's forbidden tokens (`DELETE FROM`/`TRUNCATE`/`DROP TABLE`) and preserves data (backfilled first) — provide a `downgrade()` that re-adds the column and back-fills the representative. Confirm `alembic upgrade head` and `downgrade` both run clean on SQLite and are reversible.

- [x] **Task 3 — Non-mutating, conflict-safe, union-always persistence (AC2, AC3, AC5).** Rewrite the piece loop in `store.save()`:
  - Replace `session.merge(Piece(...))` with **insert-if-absent**: classify each piece as *new* vs *already-present* (via `session.get(Piece, id)` **and** a local `seen: set[str]` so two copies within one save are handled), **never overwrite an existing row** (AC2 "unmodified"). Under concurrency the classifying read is racy, so guard the insert with a savepoint (`session.begin_nested()`) and treat an `IntegrityError` on the piece PK as *already-present* (AC5 — exactly one copy, no raise).
  - On **every** piece (new or already-present), **union** its `provenance_path` and its `custodian` into the link tables via the deterministic-id insert-if-absent (savepoint + `IntegrityError` → skip), so a second import adds the new path/custodian and never collapses the set (AD-9). The first-seen import also sets the piece's representative `provenance_path` scalar; re-imports never touch it.
  - Extend `SaveOutcome` with `pieces_new: int` and `pieces_already_present: int` (keep `pieces_written` as an alias for `pieces_new` to avoid churning callers, or migrate the one asserting test). The worker path (`_persist_unit`, `audit=False`) benefits automatically since it calls the same `save()`.
  - Add `store.provenances(piece_id) -> set[str]` and `store.custodians(piece_id) -> set[str]` reads (decrypt + `set()`), for the AC3 assertions and future surfaces.

- [x] **Task 4 — Keep key-rotation whole (AD-31/AD-47).** Update `backfill.py::ENCRYPTED_COLUMNS`: remove the dropped `("piece", "id", "custodian", …)` entry and add `("piece_provenance", "id", "provenance_path", "piece_provenance.provenance_path")` and `("piece_custodian", "id", "custodian", "piece_custodian.custodian")`, so `encrypt_backfill` and `rekey_all` still cover every encrypted value. Extend `test_rekey.py` / `test_encrypt_backfill.py` to seed the new tables.

- [x] **Task 5 — Structural property: no custodian/scope column on `piece` (AD-9).** Add a check `no_custodian_or_scope_column_on_piece` to `apx/checks/payload_schema.py` (mirror `chunk_columns_enumerated`: read the real DB column name of the `Piece` model; fail if any column is named or aliased `custodian`, `scope`, `rbac_scope` or `wall`). Register it in `registry.py`/`manifest.py` and document it in `README.md`. Add a failure-path fixture test (a `Piece` fixture that *has* a `custodian` column ⇒ the check fires) alongside the passing real-tree assertion — the 1.1/1.2/2.3/2.4 pattern. This check goes **green precisely because** Task 2 removes the column.

- [x] **Task 6 — Integration tests through the real ingestion + store (all ACs).** In `tests/adapters/test_store.py` (and/or a new `test_idempotent_ingest.py`): re-import the same folder twice (AC2: count unchanged, `ingestion_timestamp` unchanged, `pieces_already_present` reported); same content two paths one matter (AC3: one piece, provenance set of two); two custodians across two jobs (AC3: custodian set union, never collapsed); same file two matters (AC4: two pieces); induced write-conflict (AC5: one copy, no raise). Update the existing `test_re_ingesting_does_not_duplicate` to also assert non-mutation and the already-present line.

- [x] **Task 7 — Gate + docs.** Full green: `ruff`, `pytest` (no regressions — mind the four `provenance_path` readers and the `_BACKUP_TABLES`/backup-restore round-trip must include the two new tables), `apx.checks` exit 0, `alembic upgrade head` + `downgrade`. Add the two new tables to `_BACKUP_TABLES` in `store.py` and to the backup/restore test so a tenant backup captures the sets. Update the `Piece`/`Chunk` docstrings and `payload.py` note to reflect that `CUSTODIAN_LINK` now exists (no longer "owed to a later story").

## Dev Notes

### The one thing this story changes, precisely

`store.save()` currently does `session.merge(Piece(...))` (store.py ~L550). `merge` is an **upsert keyed on the PK** — so a second import of the same content into the same matter finds the existing row and **overwrites** its `provenance_path`, `custodian` and `ingestion_timestamp` with the new import's values. That single line is the v1 defect wearing a new coat: it silently destroys the first custodian and the first provenance path, and mutates a piece the AC says must stay "readable and unmodified". The whole story is: **make the write insert-if-absent (never mutate), and move the two multi-valued facts — provenance and custodian — into unioned sets.**

### Architecture guardrails (binding)

- **AD-8 (identity + supersession):** identity = deterministic hash of (content, matter); **provenance path is not identity and one pièce may carry several**; the same file in two matters is two pièces; **cross-matter dedup and "seen before" are forfeited** (the Chinese wall). Identifiers are never from a counter. **Supersession is out of scope for this story and must NOT be written here:** AD-8 says a `supersedes` relation is "**never a silent write during ingestion**" — it is created only by an explicit user act with a reason, or a declared/configured/audited rule that emits a *worklist* line offering the relation. The 2.5 ACs do not ask for it. "Changed content produces a new pièce" is satisfied by identity alone (new bytes → new `content_hash` → new `piece_id` → a new, separate piece that does not overwrite the old). **Defer the `supersedes` relation schema + write to the story that builds the worklist/user-act surface** (record this deferral in Completion Notes with the AD-8 citation — a reviewer will probe it).
- **AD-9 (`CUSTODIAN_LINK`, column ban):** custodianship is a **set on the pièce**, `CUSTODIAN_LINK`, **unioned — never replaced or collapsed — by every import job** admitting the same content, resolved by join at read time; and **no column named or aliased as scope or custodian exists on `chunk`, `piece` or `full_text`** (enforced as a structural property — Task 5). `payload.py` L16-19 explicitly names this story as the one that lands the set and removes the `piece.custodian` legacy column.
- **AD-40 (frozen payload):** the **chunk** payload is frozen; this story does not touch chunk columns. The provenance/custodian sets are *pièce*-level, outside the frozen chunk enumeration, so no payload freeze is broken.
- **AD-7 (no hard delete / no cascade):** the two new FKs are **`ON DELETE RESTRICT`** (never CASCADE/SET NULL/SET DEFAULT — the `no_cascade_delete` check inspects `ForeignKey(...)`). Dropping the `piece.custodian` *column* is allowed (it is not `DELETE FROM`/`TRUNCATE`/`DROP TABLE`) and is data-preserving (backfilled first).
- **AD-31 (encrypt at rest):** a provenance path and a custodian name are PII → `EncryptedText`. The set-membership key cannot be the ciphertext (AES-GCM is randomised — `crypto_types.py` docstring). Use the deterministic `id = sha256(piece_id \x00 value)` PK as the set key: this is exactly the `_failure_id(matter, path)` pattern already in the store (a plaintext hash of matter+path as the dedup PK while the path column is encrypted), so it introduces no new side-channel posture, only reuses the established one.
- **AD-12 (tenant-first):** tenant is already inside `piece_id`; the `uq_piece_tenant_matter_content` constraint stands. Nothing new.

### Files to touch (and the blast radius to respect)

- `apx/adapters/store_postgres/models.py` — add `PieceProvenance`, `PieceCustodian`; **remove** `Piece.custodian` (keep `Piece.provenance_path` as representative); refresh the `Piece`/`Chunk` docstrings.
- `apx/adapters/store_postgres/store.py` — rewrite the piece loop in `save()` (insert-if-absent + union + classify); extend `SaveOutcome`; add `provenances()`/`custodians()`; add `piece_provenance`, `piece_custodian` to `_BACKUP_TABLES` and to the backup/restore gather+restore paths. **Do not remove the scalar `provenance_path`** — four reads depend on it: `deduplicate()` (~L786), `labels()` (~L865), `sample_discards()` (~L894), `search()` (~L978). They keep working against the representative.
- `apx/adapters/store_postgres/migrations/versions/0018_piece_provenance_and_custodian_sets.py` — new; create tables, backfill from scalars, drop `piece.custodian`; reversible downgrade. Model the data-backfill on `0013_encrypt_backfill` and the DDL on `0017_import_job_ledger`.
- `apx/adapters/store_postgres/backfill.py` — update `ENCRYPTED_COLUMNS` (Task 4).
- `apx/checks/payload_schema.py`, `registry.py`, `manifest.py`, `README.md` — the new structural check (Task 5).
- `apx/core/domain/payload.py` — update the L16-19 note (`CUSTODIAN_LINK` now exists).
- Tests: `tests/domain/test_identity.py`, `tests/adapters/test_store.py` (+ maybe `test_idempotent_ingest.py`), `tests/adapters/test_backup_restore.py`, `tests/adapters/test_rekey.py`, `tests/adapters/test_encrypt_backfill.py`, `tests/checks/…` for the new check's fixture.

### Concurrency / dual-dialect note

Tests run on SQLite (in-memory, `StaticPool`); production is PostgreSQL. Prefer a **dialect-portable** insert-if-absent: `session.begin_nested()` (SAVEPOINT) around the `session.add` + `session.flush()`, catching `sqlalchemy.exc.IntegrityError` → treat as already-present/absorbed. Both backends support SAVEPOINT and raise `IntegrityError` on a PK/unique collision, so one code path serves both (avoid `postgresql.insert(...).on_conflict_do_nothing()` unless mirrored with the sqlite dialect — the SAVEPOINT approach is simpler and already the house style for `record_auth_event`'s retry). AC5 can be tested deterministically by opening two sessions on the same engine, or by asserting the `IntegrityError` branch directly — do not depend on OS thread timing.

### What NOT to build (scope discipline — AD-8/epics)

No `supersedes` relation/schema/write (deferred, AD-8 — see above). No worklist line, no completion-summary rendering (Story 2.10). No failure-register table changes (Story 2.6). No embedding/chunking. No fuzzy/near-duplicate tier beyond the existing `dedup.py` (untouched). The "recognised-already-present" requirement is a **count on `SaveOutcome`** (and available to the audit detail), not a UI.

### Project Structure Notes

Hexagonal boundaries hold: identity/dedup are Domain (`apx/core/domain`), the ingestion use case is Application (`apx/core/app/ingest.py`, unchanged here), persistence + the link tables are the Adapter (`apx/adapters/store_postgres`). The core imports no adapter. The structural check lives with the other build-time properties in `apx/checks`.

### References

- `epics.md` §Story 2.5 (the five ACs, verbatim above); FR-4.
- `ARCHITECTURE-SPINE.md`: AD-8 (L260-287, identity + supersession), AD-9 (L289-320, `CUSTODIAN_LINK` + column ban), AD-40 (L1117-1160, frozen payload), AD-7 (L226-258, no cascade / no hard delete), AD-31 (encrypt at rest), AD-12 (tenant-first).
- `apx/core/domain/payload.py` L11-19 — names 2.5 as the `CUSTODIAN_LINK` story.
- Existing seams: `store.py::save` (the `merge` to replace), `store.py::_failure_id` (the deterministic-PK pattern to reuse), `backfill.py::ENCRYPTED_COLUMNS`, `checks/payload_schema.py::chunk_columns_enumerated` (the check to mirror), `crypto_types.py` (why the ciphertext can't be the set key).

## Senior Developer Review (AI)

**Reviewed:** 2026-07-28 · **Outcome:** Approve (all findings resolved before completion) · three parallel adversarial reviewers, execution-verified, distinct lenses (persistence correctness / migration+encryption / architecture fidelity), each left the tree clean.

**Confirmed sound (interrogated, no defect):** AC2 non-mutation (a re-import leaves the pièce row byte-identical across all 15 columns); AC3 union-always never collapsed (proven at runtime, both the API sync path and the worker route through one `save()`); AC5 SAVEPOINT conflict-safety; backup/restore round-trip of the sets under FK enforcement; `link_id` introduces no new side-channel (same shape as `_failure_id`/`_unit_id`); the four `provenance_path` readers show no semantic/statistical drift; AD-7 FKs are RESTRICT and the column drop is permitted; the manifest/README lock-step passes for the right reason. The **`supersedes` deferral is faithful** — AD-8 forbids a silent supersedes write during ingestion (it is a user act or a worklist-offer rule), no 2.5 AC requires it, and "changed content → a new pièce" is met by identity alone.

**Action items (all resolved):**
- [x] **[Med] Precise conflict absorb (correctness + migration lenses).** The bare `except IntegrityError` in `_insert_piece_if_absent` / `_insert_link_if_absent` swallowed *any* constraint violation (NOT NULL / CHECK / FK) as "already-present" → a malformed pièce could vanish, miscounted, with orphan link rows. **Fix:** re-query inside the except and absorb ONLY a genuinely-present row; re-raise otherwise (fails the unit loudly, the outer tx rolls back). Also closes the migration lens's "blank-custodian → zero-link → downgrade NOT NULL" latent. New tests: `test_a_genuine_integrity_failure_fails_loudly_never_a_silent_drop`, and the AC5 test rewritten to a stale-first-read race that exercises the precise absorb.
- [x] **[High, pre-existing] Key rotation skipped 8 encrypted PII columns.** `ENCRYPTED_COLUMNS` omitted `matter_scope.case_theory`, `import_job.{actor,custodian,case_theory}`, `import_unit.provenance_path`, `backup_record.detail`, `truncation_marker.{cleared_by,reason}` — a rotation left them under the retired key (silent PII loss). The gap predated 2.5, but Task 4 owns rotation-completeness and I was editing the list. **Fix:** added all 8 (with composite-PK support in `encrypt_backfill`/`rekey_all` for `matter_scope`), plus a drift-guard test (`test_rekey_covers_every_encrypted_column`) that reflects the live model metadata so a new encrypted column can never ship uncovered.
- [x] **[Low-Med] The recognised-already-present count was inert on the trail.** AC2's machine-checkable assertion (the `SaveOutcome` field) passed, but the `ingest` audit detail was identical for a real ingest and a re-import no-op. **Fix:** the sync-path `ingest` audit detail now carries `already_present=N` (audit append moved after the loop). The worker-path per-job breakdown remains Story 2.10's completion-summary surface (noted, not over-claimed).
- [x] **[Low] Structural check widened.** `no_custodian_or_scope_column_on_piece` now also catches a bare `Column(...)`/`sa.Column(...)` (not only `mapped_column`), with a fixture. Remaining base-class/synonym AST blind spots are identical to the accepted sibling `chunk_columns_enumerated`.
- [x] **[Low] Test coverage.** The at-rest sweep now includes `piece_provenance.provenance_path`.
- [x] **[Nit] Typing.** `_insert_piece_if_absent(p: object)` → `p: IngestedPiece`.

**Deferred (out of scope, recorded):** a story must be scheduled to build the `supersedes` user-act/worklist write-surface (AD-40 binds it to *the increment*, not to 2.5). The migration's plaintext-without-key path is unreachable (gated by migration 0013) and the "representative" scalar being first-seen (runtime) vs smallest-link-id (downgrade) is cosmetic — both are valid members of the set.

Post-fix gate: **ruff clean · pytest 609 passed / 9 skipped · apx.checks 44 · alembic single head 0018**.

## Dev Agent Record

### Agent Model Used

Claude Opus 4.8 (1M context)

### Debug Log References

- Baseline gate green at `480de8e` (589 passed / 9 skipped). The API/offline tests fail only when `DATABASE_URL=sqlite://` is exported into the pytest run (an in-memory, non-shared connection) — run the suite with no `DATABASE_URL` override.
- The full Alembic chain runs on **PostgreSQL only** (`0009` uses `encode`/`convert_to`/`sha256`, Postgres built-ins) — it is not exercisable end-to-end on SQLite. CI runs `upgrade head → downgrade base → upgrade head` on Postgres. Migration 0018's *data* logic (`migrate_piece_scalars_to_links` / `revert_piece_links_to_scalar`, incl. the AAD-changing re-encryption) is tested directly on SQLite in `test_piece_links_migration.py`; its DDL mirrors 0017/0009/0004 exactly.

### Completion Notes List

- **The change in one line:** `store.save()` replaced `session.merge(Piece(...))` (an upsert that overwrote provenance/custodian/timestamp on re-import — the v1 defect in a new coat) with **insert-if-absent** (never mutates a prior pièce) plus a **union-always** write of the provenance and custodian **sets**.
- **New schema (migration 0018):** `piece_provenance` and `piece_custodian` — set tables keyed by a deterministic `id = sha256(piece_id \x00 value)` (the `_failure_id` pattern), FK `ON DELETE RESTRICT` (AD-7), value `EncryptedText` (AD-31). The `piece.custodian` **column was dropped** (AD-9: no custodian column on `piece`); `piece.provenance_path` stays as the first-seen representative for the four existing readers.
- **AC coverage:** AC1 identity determinism incl. a fresh-process subprocess check (`test_identity.py`); AC2 non-destructive re-import + `SaveOutcome.pieces_new`/`pieces_already_present`; AC3 provenance set of two + custodian union never collapsed; AC4 two matters → two pièces; AC5 induced write-conflict absorbed via `begin_nested()` SAVEPOINT + `IntegrityError` (deterministic test blinds `Session.get(Piece)` to simulate a concurrent worker's stale read). All in `test_idempotent_ingest.py`.
- **New structural property (AD-9):** `no_custodian_or_scope_column_on_piece` — forbids a `custodian`/`scope`/`rbac_scope`/`wall` column (real DB name) on the `Piece` model; registered + in the manifest + README; failure-path fixtures in `test_payload_schema_checks.py`. Goes green because the column was removed (44 checks now).
- **Key-rotation + backup kept whole:** `ENCRYPTED_COLUMNS` updated so `encrypt_backfill`/`rekey_all` cover the two set tables (not the dropped column); the backup/restore path captures the sets via the tenant's piece ids (like `user_scope`) and restores them; round-trip + rekey-read-back asserted.
- **Deferred (faithful, AD-8):** the `supersedes` relation (schema + write) is **not** built here. AD-8 is explicit that supersession is *never a silent write during ingestion* — it is a user act with a reason, or a configured rule offering a *worklist* line (surfaces that do not exist yet). The 2.5 ACs do not ask for it; "changed content → a new pièce" is satisfied by identity alone (new bytes → new `content_hash` → new `piece_id`, never overwriting the old). Defer to the story that builds the worklist/user-act supersedes surface.
- Final gate: **ruff clean · pytest 606 passed / 9 skipped · apx.checks 44 · alembic single head 0018**. `apx/core/ports/embedding.py` left untracked (out of scope).

### File List

**Production**
- `apx/adapters/store_postgres/models.py` — new `PieceProvenance` / `PieceCustodian`; dropped `Piece.custodian` column; docstrings.
- `apx/adapters/store_postgres/store.py` — `save()` insert-if-absent + union-always; `SaveOutcome` (`pieces_new`/`pieces_already_present` + `pieces_written` alias); `_insert_piece_if_absent`, `_insert_link_if_absent`, `provenances()`, `custodians()`; backup/restore of the sets; `TenantBackup.piece_links`.
- `apx/adapters/store_postgres/backfill.py` — `link_id`, `migrate_piece_scalars_to_links`, `revert_piece_links_to_scalar`, `_cipher_if`; `ENCRYPTED_COLUMNS` updated (link tables in, dropped column out).
- `apx/adapters/store_postgres/migrations/versions/0018_piece_provenance_and_custodian_sets.py` — new migration (create sets, backfill, drop column; reversible).
- `apx/checks/payload_schema.py` — `no_custodian_or_scope_column_on_piece` + in `run()`.
- `apx/checks/registry.py`, `apx/checks/manifest.py`, `README.md` — registered the new structural property.
- `apx/core/domain/payload.py` — note updated (`CUSTODIAN_LINK` now exists).

**Tests**
- `tests/domain/test_identity.py` (new) — AC1.
- `tests/adapters/test_idempotent_ingest.py` (new) — AC2–AC5.
- `tests/adapters/test_piece_links_migration.py` (new) — 0018 backfill/downgrade + re-encryption.
- `tests/checks/test_payload_schema_checks.py` — new check's fixtures + fail-closed loop.
- `tests/adapters/test_encryption_at_rest.py`, `tests/adapters/test_encrypt_backfill.py`, `tests/adapters/test_rekey.py`, `tests/adapters/test_backup_restore.py`, `tests/adapters/test_chunk_writer.py`, `tests/api/test_ingest_api.py` — moved custodian references from the dropped column to `piece_custodian` / `store.custodians()`.
