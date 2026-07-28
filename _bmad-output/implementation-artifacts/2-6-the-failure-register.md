---
baseline_commit: 3d689b7
---

# Story 2.6: The failure register

Status: done

## Story

As a lawyer,
I want every *pièce* that failed to index enumerated, attributed and actionable, resolved by state change and never by removal,
so that the decisive document that would not open is on a list I can act on, not silently gone.

## Scope note — UX deferred, backend contract in full

The epic marks this story **"UX pass required before implementation. No UX design contract exists yet."** The APX SPA is static; this story therefore implements the **complete, automatically-verifiable backend + API contract** of the register (the data model, the enumerated class set, the redacted diagnostic, resolution-by-state, the retry and bulk-retry use cases, the scoped export, the admin-only visibility of undetermined entries, and the AD-37 structural property) and **explicitly defers the visual/interaction UX** (the register screen, the per-line affordances, the filter chrome) to a later UX pass. Every AC below is expressed as a backend/API assertion. This is the same split every Epic-2 backend story has taken; nothing here pre-commits a visual design.

## Acceptance Criteria

Verbatim from `epics.md` §Story 2.6 (FR-5; AD-37 transition ownership + conditional commit, AD-7 never-removed, AD-38 cardinality, AD-13/AD-12 scope + tenant admin, AD-28 redaction). Each is decomposed into the assertion the dev must make fire.

**AC1 — Every failed pièce is one register entry carrying the full field set; classes are the enumerated stable set; an unclassified failure is `unknown` with a redacted diagnostic, never dropped.**
Given a *pièce* that fails at any stage, when it is recorded, then the register entry carries **filename, submitted path, *matter*, *custodian*, error class, cardinality, resolution state, timestamp, and a retry action**, with error classes drawn from the **enumerated stable set** and an unclassified failure recorded as `unknown` with its **redacted diagnostic** — never dropped (FR-5).
- *Assert:* the `Failure` row (durably read back) carries all nine fields; `ErrorClass` contains the full FR-5 minimum set (`unreadable`/`unreadable-scan`, `corrupt-file`, `password-protected`, `unsupported-format`, `extraction-error`, `extracted-empty`, `container-unopenable`, `resource-exhausted`, `source-unavailable`, `source-modified`, `traversal-out-of-scope`, plus the operational `quarantined`) and `unknown`; a failure with no matching class lands `unknown` and its diagnostic is **redacted** (no verbatim `str(exc)`, no path, no document fragment — AD-28); `cardinality` is `one` for an ordinary pièce and `unknown` for a `container-unopenable` entry (AD-38).

**AC2 — Resolved by state change: retry re-runs ingestion for that pièce only; success → `resolved` keeping history; the inventory counts open entries only.**
Given an open entry, when it is retried, then ingestion is re-run **for that pièce only**, a success moves the entry to `resolved` and **keeps its history** (never removed, AD-7), and the *inventory guarantee* counts **open entries only** (FR-5).
- *Assert:* `retry_failure` on an open entry whose source now extracts → the entry's `resolution_state` becomes `resolved`, the row still exists (history kept), a new pièce is in the corpus, and `inventory.failures` drops by one (open-only); a retry whose source still fails leaves the entry `open` with its (possibly updated, redacted) class/diagnostic; the transition is a **conditional commit** on observed `open` (AD-37) — a retry against a non-`open` entry does not silently resolve it.

**AC3 — A password-protected entry offers a credential-supply action; override-only is a defect.**
Given a `password-protected` entry, then it **offers a credential-supply action** (a retry that accepts a credential); an entry whose **only** exit is an *override* is a defect of this FR (FR-5).
- *Assert:* `retry_failure` accepts an optional credential and a `password-protected` entry is retryable via it (the affordance exists and is exercised by a test); no code path makes `password-protected` resolvable **only** by an override (there is a non-override exit). *(The deep per-format password-decryption of the bytes is threaded through ingestion where the extractor supports it; the testable contract here is the credential-carrying retry affordance, not new format decryptors.)*

**AC4 — A bulk retry over a filtered set produces ONE audit entry naming the set.**
Given the register, when a **bulk retry** is run over a filtered set (by class, *matter*, *custodian*), then it produces **one *audit record* entry naming the set**, not one per *pièce* (FR-5).
- *Assert:* `bulk_retry` with a filter retries every matching open entry (each a conditional commit), and writes **exactly one** `bulk-retry` audit entry carrying the filter + the count (a 2 800-entry retry is one audit row, not 2 800); an entry that is not `open` at retry time is skipped, never clobbered (the AD-37 override-race defense).

