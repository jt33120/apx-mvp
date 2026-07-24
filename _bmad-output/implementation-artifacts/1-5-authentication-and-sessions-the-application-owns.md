---
baseline_commit: 13f1497
---

# Story 1.5: Authentication and sessions the application owns

Status: done

## Story

As a lawyer signing in to a tool holding privileged material,
I want authentication and sessions handled by the application itself, not by a hosting provider,
so that the same identity model works air-gapped and hosted, and no third party stands between me and the wall.

**Scope in one line:** migrate the owned auth to AD-15's adopted stack — **Argon2id via `pwdlib[argon2]`** for passwords and **opaque server-side sessions in PostgreSQL** (replacing the ad-hoc scrypt + stateless-HMAC tokens) — with lifetimes and invalidation (password change, scope revocation, sign-out), lockout recorded in the *audit record*, `Principal` resolution behind **one** interface, and the **no-reversible-credential-storage** structural check. MFA is *configuration-as-data per tenant* (`[ASSUMPTION]` carried, minimal). **Not** the grant-administration UX (1.6), **not** encryption-at-rest (1.7).

> AD-15 is `[ADOPTED]` and specific. The ad-hoc build chose scrypt + stateless signed tokens — reasonable, but not the adopted stack. This story brings the code to AD-15 exactly, because the security core is where "reasonable but divergent" is most expensive later.

## Acceptance Criteria

> **Given** the authentication surface, **When** a credential is stored, **Then** it uses **Argon2id via `pwdlib[argon2]` 0.3.0** with a per-credential salt, and a **static check asserts no reversible credential storage exists anywhere** (FR-48, FR-56).
> **And** sessions are **opaque, server-side (PostgreSQL)**, with a configured **absolute and idle lifetime**, invalidated on **password change**, on **scope revocation**, and on **explicit sign-out**, with identifiers that are **not guessable and not reusable** (FR-48; no JWT for user sessions).
> **And** a configured **lockout / rate limit** applies to repeated authentication failure, and **every failure and lockout is recorded in the *audit record*** (FR-48).
> **And** **multi-factor authentication exists and is *configuration-as-data* per tenant** (FR-48, TOTP via `pyotp`; `[ASSUMPTION]` carried — minimal).
> **And** *(failure path)* a **revoked scope invalidates the live session** that held it, at the **next request**, not at the next login (ties FR-14, FR-49).

1. **AC1 — Argon2id passwords.** `hash_password`/`verify_password` use `pwdlib[argon2]` 0.3.0 (Argon2id, per-credential salt, self-describing PHC string). No password plaintext is ever stored. Legacy scrypt hashes verify during a transition **and are re-hashed to Argon2id on the next successful login** (upgrade-on-verify), OR the sole bootstrap admin is re-created with an Argon2id hash — pick the migration path and document it. The domain module still imports only its dependency (no hosted SDK).
2. **AC2 — Opaque server-side sessions.** A `session` table in PostgreSQL holds: an **opaque, unguessable** id (`secrets.token_urlsafe`, ≥128 bits), `user_id`, `tenant`, `created_at`, `last_seen_at`, and the configured **absolute expiry**; a session is valid iff not past its absolute expiry **and** not idle beyond the configured idle window. Sign-in creates a row and sets an opaque cookie (the id, never a signed claim blob); each request **looks up** the session (there is no stateless self-verifying token for user sessions — no JWT). Sign-out **deletes** the row (the id is not reusable). Lifetimes are configuration-as-data.
3. **AC3 — Invalidation.** A **password change** deletes all of that user's sessions; an **explicit sign-out** deletes the current one; a session past absolute/idle expiry is treated as absent and its row is reaped. Each is covered by a test.
4. **AC4 — Scope revocation reaches live sessions (AC/FR-14, FR-49).** Because scopes are resolved **live** at each request from the grant store (AD-13), a session re-resolves the caller's current scopes every request — a revoked scope is gone on the **next request**, not the next login. A test grants A a scope, opens a session, revokes it, and asserts the very next authorised read fails closed.
5. **AC5 — Lockout recorded in the audit.** A configured threshold of consecutive failures for an identity/IP triggers a lockout window; **every failed attempt and every lockout is written to the *audit record*** under a system actor (the existing per-tenant audit chain). The in-memory rate-limiter added during hardening is folded into this (or replaced) so failures are durably audited, not only throttled in memory.
6. **AC6 — Principal behind one interface; no reversible storage (structural).** `Principal` resolution (tenant + held scopes + admin flag from a session) sits behind **one** interface; **no route imports the session table directly**. A **structural check** asserts **no reversible credential storage** exists — no plaintext password column, no reversible cipher/encoding applied to a credential — with a failure-path fixture. A second (cheap, forward-looking) structural check asserts every `jwt.decode` passes a **literal `algorithms=` list** and that `PyJWK`/`PyJWKClient`/`jwks` appear in no runtime module (AD-15) — it passes vacuously today (no user-session JWT) and is ready when internal service tokens land.
7. **AC7 — MFA is configuration-as-data (`[ASSUMPTION]`, minimal).** A per-tenant config flag enables TOTP (`pyotp` 2.10.0) as a second factor; when enabled, a correct TOTP is required after the password. Enrollment/recovery UX is minimal and the assumption is carried forward (WebAuthn via `py_webauthn` is additive and **deferred**). Keep this lean — do not build a full MFA management surface here.
8. **AC8 — Green and honest.** New deps pinned exactly (AD-30) and load offline; migration up/down; all checks (incl. the two new) registered and green; the SPA login still works end-to-end; no grant-admin UX (1.6) or encryption (1.7) built here.

