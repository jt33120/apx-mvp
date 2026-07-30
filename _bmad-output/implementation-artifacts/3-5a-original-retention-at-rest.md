---
baseline_commit: 7f34bff
---

# Story 3.5a — Original bytes retained at rest (the pièce-viewer foundation)

**Part of Story 3.5 (the pièce viewer), increment 1 of 4.** Julian chose the full-fidelity build
(AskUserQuestion, 2026-07-30): originals retained at rest + per-format renderers inside the tenant
boundary. This increment lays the foundation the other three stand on.

Status: done

## Story

As the pièce viewer that must **render** documents (not merely their extracted text),
I need the **original bytes** of every ingested pièce retained durably at rest, inside the tenant
boundary, encrypted and content-addressed,
So that a PDF page, a scan, a `.msg` and a `.xlsx` can be rendered — and an un-renderable format's
original offered — instead of only the text we keep today.

**The problem this fixes.** Ingestion keeps only the extracted `full_text`; the uploaded spool
(the original bytes) is **deleted** on job completion (`queue/__init__.py:170`, `owns_spool=True`).
Nothing renderable survives. This story retains the originals.

## Acceptance Criteria

**AC1 — Retention.** Given a pièce ingested from any format, when ingestion completes, its original
bytes are retained durably on the tenant data volume — **not** deleted with the spool — resolvable
by `(tenant, content_hash)`. Asserted end-to-end: ingest a file, then read its original back.

**AC2 — Encrypted at rest (AD-31).** The retained original is **application-encrypted**
(AES-256-GCM, the existing `Cipher`) *before* it touches disk. Reading the raw file off disk yields
**ciphertext**, undecryptable without `APX_ENCRYPTION_KEY` — asserted by reading the on-disk bytes
and confirming they are neither the plaintext nor decryptable under a wrong key. The AAD binds the
blob to `(tenant, content_hash)`, so a blob relocated to another identity fails authentication (it
cannot be silently re-addressed). *(The original is content and is not searchable, so the AD-31
named exception for the `full_text` search index does not apply — the default, application-encryption,
does. The volume layer covers it too, as it covers `full_text`.)*

**AC3 — Content-addressed, deduplicated.** The store is addressed by `content_hash`; the same bytes
ingested twice within a tenant resolve to **one** blob (`put` is idempotent — it never rewrites an
existing blob).

**AC4 — Tenant-partitioned.** A blob's location includes the `tenant`; two tenants that ingest the
byte-identical file get **separate** blobs — one tenant can never address another's original. (The
piece_id is already tenant-qualified; the blob store mirrors that isolation.)

**AC5 — Member retention (the AC-critical case).** An attachment inside a container — a `.msg`
attachment, a `.zip` member — is a pièce in its own right (FR-3), and its **own** original is
retained, even though a member's bytes exist only transiently during ingestion (a tmpdir). This is
why retention lives at piece-creation in the ingest use case (via a port), not in the worker: the
worker only sees top-level spool files, never a member's bytes. Asserted with a planted `.msg`
attachment.

**AC6 — Fail-closed.** A missing/unusable encryption key means **no plaintext blob is ever written**
(the write path requires the cipher). A tampered or truncated blob **fails closed on read** (raises,
never returns garbage — the `Cipher` already authenticates). A blob write that fails at ingest (disk
full) is that pièce's failure, recorded, never an escaping exception (mirrors the existing
member-spool-failure handling in `_ingest_one`).

**AC7 — The structural gate.** A structural check asserts originals are encrypted at rest, with a
**behavioural leg** that executes the adapter, puts a known plaintext, reads the raw file, and
proves it is ciphertext (the ungameable leg — AST-sniffing alone is gameable). Registered in
`registry.CHECKS` + `manifest.PROPERTY_MANIFEST` + the README lockstep row; the meta-checks keep the
three in step.

**AC8 — No over-build.** The **read path** (who serves an original, under the RBAC scope pre-filter,
audited on open) and the **"never egress" gate** are increments 2/3 — *not* built here. The
adapter's `open()` (read) exists and is unit-tested, but is wired to **no** endpoint yet. No new DB
column, **no migration** (the blob is located by existing `content_hash` + `tenant`); the alembic
head is unchanged.

## Dev Notes

**Design (worked out against the code).**

1. **A bytes crypto API on `Cipher`** (`core/domain/crypto.py`) — `encrypt_bytes(data, aad) -> bytes`
   / `decrypt_bytes(token, aad) -> bytes`, mirroring `encrypt`/`decrypt` but over raw bytes (token =
   `b"apxenc:v1:" + nonce + ciphertext`, no base64/utf-8 — a blob file needs no ASCII armour). ONE
   crypto implementation; the bytes path reuses the same AESGCM key set and AAD semantics.