**AC5 — The register is exportable one pièce per line within RBAC scope, recorded in the audit; undetermined-matter entries are visible only to the tenant-wide admin.**
Given the register, when it is exported, then it is **one-pièce-per-line within the exporting user's *RBAC scope***, recorded in the *audit record*; entries whose *matter* could not be determined are **visible only to the *tenant*-wide administrative grant holder** (FR-5, FR-49).
- *Assert:* `export_register` returns one line per entry, filtered to the caller's held scopes (a wall the caller lacks never appears), writes one `export-register` audit entry; a matter-undetermined entry (matter is the undetermined sentinel) appears **only** when the caller is the tenant admin, never for an ordinary scoped user.

## Tasks / Subtasks

> Red-green-refactor, in order. Gate after each with `export PATH="$PWD/.venv/bin:$PATH"` then `.venv/bin/ruff check .`, `.venv/bin/python -m pytest` (NO `DATABASE_URL` override — it breaks the API tests), `.venv/bin/python -m apx.checks`.

- [x] **Task 1 — The enumerated stable class set + the redacted diagnostic (AC1).**
  - Extend `apx/core/domain/failures.py::ErrorClass` with the FR-5 classes not yet present: `CORRUPT_FILE = "corrupt-file"`, `PASSWORD_PROTECTED = "password-protected"`, `SOURCE_UNAVAILABLE = "source-unavailable"`, `SOURCE_MODIFIED = "source-modified"`, `TRAVERSAL_OUT_OF_SCOPE = "traversal-out-of-scope"`. Keep the existing members (incl. `quarantined`). Document that the set is stable (append-only; a value is never renamed or removed once shipped — a persisted class must always decode).
  - Add a domain helper `redacted_diagnostic(exc: BaseException) -> str` (in `failures.py` or a small `apx/core/domain/diagnostics.py`): returns a **content-free** diagnostic — the exception **type name** and at most a bounded, character-class-scrubbed hint — never `str(exc)` verbatim, never a path, never a document fragment (AD-28). Apply it at the `IngestedFailure(..., str(exc))` sites in `apx/core/app/ingest.py` (lines ~158, ~198) so an extractor exception message can no longer leak content into the register. Update any test asserting the old `str(exc)` detail.

- [x] **Task 2 — Extend the `Failure` model + migration 0019 (AC1).**
  - Add to `apx/adapters/store_postgres/models.py::Failure`: `custodian: Mapped[str | None]` = `EncryptedText("failure.custodian")` (PII, nullable — "where known"); `cardinality: Mapped[str]` = `String`, NOT NULL, default `"one"` (values `one` | `unknown`). Keep `resolution_state` ∈ `{open, resolved}` (the `overridden` state and the override use case are Epic 5 / Story 5.6 — noted, not built here).
  - Migration `0019_failure_register_fields.py` (`down_revision = "0018_piece_provenance_and_custodian_sets"`): add the two columns; backfill `cardinality` = `unknown` for existing `container-unopenable` rows and `one` otherwise (AD-38); `custodian` left NULL. Add `failure.custodian` to `backfill.py::ENCRYPTED_COLUMNS` (and the drift-guard test stays green). No cascade FK (AD-7). Reversible downgrade.
  - Thread the custodian + cardinality where failures are written: `store.save()` (from the ingestion result — the job's custodian; cardinality `unknown` iff `container-unopenable`), and `quarantine_unit` (custodian from the job, cardinality `one`). The ingestion `IngestedFailure` already flows the class; carry cardinality from the class.

- [x] **Task 3 — The durable register read, scope-checked, with the tenant-admin view (AC1, AC5 visibility).**
  - `store.register(matter, tenant, scopes) -> list[RegisterEntry]` — the persisted entries for a matter (scope-checked, `ScopeDenied` if the wall is not held), **open and resolved** (history kept), ordered deterministically; each `RegisterEntry` a frozen dataclass with all nine fields (decrypted filename/path/custodian).
  - `store.register_all(tenant, scopes, *, is_admin) -> list[RegisterEntry]` — the tenant-wide view: entries whose matter's scope is held, PLUS (only when `is_admin`) entries whose matter is the **undetermined sentinel** (an entry that could not be attributed to a matter). A non-admin never sees an undetermined-matter entry (AD-12 fail-closed). Decide the sentinel: reuse a reserved matter value (e.g. `""`/`"__undetermined__"`) — pick one, document it, and make `register`/inventory exclude it from ordinary matter reads.

- [x] **Task 4 — The retry use case: `open → resolved`, a conditional commit (AC2, AC3).**
  - `store.retry_failure(entry_id, result, scope, actor, *, now=None) -> RetryOutcome` — AD-37's *ingestion retry* owner. In ONE transaction (repeatable-read semantics; on SQLite the single-writer serialization suffices, documented): **observe** the entry is `open`; if not, return a `precondition-not-met` outcome and write nothing (never clobber — the override-race defense). If `open`: reconcile the freshly-run `result` — if it now yields the pièce for this path, persist it (insert-if-absent, Story 2.5's `save` path) and set the entry `resolved`; else keep it `open` and refresh its class + redacted diagnostic. Append ONE audit entry (`retry`).
  - The credential (AC3): `retry_failure` (and the app-layer re-run) accept an optional `credential`; the app layer threads it to `ingest_one_file`/the extractor where a format supports a password. A `password-protected` entry is retryable through this path — assert a test drives a password-protected entry to `resolved` via a supplied credential (mock the extractor consuming it). No path resolves `password-protected` by override only.