## Tasks / Subtasks

- [x] **Task 1 — Dependencies** (AC: #1, #7) — add to `pyproject` **exact** pins per AD-15/Stack: `pwdlib[argon2]==0.3.0`, `pyotp==2.10.0`. (`PyJWT==2.13.0` and `py_webauthn==3.0.0` are AD-15's stack but are **not** needed by user sessions here — add PyJWT only if the jwt.decode check needs an import target; otherwise defer.) Confirm they resolve and load with the offline env set. Record any environment substitution per the 1.1 deviation convention.
- [x] **Task 2 — Argon2id** (AC: #1) — rewrite `apx/core/domain/auth.py`'s `hash_password`/`verify_password` over `pwdlib` (Argon2id). Self-describing PHC output; constant-time verify; per-credential salt (pwdlib default). Decide + implement the legacy path (upgrade-on-verify for scrypt, or admin re-bootstrap) and document it. Keep the module import-clean (pwdlib only).
- [x] **Task 3 — The session store** (AC: #2, #3) — `apx/adapters/store_postgres`: a `session` model (opaque id PK, user_id, tenant, created_at, last_seen_at, absolute_expiry; no cascade FK — AD-7) + a `SessionStore`/store methods `create_session`, `resolve_session` (validate absolute+idle, touch `last_seen_at`), `delete_session`, `delete_user_sessions`. Opaque id via `secrets.token_urlsafe(32)`. Migration `0011`. Lifetimes from config-as-data (env/config, with sane defaults).
- [x] **Task 4 — Principal behind one interface** (AC: #2, #4, #6) — a single `Principal` resolution entry point (tenant + live scopes + admin) used by the API; **no route touches the session table directly**. Rewire `apx/api/app.py` login to create a server-side session and set an **opaque** cookie (Secure, HttpOnly, SameSite — the hardening cookie flags), `me`/authenticated routes to resolve via the session store and **re-resolve scopes live** each request, `logout` to delete the session, and `change_password` to delete all the user's sessions. Remove the stateless `sign_token`/`verify_token` user-session path (keep those functions only if reused for internal service tokens; else delete).
- [x] **Task 5 — Lockout in the audit** (AC: #5) — a configured consecutive-failure threshold + window; every failed login and every lockout written to the *audit record* under a system actor (per-tenant chain, AD-22/AD-44 shape). Fold in / replace the in-memory `_LoginRateLimiter`.
- [x] **Task 6 — MFA config-as-data (minimal)** (AC: #7) — a per-tenant config flag; when on, require a correct `pyotp` TOTP after the password. Minimal enrollment (a stored TOTP secret per user, set at create/first-login); no recovery-code UX (assumption carried). Keep lean.
- [x] **Task 7 — Structural checks** (AC: #6) — `apx/checks`: (a) **no reversible credential storage** — assert no plaintext-password column and no reversible cipher/encoding of a credential field (AST/name-based over models + store), fail closed, with a failure fixture; (b) **jwt.decode algorithm list** — every `jwt.decode` call passes a literal `algorithms=[...]`, and `PyJWK`/`PyJWKClient`/`jwks` appear in no runtime module (passes vacuously today), with a failure fixture. Register both in the harness.
- [x] **Task 8 — Tests + green** (AC: all) — domain (Argon2id round-trip, legacy verify/upgrade, TOTP); adapter (session create/resolve/expire/delete, invalidation on password-change and revocation, PostgreSQL leg); API (login→session cookie, me, logout, change_password invalidates, lockout audited); checks (both fire on fixtures). Migration up/down. `ruff` + `python -m apx.checks` + `pytest` + fitness green.

## Dev Notes

- **AD-15 is the contract, verbatim.** Opaque server-side sessions in PostgreSQL; Argon2id via `pwdlib[argon2]` 0.3.0; PyJWT 2.13.0 **internal service tokens only, never user sessions**; `pyotp` 2.10.0 TOTP; `py_webauthn` 3.0.0 additive (deferred); **no reversible credential storage** (structural); `Principal` behind one interface, no route imports the session table; and — when any `jwt.decode` exists — an explicit literal `algorithms=` list (structural), with `PyJWK`/`PyJWKClient`/`jwks` absent from runtime. [Source: ARCHITECTURE-SPINE.md#AD-15]
- **What exists today and must change** (read these before editing): `apx/core/domain/auth.py` hashes with **scrypt** and issues **stateless HMAC-SHA256 tokens** (`sign_token`/`verify_token`) — both diverge from AD-15. `apx/api/app.py` sets a cookie from `sign_token` and resolves the caller in `current_identity` from `verify_token`; there is an in-memory `_LoginRateLimiter` (hardening). `apx/adapters/store_postgres/store.py` has `authenticate`, `create_user`, `set_password`, `verify_user_password`, `scopes_for`, `identity`, and the User/UserScope models. Story 1.5 swaps scrypt→Argon2id and stateless-token→server-side-session **without** changing the RBAC/tenant model (1.4) or the audit chain (keep them intact). [Source: apx/core/domain/auth.py; apx/api/app.py; apx/adapters/store_postgres/store.py]
- **The migration path for existing credentials.** No real *corpus*/users exist (CLAUDE.md), but the deployed demo admin has a scrypt hash. Prefer **upgrade-on-verify** (verify accepts a legacy scrypt hash once, then re-hashes to Argon2id) so nothing locks out; or re-bootstrap the admin with Argon2id via `ensure-admin`. Document the choice. Do not keep scrypt as a *new-credential* path — Argon2id is the only forward hasher.
- **Sessions are looked up, not self-verified.** The whole point of "opaque server-side" is that the cookie carries an unguessable **id**, and authority comes from the row — so revocation, sign-out and password-change are immediate (delete the row) rather than "wait for the token to expire". This is why AD-15 rejects JWT for user sessions. Re-resolve **scopes** live each request (AD-13) so 1.4's revocation-reaches-live-sessions holds. [Source: ARCHITECTURE-SPINE.md#AD-13, #AD-15]
- **No route imports the session table.** Put session lifecycle behind the store's `SessionStore` methods and Principal resolution behind one function; the API calls that, never `select(Session)`. A future check (or the AD-14 unit) can enforce it; here, keep the discipline and note it.
- **Structural-check pattern (AD-33).** Reuse the 1.3/1.4 pattern: `CheckResult`, registered in `CHECKS`, explicit `roots`, fail closed on unparseable (reuse `_load_trees`), fixtures AST-parsed only and `ruff`-clean. The no-reversible-storage check is the load-bearing one (FR-56); the jwt.decode check is cheap insurance that pays off when service tokens land.
- **Dependencies load offline.** `pwdlib[argon2]` pulls `argon2-cffi` (a C ext) — confirm it builds/loads in the slim runtime image and under the offline env; record any substitution per the 1.1 convention. `pyotp` is pure-Python. Pin exactly (AD-30).
- **Testing standards.** Domain pure/fast (Argon2id is slow by design — keep hashing tests few, or use low params for tests); adapter session tests on SQLite everywhere + a PostgreSQL leg (skip locally); API tests via the TestClient. Tests unreachable from runtime (AD-16). [Source: tests/adapters/test_chunk_writer.py]

### Project Structure Notes

- New: `apx/adapters/store_postgres/migrations/versions/0011_session.py`; a `Session` model + `SessionStore` methods in `store_postgres`; `apx/checks/credential_storage.py` (the two checks); tests + fixtures.
- Modified: `apx/core/domain/auth.py` (Argon2id; session helpers if any move here), `apx/api/app.py` (server-side session wiring), `apx/checks/__main__.py`, `pyproject.toml`, `README.md`.
- Naming per the tree; `Session` is a glossary-neutral technical term (not a domain entity) — fine.

### References

- [Source: PRD FR-48] — owned auth, Argon2id, server-side sessions, lockout, MFA config-as-data.
- [Source: ARCHITECTURE-SPINE.md#AD-15] — the adopted auth stack + the no-reversible-storage and algorithm-list structural properties.
- [Source: ARCHITECTURE-SPINE.md#AD-13] — scopes resolved live at query time (why revocation reaches live sessions).
- [Source: PRD FR-14, FR-49] — revocation reaches open sessions within a bounded interval / at the next request.
- [Source: implementation-artifacts/1-3, 1-4] — the structural-check + failure-fixture + fail-closed pattern; the tenant/audit model to preserve.

## Dev Agent Record

### Agent Model Used

Claude Opus 4.8 (1M context) — Claude Code dev-story workflow.

### Debug Log References

- `uv run pytest -q` → **240 passed, 8 skipped**. `uv run python -m apx.checks` → **10 passed**. `uv run ruff check .` → clean. Migration head `0012`.
- Dependency gate confirmed first: `pwdlib[argon2]==0.3.0` (+ `argon2-cffi`, a C ext) and `pyotp==2.10.0` install and load; Argon2id `$argon2id$…` + `verify_and_update` + TOTP APIs verified.

### Completion Notes List

- **Passwords: scrypt → Argon2id (AC1).** `auth.py` now hashes with `pwdlib` (Argon2id). `verify_password` accepts a legacy scrypt hash, and `verify_and_upgrade` re-hashes it to Argon2id on the next successful login (upgrade-on-verify — Open Question 1's recommended default). `store.authenticate` persists the upgraded hash. scrypt is never a new-credential hasher.
- **Sessions: stateless HMAC token → opaque server-side rows (AC2/AC3).** A `session` table (migration `0011`) holds an unguessable `secrets.token_urlsafe(32)` id, `user_id`, `tenant`, and absolute expiry; the idle window slides on `last_seen_at`. The cookie carries only the id — authority is the row (no JWT for user sessions). One Principal-resolution interface (`create_session`/`resolve_session`/`delete_session`/`delete_user_sessions`); `resolve_session` reaps expired rows and resolves actor/admin/**scopes live**. `app.py` rewired: `login` creates a session, `current_identity` resolves it, `logout` deletes it, `change_password` invalidates all of a user's sessions. `APX_SECRET_KEY` is no longer needed for sessions (removed `_secret`); lifetimes are config-as-data (`APX_SESSION_ABSOLUTE_SECONDS`/`_IDLE_SECONDS`).
- **Revocation reaches live sessions (AC4).** Scopes are re-resolved live at every `resolve_session`, so a revoked scope is gone on the next request — proven by a test.
- **Lockout in the audit (AC5).** `record_auth_event` appends a matterless, tenant-level audit entry (AD-43); `login` records each failed attempt and the lockout transition under a `system:auth` actor. *Consideration:* failures are recorded against the **attempted** tenant, so a login attempt names a tenant even when the tenant/credential is wrong (a minor audit-chain-for-a-nonexistent-tenant possibility, bounded by the per-IP rate limit).
- **MFA config-as-data per tenant (AC7, [ASSUMPTION] carried, minimal).** A `tenant_config` table (migration `0012`) carries `mfa_required`; `user.mfa_secret` holds a TOTP secret. When a tenant requires MFA and the user is enrolled, `login` demands a correct `pyotp` TOTP. *Known limitation (assumption-carried):* an unenrolled user in an MFA tenant passes (enrolment is a minimal out-of-band step — `set_mfa_secret`; no enrolment UX / recovery codes). WebAuthn deferred.
- **Structural checks (AC6/FR-56).** `no_reversible_credential_storage` (a plaintext-password column fails the build) and `jwt_decode_pins_algorithms` (every `jwt.decode` pins a literal `algorithms=[...]`; `PyJWK`/`PyJWKClient`/`jwks` forbidden) — the latter vacuous today (no user-session JWT), ready for internal service tokens. Both fail closed, each with a failure fixture.
- **Open Questions resolved with the recommended defaults:** (1) upgrade-on-verify; (2) minimal MFA (config-as-data + a TOTP gate, no fuller surface); (3) PyJWT deferred (the check is vacuous-but-ready). No user-session JWT was introduced.

### File List

**New**
- `apx/adapters/store_postgres/migrations/versions/0011_session.py`, `0012_mfa_config.py`.
- `apx/checks/credential_storage.py` — the two AD-15 structural checks.
- `tests/adapters/test_session_store.py`, `tests/adapters/test_mfa.py`, `tests/checks/test_credential_storage_checks.py`.

**Modified**
- `apx/core/domain/auth.py` — Argon2id via pwdlib + legacy-scrypt `verify_and_upgrade`; `sign_token`/`verify_token` retained (not for user sessions).
- `apx/adapters/store_postgres/models.py` — `SessionRecord`, `TenantConfig`, `User.mfa_secret`.
- `apx/adapters/store_postgres/store.py` — session methods, `record_auth_event`, MFA methods, `_as_utc`, upgrade-on-verify in `authenticate`.
- `apx/api/app.py` — server-side session wiring (login/logout/current_identity/change_password), the MFA gate, lockout-in-audit; `_session_ttls` replaces `_secret`.
- `apx/checks/__main__.py` (registered), `apx/checks/tenant_isolation.py` (`session`/`tenant_config` in OWNED_TABLES).
- `pyproject.toml`/`uv.lock` (pwdlib[argon2], pyotp), `README.md`, `tests/domain/test_auth.py`, `tests/api/test_ingest_api.py`.

### Change Log

| Date | Change |
|---|---|
| 2026-07-24 | Implemented story 1.5 — owned auth (AD-15): Argon2id (pwdlib) with legacy-scrypt upgrade-on-verify; opaque server-side sessions in PostgreSQL (migration 0011) behind one Principal interface, replacing stateless HMAC tokens; app.py rewired (login/logout/current_identity/change_password); revocation reaches live sessions; lockout recorded in the audit; MFA config-as-data per tenant via TOTP (migration 0012); two structural checks (no-reversible-storage, jwt.decode algorithm-list). 240 passed / 8 skipped, 10 checks + ruff green, migration head 0012. Status → review. |
| 2026-07-24 | Addressed the adversarial code review (three-reviewer pass): fixed 3 Med + several Low findings — MFA fail-closed, auth-event audit hardening, XFF trust config-gated, stronger credential check, and cheap hardening. 241 passed / 8 skipped; 10 checks green. Status → done. |

## Senior Developer Review (AI)

**Date:** 2026-07-24 · **Reviewers:** Blind Hunter + Edge-Case Hunter + Acceptance Auditor (parallel, blind, same model tier) · **Outcome:** APPROVE-WITH-NITS → fixes applied. **No auth bypass and no session hijack/fixation** — the reviewers verified the session, password-hashing and rewiring core is solid.

### Findings and resolutions

- [x] **[Med] MFA failed OPEN for unenrolled users.** `if requires_mfa and secret:` let a user with no `mfa_secret` log in with a password alone in an MFA-required tenant (the dangerous downgrade). **Fixed:** the gate now **fails closed** — an MFA-required tenant refuses (403) an unenrolled user (and an empty secret) until enrolled; an API test proves it.
- [x] **[Med] Auth events on the serialized per-tenant audit chain — pollution + a concurrent 500.** Failed logins wrote to the *attempted* (attacker-controlled) tenant's chain, seeding chains for non-existent firms; two concurrent failures for one tenant raced on `(tenant, seq)` → an `IntegrityError`/500. **Fixed:** `record_auth_event` records only for a **tenant that exists** (no spray-seeded chains) and **retries** on the seq collision; tests added. **Deferred (documented, AD-44):** high-volume auth events on the serialized chain head is a real architectural tension — a dedicated non-chained auth-events log is the AD-44-aligned follow-up.
- [x] **[Med] `X-Forwarded-For` spoofable → rate-limit/lockout bypass + forged audit IP.** The leftmost XFF (client-controllable even behind a proxy, which *appends*) keyed the per-IP limiter. **Fixed:** the client IP is the **direct socket peer** unless `APX_TRUST_FORWARDED_FOR` is set (deployed image), where the **rightmost** (trusted-proxy-appended) entry is used.
- [x] **[Low-Med] `no_reversible_credential_storage` was name-only.** A reversibly-encrypted `password_enc` slipped past. **Fixed:** it forbids **any** password-ish column except `password_hash`, with a `password_enc` fixture. *Documented limitation:* a reversible cipher in store *code* is not caught (a store-AST leg is a noted follow-up).
- [x] **[Low] Cheap hardening:** the rate-limiter is now **thread-safe** (a lock — it runs in FastAPI's threadpool); the ≥8 password floor is enforced at **creation**, not only on change; the dead `sign_token`/`verify_token` HMAC primitives are **deleted** (a footgun — nothing structurally stopped them being re-wired into user sessions); the stale "scrypt" docstrings corrected; `SessionIdentity.tenant` resolves live from the user; a malformed session-TTL env value defaults instead of 500.

### Deferred (documented)

- [x] TOTP replay within the ~90s window (no used-code cache) — a later hardening; MFA stays gated ([ASSUMPTION] carried).
- [x] `mfa_secret` (a shared TOTP secret) at rest — encryption-at-rest is story 1.7.
- [x] The general `_append_audit` seq-collision race (pre-existing, affects every audited op) + auth-events-off-the-chain — an AD-44 story.
- [x] The limiter's residual check-then-act over-permit at the threshold boundary (a shared store is the multi-instance step).

**Post-fix verification:** `ruff` clean · `python -m apx.checks` **10/10** · `pytest` **241 passed, 8 skipped** · migration head `0012`.

## Open Questions for the human

1. **Credential migration path:** upgrade-on-verify (accept a legacy scrypt hash once, re-hash to Argon2id) vs. re-bootstrap the demo admin with Argon2id. Recommend upgrade-on-verify (nothing locks out). Confirm.
2. **MFA depth:** 1.5 delivers TOTP as per-tenant config-as-data with *minimal* enrollment (assumption carried). Confirm that's the right line, vs. a fuller MFA surface (enrollment QR, recovery codes) as its own later story.
3. **PyJWT now or later:** user sessions need no JWT (opaque server-side). Add `PyJWT==2.13.0` now only to give the algorithm-list check a real import target, or defer it until internal service tokens are introduced? Recommend defer; keep the check vacuous-but-ready.