2. **The `OriginalStore` port** (`core/ports/originals.py`, a `Protocol`) — `put(tenant,
   content_hash, data)` (idempotent, content-addressed) and `open(tenant, content_hash) -> bytes`
   (decrypts, fail-closed). The core depends on the port (AD-4); the adapter implements it.

3. **`FilesystemOriginalStore`** (`adapters/originals_fs/store.py`) — `root` (the data volume's
   `originals/` dir) + a `Cipher`. `put`: if the blob is absent, encrypt with AAD
   `f"original:{tenant}:{content_hash}"`, write **atomically** (temp file + `os.replace`) to
   `{root}/{tenant}/{ch[:2]}/{ch}`; present → no-op (dedup). `open`: read + `decrypt_bytes`
   (fail-closed). `from_env()` builds `root` from `APX_DATA_PATH` and the cipher from
   `Cipher.from_env()`. A path-traversal guard on `content_hash`/`tenant` (must be `[0-9a-f]`/safe).

4. **Wire into ingest** (`core/app/ingest.py`) — add an optional `original_store: OriginalStore |
   None` to `_ingest_one`/`ingest_one_file`/`ingest_folder`; when a pièce is created (`outcome.ok`,
   after `ch = content_hash(raw)`), `original_store.put(tenant, ch, raw)` guarded by `is not None`.
   A `put` `OSError` → the same register-failure handling as a spool-write failure (never an escape).
   Build the store at the **worker composition root** (`queue/_run_import`/`_persist_unit`) and thread
   it through; the optional param keeps every existing caller/test pure. The docstring's "persists
   nothing" becomes "persists nothing except, when given an OriginalStore, each pièce's
   content-addressed original — streamed, never accumulated."
   - **A register-failed pièce's original is retained too** (put happens at ingest, before admission
     decides): a conscious, benign choice — it is the client's own uploaded file, in the client's own
     tenant volume, encrypted, content-addressed (dedup-bounded), and OFF-ledger so AD-38 still holds.
     It is **not** retrievable on demand (the `IngestedFailure` carries no `content_hash`, and the
     spool is dropped) — it is inert **dead storage**, safely garbage-collectable by a later
     content-hash sweep, never a leak. *(Corrected 2026-07-30 after review flagged the earlier
     "retrievable by filename" claim as false.)*

5. **The structural check** (`checks/originals_encrypted.py`) — `originals_are_encrypted_at_rest`:
   a static leg (the adapter imports/uses the `Cipher` and has no plaintext disk-write of the `data`
   param) + a **behavioural leg** (put a known plaintext through a real `FilesystemOriginalStore`
   into a tmp root, read the raw file, assert it is not the plaintext and does not decrypt under a
   fresh wrong key). Fail-closed on an unparseable adapter. Register in `registry.CHECKS`,
   `manifest.PROPERTY_MANIFEST` (AD-31), and the README `<!-- structural-properties -->` block.

**Boundaries / non-goals.** No read endpoint, no scope-filtered read path, no audit-on-open, no
renderers, no "never egress" static gate, no React — all later increments. No DB column, no
migration. `full_text` retention is unchanged (the extracted text still lives in `Piece`).

**Files (expected).**
- `apx/core/domain/crypto.py` (UPDATE) — `encrypt_bytes`/`decrypt_bytes`.
- `apx/core/ports/originals.py` (NEW) — the `OriginalStore` port.
- `apx/adapters/originals_fs/__init__.py`, `apx/adapters/originals_fs/store.py` (NEW).
- `apx/core/app/ingest.py` (UPDATE) — the optional `original_store` seam.
- `apx/adapters/store_postgres/queue/__init__.py` (UPDATE) — build + thread the store.
- `apx/checks/originals_encrypted.py` (NEW), `apx/checks/registry.py` + `manifest.py` + `README` (UPDATE).
- tests under `tests/` (crypto bytes, adapter, ingest retention incl. member, the check).

## Tasks / Subtasks

- [x] Bytes crypto API on `Cipher` (+ tests: round-trip, AAD binding, tamper/truncation fail-closed).
- [x] The `OriginalStore` port.
- [x] `FilesystemOriginalStore` (encrypt, content-address, tenant-partition, atomic, dedup, traversal
  guard, `from_env`) + tests (encrypted-at-rest on disk, dedup, tenant isolation, fail-closed read).
- [x] Wire the optional `original_store` into ingest; build at the worker root; register-failure on a
  write error + tests (retention end-to-end, **member/attachment retention**, put-error → register).
- [x] The structural check (static + behavioural legs) + registry/manifest/README lockstep + tests.
- [x] Full gate: ruff, pytest, structural checks (+1), `tsc -b` unchanged, alembic head unchanged.

