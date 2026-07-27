# APX

Mass-document triage for law firms. Hexagonal core, adapters at the edges, **one
stateful service** (PostgreSQL). Runs the same one artefact hosted, in CI, and
air-gapped inside a firm (AD-3).

> **Status: story 1.11 — backup, restore & disaster recovery.** The frozen payload schema (1.3),
> the *tenant* wall (1.4), owned auth (1.5), scope administration (1.6), encryption at rest with a
> fail-closed start-up gate (1.7), secrets held only in the environment (1.8), configuration-as-data
> through one audited surface (1.9), the content-free projection primitive (1.10), and now **a head
> journal held outside the restorable store** so a dump restore can no longer silently truncate the
> evidential record, a **complete tenant-boundary backup + an exercised restore**, and a **stated
> storage footprint with a pre-flight capacity refusal** (1.11) — exist; ingestion, retrieval and the
> model tiers do not yet. What is deliberately absent, and which story owns it, is listed at the
> bottom.

Planning artefacts (PRD, architecture spine, epics, stories) live under
`_bmad-output/planning-artifacts/`. The previous implementation at
`../apx-platform/` is reference only — never an edit target.

## Prerequisites

- [`uv`](https://docs.astral.sh/uv/) (Python 3.13 is fetched by `uv`, not the system)
- Docker + Docker Compose
- Node — build-time only; pin in `apx/web/.nvmrc` (24.18.0). No Node runtime ships (AD-29).

## Setup

```bash
uv sync --group dev                 # backend deps + dev tools, into .venv
cd apx/web && npm ci && npm run build   # static SPA -> apx/web/dist
```

Start the single stateful service (PostgreSQL + pgvector). Credentials come from
the environment — **never commit them** (AD-47):

```bash
POSTGRES_USER=apx POSTGRES_PASSWORD=change-me \
  docker compose -f deploy/docker-compose.yml up -d postgres
```

## Run the checks and tests

```bash
uv run python -m apx.checks   # structural-property checks (AD-33) — the layering rule (AD-4)
uv run ruff check .           # lint
uv run pytest -q              # tests, incl. the layering failure-path regression
```

All three are green on the empty project, and CI (`.github/workflows/ci.yml`)
runs them on every push.

## Source tree

```
apx/
  core/            # the hexagon — imports NO adapter (AD-4)
    domain/  ports/  app/  app/read/
  adapters/        # third-party edges (store_postgres, embedder_bgem3, llm_openai_compat, extraction, ocr_tesseract)
  api/             # FastAPI edge — validate, authorise, enqueue, return (empty in 1.1)
  worker/          # Procrastinate worker entrypoint (no tasks in 1.1)
  checks/          # structural-property checks (AD-33); a cut cannot drop them
  eval/            # gold set / degradation / estimator simulation (empty in 1.1)
  web/             # Vite + React Router SPA, built to static files (AD-29)
tests/             # unreachable from any runtime module (AD-16)
deploy/            # docker-compose (the single service); upgrade/backup land later
```

## Offline fitness (AD-2)

"Can this run, unmodified, on one machine inside a firm with no internet?" is
measured in CI from week one, not discovered in front of a client.

```bash
uv run python -m apx.fitness   # the end-to-end driver (asserts what exists, marks the rest PENDING)
uv run pytest tests/fitness -q # offline boot (no outbound network) + driver honesty
```

The frame guarantees today: the app boots with the offline env set and makes no
outbound network call, and the **egress deny-list** fails the build if any `apx`
runtime module imports a hosted-provider SDK (`supabase`, `boto3`, `google`, …;
`openai` is forbidden in the core — it belongs behind the local-LLM adapter). The
driver enumerates the full FR-55 pipeline; stages that do not exist yet are printed
`PENDING (story N)` and are **never** faked green. Coverage grows as the pipeline
is built.

## The layering rule (AD-4)

The core imports no adapter, and the dependency direction is one-way. This is
**enforced as a structural property** — a static import-graph check
(`import-linter`), not a runtime test. It runs via `python -m apx.checks` and in
CI, and fails the build on violation.

**Manual demonstration for the acceptance review** (the committed regression test
in `tests/checks/test_layering_check.py` keeps it honest afterward):

```bash
# add, temporarily, inside apx/core/domain/__init__.py:
#     from apx.adapters.store_postgres import x
uv run python -m apx.checks     # -> FAIL, non-zero exit
# then revert the line
uv run python -m apx.checks     # -> PASS
```

## The frozen payload schema (AD-9)

The increment's one irreversible decision: what travels on every indexed *chunk*. A
`piece` holds a document's full extracted text once — the target of exhaustive search —
with its own `text_identity` and `text_version`. A `chunk` carries only the enumerated
provenance: `chunk_id`, `piece_id`, `tenant`, `matter`, `position`, `full_text_version`,
`chunking_config_version`, `schema_version`, and a reserved external-authority reference.
The embedding vector and its `model_id`/`model_version` are added by the embedder story
(2.8); adding a *mandatory* field later would mean re-indexing every installed site blind,
so the set is fixed here.

Two things are deliberately **not** columns (AD-9/AD-13/AD-40): *RBAC scope* and
*custodian*. Scope is a **required write-time argument** the writer checks against the
matter's authoritative `matter_scope` — never persisted — so a re-scope takes effect at
the next read with nothing to propagate. There is exactly **one** `chunk` writer; it
defaults nothing and rejects, with a typed error, an incomplete payload, an unauthorised
or empty scope, or a schema/chunking version that differs from the import job's (one
*matter* never holds two generations).

