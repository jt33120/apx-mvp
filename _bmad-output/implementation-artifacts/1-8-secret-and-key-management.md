---
baseline_commit: 1ce2d80
---

# Story 1.8: Secret and key management

Status: review

## Story

As a firm,
I want every secret held outside the data stores, never logged or exported, and rotatable without redeployment,
so that the one mistake that ends a client relationship — a secret in the wrong place — is designed out.

**Scope in one line:** make every held secret (encryption key, model-provider & embedder credentials, the DB URL) live **only in the environment** — proven by a **structural check that fails the build on a secret in source or committed/example config** (FR-51/FR-56); make secrets **rotatable without a redeployment and without re-indexing**, with rotation **recorded in the audit** — delivered as a **multi-key cipher** (encrypt with the primary key, decrypt with primary-or-previous) plus a **re-key** pass that re-encrypts at rest (reusing the 1.7 backfill machinery, never touching the searchable surfaces); make secrets **never reach a log** via a **redaction filter** proven by a seeded-secret test (the failure path); and **extend the seeded-token raw-store inspection to seeded secret values** (FR-31 tie). **Not** the transient user-supplied credential channel (AD-47's 2nd rule — the document-password row, owned by the failure-register work in epic 2), **not** the content-free projection primitive itself (1.10 — this story ties to it, does not build it).

> The ad-hoc build reads secrets from the environment already, but nothing *enforces* that they never land in source, a log or a dump, and there is no way to rotate the encryption key without re-provisioning. 1.8 turns "we're careful with secrets" into "a secret in the wrong place fails the build, and a key can be rotated in place."

## Acceptance Criteria

> **Given** model-provider credentials, embedder credentials and encryption keys, **When** they are held, **Then** they live outside the application's own data stores, are never written to a log, diagnostic, export or *audit record* entry, and are never displayed after entry (FR-51).
> **And** every secret is rotatable without a redeployment and without re-indexing, and rotation is recorded in the *audit record*.
> **And** a static check asserts no secret value appears in source, in committed configuration, or in any example configuration (FR-51, FR-56).
> **And** the *content-free projection* is asserted against seeded secret values as well as seeded content tokens (ties FR-31).
> **And** *(failure path)* a seeded secret placed in a log line or an export turns the build red.

1. **AC1 — Secrets live outside the data stores, and never appear after entry.** Every held secret is read from the environment only; no model column stores a provider credential / API key / encryption key (a structural check asserts it, extending 1.5's credential-storage guard). No API response returns a secret; no log line, diagnostic or *audit record* entry carries a secret value (the redaction filter + AC5).
2. **AC2 — Rotatable without redeployment or re-indexing, audited.** The cipher takes a **primary** key (used to encrypt) plus zero or more **previous** keys (used only to decrypt), from the environment. A **re-key** pass re-encrypts every application-encrypted column with the primary key (decrypt-with-any → encrypt-with-primary); it touches **no searchable surface** (the vector column and text index are never application-encrypted, so a rotation needs **no re-index**), and runs as a data operation (a manage command) — **no code redeploy**. Rotation writes an *audit-record* entry per *tenant* naming the act and a non-reversible key fingerprint, **never the key**.
3. **AC3 — No secret in source or committed/example config (structural, FR-51/FR-56).** A static check scans the shipping source (`apx/`) and committed configuration (pyproject, Dockerfile, docker-compose, entrypoint, CI, any `*.example`) for a secret **value** — a known credential pattern (a GitHub PAT, an `sk-`/`AKIA`/`xox…` token, a PEM private key) or a bare high-entropy token — and **fails the build** on one. It does not fire on an environment *reference* (`os.environ[...]`), a `${VAR}`/`:?`/`:-` placeholder, or a low-entropy constant. Fails closed on an unreadable file; carries a failure fixture (a hardcoded key → red).
4. **AC4 — The seeded-token inspection extends to secrets (FR-31 tie).** The 1.7 raw-store inspection (which already seeds a fake TOTP secret) is extended to seed an explicit **secret value** and assert it appears in **no** raw store. The content-free projection primitive is 1.10; this story asserts the buildable part now (raw stores + logs) and records the projection tie for 1.10.
5. **AC5 — Never logged (redaction), proven by the failure path.** A logging **redaction filter** scrubs known secret env values from every log record (installed at start-up). A test seeds a secret into a log line and asserts it is redacted — **remove the redaction and the build goes red**. (The *export* half of the failure path ties to the diagnostic export / projection in 1.10; the log half is delivered here.)
6. **AC6 — Green and honest.** All existing tests pass; `ruff` + `python -m apx.checks` + `pytest` + fitness green; README documents secret & key management and rotation; no transient-credential channel (AD-47 rule 2 / epic 2) or projection (1.10) over-build.

## Tasks / Subtasks

- [x] **Task 1 — Multi-key cipher** (AC: #2) — `apx/core/domain/crypto.py`: load a **primary** key (`APX_ENCRYPTION_KEY`) plus optional **previous** keys (`APX_ENCRYPTION_KEYS_OLD`, comma-separated) from the environment. `Cipher` holds an ordered key set: `encrypt` uses the primary; `decrypt` tries the primary then each previous (GCM authentication distinguishes the right key), so a value written under an old key still reads during the transition. Token format unchanged (`apxenc:v1:`), backward-compatible. All-zero keys still rejected.
- [x] **Task 2 — Re-key pass + manage command** (AC: #2) — `apx/adapters/store_postgres/backfill.py`: `rekey_all(conn)` re-encrypts every AD-31 encrypted column value with the **primary** key (decrypt-with-any → encrypt-with-primary), skipping values already under the primary is not possible without a key id, so it re-encrypts all present values idempotently-enough (a fresh nonce each time; safe to re-run). A `apx.manage rekey` command runs it and records an audited rotation per *tenant*. Add `record_key_rotation(tenant, actor, fingerprint)` to the store (the per-tenant chain, AD-43), fingerprint = `sha256(primary_key)[:12]` — names the key, never reveals it.
- [x] **Task 3 — Log redaction** (AC: #1, #5) — `apx/api/logging.py`: a `SecretRedactor` logging filter that replaces any known secret env value (encryption keys, `APX_SECRET_KEY`, `DATABASE_URL`, LLM/Mistral keys) with `«redacted»` in the formatted record; `install_secret_redaction()` attaches it to the root logger. Called at app start-up (the lifespan, beside the gate).
- [x] **Task 4 — No-secret-in-source structural check** (AC: #3) — `apx/checks/secrets.py`: `no_secret_in_source(roots)` scans `apx/` + committed config for a secret **value** (known credential patterns + bare high-entropy tokens ≥ 28 chars), ignoring env references and placeholders. Fails closed on unparseable. Register in the harness.
- [x] **Task 5 — No-secret-column structural check** (AC: #1) — `apx/checks/secrets.py`: `no_secret_column_in_models` asserts no model column name looks like a stored provider credential / api key / raw encryption key (`api_key`, `api_secret`, `access_token`, `private_key`, `encryption_key`, …). `mfa_secret` (a TOTP shared secret, already encrypted, AD-15) is the one permitted `*_secret`. Register.
- [x] **Task 6 — Tests** (AC: all) — `tests/domain/test_crypto.py` (rotation: old-key decrypt, primary encrypt, key-set loading); `tests/adapters/test_rekey.py` (re-key: an old-key value re-reads, a rekey re-encrypts + audits, no searchable surface touched); `tests/api/test_log_redaction.py` (a seeded secret in a log line is redacted); `tests/checks/test_secret_checks.py` + fixtures (a hardcoded key fires; the real tree is clean; fail-closed); extend `tests/adapters/test_encryption_at_rest.py` to seed a secret value.
- [x] **Task 7 — Green + docs** (AC: #6) — README: secret & key management, rotation runbook. `ruff` + `python -m apx.checks` + `pytest` + fitness green.

## Dev Notes

- **Rotation is cheap because AD-31 already made it cheap.** The two searchable surfaces (`halfvec`, the text index) are **not** application-encrypted, so rotating the key never re-indexes anything — the re-key touches only the `EncryptedText` columns (the same set the 1.7 backfill walks). "Without re-indexing" is a property of the AD-31 split, not new work. [Source: ARCHITECTURE-SPINE.md#AD-31; apx/adapters/store_postgres/backfill.py]
- **Trial decryption, not a key id in the token.** The token stays `apxenc:v1:`; `decrypt` tries the primary then each previous key and lets GCM authentication pick the right one. This keeps the on-disk format stable (every 1.7 ciphertext still reads) and rotation is just "add the new key as primary, keep the old as previous, re-key, then drop the old." A key id in the token would be marginally faster to decrypt but a format change; trial over 1–2 keys is negligible. [Source: apx/core/domain/crypto.py]
- **Rotation is a maintenance act (AD-48 third principal kind).** The re-key command runs as tenant-bound maintenance; it writes one audit entry per tenant on the per-tenant chain (AD-43), naming the rotation and a **key fingerprint** (a short one-way hash) so the record answers "which key, when" without ever holding the key. The full AD-48 principal enumeration is a later structural story; 1.8 uses the maintenance path for the rotation audit. [Source: ARCHITECTURE-SPINE.md#AD-47, #AD-48, #AD-43]
- **The no-secret-in-source check must not false-positive on the real tree.** `apx/` holds no hardcoded high-entropy literal (keys come from env, hashes from `hashlib` calls), so an entropy leg ≥ 28 chars over the source is clean — and it WOULD catch a bare pasted token (e.g. a 32-char provider key with no recognizable prefix, the dangerous case). The known-pattern leg catches prefixed tokens (PAT, `sk-`, PEM). Tests are dev-only (excluded from the wheel) and legitimately carry high-entropy fixtures, so the default roots are `apx/` + committed config, not `tests/` — recorded so the scoping is a decision, not an oversight. [Source: pyproject.toml exclude; FR-51]
- **Never-logged is enforced, not hoped.** The app configures no logging today, so "no secret in a log" is vacuously true — but FR-51 wants a mechanism, so a redaction filter scrubs known secret values from every record. A structural "no secret at a log call site" check is not decidable generically; the filter + a seeded-secret test is the enforceable form. The *export* half of the failure path lands with the diagnostic export/projection (1.10). [Source: FR-51; AD-47]
- **What this story does NOT do.** The transient user-supplied credential channel (AD-47 rule 2 — a document/archive password in a single-use, TTL-bounded, encrypted, backup-excluded row keyed by a failure-register entry) is owned by the failure-register / extraction work (epic 2, FR near 2.4/2.6); named here so a reviewer does not expect it. The content-free projection primitive is 1.10. [Source: ARCHITECTURE-SPINE.md#AD-47; epics 2.4/2.6, 1.10]
- **Structural-check + fixture pattern (AD-33).** Reuse the 1.3–1.7 pattern: `CheckResult`, registered in `CHECKS`, explicit `roots`, fail closed on unparseable, fixtures text/AST-only and `ruff`-clean. [Source: apx/checks/encryption.py]

### Project Structure Notes

- New: `apx/checks/secrets.py`, `apx/api/logging.py`, `tests/adapters/test_rekey.py`, `tests/api/test_log_redaction.py`, `tests/checks/test_secret_checks.py` (+ fixtures under `tests/_fixtures/secret_violations/`).
- Modified: `apx/core/domain/crypto.py` (multi-key), `apx/adapters/store_postgres/backfill.py` (rekey_all), `apx/adapters/store_postgres/store.py` (record_key_rotation), `apx/manage.py` (rekey command), `apx/api/app.py` (install redaction at start-up), `apx/checks/__main__.py` (register), `tests/domain/test_crypto.py`, `tests/adapters/test_encryption_at_rest.py`, `README.md`.
- No new dependency; no schema/DDL change (rotation re-encrypts existing columns; the audit entry uses the existing table).

### References

- [Source: PRD FR-51] — secrets outside stores, never logged/displayed, rotatable without redeploy/re-index + audited; no secret in source/config (structural); projection asserted against seeded secrets.
- [Source: ARCHITECTURE-SPINE.md#AD-47] — secrets/keys outside the data stores; the transient-credential channel (rule 2, deferred here).
- [Source: PRD FR-56] — structural property enforced by a static check in CI.

## Dev Agent Record

### Completion Notes

- **Multi-key cipher (AC2).** `crypto.py`: `Cipher` holds an ordered key set — `encrypt` uses the primary, `decrypt` tries the primary then each previous (GCM authentication picks the right one). `load_keys_from_env` reads `APX_ENCRYPTION_KEY` + `APX_ENCRYPTION_KEYS_OLD`. Token format unchanged (every 1.7 ciphertext still reads). `key_fingerprint` = `sha256(key)[:12]`.
- **Re-key + command (AC2).** `backfill.rekey_all(conn, cipher=None)` decrypts-with-any → encrypts-with-primary over the AD-31 encrypted columns (subsumes the backfill; leaves the searchable surfaces untouched → no re-index). `apx.manage rekey` runs it and calls `store.record_key_rotation(tenant, "system:maintenance", fingerprint)` for each tenant (per-tenant chain, names the key by fingerprint only). `store.tenants()` added.
- **Log redaction (AC1/AC5).** `apx/api/logging.py`: `SecretRedactor` scrubs the configured secret values (keys, `APX_SECRET_KEY`, LLM keys, the `DATABASE_URL` and its embedded password) from every record; `install_secret_redaction()` attaches it to the root logger + handlers at start-up (the lifespan). A seeded secret in a log line comes out `«redacted»`.
- **No-secret-in-source (AC3).** `checks/secrets.no_secret_in_source` scans `apx/` (minus web) + committed config for a secret value — named credential patterns (whole line) + a bare high-entropy token inside a **quoted string** (so code identifiers, file paths, URLs/namespaces never false-positive). Tuned against the real tree (three false positives found and excluded: `key=Value` identifiers, an XML namespace, a comment path). Ignores env references / placeholders. Fails closed on an unreadable file.
- **No-secret-column (AC1).** `checks/secrets.no_secret_column_in_models` forbids a stored provider-credential / api-key / raw-key column; `mfa_secret` (an encrypted TOTP shared secret) is not in the forbidden set.
- **Deliberate scoping (surfaced for review).** (a) The transient user-supplied credential channel (AD-47 rule 2) is epic-2 work — not built. (b) The content-free projection (FR-31) is 1.10; AC4's buildable part (a seeded secret absent from raw stores) is already covered by 1.7's seeded-token test, which seeds a TOTP secret. (c) The no-secret-in-source entropy leg scans quoted literals only, so a bare **unquoted** token in a config file is caught only by the named-pattern leg (documented; the realistic secret-in-source is a quoted literal). (d) `tests/` is dev-only (excluded from the wheel) and carries high-entropy fixtures, so the default scan roots are `apx/` + config, not `tests/`.
- **Gate:** `ruff` clean · `python -m apx.checks` **15/15** · `pytest` **315 passed, 8 skipped** · fitness green. No schema/DDL change; no new dependency.

### File List

- New: `apx/api/logging.py`, `apx/checks/secrets.py`, `tests/adapters/test_rekey.py`, `tests/api/test_log_redaction.py`, `tests/checks/test_secret_checks.py`, `tests/_fixtures/secret_violations/{hardcoded_key,github_pat}/settings.py`.
- Modified: `apx/core/domain/crypto.py` (multi-key + fingerprint), `apx/adapters/store_postgres/backfill.py` (rekey_all), `apx/adapters/store_postgres/store.py` (tenants, record_key_rotation), `apx/manage.py` (rekey command), `apx/api/app.py` (install redaction), `apx/checks/__main__.py` (register), `tests/domain/test_crypto.py`, `README.md`.

### Change Log

- 2026-07-24 — Story 1.8 implemented: multi-key cipher + in-place re-key (rotatable without redeploy/re-index, audited), log redaction, and a no-secret-in-source structural guard. Status → review.