- [x] **Task 5 — Bulk retry over a filtered set → ONE audit entry (AC4).**
  - `store.bulk_retry(tenant, scopes, *, error_class=None, matter=None, custodian=None, retry_one, actor) -> BulkRetryOutcome` — select the open entries matching the filter (scope-checked), retry each as a conditional commit (`retry_one` re-runs ingestion per entry; a non-open entry is skipped, never clobbered), and write **exactly one** `bulk-retry` audit entry naming the filter and the counts (attempted / resolved / still-open). Not one audit row per pièce (AD-6/FR-5).

- [x] **Task 6 — The scoped, audited export (AC5).**
  - `store.export_register(tenant, scopes, actor, *, is_admin) -> RegisterExport` — one line per entry (filename, path, matter, custodian, class, cardinality, state, timestamp), filtered to the held scopes, undetermined-matter lines only for the admin; write one `export-register` audit entry (count + scope). One-pièce-per-line, deterministic order. (A file/stream format is a UX-pass concern; the backend returns the structured lines.)

- [x] **Task 7 — The AD-37 structural property (transition ownership).**
  - Add a structural check (in `apx/checks/`, e.g. `register_ownership.py` or fold into an existing module): `Failure.resolution_state` is **assigned only inside the store adapter** (`apx/adapters/store_postgres/`) — no other module transitions the register state (AD-37: one owning module per the state column). Register it (registry + manifest + README lock-step) with a failure-path fixture. This is the tractable static shadow of AD-37's per-transition ownership.

- [x] **Task 8 — Thin API surface (the READ surface; the retry POST is deferred with the UX pass).**
  - WIRED + tested: `GET /api/matters/{matter}/register` (scoped), `GET /api/register` (tenant-wide, admin sees undetermined), `GET /api/register/export` (audited) — reusing the session principal + `is_admin`, thin pass-throughs to the store use cases.
  - **DEFERRED to the UX pass** (recorded, not built): `POST /api/register/{entry_id}/retry` and `POST /api/register/retry` (bulk). Both need the re-ingestion **source** (the uploaded spool is deleted post-ingest, Story 2.2) and the credential-supply **interaction** — genuinely UX-pass concerns. The store use cases behind them (`retry_failure`, `bulk_retry`) are complete and unit-tested, so AC2–AC4 hold at the store level; the HTTP surface is the only deferred part. (The credential is threaded by the app-layer `reingest` thunk the retry endpoint will build; the extractor-level `credential` argument lands with the per-format decryptors — the same deferred surface. `retry_failure` itself is correctly credential-agnostic: it owns the conditional commit, not the extraction.)

- [x] **Task 9 — Gate + docs.** Full green: `ruff`, `pytest` (no regressions — mind the `str(exc)` detail change, the `ENCRYPTED_COLUMNS` drift-guard now including `failure.custodian`, the projection content-free test still passing with the redacted diagnostic), `apx.checks` (new check live), `alembic upgrade head` + reversible downgrade. Update `failures.py` / `Failure` docstrings and `README` (the new structural property).