Four static checks defend this at build time (`python -m apx.checks`): one writer,
`rbac_scope` required with no default, no scope/custodian column on `chunk`, and no
`ON DELETE CASCADE` on the piece FK (a *retired* state instead — AD-7). Each has a
failure-path fixture proving it fires. The migration is exercised up **and** down against
real PostgreSQL in CI.

## Tenant isolation (AD-12)

The wall between firms is the product's premise, and a cross-*tenant* leak is silent — no
error, no message. So it is a **proven, checked** property, not a hope. Every *tenant*-owned
table pins a non-nullable `tenant` (a record without one cannot be written); every read is
constrained by `tenant` **before** *RBAC scope* (scope is applied after tenant, never
instead of it); a user with no scope gets an **empty** corpus, not the whole one; and an
unknown *tenant* or a foreign *matter* fails closed (empty / `ScopeDenied`), never another
firm's rows.

Two build-time guards (`python -m apx.checks`) keep it from regressing: `tenant` is NOT
NULL on every owned table, and no store method applies a `scopes` filter without a
`tenant`. An **adversarial suite** (`tests/adapters/test_tenant_isolation.py`) seeds two
tenants sharing a common word and asserts zero cross-*tenant* results, counts or metadata
across every read surface. *(The full AD-14 single-read-entry-point consolidation — one
`core/app/read/` path plus a grep forbidding tenant-table queries elsewhere — is a
separate, larger unit; 1.4 delivers the tenant guarantee and a store-scoped check.)*

## Owned authentication (AD-15)

Auth is the application's own, so the same identity model works air-gapped and hosted with no
third party between a lawyer and the wall. Passwords are **Argon2id** (`pwdlib[argon2]`); a
legacy scrypt hash still logs in and is re-hashed to Argon2id on the next login
(upgrade-on-verify). Sessions are **opaque, server-side rows in PostgreSQL** — the cookie is an
unguessable id, authority is the row — with absolute and idle lifetimes (config-as-data), so
sign-out, a password change and a scope revocation take effect immediately (the row is deleted,
or scopes re-resolve live on the next request), never "wait for a token to expire". **No JWT
for user sessions.** Repeated failures are rate-limited **and recorded in the audit trail**;
MFA (TOTP) is configuration-as-data per tenant.

Two build-time guards (`python -m apx.checks`): **no reversible credential storage** (a
plaintext password column fails the build — passwords live only as a one-way hash), and every
`jwt.decode` must pin a literal `algorithms=[...]` (vacuous today; ready for internal service
tokens). `pwdlib[argon2]` and `pyotp` are pinned exactly (AD-30); PyJWT / WebAuthn are deferred.

## Scope administration (grant-time authorisation, FR-49)

