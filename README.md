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
| `chunking_target_chars` | int | `1200` | the target passage size (characters) the deterministic chunker aims for; its content-derived identity is carried into every chunk id (FR-11/AD-40). The value awaits the 2.13 chunk-yield measurement. |
| `backup_interval_hours` | int | `24` | the interval before a tenant with no successful backup is flagged overdue (AD-32) |
| `configured_sources` | list | `[]` | the enumerated data sources a corpus may be drawn from (AD-16) |
| `exclusion_list` | list | `[.DS_Store, Thumbs.db, desktop.ini, .gitkeep, ~$*, .~lock.*, ._*]` | filesystem-noise filename patterns excluded from ingestion (FR-6). A set value **replaces** the default wholesale — include the OS-noise patterns if you still want them excluded. |
| `taxonomy` | list | `[]` | the tenant's classification taxonomy (seeded at provisioning) |
| `off_corpus_refusal_enabled` | bool | `true` | the honest "not in the corpus" refusal (AD-20) — **on by default** |
| `cascade_stage3_max_share` | float | `0.5` | the ceiling on the share of a matter reaching the LLM (AD-18) |
| `cascade_uncertain_low` | float | `0.35` | the stage-2 score at/below which a pièce is confident-discard; between this and `cascade_uncertain_high` is the uncertain band the LLM judges (FR-38/AD-18). Value awaits Epic-4 gold tuning. |
| `cascade_uncertain_high` | float | `0.65` | the stage-2 score at/above which a pièce is confident-relevant (FR-38/AD-18); must exceed `cascade_uncertain_low` |
| `cascade_calibration_sample` | int | `20` | confident-band pièces sampled into the LLM stage per run so the cascade's calibration is measurable (FR-38/AD-18) — a mandatory sample |
| `similarity_threshold` | float | `0.3` | the minimum cosine similarity a semantic (suggestive) result must meet, recorded on every result set (FR-12/AD-20); a default of `1.0` would disable retrieval |
| `import_unit_max_bytes` | int | `209715200` | the per-unit size ceiling above which an import unit is `resource-exhausted` rather than read whole into memory (AD-17) |
| `import_max_attempts` | int | `3` | attempts after which a unit that keeps killing the worker is quarantined and the job proceeds (AD-17) |
| `container_max_depth` | int | `6` | maximum container nesting depth; deeper is a `container-unopenable` entry, never recursed (AD-17) |
| `container_max_members` | int | `5000` | maximum members expanded from one top-level unit, so a container fan-out cannot exhaust the machine (AD-17) |
| `container_max_expansion_ratio` | int | `100` | maximum ratio of expanded bytes to a container's size; over it is a zip-bomb `container-unopenable` entry (AD-17) |
| `attachments_per_message_max` | int | `1000` | maximum attachments expanded from one message before it is a `container-unopenable` entry (AD-17) |
| `retained_ranking_versions_max` | int | `20` | the number of ranking versions retained per matter before old, unreferenced ones may be retired (FR-16) — a never-delete-safe capacity bound |
| `line_retain_bands` | list | `[confident-relevant, uncertain]` | the stage-2 bands the recommended line retains (Story 4.8/FR-17) — recall-first: the cut falls after the deepest pièce in one of these bands |

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

## Structural properties (AD-33/FR-56)

Where the design says *no code path does X*, a **static check decides it and a violation fails the
build** — never a runtime test (a test cannot decide a universal negative), never a human
remembering to look. The checks live in `apx/checks/` (`python -m apx.checks`); the **registry**
(`registry.py`) is the one list the runner executes, and the **manifest** (`manifest.py`) names
every property — its FR, its AD, the check callable, and the file or pattern it inspects.