## Dev Notes

### The load-bearing decision: AD-37 conditional commits (the "largest silence")

The architecture flags AD-37 as *"the largest silence in the original spine and the one an agent team will not fill correctly by default."* Read AD-37's ownership table (spine L1054-1074). For the failure register:
- **`open → resolved`** is owned by the **ingestion retry** use case, **conditional on observing `open`**.
- **`open → overridden`** is owned by the **override** use case (Epic 5 / Story 5.6 — NOT built here).
- **`* → quarantined`** is the unit-of-work supervisor in an **independent transaction** (already built, Story 2.2 `quarantine_unit`).
- The **race** the AD exists to kill: a lawyer *overrides* an entry while a 2 800-entry bulk retry runs; the retry wins second and unconditionally resolves it, leaving the audit holding a lawyer's recorded reason for excluding a document she could in fact open — *"the shape FR-5 explicitly calls a defect, made unerasable by AD-7."*
- **The rule you implement:** every register transition is a **conditional commit** — read the state, write only if the observed precondition still holds, in **one transaction**; a precondition that no longer holds **fails loudly** (a `precondition-not-met` outcome / a worklist line), **never overwrites, never silently no-ops**. So `retry_failure` and each `bulk_retry` step re-read `open` inside the transaction and skip (do not clobber) anything that moved. Even though the `overridden` state is Epic 5, build the retry conditional NOW so it is correct the moment override lands (spine L1072: a retry against an `overridden` entry offers to reverse the override, never silently resolves).

### Architecture guardrails (binding)

