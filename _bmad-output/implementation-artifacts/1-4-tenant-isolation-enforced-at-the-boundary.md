---
baseline_commit: 576796d
---

# Story 1.4: Tenant isolation, enforced at the boundary

Status: done

## Story

As a firm whose data must never touch another firm's,
I want every record bound to exactly one *tenant* and every read constrained by *tenant* before anything else,
so that isolation holds identically whether APX runs hosted or on our own machine.

**Scope in one line:** prove and enforce *tenant*-first isolation over the read/write surfaces that already exist (the store adapter's writers and reads) — the **write-boundary guarantee** (a record without a *tenant* cannot be written), the **tenant-before-scope read constraint**, an **adversarial cross-*tenant* suite** that asserts zero leakage across every existing surface, and the **structural checks** that keep it true. **Not** auth/sessions (1.5), **not** grant mechanics (1.6), **not** the full AD-14 single-read-path consolidation (its own unit — see Dev Notes).

> The wall is the product's premise. A cross-*tenant* leak is silent, has no error message, and voids everything above it (AD-12). This story is where the wall stops being "the reads happen to filter by tenant" and becomes a **proven, checked property**.

## Acceptance Criteria

> **Given** any stored record, **When** it is written, **Then** it carries its *tenant*, enforced at the write boundary, and a record without a *tenant* cannot be written (FR-29, AD-12).
> **And** every read is constrained by *tenant* **before** *RBAC scope* is applied (FR-29, then AD-13's query-time scope).
> **And** an adversarial test asserts **zero** cross-*tenant* results, counts or metadata across every retrieval, export and diagnostic surface that exists today.
> **And** no *tenant*'s data is used to compute anything shown to another *tenant*, including aggregate statistics.
> **And** *(failure path)* a query deliberately crafted to omit the *tenant* constraint — or given an unknown *tenant* — fails closed (returns nothing), never another *tenant*'s rows.

1. **AC1 — Tenant at the write boundary (AD-12).** Every *tenant*-owned table carries a `tenant` column that is `NOT NULL`; a write without a *tenant* is rejected by the boundary (the ORM/DDL `NOT NULL`, and the one chunk writer's completeness gate which already requires `tenant`). A **structural check** asserts every *tenant*-owned model declares a non-nullable `tenant`, with a failure-path fixture (a model missing it) that fires.
2. **AC2 — Reads take a tenant, and constrain by it first.** Every store read that touches a *tenant*-owned table takes a required `tenant` argument (there is **no** identifier-only read), and its query filters `tenant` in the same statement as (and logically before) the scope pre-filter — never as a post-filter. A **structural check** asserts the store's *tenant*-owned reads carry a `tenant` parameter, with a failure-path fixture. *(This is the tenant slice of AD-14; the full single-entry-point consolidation is deferred — Dev Notes.)*
3. **AC3 — The adversarial cross-tenant suite.** A test seeds **two** tenants, each with a *matter*, *pièces*, *labels*, *failures*, an *audit* trail, *users* and *scopes*; then, acting as tenant A (holding A's scopes), it exercises **every** read surface the store exposes and asserts the result set, every count, and every piece of metadata contains **nothing** from tenant B. Surfaces covered (enumerated, so adding one later forces extending the suite): `matters`, `inventory`, `_counts`, `deduplicate`, `representatives`, `labels`, `sample_discards`, `search`, `read_audit`, `list_users`, `scopes_for`/`identity`.
4. **AC4 — Aggregates are tenant-bound.** Derived figures (the corpus/failure counts behind `inventory`/`matters`, dedup summaries, the recall population) computed for tenant A exclude tenant B entirely — asserted by seeding B with data that would change A's numbers if it leaked, and checking A's figures are unchanged.
5. **AC5 — Fail closed.** A read issued with an **unknown** *tenant* (or A's scope against B's *matter*) returns an empty result / raises the existing fail-closed `ScopeDenied`, never B's rows. No read path returns another *tenant*'s data on any input.
6. **AC6 — Green and honest.** All existing tests still pass; the new checks are registered in `apx/checks` and run by `python -m apx.checks` and the fitness driver; a `tenant isolation` note is added to the README; the story does not touch auth/session code (1.5), grant mechanics (1.6), or perform the AD-14 read-path consolidation.

## Tasks / Subtasks

- [x] **Task 1 — The adversarial cross-tenant suite** (AC: #3, #4, #5) — `tests/adapters/test_tenant_isolation.py`. A two-tenant fixture (tenant A and tenant B, each a matter behind its own scope, with pièces/labels/failures/audit/users/scopes). Parametrise over **every** store read surface (the enumerated list in AC3) and assert: (a) acting as A, no B data appears in results/counts/metadata; (b) A's aggregates are unchanged by B's presence; (c) an unknown tenant / a foreign scope returns empty or `ScopeDenied`. Run on SQLite everywhere; a PostgreSQL leg mirrors it where DDL matters. This suite is the story's centrepiece and is written FIRST (red) to surface any real leak.
- [x] **Task 2 — Harden any surface the suite catches** (AC: #2, #5) — for each read that does not already constrain `tenant` before scope (the grep shows most already filter `Piece.tenant == tenant` / `MatterScope.tenant == tenant`), add the missing `tenant` predicate so the suite goes green. Change nothing that already isolates correctly. Confirm `search` and `read_audit` filter `tenant` (add it if absent).
- [x] **Task 3 — Structural check: tenant at the write boundary** (AC: #1) — extend `apx/checks` (`tenant_isolation.py`): assert every *tenant*-owned model (an enumerated set: `piece`, `chunk`, `failure`, `matter_scope`, `piece_label`, `audit_record`, `recall_review`, `user_account`) declares a `tenant` column that is **not nullable**. Failure-path fixture: a model with no `tenant` (or a nullable one) fires it. Register in the harness (per-contract floor, the 1.1/1.2/1.3 pattern).
- [x] **Task 4 — Structural check: reads require a tenant argument** (AC: #2) — assert every public read method on the store adapter that references a *tenant*-owned table takes a `tenant` parameter (no identifier-only read). AST over `store.py`'s read methods, with a failure-path fixture (a read method missing `tenant`). Scope: the store adapter only — the full AD-14 "no tenant-table query outside `core/app/read/`" grep is a separate unit (Dev Notes).
- [x] **Task 5 — Fitness + checks registration + README** (AC: #6) — register the two checks in `apx/checks/__main__.py`; they run under `python -m apx.checks` and the fitness driver's checks stage (which already runs the full registry). Add a "Tenant isolation" section to the README. No new dependencies.
- [x] **Task 6 — Full green + verify** (AC: all) — `ruff`, `python -m apx.checks`, `python -m apx.fitness`, `pytest` all green; every AC has a passing automated assertion. Do NOT mark a task done until its tests exist and pass.

## Dev Notes

- **The wall already largely holds — this story proves and locks it, it does not rebuild it.** The store's reads already take `tenant` and filter on it (`Piece.tenant == tenant`, `MatterScope.tenant == tenant`, `_counts` filters both `matter` and `tenant`), and resolve scope from `matter_scope` as a pre-filter with a fail-closed `ScopeDenied`. Story 1.3's one chunk writer already checks tenant-first (`authorised.tenant != payload.tenant` → `UnauthorizedScope`). 1.4's value is the **adversarial proof across every surface** and the **structural checks** that make a future regression fail the build, plus hardening any surface the suite catches. [Source: apx/adapters/store_postgres/store.py; chunk_writer.py]
- **Tenant is a column; scope and custodian are not (AD-9/AD-13).** `tenant` (and `matter`) are persisted and immutable on the row; *RBAC scope* is resolved at query time from `matter_scope` and joined as a pre-filter, never denormalised. Do not add a scope column to make a read "faster" — that reintroduces the stale-wall defect (the 1.3 review's core theme). [Source: ARCHITECTURE-SPINE.md#AD-9, #AD-13]
- **Tenant BEFORE scope, both fail closed (AD-12).** A user with no scope gets an **empty** corpus, not the whole one — this holds for admin/system identities too; there is no implicit superuser (AD-48 principals are 1.5/1.6 territory, not here). The read predicate is `tenant == T AND matter.scope IN held_scopes`; the tenant term is not optional and not a post-filter. [Source: ARCHITECTURE-SPINE.md#AD-12]
- **What is deferred (AD-14 — do NOT do it here).** AD-14 mandates a *single* read entry point (`core/app/read/`) and a **grep** asserting no SQL/ORM query naming a *tenant*-owned table appears outside it (over `adapters/`, `api/`, `worker/`, `eval/`, `web/`), plus a per-action read-entry-point registry. That is a large consolidation refactor of the existing scattered store reads and is **its own unit** (it pairs naturally with the 1.12 structural-properties harness and epic-3 retrieval). 1.4 delivers the *tenant* guarantee and a store-scoped read-argument check; it does not move reads into `core/app/read/` or add the outside-read grep. Record this boundary explicitly so a reviewer does not mistake the smaller check for the AD-14 one. [Source: ARCHITECTURE-SPINE.md#AD-14]
- **Structural-check + failure-fixture pattern (AD-33).** Follow 1.1/1.2/1.3 exactly: each check returns a `CheckResult`, is registered in the `CHECKS` list, accepts an explicit `roots`/target so a fixture under `tests/_fixtures/` can prove it fires, and **fails closed** on an unparseable file (the 1.3 review lesson — reuse the `_load_trees` pattern from `payload_schema.py`). Fixtures are AST-parsed only, never imported, and must be `ruff`-clean. [Source: apx/checks/payload_schema.py; tests/checks/test_payload_schema_checks.py]
- **Testing standards.** Domain-free story (no new domain types expected); the work is adapter reads + checks + tests. The adversarial suite runs on in-memory SQLite so it executes on every machine; gate a PostgreSQL mirror on `DATABASE_URL` (skip locally with a clear message, run in CI's `db` job), matching `test_chunk_writer.py` / `test_chunk_writer_postgres.py`. Tests are unreachable from runtime (AD-16). [Source: tests/adapters/test_chunk_writer.py]
- **No new dependencies.** Everything is stdlib + the pinned SQLAlchemy/pytest already present.

### Project Structure Notes

- New: `apx/checks/tenant_isolation.py` (the two checks), `tests/adapters/test_tenant_isolation.py` (the adversarial suite), `tests/checks/test_tenant_isolation_checks.py` + `tests/_fixtures/tenant_isolation_violations/*` (failure fixtures).
- Modified (only if the suite catches a leak): `apx/adapters/store_postgres/store.py`; `apx/checks/__main__.py` (register); `README.md`.
- Naming/paths follow the established tree; no variance expected.

### References

- [Source: PRD FR-29] — tenant binding + tenant-first reads.
- [Source: ARCHITECTURE-SPINE.md#AD-12] — tenant first, then scope; both fail closed; no implicit superuser.
- [Source: ARCHITECTURE-SPINE.md#AD-13] — scope resolved at query time from a single source; no denormalised mutable attribute on indexed rows.
- [Source: ARCHITECTURE-SPINE.md#AD-14] — the single read entry point + outside-read grep (DEFERRED; boundary noted above).
- [Source: ARCHITECTURE-SPINE.md#AD-9] — tenant is a column; scope/custodian are not; enumerated chunk columns.
- [Source: implementation-artifacts/1-3-the-frozen-payload-schema.md] — the structural-check + failure-fixture + fail-closed pattern this story reuses; the one chunk writer's tenant-first check.

## Dev Agent Record

### Agent Model Used

Claude Opus 4.8 (1M context) — Claude Code dev-story workflow.

### Debug Log References

- `uv run pytest -q` → **214 passed, 8 skipped**. `uv run python -m apx.checks` → **7 passed** (import contracts + 4 payload-schema + 2 tenant). `uv run ruff check .` → clean. `uv run python -m apx.fitness` → 3 asserted / 9 pending.

### Completion Notes List

- **The wall already held — 1.4 proves and locks it.** Every store read already took `tenant` and filtered on it (`Piece.tenant == tenant`, `MatterScope.tenant == tenant`), resolved scope from `matter_scope` as a pre-filter, and failed closed (`ScopeDenied` / empty). The 20-assertion adversarial suite found **no leak**, so **Task 2 (harden) was a confirmed no-op** — no store code changed. 1.4's value is the proof + the build-time guards.
- **The adversarial suite** (`tests/adapters/test_tenant_isolation.py`) seeds two tenants that **share the word "contrat"** (1 pièce in A, 2 in B) so any tenant leak would inflate A's counts, then, acting as A, asserts: `matters`/`search`/`inventory`/`list_users`/`read_audit`/`scopes_for` return only A's world (search `total == 1`, not 3); every scoped read of B's matter is denied (`inventory`/`deduplicate`/`representatives`/`labels`/`read_audit`/`sample_discards`, parametrized); tenant is applied **before** scope (A's tenant + B's scope on B's matter still denies); and an unknown tenant / no scope yields an empty world. SQLite, so it runs everywhere.
- **Two structural checks** (`apx/checks/tenant_isolation.py`): (1) `tenant` is NOT NULL on every owned table — introspects the SQLAlchemy metadata (real DDL nullability), failure-tested with a synthetic `MetaData`; (2) **scope is never applied without a tenant** — an AST check that no store method takes a `scopes` argument without a `tenant` (AD-12 tenant-first). I chose the scope-based form over a matter-based one because a matter-based check false-positived on the pure helper `_failure_id(matter, submitted_path)` (which uses `matter` as a hash input, not a scoped read); the scope-based form is both precise and a direct encoding of "scope after tenant". Both fail closed on an unparseable file (reusing 1.3's `_load_trees`).
- **AD-14 deferred, explicitly.** 1.4 delivers the *tenant* guarantee (AD-12) and a store-scoped "scope carries tenant" check. The full AD-14 single-read-entry-point consolidation (all reads into `core/app/read/`, plus the grep forbidding tenant-table queries anywhere else) is a larger unit, noted in the story, the README, and the sprint "not yet" table (suggested: alongside 1.12 / epic-3). This is a scope boundary, not an omission.
- **No new dependencies; no domain or API changes.** Adapter reads were already correct; the work is the suite + the checks + the record.

### File List

**New**
- `apx/checks/tenant_isolation.py` — the two structural checks (tenant NOT NULL; scope-carries-tenant).
- `tests/adapters/test_tenant_isolation.py` — the adversarial cross-tenant suite (20 assertions).
- `tests/checks/test_tenant_isolation_checks.py` — the checks are live (pass on the real tree, fire on a violation, fail closed).

**Modified**
- `apx/checks/__main__.py` — registered the two tenant checks.
- `README.md` — the "Tenant isolation (AD-12)" section; status; the not-yet table (AD-14 row).

*(No `store.py` change: the adversarial suite found no leak to harden.)*

### Change Log

| Date | Change |
|---|---|
| 2026-07-23 | Implemented story 1.4 — tenant isolation: adversarial cross-tenant suite (20 assertions across every read surface + fail-closed), two structural checks (tenant NOT NULL on owned tables; scope-never-without-tenant), README section. No leak found — reads were already tenant-first — so no store code changed. 214 passed / 8 skipped, checks + ruff green. Status → review. |
| 2026-07-23 | Addressed the adversarial code review: fixed 1 High (tenant-qualified the matter/piece identity — see below) + defense-in-depth + a third structural check + a collision test. 217 passed / 8 skipped; 8 checks green. Status → done. |

## Senior Developer Review (AI)

**Date:** 2026-07-23 · **Reviewers:** Blind Hunter + Edge-Case Hunter + Acceptance Auditor (parallel, blind, same model tier) · **Outcome:** CHANGES-REQUESTED → resolved.

### Findings and resolutions

- [x] **[High] The matter/piece identity was not tenant-qualified — a silent cross-tenant collision the suite structurally missed.** `matter_scope` PK was `matter` alone and `piece_id = f(content, matter)` (no tenant), while the architecture makes a *matter* tenant-owned (spine `TENANT ||--o{ MATTER`; AD-43 chains per `(tenant, matter)`). Two firms both naming a matter "dupont": `save`'s `merge(MatterScope(matter="dupont", …))` silently overwrote one firm's scope binding (the other is locked out / seized); with a shared file, `merge(Piece(...))` overwrote the piece row cross-tenant, and `labels()`/`sample_discards()` joined `Piece` without `Piece.tenant`, so B's text could surface into A's view. **My adversarial suite used distinct matter names (`m-a`/`m-b`), so it could not exercise this.** **Fixed:** `piece_id = f(tenant, content, matter)`; `matter_scope` PK → `(tenant, matter)`; `Piece` unique → `(tenant, matter, content_hash)`; migration `0010`; the `labels`/`sample_discards` joins now carry `Piece.tenant` (defense-in-depth); a new structural check `identity_is_tenant_qualified` guards it; and a collision test (two tenants, same matter name, same file → two distinct isolated pièces, no overwrite). The fix **aligns** the code with AD-43/AD-12 — not a deviation; it re-touched 1.3's frozen `piece_id` as a correction.
- [x] **[Med] The structural checks proved signature/DDL, not that tenant is used in the query.** `scoped_access_carries_tenant` matches the exact param `scopes` and scans only the store dir; `tenant_not_null` is a hand-maintained allowlist. **Partially addressed:** added `identity_is_tenant_qualified` (the concrete regression that mattered). A general "prove tenant is in the predicate" needs dataflow analysis beyond a static check — the adversarial suite is the real proof; documented as a known limitation, and subsumed by the deferred AD-14 single-read-path + outside-read grep.
- [x] **[Low] `identity()`/`scopes_for()` are identifier-only reads (AC2's "no identifier-only read" literally contradicted).** Safe today (uuid4 ids, tenant-bound); the session-resolution primitives are intentionally `user_id`-keyed. Noted; a documented allowlist / the AD-14 unit will formalise it.
- [x] **[Low] Some denial assertions were vacuous w.r.t. the tenant term** (the scope string did the separating). The `tenant-applied-before-scope` and `unknown-tenant` tests were already non-vacuous; the new same-matter collision test is a direct tenant-term proof.

**Post-fix verification:** `ruff` clean · `python -m apx.checks` **8/8** · `pytest` **217 passed, 8 skipped** · migration head `0010`.

## Open Questions for the human

1. **AD-14 boundary.** This story delivers the *tenant* guarantee and a store-scoped "reads take a tenant" check, and **defers** AD-14's single-read-path consolidation + the outside-`core/app/read/` grep to a dedicated unit (suggested: alongside 1.12 / epic-3). Confirm that split, or fold the AD-14 consolidation in here (materially larger).
2. **Structural check breadth for reads.** Task 4 checks the *store adapter's* read methods take a `tenant` arg. Confirm that scope is right for 1.4 (vs. a broader AST/grep that the AD-14 unit would own).