A wall anyone can move is not a wall. Granting or revoking a *RBAC scope*, and **re-scoping a
matter**, are **privileged** acts (an administrative grant held by a named *tenant* user),
each **recorded in the audit** with actor, subject, scope, authority and timestamp, and each
**reversible**. The administrative grant is itself granted by the same audited path; its first
holder is set at provisioning, so every admin traces back to it — there is **no implicit
superuser**: holding the grant administers, it does not widen a data read (an admin with no
scope still reads an empty *corpus*). A re-scope is a single `matter_scope` UPDATE that takes
effect at the **next query** with nothing to propagate (AD-13) — proven by a mutating
adversarial suite that moves a matter's wall mid-*corpus* and asserts it holds in its new
position immediately and its old position never. A build-time guard (`python -m apx.checks`)
fails the build on a scope mutator that skips the audit.

## Encryption at rest and in transit (AD-31)

Everything content-bearing at rest is encrypted **by the application's storage adapters** —
AES-256-GCM behind the `EncryptedText` column type, keyed from `APX_ENCRYPTION_KEY` (never in
source): a *pièce*'s provenance and custodian, the *failure register*, the *audit record*'s
detail, triage rationales, the TOTP secret. **Two named surfaces are the only exceptions** —
the `halfvec` vector column (from 2.8) and the **deterministic text index**, which today is
`piece.full_text`, the column exhaustive search runs an SQL `ILIKE` over: you cannot index
ciphertext, so they are protected by **volume-/cluster-level encryption** and asserted by the
start-up gate instead. A seeded-token raw-store inspection proves no plaintext token survives
anywhere but that named index. In transit, the app↔store connection requires TLS
(`APX_DB_SSLMODE=require` by default; a same-host loopback may opt out) and the browser edge is
HTTPS.

The **start-up gate fails closed on both layers**: no application key, or no attested data
volume (`APX_VOLUME_ENCRYPTED` — a conscious per-deployment act, never baked into the image),
and the app **refuses to boot** — no permissive default, no warning-and-continue. Each
ciphertext is bound to its column (AES-GCM associated data), so a stolen-disk attacker cannot
relocate one column's value into another. Two build-time guards (`python -m apx.checks`) hold
the line: one requires every string column to be encrypted **unless allowlisted** (so a new
content column is encrypted-by-default) and forbids encrypting the text index; the other
*executes* the gate to prove it refuses a missing-layer env. Enabling encryption on a store
that already holds data is supported — a one-shot backfill migration re-encrypts existing rows.

> The volume attestation is an honest operator promise (the app cannot verify a block device
> from inside a container) — back it with dm-crypt/LUKS on a single-machine install, or a
> provider-managed encrypted volume in the hosted tier. The cryptographic teeth are the
> application-layer key gate. Key **rotation/custody** is story 1.8.

## Secret & key management (AD-47)

Every held secret — the encryption key(s), model-provider & embedder credentials, the DB URL —
lives **only in the environment**, never in a data store, and is **scrubbed from logs** by a
redaction filter (installed at start-up) so a careless log line comes out masked. A build-time
guard (`python -m apx.checks`) **fails the build on a secret value in source or committed/example
config** — a known credential pattern (a GitHub PAT, an `sk-`/`AKIA` token, a PEM key) or a bare
high-entropy token — the one mistake that ends a client relationship.

The encryption key is **rotatable in place**, no redeploy and no re-index: the cipher encrypts
with a **primary** key and decrypts with primary-or-previous. A rotation is a config change plus
a restart (the live cipher is process-cached), never a code deploy:

```
# 1. RESTART the app with the new key primary and the old key as a decrypt-only fallback
export APX_ENCRYPTION_KEY="$(openssl rand -base64 32)"   # the NEW key (primary)
export APX_ENCRYPTION_KEYS_OLD="$OLD_KEY"                # the previous key (decrypt-only)
#    …restart the app so it reads both — now it decrypts old values and writes new ones…
# 2. re-encrypt every stored value under the new key (atomic; audited per tenant)
python -m apx.manage rekey
# 3. RESTART again with APX_ENCRYPTION_KEYS_OLD removed, once the re-key completes
```

The restart in step 1 is required — a running app caches its cipher, so it must be restarted to
pick up the new key set *before* the re-key rewrites values (otherwise the live app would fail to
read the newly re-encrypted rows). The re-key touches only the application-encrypted columns —
never the searchable surfaces (the vector column and text index are not application-encrypted),
which is why a rotation needs no re-index. It runs in one transaction, and records the rotation on
each data-bearing *tenant*'s audit chain, naming a one-way key fingerprint, never the key.
*(The transient user-supplied credential channel — a document password — is AD-47's second rule,
owned by the failure-register work in epic 2.)*