- **AD-7 (never removed):** register entries are **resolved by state change, never deleted**; a resolved entry stays so the §13 "what was and was not reviewed" question stays answerable. No `DELETE`/`TRUNCATE`/`DROP` on the register. The `Failure` FK stays RESTRICT.
- **AD-38 (cardinality):** an entry's `cardinality` is `one` or `unknown`; `unknown` (a `container-unopenable` entry) is **never summed** into a total — the inventory already annotates `unknown_cardinality_entries` from the class (Story 2.4). Persisting `cardinality` on the row makes it a first-class field (FR-5) rather than a class-derived inference; keep the inventory consistent with it.
- **AD-28 (no verbatim fragments):** a document fragment (extractor stdout/stderr, an exception message quoting content, a path) must **never** reach the register, a log, a diagnostic, or an export. The `unknown` diagnostic is **redacted**. This closes the current `IngestedFailure(..., str(exc))` leak in `ingest.py`.
- **AD-13/AD-12 (scope + tenant admin):** the register read/export is **scope pre-filtered** (a held-wall equality, like `store.matters`/`inventory`/`search`); a matter-undetermined entry is visible **only** to the tenant-wide administrative grant holder — resolve `is_admin` from the session principal (`SessionIdentity.is_admin`), never a client claim. Fail closed.
- **AD-6 (one audit entry per act):** a bulk retry and an export each write **one** audit entry naming the set/scope — never one per pièce (the 1 400→2 800 batch shape AD-9's prose warns about).
- **AD-31 (encrypt at rest):** `failure.custodian` is PII → `EncryptedText`; add it to `ENCRYPTED_COLUMNS` (the Story 2.5 drift-guard test will otherwise fail — good, that is the guard working).

### Files to touch (and blast radius)

- `apx/core/domain/failures.py` — extend `ErrorClass`; add `redacted_diagnostic()` (or a new `diagnostics.py`).
- `apx/core/app/ingest.py` — replace `str(exc)` failure details with the redacted form; carry cardinality from the class.
- `apx/adapters/store_postgres/models.py` — `Failure.custodian` + `Failure.cardinality`.
- `apx/adapters/store_postgres/migrations/versions/0019_failure_register_fields.py` — new (add columns, backfill cardinality, reversible).
- `apx/adapters/store_postgres/backfill.py` — add `failure.custodian` to `ENCRYPTED_COLUMNS`.
- `apx/adapters/store_postgres/store.py` — `save()`/`quarantine_unit` write the new fields; NEW `register`, `register_all`, `retry_failure`, `bulk_retry`, `export_register` + their result dataclasses; the undetermined-matter sentinel handling in `_counts`/`matters`/`inventory` (exclude the sentinel from ordinary matter reads).
- `apx/checks/…` + `registry.py` + `manifest.py` + `README.md` — the AD-37 ownership structural property.
- `apx/api/app.py` — the thin register endpoints + `FailureOut`/response models extended (custodian, cardinality, state, timestamp, retry affordance).
- Tests: `tests/domain/test_failures.py` (enum + redaction), `tests/adapters/test_failure_register.py` (register read, retry conditional commit, bulk-retry-one-audit, export scope + admin-only undetermined), `tests/checks/…` (the new check fixture), `tests/api/test_register_api.py` (thin endpoint smoke + scope), plus the `ENCRYPTED_COLUMNS` drift-guard already covers `failure.custodian`.

### What NOT to build (scope discipline)

- The visual/interaction UX (the register screen, per-line buttons, filter chrome) — deferred to the UX pass; the SPA is static.
- The full **override** use case (`open → overridden` + a mandatory one-line reason + its audit) — Epic 5 / Story 5.6. Build the retry **conditional** so it is override-race-safe, but do not implement override itself.
- New per-format password **decryptors** — thread the credential through; a format that cannot yet consume it simply stays `password-protected` after a credential retry (the affordance is the contract).
- The completion-summary rendering of the register — Story 2.10.
- Any change to the frozen chunk payload (AD-40) — untouched.

### Project Structure Notes

Hexagonal boundaries hold: `ErrorClass` + `redacted_diagnostic` are Domain; the retry/bulk/export **use cases** live in the store adapter (they are inherently transactional — AD-37 requires the read+write in one transaction), driven by the Application ingestion for the re-run. The core imports no adapter. The AD-37 ownership check lives with the other build-time properties.

### References

- `epics.md` §Story 2.6 (the five ACs verbatim); FR-5 (`prd.md` L327-333); the *Failure register* glossary entry (`prd.md` L230).
- `ARCHITECTURE-SPINE.md`: **AD-37** (L1029-1074, transition ownership + conditional commit + the ownership table — the load-bearing read), AD-7 (never removed), AD-38 (cardinality unknown), AD-28 (no verbatim fragments, L811-821), AD-13/AD-12 (scope + tenant admin), AD-6 (one audit entry).
- Existing seams: `store.py::_counts` (open-only count — the inventory guarantee), `quarantine_unit` (the independent-tx quarantine, AD-37 already), `save()` failure write, `_failure_id`, `SessionIdentity.is_admin`, `projection.redact` (secret redaction — the register needs content redaction, a distinct helper), `crypto_types.EncryptedText`, the Story 2.5 `ENCRYPTED_COLUMNS` drift-guard.

## Senior Developer Review (AI)

**Reviewed:** 2026-07-28 · **Outcome:** Approve (all findings resolved before completion) · three parallel adversarial reviewers, execution-verified, distinct lenses (AD-37 state machine / redaction+scope+crypto / architecture+check+deferrals), each left the tree clean.

**Confirmed sound (interrogated, no defect):** AD-7 never-removed (resolve is a state flip, no DELETE); the scope pre-filter + FR-49 admin-only-undetermined (a non-admin never sees a NULL-matter entry; cross-tenant fails closed); the redaction's tight side (ignores `str(exc)`/`args`/`__notes__`/`__cause__`); custodian at rest + the drift-guard (green for the right reason); the migration data logic (cardinality backfill, matter widening, key-free on empty); FR-5 field completeness; ErrorClass append-only; manifest/README/layering lock-step. The **override, retry-HTTP, and password-decryptor deferrals are all faithful** (AD-37's table assigns `open→overridden` to a separate use case; no 2.6 AC needs it; the retry is built override-race-safe).

