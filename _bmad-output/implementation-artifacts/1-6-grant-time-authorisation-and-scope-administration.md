---
baseline_commit: 6b6dc3e
---

# Story 1.6: Grant-time authorisation and scope administration

Status: done

## Story

As a firm's supervising partner,
I want creating, granting, revoking and re-scoping *RBAC scopes* to be privileged, recorded and reversible acts,
so that a Chinese wall cannot be widened by anyone who happens to have access — a wall anyone can move is not a wall.

**Scope in one line:** make every scope mutation — **grant**, **revoke**, and **matter re-scope** — a **privileged** act (an administrative grant held by a named *tenant* user), **audited** (actor, subject, scope, authority, timestamp), and **reversible**; make the administrative grant *itself* an audited, reversible act whose first holder is set at provisioning (no implicit superuser); and prove it with a **mutating adversarial suite** that re-scopes a *matter* mid-*corpus*. **Not** the full AD-48 three-principal-kind enumeration (a later structural story), **not** encryption (1.7).

> The ad-hoc build has the scope CRUD (`grant_scope`/`revoke_scope`, the cockpit endpoints) but **does not audit it** and gates admin on a bare `is_admin` flag. 1.6 turns "the reads happen to filter by scope" into "the wall can only be moved by a named authority, and every move is on the record."

## Acceptance Criteria

> **Given** scope administration, **When** a scope is granted, revoked, or a *matter* re-scoped, **Then** each is a **privileged** act requiring an explicit **administrative grant** held by a named user of the *tenant*, each **recorded in the *audit record*** with actor, subject, scope, authority and timestamp, and each **reversible** (FR-49).
> **And** the administrative grant is **itself granted by the same mechanism**, its **first holder established at *tenant* provisioning**, with **no implicit superuser** and no identity that bypasses FR-14 — fail-closed applies to administrative and system identities alike (AD-12/AD-48).
> **And** a **re-scope** takes effect at the **next query** with nothing to propagate and no half-stamped window (FR-49 as amended, AD-13), recorded as **one operation with its before and after scope**.
> **And** *(failure path)* the **mutating adversarial suite** re-scopes a *matter* mid-*corpus* and asserts the wall holds in its **new** position **immediately** and in its **old** position **never**.

1. **AC1 — Every scope mutation is privileged, audited, reversible.** `grant_scope`, `revoke_scope`, and `rescope_matter` require the caller to hold the **administrative grant** (else fail closed, 403), and each writes an *audit-record* entry carrying `actor`, `subject` (the user or matter acted on), `scope` (and, for a re-scope, before→after), the `authority` (the admin acting), and the timestamp. Grant↔revoke and re-scope↔re-scope-back are reversible; nothing is hard-deleted (a revoke removes the grant row; the act is on the audit trail).
2. **AC2 — The administrative grant is a grant, not a bare superuser.** Administering scopes/admin requires the administrative grant (today `user_account.is_admin`, treated as the *scope-administration authority*). Granting/revoking it is **itself** a privileged, audited act (`set_user_admin`) that only a current admin may perform; the **first** admin is established at *tenant provisioning* (`ensure-admin`), tracing every admin back to it. There is **no implicit superuser**: holding the administrative grant does **not** widen a data read — an admin with no *RBAC scope* still gets an **empty** *corpus* (AD-12), proven by a test. Fail-closed applies to admin identities.
3. **AC3 — Re-scope is one operation, effective at the next query.** `rescope_matter(tenant, matter, new_scope)` updates the single authoritative `matter_scope` row and records one audit entry with before/after. Because scope is resolved live at query time (AD-13), the change takes effect on the next query with **nothing to propagate**, **no re-index**, and no half-stamped window. A no-op (same scope) is rejected or recorded as such — never a silent write.
4. **AC4 — The mutating adversarial suite.** A test seeds a *matter* with a *corpus* behind scope `old`, holds a session/user with `old` and another with `new`; re-scopes the *matter* to `new`; then asserts, on the **next** read: the `new`-holder now sees the *matter* and its counts (the wall moved), and the `old`-holder sees **nothing** and is denied (`ScopeDenied`) — the wall never holds in its old position after the move, and never held in its new position before it.
5. **AC5 — Structural check.** A static check asserts scope-mutating store methods (`grant_scope`, `revoke_scope`, `rescope_matter`) are audited (write an audit entry) — or the narrower, robust proxy the 1.x pattern allows — with a failure-path fixture. Registered in the harness.
6. **AC6 — Green and honest.** All existing tests pass; the cockpit endpoints (1.5-era) now flow through the audited, admin-gated methods; the README notes scope administration; no encryption (1.7) or AD-48 principal-enumeration over-build.

## Tasks / Subtasks