## Dev Agent Record

### Completion Notes

- **Bytes crypto** (`Cipher.encrypt_bytes`/`decrypt_bytes`): the binary sibling of the string cipher,
  same key set + AAD semantics, token = raw `apxenc:v1:` ‖ nonce ‖ ciphertext (no base64/utf-8).
- **`OriginalStore` port** + **`FilesystemOriginalStore`**: content-addressed
  (`{root}/{tenant}/{ch[:2]}/{ch}`), application-encrypted (AAD binds a blob to `(tenant,
  content_hash)`), atomic write (temp + `os.replace`), idempotent (dedup), traversal-guarded,
  `from_env()` = `$APX_DATA_PATH/originals` + `Cipher.from_env()`.
- **Ingest seam**: an optional `original_store` threaded through `_ingest_one`/`ingest_one_file`/
  `ingest_folder`; `put(tenant, ch, raw)` at pièce-creation — the ONLY place a container member's
  bytes exist (why retention is here, not in the worker). A `put` `OSError` → a `RESOURCE_EXHAUSTED`
  register entry, never an escape. Built once at the worker root; the spool is still dropped.
- **Gate**: `originals_are_encrypted_at_rest` — static (put encrypts, never writes raw `data`) +
  behavioural (execute the store, prove the on-disk blob is ciphertext). Registered lock-step
  (registry/manifest/README). Checks 56 → 57.
- Backward-compatible: no `original_store` → no retention (existing callers/tests unchanged). No DB
  column, **no migration** (alembic head `0022` unchanged). Worker tests isolate retention to their
  tmp via an `APX_DATA_PATH` autouse fixture.

### File List

- `apx/core/domain/crypto.py` (UPDATE — `encrypt_bytes`/`decrypt_bytes` + `_PREFIX_B`)
- `apx/core/ports/originals.py` (NEW)
- `apx/adapters/originals_fs/__init__.py`, `apx/adapters/originals_fs/store.py` (NEW)
- `apx/core/app/ingest.py` (UPDATE — optional `original_store` seam)
- `apx/adapters/store_postgres/queue/__init__.py` (UPDATE — `_build_original_store` + thread)
- `apx/checks/originals_encrypted.py` (NEW), `apx/checks/registry.py`, `apx/checks/manifest.py`,
  `README.md` (UPDATE — lock-step registration)
- `tests/domain/test_crypto.py`, `tests/adapters/test_originals_fs.py`,
  `tests/app/test_ingest_originals.py`, `tests/checks/test_originals_encrypted.py`,
  `tests/worker/test_import_job.py` (UPDATE)

### Change Log

- 2026-07-30 — Story 3.5a implemented. Gate: ruff clean, 875 passed / 11 skipped, 57 structural
  checks, alembic head `0022` unchanged, `apx/web` untouched.
- 2026-07-30 — 3-reviewer adversarial pass (crypto/security · architecture · correctness/tests).
  **Verdict: security promises hold, design sound (AD-4 clean, streaming, member retention real,
  lockstep holds), no over-build.** All findings resolved:
  - MED (R1/R2/R3) — a realistic FR/LU tenant slug (`cabinet.fr`, `étude-müller`) broke retention
    (`_SAFE_TENANT` too strict → `ValueError` escaped `except OSError`). **Fixed:** the tenant is
    HASHED into its path segment (any slug is safe, isolation preserved via the AAD).
  - MED (R2) — the sync `POST /api/ingest` retained nothing (unwired). **Fixed:** wired an
    `_original_store()` at the API root + a retention assertion.
  - MED (R3) — a sibling `_persist_unit` call site (`test_import_resume_postgres.py`, PG-only) was
    stale (missing `embedder` since 2.8 + `original_store`). **Fixed.**
  - MED (R3) — worker/api tests leaked real blobs to the global temp dir. **Fixed:** `APX_DATA_PATH`
    isolation in the API `_prepare` + the worker autouse fixture (verified: no global-temp leak).
  - LOW-MED (R1) — the gate's behavioural leg read only the canonical blob. **Fixed:** it now sweeps
    the whole store root (a plaintext sidecar/aliased-write leak is caught); "ungameable" over-claim
    softened.
  - LOW (R1) — no parent-dir fsync after `os.replace`. **Fixed** (best-effort dir fsync).
  - LOW-MED (R2) — the register-failure "orphan" rationale was false ("retrievable by filename").
    **Corrected:** it is benign, off-ledger, GC-able dead storage — not retrievable on demand.
  - LOW (R2/R3) — `from_env` fallback docstring inaccurate; `has()` dead code; AAD injectivity
    untested. **Fixed:** honest docstring; `has()` removed; injective AAD (`content_hash`-first) +
    a colon-tenant test. Re-gate green.