## Configuration-as-data & the provisioning surface (AD-24/AD-25)

Per-*tenant* behaviour is **data rows, never code** (AD-24) — one code base for many firms, so a
firm's bespoke need never becomes a per-site fork. Every configurable value has a declared type
and a **default** (`apx/core/domain/config.py`); a *tenant*'s non-default values live in a
`tenant_setting(tenant, key, value)` table, edited through **one audited surface** (AD-25):
`set_config` validates against the schema, records the change on the audit trail with actor / key
/ **before** / **after** (so it is reversible — set the before back), and refuses an unknown key or
a wrong-typed value. A value written by a direct DB edit (bypassing the surface) is **detectable**
(`GET /api/admin/config/provenance`). The admin API — `GET /api/admin/config`, `PUT
/api/admin/config/{key}` — is inside the *tenant* boundary; the tenant comes from the session,
never the request.

A *tenant* is **provisioned** off-line (the first-run bootstrap, before any admin exists to
authenticate) — establishing its first administrative grant, scopes and taxonomy in one audited
act, failing closed if the *tenant* already has an administrator:

```
python -m apx.manage provision --tenant cabinet --admin-email patron@cabinet.fr \
    --admin-name "Le Patron" --scope pole-assurance --taxonomy conclusions --taxonomy "pièce adverse"
# (the admin password comes from APX_NEW_PASSWORD or an interactive prompt, never argv)
```

Three build gates back the guarantees (`python -m apx.checks`): **no conditional under `core/`
branches on a *tenant* identifier** (a *tenant* is a filter argument and a row key, never a
branch); **every documented key exists** in the schema (no key that lives in zero source files);
**no default disables the guarantee its key governs** (the v1 off-corpus gate shipped disabled —
that default is now build-checked to stay on). The visual settings/provisioning SPA is deferred
with the rest of the front-end (AD-29).

The configuration keys (each editable as data, no redeploy):

<!-- config-keys:start -->

| Key | Type | Default | Governs |
|---|---|---|---|
| `interface_language` | enum | `fr` | the interface language the tenant's users see (fr/en/de/lb) |
| `mfa_required` | bool | `false` | whether a second factor (TOTP) is demanded (FR-48) |
| `model_provider` | str | `mistral` | which inference provider serves the judgment LLM (AD-27) |
| `model_endpoint` | str | Mistral EU | the OpenAI-compatible inference endpoint (AD-27) — honoured live by the judge |
| `model_name` | str | `mistral-small-latest` | the model the endpoint serves (AD-27) |
| `chunking_config_version` | str | `v1` | the chunking configuration identity (AD-9/AD-40) |
| `backup_interval_hours` | int | `24` | the interval before a tenant with no successful backup is flagged overdue (AD-32) |
| `configured_sources` | list | `[]` | the enumerated data sources a corpus may be drawn from (AD-16) |
| `exclusion_list` | list | `[]` | filename/path patterns excluded from ingestion |
| `taxonomy` | list | `[]` | the tenant's classification taxonomy (seeded at provisioning) |
| `off_corpus_refusal_enabled` | bool | `true` | the honest "not in the corpus" refusal (AD-20) — **on by default** |
| `cascade_stage3_max_share` | float | `0.5` | the ceiling on the share of a matter reaching the LLM (AD-18) |

<!-- config-keys:end -->

Wiring each value into its consumer (the cascade share into stage-3 gating, sources into
ingestion, chunking into the chunker) lands in the consuming story (epics 2/4/5); 1.9 delivers the
surface, the defaults and the guarantees.

## The content-free projection (AD-26/FR-31)

"Only code travels" is one **enforceable mechanism**, not a promise repeated in three places. All
emission of information *about* a *tenant*'s data goes through **one registry of named projectors**
(`apx/core/projection.py`); each declares the **shape** it emits (a value kind from a content-free
set — count, version, error-class, timing, redacted-diagnostic, opaque-id, attested-aggregate). The
registry is **open by construction** (FR-31): the next increment's on-premises style extractor
registers a projector, it does not fork the primitive.

Content-freedom is a **structural property**, in three parts (`python -m apx.checks` + a seeded-token
test):