- [x] **Task 1 — Audit the scope grants** (AC: #1) — `apx/adapters/store_postgres/store.py`: `grant_scope`/`revoke_scope` write an *audit-record* entry (matterless, tenant-level, AD-43) carrying actor/subject(user)/scope/authority. Add the acting admin's identity as an argument (the API passes `ident`). Reversible (grant↔revoke); the row is removed on revoke, the act stays on the trail.
- [x] **Task 2 — Re-scope a matter** (AC: #3, #4) — a new `rescope_matter(tenant, actor, matter, new_scope)` that updates the one `matter_scope` row and records one audit entry with **before→after**; rejects a no-op; scope resolves live (AD-13) so nothing propagates. An admin endpoint `POST /api/admin/matters/{matter}/rescope`.
- [x] **Task 3 — The administrative grant** (AC: #2) — `set_user_admin(tenant, actor, subject_user, is_admin)`: an audited, admin-only mutation of the administrative grant; the first admin is the provisioned one (`ensure-admin` unchanged). An admin endpoint. Confirm holding the grant does not bypass the scope pre-filter (an admin with no scope reads an empty corpus) — a test.
- [x] **Task 4 — Wire the endpoints through the audited path** (AC: #1, #6) — `apx/api/app.py`: `admin_grant`/`admin_revoke` pass the acting admin so the mutation is audited; add the re-scope and set-admin endpoints (all `require_admin`). Keep `require_admin` as the gate; it already fails closed for non-admins.
- [x] **Task 5 — The mutating adversarial suite** (AC: #4) — `tests/adapters/test_rescope_isolation.py`: seed a matter+corpus behind `old`, a user with `old` and one with `new`; re-scope to `new`; assert on the next read the wall moved (new sees, old denied), and (before the re-scope) old saw and new was denied. SQLite + a PostgreSQL leg.
- [x] **Task 6 — Structural check** (AC: #5) — `apx/checks`: assert the scope-mutating store methods are audited (call the audit path), with a failure-path fixture (a mutator that skips the audit). Register in the harness; fail closed on unparseable (the 1.3–1.5 pattern).
- [x] **Task 7 — Tests + green** (AC: all) — audit-content tests (actor/subject/scope/authority/before-after); the no-superuser test; the re-scope no-op rejection; API tests (admin-gated, audited); the mutating suite; README. `ruff` + `python -m apx.checks` + `pytest` + fitness green.

## Dev Notes

- **What exists and what changes.** `grant_scope(tenant, user_id, scope)` / `revoke_scope(...)` exist but do **not** audit; `matter_scope` is written at ingest (`save`) and has no re-scope path; `user_account.is_admin` gates the cockpit (`require_admin`) and is set at `create_user`/`ensure-admin`. 1.6 adds auditing to the grants, a `rescope_matter` op, an audited `set_user_admin`, and the endpoints — without changing the RBAC pre-filter (1.4) or the session/auth model (1.5). [Source: apx/adapters/store_postgres/store.py; apx/api/app.py]
- **Re-scope is trivial to make correct because AD-13 already did the hard part.** Scope lives in exactly one place (`matter_scope`) and is joined live at query time; a re-scope is a single-row UPDATE, and the next query sees it — there is no denormalised copy to restamp, no re-index, no half-stamped window. This is the payoff of AD-13/FR-49; the test just has to *prove* it. [Source: ARCHITECTURE-SPINE.md#AD-13; PRD FR-49]
- **The administrative grant is a grant, not a superuser (AD-48/AD-12).** Treat `is_admin` as the *scope-administration authority*: an audited, admin-only, reversible grant whose first holder is provisioned. AD-48 defines three principal kinds and forbids a fourth and any implicit superuser; 1.6 delivers the **user** administrative grant and proves an admin does not bypass the scope pre-filter. The **full** AD-48 structural property (the closed principal enumeration; the tenant-bound maintenance kind with no path to a result-set constructor — for backup/migration/aggregates) is a **later structural story** (with 1.10/1.12), noted here so a reviewer does not expect it in 1.6. [Source: ARCHITECTURE-SPINE.md#AD-48, #AD-12]
- **Authority on the audit entry.** Each mutation records the acting admin as the `authority` and the target as the `subject`, plus the scope and (for a re-scope) before→after — so the record answers "who widened which wall, on whose authority, when" (FR-24/FR-53). Auth events use the per-tenant matterless chain (AD-43), the same path 1.5's `record_auth_event` uses. *(Carry forward 1.5's review note: high-volume events on the serialized chain head is an AD-44 concern; scope administration is low-volume, so it belongs on the chain.)* [Source: implementation-artifacts/1-5…; ARCHITECTURE-SPINE.md#AD-43]
- **Structural-check + fixture pattern (AD-33).** Reuse the 1.3–1.5 pattern: `CheckResult`, registered in `CHECKS`, explicit `roots`, fail closed on unparseable, fixtures AST-parsed only and `ruff`-clean. [Source: apx/checks/tenant_isolation.py]
- **Testing standards.** The mutating suite runs on SQLite everywhere + a PostgreSQL leg (skipped locally). Tests unreachable from runtime (AD-16). [Source: tests/adapters/test_tenant_isolation.py]

### Project Structure Notes

- Modified: `apx/adapters/store_postgres/store.py` (audit the grants, `rescope_matter`, `set_user_admin`), `apx/api/app.py` (endpoints through the audited path), `apx/checks/__main__.py` (register), `README.md`.
- New: `apx/checks/scope_admin.py` (the audited-mutation check), `tests/adapters/test_rescope_isolation.py`, `tests/checks/test_scope_admin_checks.py` + fixtures, audit-content tests.
- No new dependencies; no schema change expected (re-scope is an UPDATE; the administrative grant is the existing `is_admin`).

### References

- [Source: PRD FR-49] — re-scope takes effect at the next query, reversible, nothing to propagate.
- [Source: PRD FR-24, FR-53] — the audit record: actor, subject, authority, timestamp; a privileged act is recorded.
- [Source: ARCHITECTURE-SPINE.md#AD-13] — scope resolved live from one authoritative source; a re-scope is one UPDATE.
- [Source: ARCHITECTURE-SPINE.md#AD-48] — three principal kinds, no implicit superuser (the full enumeration deferred).
- [Source: ARCHITECTURE-SPINE.md#AD-12] — tenant/scope fail closed; an admin with no scope reads nothing.
- [Source: implementation-artifacts/1-4, 1-5] — the tenant/audit model, the adversarial-suite and structural-check patterns, the per-tenant matterless audit chain.

## Dev Agent Record

### Agent Model Used

Claude Opus 4.8 (1M context) — Claude Code dev-story workflow.

### Debug Log References

- `uv run pytest -q` → **250 passed, 8 skipped**. `uv run python -m apx.checks` → **11 passed**. `uv run ruff check .` → clean.

### Completion Notes List

- **Scope mutations are now audited (AC1).** `grant_scope`/`revoke_scope` gained an `actor` (the acting admin = authority) argument and each writes a matterless tenant-level audit entry (AD-43) with `actor`, `subject`, `scope`. Reversible: grant↔revoke, the row removed on revoke, the act on the trail. The cockpit endpoints (1.5-era) now pass `ident.actor`, so the existing surface flows through the audited path.
- **Re-scope (AC3/AC4).** `rescope_matter(tenant, actor, matter, new_scope)` updates the ONE `matter_scope` row and records one audit entry with **before→after**; it rejects a no-op (same scope) and an unknown matter — never a silent write. Because scope is resolved live (AD-13), the change takes effect at the next query with nothing to propagate. Endpoint `POST /api/admin/matters/{matter}/rescope`. The **mutating adversarial suite** proves the wall moves (new sees immediately, old denied) and never holds backwards.
- **The administrative grant is a grant, not a superuser (AC2).** `set_user_admin(tenant, actor, subject, is_admin)` is an audited, admin-only, reversible mutation of the administrative authority (today `is_admin`); the first admin is the provisioned one (`ensure-admin`), so every admin traces back to it. A test proves holding the grant does **not** widen a data read — an admin with no scope reads an empty corpus (AD-12). Endpoint `POST /api/admin/users/{user_id}/admin`.
- **Structural check (AC5).** `scope_mutations_are_audited` (AST over the store) fails the build on any scope mutator (`grant_scope`/`revoke_scope`/`rescope_matter`/`set_user_admin`) that does not call the audit path; a failure fixture proves it fires; fails closed on an unparseable file.
- **Open Questions resolved with the recommended defaults:** (1) `is_admin` is the administrative grant (the privileged, audited path is "the same mechanism"), not a reserved `user_scope` value; (2) AD-48's full three-principal closed enumeration + the maintenance-kind structural property are **deferred** to a later structural story (with 1.10/1.12) — 1.6 delivers the user administrative grant and proves no-implicit-superuser. No schema change; no new dependency.

### File List

**New**
- `apx/checks/scope_admin.py` — the audited-mutation structural check.
- `tests/adapters/test_rescope_isolation.py` — the mutating adversarial suite + audit-content + reversibility + no-superuser.
- `tests/checks/test_scope_admin_checks.py` — the check is live.

**Modified**
- `apx/adapters/store_postgres/store.py` — audited `grant_scope`/`revoke_scope` (with `actor`), new `rescope_matter`, `set_user_admin`.
- `apx/api/app.py` — grant/revoke pass the acting admin; new `admin_rescope` + `admin_set_admin` endpoints (`require_admin`).
- `apx/checks/__main__.py` (registered), `README.md`, `tests/adapters/test_auth_store.py`, `tests/adapters/test_session_store.py` (grant/revoke callers updated to the new signature).

### Change Log

| Date | Change |
|---|---|
| 2026-07-24 | Implemented story 1.6 — grant-time authorisation & scope administration: audited grant/revoke (with authority), matter re-scope as one audited op with before→after, the administrative grant as an audited admin-only reversible act (no implicit superuser), a mutating adversarial suite, and a structural check (scope mutations are audited). 250 passed / 8 skipped, 11 checks + ruff green. Status → review. |
| 2026-07-24 | Addressed the adversarial code review: fixed 1 High (ingest re-scope side-door) + 6 Med findings. 254 passed / 8 skipped; 11 checks green. Status → done. |

## Senior Developer Review (AI)

**Date:** 2026-07-24 · **Reviewers:** Blind Hunter + Edge-Case Hunter (parallel, blind; the Acceptance Auditor pass was interrupted) · **Outcome:** the sanctioned `rescope_matter` and the four mutations were verified tenant-scoped and correctly isolated — the wall was crossed **beside** them. Fixes applied.

### Findings and resolutions

- [x] **[High] The ingest side-door re-scoped a matter.** `save()` did `merge(MatterScope(...))` (PK `(tenant, matter)`), overwriting an existing matter's scope; the ingest endpoints are `current_identity`-gated (not admin) and check only the *target* scope. A non-admin could re-ingest under `matter=existing, scope=their-wall` and **seize the matter's whole corpus off the record**, bypassing every 1.6 guard (and invisible to the structural check). **Fixed:** `save()` creates the `matter_scope` on first ingest but **refuses** (`ScopeConflict` → 409) an ingest that would change an existing matter's scope — a wall moves only via the audited admin re-scope path. Store + behaviour tested.
- [x] **[Med] `create_user` granted scopes and admin with no audit** (and the check missed it). **Fixed:** it now audits the act (subject/email/scopes/admin flag) on the acting admin's authority, and is added to the structural-check mutator set.
- [x] **[Med] Last-admin self-revocation locked the tenant out.** **Fixed:** `set_user_admin` refuses to revoke the last administrator of a tenant (no in-app lockout); tested.
- [x] **[Med] Concurrent scope mutations collided on the audit `(tenant, seq)` → 500.** **Fixed:** the mutators share an `_audited_tx` helper that retries on the collision (the mitigation `record_auth_event` already had). *(The general `_append_audit` contention across all audited ops remains an AD-44 concern — deferred.)*
- [x] **[Med] The structural check was circumventable** (4 hard-coded names; passed vacuously on deletion/rename). **Fixed:** it now requires the known mutators to be **present** on the real tree (a rename/deletion fails the build) and includes `create_user`. *(Documented limitation: audit-call detection is lexical, not path-sensitive — the runtime tests cover the content.)*
- [x] **[Med] No-op mutations wrote phantom audit entries** (revoking an unheld scope, an idempotent re-grant, a no-change set-admin). **Fixed:** each mutation audits **only a real change** (matching `rescope_matter`'s "never a silent write"); tested.
- [x] **[Low] Store-level empty-scope rejection** added (fail-closed no longer depends on the edge); the **no-superuser test strengthened to the API layer** (an admin with no scope: `/me` shows no scopes, `/matters` shows nothing) since the store-level assertion short-circuited.

### Deferred (documented)

- [x] The general `_append_audit` `(tenant, seq)` contention across all audited ops (ingest/judge/…) — an AD-44 story (a non-chained or partitioned high-volume stream).
- [x] Audit `authority` is a renameable, non-unique `display_name`; `detail` is unescaped `key=value` — attribution/round-trip nits (a later observability/schema pass).
- [x] Matterless audit entries (grant/revoke/create/set-admin) have no read-back API surface — a tenant-level audit read endpoint is a later story.

**Post-fix verification:** `ruff` clean · `python -m apx.checks` **11/11** · `pytest` **254 passed, 8 skipped**.

## Open Questions for the human

1. **Administrative grant representation.** 1.6 treats `user_account.is_admin` as the scope-administration authority (an audited, admin-only, reversible grant), rather than introducing a reserved scope in `user_scope`. Confirm that's the right minimal reading of AC2's "granted by the same mechanism" (the *privileged, audited* grant flow), vs. a literal reserved-scope value.
2. **AD-48 scope.** 1.6 delivers the user administrative grant + proves no-implicit-superuser, and **defers** AD-48's full three-principal closed enumeration + the maintenance-kind structural property to a later story (with 1.10/1.12). Confirm that split.