The manifest is *itself* checked: **a property with no registered check fails the build**, an
orphan check absent from the manifest fails the build, and this reference block is kept in lock-step
with the manifest both ways (a drifted or deleted block turns the build red). Several checks are
**forward-looking** — they scan the surface their subject will occupy (the embedder, retrieval, the
i18n string sets, the confidence sentence), pass *vacuously* today, and fire the day that code
lands; each carries a failure-path fixture proving it fires, so "green" is never mistaken for
"nothing to guard". The three verbs are never conflated — *asserted by test*, **enforced as a
structural property**, *asserted by review* — and a `review`/`deferred`/`not-enforceable` row is
tracked here but **never counted as a passing check** (the most dangerous inaccuracy this programme
could contain is an inflated claim about what the suite proves).

<!-- structural-properties:start -->

| Key | FR | AD | Verb | Check | Inspects |
|---|---|---|---|---|---|
| `layering-egress-imports` | FR-56 | AD-4/45/27 | structural | run | the import graph (pyproject [tool.importlinter]) |
| `one-chunk-writer` | FR-8 | AD-9 | structural | one_chunk_writer | Chunk(...) / insert(Chunk) sites in apx/** |
| `chunk-scope-arg-required` | FR-8 | AD-9 | structural | scope_arg_required | the chunk writer's signature (no default) |
| `chunk-columns-enumerated` | FR-8 | AD-9 | structural | chunk_columns_enumerated | the chunk model column set |
| `no-custodian-scope-column-on-piece` | FR-4 | AD-9 | structural | no_custodian_or_scope_column_on_piece | custodian/scope columns on the piece model |
| `no-cascade-delete` | FR-4 | AD-7 | structural | no_cascade_delete | ON DELETE clauses on chunk/piece FKs |
| `tenant-not-null` | FR-30 | AD-12 | structural | tenant_not_null_on_owned_tables | tenant columns in the models |
| `scoped-access-carries-tenant` | FR-30 | AD-12 | structural | scoped_access_carries_tenant | scope predicates in apx/** |
| `identity-tenant-qualified` | FR-30 | AD-12 | structural | identity_is_tenant_qualified | identity keys in the models |
| `no-reversible-credential` | FR-48 | AD-15 | structural | no_reversible_credential_storage | credential columns in the models |
| `jwt-pins-algorithms` | FR-48 | AD-15 | structural | jwt_decode_pins_algorithms | jwt.decode call sites in apx/** |
| `scope-mutations-audited` | FR-49 | AD-33 | structural | scope_mutations_are_audited | the scope-mutating store methods |
| `sensitive-columns-encrypted` | FR-47 | AD-31 | structural | sensitive_columns_are_encrypted | content columns in the models |
| `startup-gate-fail-closed` | FR-47 | AD-31 | structural | startup_gate_is_fail_closed | apx/api/startup.py |
| `no-secret-in-source` | FR-51 | AD-47 | structural | no_secret_in_source | apx/, docker/, deploy/, .github/, root config |
| `no-secret-column` | FR-51 | AD-47 | structural | no_secret_column_in_models | the model columns |
| `no-tenant-branch-core` | FR-30 | AD-24 | structural | no_tenant_conditional_in_core | conditionals under apx/core/** |
| `config-defaults-preserve` | FR-30 | AD-24 | structural | config_defaults_preserve_guarantees | apx/core/domain/config.py |
| `documented-config-keys-exist` | FR-30 | AD-24 | structural | documented_config_keys_exist | the README config-keys block |
| `config-reference-complete` | FR-30 | AD-24 | structural | config_reference_is_complete | the README config-keys block |
| `projection-registry-only` | FR-31 | AD-26 | structural | projection_emitted_only_by_registry | Projection(...) sites in apx/** |
| `snapshot-content-free` | FR-31 | AD-26 | structural | snapshot_fields_are_content_free | the Snapshot type fields |
| `projectors-declare-attestation` | FR-31 | AD-26 | structural | projectors_declare_attestation | the projection registry |
| `no-runtime-import-from-tests` | FR-33 | AD-16 | structural | no_runtime_import_from_tests | imports in the runtime tree |
| `no-fixture-path` | FR-33 | AD-16 | structural | no_fixture_path_in_runtime | _fixtures/fixtures path literals in runtime |
| `no-egress-call-site` | FR-32 | AD-45 | structural | no_egress_call_site_outside_adapters | network imports + call sites in apx/** (excl. the egress adapters) |
| `no-tenant-identifier-source` | FR-30 | AD-24 | structural | no_tenant_identifier_in_source | conditionals in the runtime tree |
| `queue-sealed` | FR-2 | AD-17 | structural | no_queue_import_outside_submodule | procrastinate imports in the runtime tree (excl. the queue submodule) |
| `extract-msg-sealed` | FR-3 | AD-28 | structural | no_extract_msg_import_outside_worker | extract_msg imports in the runtime tree (excl. adapters/extraction/msg_worker.py) |
| `subprocess-only-in-extraction` | FR-3 | AD-28 | structural | no_subprocess_call_outside_extraction | subprocess imports in the runtime tree (excl. adapters/extraction) |
| `extraction-captures-stderr` | FR-3 | AD-28 | structural | extraction_subprocess_captures_stderr | subprocess call sites in adapters/extraction (capture_output / stderr=PIPE or DEVNULL) |
| `no-fallback-embedder` | FR-9 | AD-11 | structural | embedder_has_one_implementation | embed/encode-method classes + except-handlers in the runtime tree (live as of 2.8) |
| `destructive-index-one-entry` | FR-10 | AD-7 | structural | destructive_index_ops_single_entry | index drop/truncate call sites (vacuous until 2.8) |
| `no-post-filter-retrieval` | FR-14 | AD-14 | structural | no_post_filter_in_retrieval | functions taking a result set + a scope (retrieval landed 3.x — live, no offender) |
| `no-nl-translation-key` | FR-34 | conventions | structural | no_natural_language_translation_key | t()/gettext() call args (vacuous until 6.3) |
| `no-hardcoded-locale` | FR-35 | AD-24 | structural | no_hardcoded_locale | locale= / setlocale / Locale literals (vacuous until 6.4) |
| `no-model-reported-confidence` | FR-42 | AD-19 | structural | no_model_reported_confidence | confidence fields read off a model response (vacuous until 4.x) |
| `no-banned-confidence-phrasing` | FR-23 | FR-23 | structural | no_banned_confidence_phrasing | banned phrases in string literals / locale resources (vacuous until 5.4/6.x) |
| `gold-set-merge-gate` | FR-54 | AD-34 | structural | ranking_code_requires_the_gold_gate | ranking/triage sites in apx/** + eval/harness.py recall gate (vacuous until Epic 4) |
| `no-perf-ceiling-before-measurement` | NFR-2 | AD-32 | structural | no_perf_ceiling_before_measurement | module-level latency/throughput/wall-clock ceiling constants in apx/** vs the pending measurement record (vacuous until a ceiling is declared) |
| `truth-status-constant-per-engine` | FR-12 | AD-20 | structural | truth_status_is_constant_per_engine | truth_status fields on result-set types in apx/** (a constant, non-overridable TruthStatus member — no config can forge exhaustive) |
| `exhaustive-engine-no-limit` | FR-13 | AD-20 | structural | exhaustive_engine_takes_no_limit | params of functions returning an exhaustive result set in apx/** (no limit/top-k/page-size — an exhaustive set is never truncated) |
| `tenant-reads-one-entry-point` | FR-14 | AD-14 | structural | tenant_reads_have_one_entry_point | select/query/join over a tenant-content model outside core/app/read/ + the store read modules (a surface cannot hand-roll a scoped read) |
| `scoped-read-scope-in-query` | FR-14 | AD-14 | structural | scoped_read_puts_scope_in_the_query | scopes-taking functions that select a scoped content table filtered by tenant alone (the register_all fetch-then-post-filter shape) |
| `corpus-read-no-admin-bypass` | FR-14 | AD-12 | structural | corpus_read_takes_no_admin_bypass | Piece/Chunk-reading functions that take an is_admin/super-user bypass parameter (no super-user corpus read) |
| `result-response-serialises-truth-status` | FR-15 | AD-20 | structural | result_set_response_serialises_truth_status | response/export models in apx/api/ carrying engine result items (must declare truth_status — never dropped on the wire) |
| `no-response-merges-engines` | FR-15 | AD-20 | structural | no_response_merges_the_two_engines | response/export models in apx/api/ carrying both a semantic and a deterministic result item (the two engines are never combined) |
| `originals-encrypted-at-rest` | FR-44 | AD-31 | structural | originals_are_encrypted_at_rest | the filesystem original store's put() encrypts before writing + a behavioural on-disk-ciphertext probe (retained originals encrypted at rest, Story 3.5a) |
| `rendered-html-is-sanitized` | FR-44 | AD-29 | structural | rendered_html_is_sanitized | the render_html package builds a RenderedDocument at one site (inside _rendered, which nh3-sanitises) so no render path — office or .msg — emits unsanitised HTML + a behavioural XSS-battery and adversarial-.xlsx probe (Story 3.5c-2/3) |
| `register-state-written-once` | FR-5 | AD-37 | structural | register_state_written_once | Failure.resolution_state writes across apx/** |
| `case-theory-append-only` | FR-37 | AD-37 | structural | case_theory_version_is_append_only | CaseTheoryVersion construction outside the store adapter + any UPDATE/DELETE of case_theory_version across apx/** (append-only, one owner — Story 4.1) |
| `ranking-append-only` | FR-39 | AD-37 | structural | ranking_version_is_append_only | RankingVersion/RankedEntry construction outside the store adapter + any UPDATE/DELETE of ranking_version/ranked_entry across apx/** (append-only, one owner — Story 4.3) |
| `no-retained-discarded-set` | FR-16 | AD-39 | structural | no_retained_or_discarded_set_column | table + column names across the ORM models — no table/column names a retained/discarded set membership; those sets are views over the order + the line + pins (Story 4.3) |
| `confidence-one-derivation` | FR-42 | AD-19 | structural | confidence_has_one_derivation | Confidence(...) construction sites across apx/** — the per-pièce confidence is built only in core/domain/piece_confidence.py, so it has one auditable derivation, never a self-reported figure (Story 4.4) |
| `taxonomy-label-append-only` | FR-40 | AD-37 | structural | taxonomy_label_is_append_only | TaxonomyLabelEntry construction outside the store adapter + any UPDATE/DELETE of taxonomy_label_entry across apx/** — an assignment and its reversal are always new entries (append-only, one owner — Story 4.5) |
| `label-not-a-ranking-input` | FR-43 | AD-39 | structural | ranking_order_ignores_the_taxonomy_label | core/domain/ranking.py + core/app/rank.py import/reference of the taxonomy-label axis — a label is never an ordering input, so it never moves a pièce or the line (Story 4.5) |
| `triage-sets-one-derivation` | FR-16 | AD-39 | structural | triage_sets_have_one_derivation | TriageSets(...) construction sites across apx/** — the retained/discarded sets are one derived view built only in core/domain/triage_sets.py, never a hand-rolled or stored membership (Story 4.7) |
| `line-stored-by-piece-identity` | FR-17 | AD-23 | structural | line_is_stored_by_piece_identity | the line_placement model's columns — it stores last_retained_piece_id and NO ordinal position column, so an import that adds pièces cannot silently move the line (Story 4.8/FR-17) |
| `line-placement-append-only` | FR-17 | AD-37 | structural | line_placement_is_append_only | LinePlacement construction outside the store adapter + any UPDATE/DELETE of line_placement across apx/** — a line move and its reversal are always new placements (append-only, one owner — Story 4.8) |
| `line-projection-not-a-bound` | FR-19 | AD-20 | structural | line_projection_is_not_a_sampling_bound | core/domain/line_projection.py imports/references — the priced move never depends on confidence.prevalence_upper_bound, so a projection is never computed by (or mistaken for) the sampling bound (Story 4.9/§0.2) |
| `pin-ledger-append-only` | FR-43 | AD-37 | structural | pin_ledger_is_append_only | PinEntry construction outside the store adapter + any UPDATE/DELETE of pin_entry across apx/** — a pin and its removal are always new entries (append-only, one owner — Story 4.11) |
| `pin-not-a-ranking-input` | FR-43 | AD-39 | structural | ranking_order_ignores_the_pin | core/domain/ranking.py + core/app/rank.py import/reference of the pin axis — a pin is never an ordering input, so it moves exactly one pièce in the VIEW, never in the ranked order (Story 4.11) |
| `justification-names-evidence` | FR-41 | AD-19 | structural | justification_names_its_evidence | Justification(...) construction sites across apx/** — built only in core/domain/justification.py, whose invariant requires named extracts or intrinsic signals, so the sentence is never the checkable part (Story 4.6/R-11) — plus record_justification's call to validate_named_evidence, so the write seam re-runs the invariant and never persists a justification the read path could not rebuild |
| `justification-verified-show-time` | FR-11 | AD-10 | structural | justification_verified_at_show_time | SqlStore.read_justification references resolve_chunk + verify_justification — every named extract is re-verified by exact containment when shown, so an extract that no longer resolves is unverified, never ordinary (Story 4.6) |
| `user-action-registry-complete` | FR-21 | AD-7 | structural | user_action_registry_is_complete | every HTTP route declared anywhere under apx/api/ (every verb, decorator or call form, incl. api_route) + every Ports-taking public callable anywhere under apx/core/app/ (incl. subpackages, nested blocks and class methods), checked against USER_ACTIONS both ways — an action that exists but is not registered, or a registered one that no longer exists, fails the build, because an action outside the registry is outside the bounded runtime probe that proves it destroys nothing; a routing or import shape the check cannot read fails it closed (Story 4.12) |
| `deletion-shaped-names-reversal` | FR-21 | AD-7 | structural | deletion_shaped_actions_declare_their_reversal | the HTTP verb and the word parts of every registered action's route path / use-case name — an act a user could read as deletion (DELETE, revoke, clear, remove, reject, revert…) must declare that it does and name the reversal that undoes it (Story 4.12/FR-5) |
| `staleness-trigger-has-observable` | FR-58 | AD-23 | structural | every_staleness_trigger_has_an_observable | the TRIGGERS enumeration and FreshnessStamp's fields in core/domain/freshness.py, compared both ways — a trigger with no observable is a staleness nothing can detect (the artefact would read FRESH while its input moved, which is the failure AD-23 names), and an observable named by no trigger is a staleness the surface could not explain (FR-58 requires naming the input that changed); every trigger must carry a French phrase and a source requirement, and no observable may be a clock; AD-23's eight are a floor that may not shrink (FR-23 adds a ninth, the population a bound was drawn from); the per-kind narrowing INPUTS_BY_KIND is bounded too — no invented input, the union over kinds is the whole enumeration (a trigger every kind excluded is a staleness deleted rather than argued), and the confidence bound depends on every one of them because FR-58 and FR-23 are written about it; a TRIGGERS that is not a literal tuple fails it closed (Story 4.13) |
| `freshness-names-no-clock` | FR-58 | AD-23 | structural | freshness_is_never_time_based | time imports (including aliased and from-forms), clock calls (now/utcnow/today/monotonic/timestamp…) and timedelta across the three modules that decide freshness — core/domain/freshness.py, core/domain/worklist.py and core/app/read/freshness.py; a TTL would invert the guarantee, making an artefact whose input moved read fresh again by waiting, so staleness is resolved only by an explicit user-initiated recomputation producing a NEW artefact (Story 4.13) |
| `artefact-stamp-append-only` | FR-58 | AD-37 | structural | artefact_stamp_is_append_only | ArtefactStamp constructions outside the store adapter and every UPDATE/DELETE idiom against artefact_stamp (Core update/delete, ORM query mutation, raw SQL, session.delete of a loaded row, attribute assignment) — a stamp records what the inputs WERE, so rewriting one would make a stale artefact read fresh; re-producing an artefact mints a new artefact with a new stamp, never a refreshed stamp on the old one (Story 4.13) |
| `sampling-population-derived` | FR-22 | AD-39 | structural | sampling_population_is_the_derived_view | the sampling-run functions in the store adapter — the draw and the `discard_population` observable must BOTH go through `derive_triage_sets` (one derivation, so a run is never invalidated against a set it was not drawn over), and none of them may read the Story-2.x label pile: Epic 5's discarded set is the Epic-4 derived VIEW, which is the only population FR-22's "records the ranking version and the position of the line" can even be stated over (Story 5.1, decision A1) |
| `sampling-freeze-identifiers` | FR-22 | AD-23 | structural | a_sampling_run_freezes_its_identifiers | SamplingRun's five freeze columns (ranking version id + no, the line by last-retained-pièce identity, the pin ledger seq, the scope), each declared `nullable=False`, plus SamplingRunItem's `proxy_piece_id`/`member_piece_ids` — FR-22 says in as many words that a seed alone is insufficient, so the explicit identifier list is a SHAPE: deleting the item table to keep only the seed fails the build (Story 5.1) |
| `no-new-legacy-bound` | FR-23 | AD-7 | structural | no_new_legacy_bound_is_written | `RecallReview(...)` constructions across apx/** — the label-pile bound is readable history (AD-7: rows stay, `read_current_bound` still falls back to them), never a second live writer over a second population; two bound writers over two "discarded sets" is the ambiguous referent the Epic 4 retrospective named (Story 5.1) |
| `estimator-piece-worst-case` | FR-38 | AD-19 | structural | piece_figure_is_a_worst_case | every `count_upper_pieces=` assignment and every multiplication across apx/** — the bound is computed over near-duplicate FAMILIES (forty copies of one email are one draw), so the *pièce* figure is the sum of the D LARGEST frozen family sizes, never `prevalence_upper × population_pieces`: that rescale assumes the relevant families are average-sized and understates whenever the big threads are the relevant ones — in the flattering direction (Story 5.2, OQ-4 input 1) |
| `estimator-census-no-bound` | FR-22 | AD-19 | structural | a_census_states_no_bound | `census_statement_fr` and `estimate_for_run` in core/domain/sampling.py — a census is not a tighter bound but a categorically different statement, so its branch carries an exact count and builds no percentage at all, and the bound branch carries no exact count; the crossover is `n == N` exactly and no third register exists near it (Story 5.2, OQ-4 input 2) |
| `estimator-one-run-one-bound` | FR-22 | AD-37 | structural | one_run_one_bound_chosen_by_recency | `prevalence_upper_bound` call sites across apx/** and `read_current_bound`'s ordering — a bound is born in one module only (no second path could pool two draws over one population) and the matter's current bound is the most RECENT completed run, never the most flattering; the sentence travels alone (Story 5.2, OQ-4 input 3) |
| `estimator-bound-from-the-freeze` | FR-22 | AD-23 | structural | the_bound_is_computed_from_the_freeze | `complete_sampling_run` in the store adapter — the estimator's population and sample are read off the frozen run row and the function reaches no live derivation of the discarded set; re-deriving would quote a bound over the matter as it is NOW with the authority of a draw made over what it was THEN (Story 5.2, OQ-4 input 4) |
| `estimator-no-model-number` | FR-42 | AD-19 | structural | the_bound_consumes_no_model_number | core/domain/confidence.py and core/domain/sampling.py — the estimator imports nothing from `line_projection` and reads no confidence field off a model response; the FR-19 projection at an unsampled position is not calibratable against TREC Legal Track and ships as counts only, so a made-up number can never be laundered through a statistical sentence (Story 5.2, OQ-4 input 5) |
| `estimator-simulation-gate` | FR-23 | AD-33 | structural | the_simulation_gate_is_wired | `ESTIMATOR_PROVEN` in core/domain/confidence.py, against apx/eval/estimator_simulation.py and tests/eval/test_estimator_simulation.py — the flag cannot be true unless the harness EXISTS, names its coverage target, its trial floor and its scenarios, and a registered test asserts BOTH the coverage floor and the tightness ceiling with nothing skipped or xfailed. A static check cannot verify the mathematics; it can make the word "proven" un-writable without the proof running. With the flag FALSE the check passes and says so — shipping counts-only is FR-23 working (Story 5.3) |
| `inventory-record-fields` | FR-6 | AD-38 | structural | inventory_record_fields_enumerated | Inventory fields in core/domain |
| `unknown-cardinality-never-summed` | FR-6 | AD-38 | structural | unknown_cardinality_never_summed | '+' operands across apx/** |
| `meta-property-has-check` | FR-56 | AD-33 | structural | every_structural_property_has_a_registered_check | this manifest vs CHECKS |
| `meta-check-in-manifest` | FR-56 | AD-33 | structural | every_registered_check_is_in_the_manifest | CHECKS vs this manifest |
| `meta-verbs-not-conflated` | FR-56 | AD-33 | structural | verbs_are_not_conflated | this manifest's verbs |
| `meta-manifest-matches-readme` | FR-56 | AD-33 | structural | manifest_matches_readme | the README structural-properties block |
| `meta-readme-lists-every` | FR-56 | AD-33 | structural | readme_lists_every_property | the README structural-properties block |
| `meta-floor-of-13` | FR-56 | AD-33 | structural | floor_of_13_has_a_structural_check | the 13 enumerated FR-56 floor items vs the manifest |
| `deferred-action-registry` | FR-21 | AD-33 | deferred | — | deferred to the usability-probe story (FR-21) — the action registry is itself a structural property, but the actions it enumerates do not exist yet |
| `deferred-fixture-env-source` | FR-33 | AD-16 | deferred | — | the third FR-33 leg — an env-var conditional selecting a data source outside the configured-source list — deferred: a bare os.getenv branch is not precisely separable from legitimate config without false positives (the fixture-path leg catches a demo override that reads a fixture dir) |
| `not-enforceable-denylist-depends` | FR-30 | AD-3 | not-enforceable | — | no check can decide whether the core 'depends on' a managed capability (AD-33/AD-3) — the package/extension deny-list (import_contracts) stands in as the enforceable half |
| `not-enforceable-rejection-record` | FR-48 | AD-15 | not-enforceable | — | AD-15's rejection-record honesty is asserted by review, not a static check (AD-33) — the no-reversible-credential and jwt-pins-algorithms checks stand in where decidable |
| `not-enforceable-plausible` | FR-19 | AD-19 | not-enforceable | — | no check can decide plausibility (AD-33) — asserted by review; the derived-confidence and gold-set calibration checks stand in where they exist |
| `not-enforceable-commercial` | FR-27 | AD-27 | not-enforceable | — | a commercial statement is not a code property (AD-33) — the pre-flight screen stands in |
| `review-refusal-phrasing` | FR-27 | AD-33 | review | — | phrasing quality is asserted by review against a checklist — never counted as a test |

<!-- structural-properties:end -->

## What does NOT belong in this repo yet

Scaffolding only. Each item below has an owning story; building it here is a
scope violation.

| Not yet | Owner |
|---|---|
| Internal service tokens (PyJWT), WebAuthn as a 2nd factor; MFA enrolment UX | later |
| Transient user-supplied credential channel (document passwords, AD-47 rule 2) | epic 2 |
| Single read entry point (`core/app/read/`) + outside-read grep (AD-14) | epic 3 (3.3) |
| Visual settings / provisioning SPA (the mechanism exists; the UI is deferred) | front-end (AD-29) |
| Diagnostic export packaging + the push act (the projection primitive exists; 1.10) | 6.2 |
| Style extractor (the projection primitive's next consumer) | next increment |
| Physical `pg_dump`/`pg_restore`/`upgrade.sh` wrappers + cron (the 1.11 mechanism exists) | deploy (AD-46) |
| Embedder, extraction, OCR, LLM client, ML weights | Epic 2 |
| Offline-fitness CI job (network-isolated, end-to-end) | 1.2 |