- **The seeded-token test** seeds a *corpus* with a unique content token AND a secret value, runs
  **every** registered projector, and asserts neither appears in any projector's output — **and** in
  the *union* of all projectors' output for one *tenant* (the attestation floor is not composable).
- **Emission outside the registry fails the build.** The `Projection` result type is **sealed** — a
  static check asserts it is constructed only inside the registry — so a projector cannot be added by
  writing an emission path; a consumer *receives* a projection from `project_all`, it never
  fabricates one.
- **A text-deriving projector must declare its attestation floor** (min *pièces* AND *matters*),
  machine-readably — one that does not turns the build red (the property is otherwise undecidable).

Today three projectors serve the client-pushed diagnostic export's needs — **corpus counts**,
an **error-class histogram**, and **version identifiers** — behind `GET /api/admin/diagnostics`
(admin, tenant-from-session). The **egress check** (AD-45, *no fourth outbound path*) deliberately
lives in the checks harness, **not** in this unit: an adversarial review predicted the projection
unit would be dropped under pressure, so dropping it must not drop the egress guarantee. The full
diagnostic **export** (packaging, the push act as a named egress) is story 6.2; the style extractor
is the next increment; the cockpit is the front-end (AD-29).

## Backup, restore & disaster recovery (AD-32/AD-35)

A dump restore is the one blessed operation that can hard-delete the evidential record — and a
truncation to an earlier *consistent* point is **undetectable from inside the database** (every
chain link still verifies). So the chain **head** — scope, sequence, chain value, wall-clock, app &
schema versions — is recorded in a **head journal held OUTSIDE the restorable store**
(`APX_HEAD_JOURNAL`, on a volume the dump does not cover), appended as it advances on every audited
write. A **missing or unwritable** journal **fails start-up**, on the same gate as the encryption
key. On start-up and after a restore the live head is **reconciled** against the journal: a live
head **behind** the journal is a **truncation** — surfaced (`GET /api/admin/dr`), named on every
future export, cleared only by a recorded, audited **override** with a reason, and **never
repaired**.

**Backup is logical and per-tenant** (inside the *tenant* boundary): it captures the tenant's
*pièces*, *failure register*, *audit record*, configuration, users and scopes — content-bearing
columns stay **ciphertext** (encrypted at rest, no re-encryption). Restore is **exercised, not
assumed**: a restore into an **empty** store reproduces the tenant's inventory (the *denominator*),
its audit sequence and its configuration **identically**, the chain **re-verifies**, and the head
**reconciles**. On demand:

```
python -m apx.manage backup  --tenant cabinet --out /backups/cabinet.json
python -m apx.manage restore --from /backups/cabinet.json     # into an empty store; head reconciled
```

The product **states** a tenant's storage footprint at the *design target* (100 000 *pièces*) and a
**pre-flight capacity check refuses** an *import job* projected not to fit — at submission (`507`),
not at 70 %. A tenant with **no successful backup within `backup_interval_hours`** reports itself
**overdue** (`GET /api/admin/dr`). The physical `pg_dump`/`pg_restore`/`upgrade.sh` wrappers + the
cron schedule are deploy artifacts (AD-46); the *worklist*/home-screen rendering is the front-end
(AD-29); 1.11 builds and **tests** the mechanism they wrap.

## What does NOT belong in this repo yet

Scaffolding only. Each item below has an owning story; building it here is a
scope violation.

| Not yet | Owner |
|---|---|
| Internal service tokens (PyJWT), WebAuthn as a 2nd factor; MFA enrolment UX | later |
| Transient user-supplied credential channel (document passwords, AD-47 rule 2) | epic 2 |
| Single read entry point (`core/app/read/`) + outside-read grep (AD-14) | later (1.12 / epic 3) |
| Visual settings / provisioning SPA (the mechanism exists; the UI is deferred) | front-end (AD-29) |
| Diagnostic export packaging + the push act (the projection primitive exists; 1.10) | 6.2 |
| Style extractor (the projection primitive's next consumer) | next increment |
| Physical `pg_dump`/`pg_restore`/`upgrade.sh` wrappers + cron (the 1.11 mechanism exists) | deploy (AD-46) |
| Embedder, extraction, OCR, LLM client, ML weights | Epic 2 |
| Structural checks beyond the layering rule | 1.12 |
| Offline-fitness CI job (network-isolated, end-to-end) | 1.2 |