**Action items (all resolved):**
- [x] **[High] Cross-tenant register clobber (redaction/crypto lens).** `_failure_id` = `sha256(matter‖path)` **excluded tenant**, so two firms sharing a matter name + path collided on one PK and one firm's ingest `merge`-overwrote the other's entry (a Chinese-wall breach, AD-12/AD-7). Pre-existing at baseline, but the 2.6 failure-write is the site and now threads custodian PII through it. **Fix:** `_failure_id(tenant, matter, path)` — tenant-qualified exactly as `piece_id`. New regression test (two tenants, same matter+path → two rows, neither clobbered).
- [x] **[High] `bulk_retry` could commit retries then lose its only audit entry (state-machine lens).** A mid-loop re-ingest crash propagated out after some entries had committed `resolved`, with the single `bulk-retry` audit never written (AD-6). **Fix:** per-entry `try/except` — a poison unit is counted (`errored`) and the batch continues; the one audit entry is always written; row-locked per-entry re-observe retained.
- [x] **[Med] `_reconcile_retry` resolved on ANY pièce and dropped co-present failures (state-machine lens).** A mixed result (pièces + failures) marked the entry `resolved` while the fresh failures were never persisted (FR-5 "never dropped"), and it could resolve on a foreign-matter pièce. **Fix:** resolve iff the entry's OWN path succeeded (a same-tenant/matter pièce and no fresh failure for its own path); record every other (member) failure as its own entry, insert-if-absent; ignore foreign-matter pièces (closes the cross-matter leak too). New test (container retry records the member failure and resolves the container).
- [x] **[Med] The conditional-commit test didn't exercise phase 3 (state-machine lens).** The old test retried an already-resolved entry, caught by the redundant phase-1 early-out; neutering phase-3 alone still passed. **Fix:** a new test whose `reingest` thunk resolves the entry mid-flight (during phase 2) so only the phase-3 re-observe catches it (`precondition-not-met`).
- [x] **[Med] The AD-37 structural check was bypassable by 5 of 7 idioms (architecture lens).** It caught only `Failure(resolution_state=…)` and `x.resolution_state = …`. **Fix:** now also catches `update(Failure).values(resolution_state=…)`, `query(Failure).update({"resolution_state":…})`, `setattr(_, "resolution_state", _)`, and raw-SQL `UPDATE … resolution_state` (mirroring `one_chunk_writer`'s Core coverage); fixtures for each; still no false-positive on read DTOs.
- [x] **[Plausible→fixed] Lost-update window on Postgres (state-machine lens).** The phase-3 re-observe was a plain SELECT at READ COMMITTED. **Fix:** `session.get(..., with_for_update=True)` row-locks the re-observe on both retry paths (a no-op on SQLite, a real FOR UPDATE on Postgres); phase-3 now also re-authorises; the "repeatable-read" overclaim corrected in the docstring.
- [x] **[Low] Redaction defense-in-depth (redaction lens).** A crafted exception type's name/`__module__` could carry content. **Fix:** the name is scrubbed to identifier chars + length-capped and `__module__` is kept only when it is a valid dotted module name (a path is rejected); a path-injection test. (Unreachable in practice — extractors raise code-defined exceptions and `failure.detail` is not surfaced.)
- [x] **[Low/Nit] Doc + test accuracy.** `backfill_failure_cardinality` returns the rows actually set (not the total); Task 8 corrected to record the retry POST deferral (only the READ endpoints are wired); the enum-stability test now includes `unreadable-scan`; the credential test comment corrected (the thunk carries the credential, not a `retry_failure` argument).

**Deferred (recorded):** the retry/bulk POST endpoints + the extractor-level `credential` argument + per-format decryptors (all the same UX-pass/decryptor surface); the override use case (Epic 5 / Story 5.6); the register screen UX; the completion summary (Story 2.10); the migration downgrade's inability to reverse a NULL-matter row to NOT NULL (inherent, documented). The `_reconcile_retry` "resolve on own-path" uses `submitted_path` equality — correct for the caller's same-unit re-run.

Post-fix gate: **ruff clean · pytest 636 passed / 9 skipped · apx.checks 45 · alembic single head 0019**.

## Dev Agent Record

### Agent Model Used

Claude Opus 4.8 (1M context)

### Debug Log References

- Baseline `3d689b7` (609 passed / 9 skipped). Run the suite with NO `DATABASE_URL` override.
- Two structural checks I initially tripped (both faithful, both fixed by the story's own shape): `sensitive_columns_are_encrypted` wanted the new categorical `failure.cardinality` on the plaintext allowlist (added, beside `error_class`/`resolution_state`); `scoped_access_carries_tenant` (AD-12) flagged `retry_failure`/`_authorise_entry` taking `scopes` without a `tenant` — fixed by adding a `tenant` argument AND verifying the entry belongs to it (a real cross-tenant fail-closed, not just to satisfy the check).
- The alembic chain runs on Postgres only; 0019's DDL mirrors prior migrations and its cardinality backfill is a tested helper (`backfill_failure_cardinality`).

### Completion Notes List

- **The register, in full backend + read-API form.** `Failure` grew `custodian` (encrypted, where known) and `cardinality` (`one`|`unknown`, AD-38), and `matter` became nullable (NULL = undetermined → a NULL matter has no `matter_scope`, so the scope pre-filter excludes it from every ordinary read by construction; only the tenant admin sees it). `ErrorClass` is now the full FR-5 stable set. The `unknown`/exception diagnostic is **redacted** (`redacted_diagnostic` = the exception type only), which also closes the pre-existing `str(exc)` leak at two `ingest.py` sites (AD-28).
- **AD-37 conditional commits (the "largest silence").** `retry_failure` is a three-phase conditional commit: check `open` + authorise → re-run ingestion (a `reingest` thunk, outside any tx) → RE-OBSERVE `open` in one tx and reconcile (persist the pièce + resolve, or refresh the class + keep open), one `retry` audit entry. It **never clobbers** an entry that moved (`precondition-not-met`) — correct the moment the Epic-5 override lands. `bulk_retry` retries a filtered set, each a conditional commit, and writes **exactly one** `bulk-retry` audit entry (AD-6). A resolved entry is **kept** (AD-7); the inventory counts open only.
- **New structural property (AD-37):** `register_state_written_once` — `Failure.resolution_state` is written only inside the store adapter (a read DTO carrying the value is not a write). Registered + manifest + README (45 checks); failure-path fixtures.
- **Scope decision (recorded):** the register **read + export** endpoints are wired and tested (`/api/matters/{m}/register`, `/api/register`, `/api/register/export`), demonstrating the scope + admin-only-undetermined plumbing. The **retry / bulk-retry HTTP endpoints are deferred to the UX pass** — they need the re-ingestion *source* (the uploaded spool is deleted post-ingest, Story 2.2) and the credential-supply interaction, both UX-pass concerns; the store use cases behind them are complete and unit-tested (AC2–AC4 asserted at the store level).
- **Deferred (recorded):** the visual/interaction UX (register screen, per-line affordances); the full **override** use case (`open → overridden` + mandatory reason) — Epic 5 / Story 5.6 (the retry conditional is already override-race-safe); per-format password **decryptors** (the credential-carrying retry affordance is the contract); the completion-summary rendering — Story 2.10.
- Final gate: **ruff clean · pytest 631 passed / 9 skipped · apx.checks 45 · alembic single head 0019**. `apx/core/ports/embedding.py` left untracked.

### File List

**Production**
- `apx/core/domain/failures.py` — the FR-5 stable `ErrorClass` set; `cardinality_for`; `redacted_diagnostic`.
- `apx/core/app/ingest.py` — redacted failure diagnostics (no `str(exc)`); `IngestedFailure.custodian` threaded through every failure site.
- `apx/adapters/store_postgres/models.py` — `Failure.custodian` + `Failure.cardinality`; `matter` nullable.
- `apx/adapters/store_postgres/migrations/versions/0019_failure_register_fields.py` — new (add columns, backfill cardinality, matter nullable; reversible).
- `apx/adapters/store_postgres/backfill.py` — `failure.custodian` in `ENCRYPTED_COLUMNS`; `backfill_failure_cardinality`.
- `apx/adapters/store_postgres/store.py` — `save()`/`quarantine_unit` write custodian+cardinality; `register`, `register_all`, `retry_failure`, `bulk_retry`, `export_register`, `_reconcile_retry`, `_authorise_entry` + their result dataclasses (`RegisterEntry`, `RetryOutcome`, `BulkRetryOutcome`, `RegisterExport`).
- `apx/adapters/store_postgres/queue/__init__.py` — thread the job custodian to `quarantine_unit`.
- `apx/checks/register_ownership.py` (new) + `registry.py` + `manifest.py` + `README.md` — the AD-37 structural property.
- `apx/checks/encryption.py` — `cardinality` on the plaintext allowlist.
- `apx/api/app.py` — `RegisterEntryOut`/`RegisterOut`; the register read + export endpoints.

**Tests**
- `tests/domain/test_failures.py` (new) — enum + redaction + cardinality.
- `tests/adapters/test_failure_register.py` (new) — AC1–AC5 through the store.
- `tests/adapters/test_failure_migration.py` (new) — 0019 cardinality backfill.
- `tests/checks/test_register_ownership.py` (new) — the check fires/holds.
- `tests/api/test_register_api.py` (new) — the read endpoints, scope-filtered.
- `tests/checks/test_encryption_checks.py` (allowlist), plus the Story 2.5 `ENCRYPTED_COLUMNS` drift-guard now covers `failure.custodian`.
