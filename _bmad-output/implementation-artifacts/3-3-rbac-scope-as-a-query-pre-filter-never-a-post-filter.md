---
baseline_commit: 3c5c106
---

# Story 3.3: RBAC scope as a query pre-filter, never a post-filter

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a firm bound by Chinese walls,
I want the scope constraint applied inside the query itself and impossible to bypass,
so that a cross-*matter* leak — silent, and a professional-conduct violation — cannot happen through any read.

## Scope note — the AD-14 CONTRACT + its GATE + the adversarial PROOF, and the one genuine post-filter FIXED; the per-action registry and the non-search screens stay deferred

This is Epic 3's **Chinese-wall consolidation** (AD-13 + AD-14), now unblocked because **both engines exist** (3.1 semantic, 3.2 deterministic). It is **pure backend/security — no UX pass** (the epic marks no UX banner on 3.3). The leak this story prevents *has no error message*: a cross-*matter* result is a professional-conduct violation that looks exactly like a correct answer, so the guarantee must be **structural and adversarially proven**, not a discipline.

**What this story builds (all CI-verifiable):**

- **Fix the one genuine post-filter that exists today — `register_all` (AD-14/AD-1 anti-pattern).** [store.py:1123](../../apx/adapters/store_postgres/store.py#L1123) fetches **every** failure in the *tenant* (`select(Failure).where(Failure.tenant == tenant)` — no scope in the query) and then drops out-of-scope rows **in Python** (`if (f.matter in held) or (f.matter is None and is_admin)`). That is the exact silent-leak vector AD-14 names: "the wrong rows were already fetched, counted or logged." Rewrite it so the scope is a **query pre-filter** (the held matters joined/sub-queried from `matter_scope`, the admin *matter-less* carve-out expressed **in SQL**), so no out-of-scope `Failure` row is ever fetched into memory. This preserves the FR-49 behaviour exactly (a non-admin never sees an undetermined entry; the tenant admin sees `matter IS NULL` entries) while moving the wall from Python into the query.
- **The single-read-path GATE (AC2 — the half that does not exist yet).** A new **structural check** (AD-14) makes "exactly one code path constructs a *tenant*-data read" mechanical. Its complement — "no read filters after returning" — is **already live** as [`no_post_filter_in_retrieval`](../../apx/checks/forward_looking.py#L219) (a function taking a result set + a scope). This story adds the two teeth that check misses: (i) **no tenant-owned-table query is *constructed* outside the sanctioned read path** (surfaces `api/ web/ worker/ eval/`, `core/` outside `read/`, and any non-read adapter module must be query-free over *tenant* tables), and (ii) **a method that takes `scopes` may not SELECT a scoped *tenant* table filtered by *tenant* alone** — an internal fetch-then-post-filter (the `register_all` shape), which the signature-only check cannot see.
- **The adversarial out-of-scope suite over BOTH engines (AC3) — the epic-DoD headline.** Plant, in an **out-of-scope** *matter*, the *pièces* that are the **top** similarity matches (semantic) and the **exact** matches (deterministic), query with the *other* scope, and assert **zero** out-of-scope results **and zero out-of-scope metadata** — ids, snippets, filenames, counts, and *denominator* figures. Extended to the **register** read after its fix.
- **The mutating suite (AC5).** Revoke a scope while a session is open and grant one mid-run; assert the wall holds in its **new** position on the very next query and its **old** never. This is true *because* the `Principal` (`SessionIdentity`, AD-15) and the scope predicate are **re-resolved live from the rows** every request (AD-13: no re-stamping, a change takes effect on the next query) — never denormalised onto the session.
- **Fail-closed with no scope, for administrative AND system identities (AC6).** A caller with an empty scope reads an **empty** *corpus*, not the whole one — asserted for an admin and a system identity alike (AD-12: "no identity bypasses the predicate"). The engines already short-circuit on empty `scopes` and take **no** `is_admin` argument (there is structurally no super-user corpus read); this story asserts that, and asserts the `register_all` admin carve-out discloses **only** *matter-less* entries, never a scoped *matter*'s.
- **The *denominator* is computed within scope (AC4).** Already true (3.2's `_scoped_inventory` joins `matter_scope`); this story asserts, in the adversarial suite, that `denominator.in_corpus` and the OCR share count **only in-scope** *pièces* — the numbers cannot leak the existence of material the caller may not see.

**What is deferred (honestly):**

- **The AD-33 action registry that names each action's read entry point** — AD-14's *second* "check that decides it" ("an action with no read entry point fails the build") and AD-42's export binding both lean on it. It is already tracked as **`deferred-action-registry`** (FR-21, the usability-probe story) *because the user-reachable actions do not exist as a registry yet*. This story does **not** build it; it builds the query-construction tooth that does not depend on an action inventory.
- **Routing every non-search API read through `core/app/read/`.** The API surface reads today by calling the store's scoped methods directly ([app.py](../../apx/api/app.py): `matters`, `register`, `inventory`, `read_audit`, `sample_discards`). Those are **safe** (authorise-then-read: they resolve the *named* matter's scope and read only that matter's rows — no out-of-scope row is ever fetched) but they are not yet a single `core/app/read/` entry point. AD-14's "one entry point for every non-search screen" is the **non-search-screens** work of **Epic 6** (FR-27/28/60/7/52) and the **viewer** of **3.5**; consolidating them now would be over-building against surfaces that change there. This story's gate makes a **new** hand-rolled query a build failure and fixes the one **actual** post-filter; the full route consolidation rides with the screens that own those routes.
- **The *confidence bound* computed within scope (AC4, second clause)** — the bound is derived in Epic 4 (`no_model_reported_confidence` stays vacuous until then). Its scope-safety is asserted when it lands; the *denominator* half of AC4 is proven here.

## Acceptance Criteria

1. **Scope is a query pre-filter on every read, resolved at query time from the one authoritative source — never a post-filter, never denormalised (FR-14, AD-13, AD-14).** Both engines already join `matter_scope` as a pre-filter. The one existing **post-filter** — `register_all`, which fetches every *tenant* `Failure` then filters by matter in Python — is rewritten so the scope (and the admin *matter-less* carve-out) is applied **inside the query**; no out-of-scope `Failure` row is fetched. Scope is never read off a denormalised row (AD-13: it lives only in `matter_scope`/`user_scope`, joined at query time). *(tests: `register_all` after the fix fetches only in-scope + (admin-only) matter-less rows — asserted by a real round-trip that plants an out-of-scope failure and asserts it is never returned and never counted; the SQL carries the scope predicate, not a Python filter.)*

2. **A static check asserts exactly one code path constructs a tenant-data read, and no read filters after returning (FR-14, FR-56).** A new **structural** check (AD-14), green on the real tree and firing on fixtures, asserts: (a) **no tenant-owned-table query is constructed outside the sanctioned read path** — a `select(Piece|Chunk|Failure|MatterScope|PieceLabel|RecallReview|AuditRecord…)` / `session.query(...)` / raw SQL naming a scoped table anywhere under `api/ web/ worker/ eval/`, or `core/` outside `read/`, or a non-read adapter module, fails the build; and (b) **a method taking `scopes` may not SELECT a scoped tenant table filtered by `tenant` alone** (the internal fetch-then-post-filter the signature-only [`no_post_filter_in_retrieval`](../../apx/checks/forward_looking.py#L219) cannot catch). The existing post-filter check stays; its stale "vacuous until 3.x" manifest/README note is corrected (retrieval has landed). *(tests: the new check fires on a planted surface `select(Piece)`, fires on a planted `scopes`-taking method that selects a scoped table by tenant only, passes the real tree, fails closed on an unparseable file; check count rises; README ↔ manifest lockstep holds.)*

3. **An adversarial suite proves zero out-of-scope leak across BOTH engines (FR-14) — results AND metadata.** With two *matters* in one *tenant* — one in scope, one out — and the out-of-scope *matter* holding the deliberately-**best** matches (highest semantic similarity; the exact deterministic hits), a query under the in-scope scope returns **zero** out-of-scope results and **zero** out-of-scope metadata: no out-of-scope `piece_id`, snippet, filename, `error_class`, count, or *denominator* figure. *(tests — deterministic: a real end-to-end round-trip on SQLite over `full_text_normalized`; the out-of-scope exact match is absent, `denominator.in_corpus` counts only the in-scope matter, `ocr_share` is computed only over in-scope pièces, no out-of-scope filename/id appears. Semantic: the compiled statement carries the `matter_scope` pre-filter join with `tenant` on both sides and `scope IN (...)` — proving a pre-filter, not a post-filter — plus a Postgres-gated integration test, skipped without a DB URL, that plants a higher-similarity out-of-scope chunk and asserts it is excluded. Register: the fixed `register_all` never returns an out-of-scope entry.)*

4. **The denominator (and any confidence bound) shown is computed within the caller's scope (FR-14).** The *denominator* the exhaustive set carries counts only in-scope material — `denominator.in_corpus`, `open_register_entries`, and the OCR/quality shares are all scoped — so the numbers cannot betray the existence of out-of-scope *pièces*. *(tests: in the adversarial fixture the denominator equals the in-scope count exactly, never in-scope + out-of-scope; the OCR share denominator is the in-scope searched set. The confidence bound's scope-safety is deferred to Epic 4 and noted, not asserted here.)*

5. **(failure path) The mutating suite: revoke mid-session, grant mid-run — the wall moves immediately, its old position never leaks (FR-14, FR-49).** Because scope is re-resolved from `matter_scope`/`user_scope` at query time (AD-13) and the `Principal` is resolved live from the user's rows every request (AD-15, `SessionIdentity`), revoking a scope makes the very next read empty, and granting one makes the next read see it — with no re-indexing and no window where the old wall still holds. *(tests: grant → a read sees the matter; `revoke_scope` → the next read is empty (the old scope never leaks a row); `grant_scope` mid-run → the next read sees the matter, and a read taken before the grant saw nothing. Exercised end-to-end through the store's audited `grant_scope`/`revoke_scope` mutators + a scoped read.)*

6. **(failure path) A caller with no scope receives an empty corpus — fail-closed, for administrative and system identities alike (FR-14).** An empty `scopes` set yields an empty result from both engines and every scoped read — and this holds identically for an **admin** and a **system** identity: there is no implicit super-user corpus read (the engines take no `is_admin` argument; AD-12). The one legitimate admin carve-out — `register_all` returning *matter-less* (`matter IS NULL`) register entries to the tenant admin — is asserted to disclose **only** those, never a scoped *matter*'s entry, and a non-admin with no scope gets a fully empty register. *(tests: both engines with `scopes=set()` return empty regardless of identity; `register_all(is_admin=True, scopes=set())` returns only matter-less entries and no scoped entry; `register_all(is_admin=False, scopes=set())` is empty; a static assertion that no corpus-read method takes an `is_admin`/super-user bypass.)*

## Tasks / Subtasks

- [x] **Task 1 — Fix the `register_all` post-filter → a query pre-filter (AC: 1, 3, 6).**
  - [x] Rewrite [`SqlStore.register_all`](../../apx/adapters/store_postgres/store.py#L1123) so the scope predicate is applied **in the query**: select `Failure` where `tenant == tenant` **and** the matter is one whose scope the caller holds (a `matter_scope` join/sub-query on `(matter, tenant)` with `scope IN sorted(scopes)`), **OR** (`Failure.matter IS NULL` **and** `is_admin`). No Python `if (f.matter in held) …` filter over a tenant-wide fetch. Empty `scopes` and non-admin ⇒ no rows (except the empty set); `scopes=set()` must not fetch scoped rows.
  - [x] Preserve the exact FR-49 semantics and the return shape/order; keep the two internal callers (`retry_*` at [store.py:1258](../../apx/adapters/store_postgres/store.py#L1258), [:1297](../../apx/adapters/store_postgres/store.py#L1297)) working unchanged.
  - [x] Add a real round-trip test: seed an in-scope failure, an out-of-scope failure, and a matter-less failure; assert `register_all` returns the in-scope one always, the matter-less one only when `is_admin`, and the out-of-scope one **never** — and that the out-of-scope row is never fetched (assert via the result, and that the SQL names `matter_scope`).

- [x] **Task 2 — The single-read-path structural check (AC: 2).**
  - [x] New module `apx/checks/read_path.py` (AD-14), mirroring the house pattern (`CheckResult`, injectable `roots`, fail-closed on an unparseable file, `_RUNTIME_EXCLUDE`/`node_modules`/`__pycache__`/migrations excluded).
  - [x] `tenant_reads_have_one_entry_point(roots=None)`: AST over the tree; a tenant-owned-table query (`select(<ScopedModel>)`, `session.query(<ScopedModel>)`, or `execute(text("… <scoped table> …"))`) constructed **outside** the sanctioned read path (`core/app/read/**` + the enumerated store read modules `adapters/store_postgres/{store.py,semantic_query.py,deterministic_query.py}`) fails the build. Scoped models: `Piece, Chunk, Failure, PieceLabel, RecallReview, AuditRecord, MatterScope` (the corpus/register/label/audit tables — the leak surface). Vacuous-safe: passes today (surfaces call store methods, they construct no queries), fires on a planted surface `select(Piece)`.
  - [x] `scoped_read_puts_scope_in_the_query(roots=None)`: a function that **takes a `scopes` parameter** and constructs a `select(<ScopedModel>)` whose `where` names `tenant` but **not** `matter` and **not** a `MatterScope` reference is a fetch-then-post-filter → fails. Passes after Task 1 fixes `register_all`; fires on the pre-fix shape. (Aggregate/projection reads take no `scopes` — the AD-48 maintenance path — so they are not flagged; document that boundary.)
  - [x] Decide packaging: two functions in `read_path.py` (preferred — one AD, mirrors `no_truncation.py`/`truth_status.py`); register both.
  - [x] Register in [`registry.py`](../../apx/checks/registry.py) `CHECKS`; add manifest rows in [`manifest.py`](../../apx/checks/manifest.py) `PROPERTY_MANIFEST` (import `read_path`); add the matching README rows in the `<!-- structural-properties -->` block — machine-compared on key/fr/ad/verb/check-`__name__`. Correct the stale `no-post-filter-retrieval` "(vacuous until 3.x)" note in both manifest and README (retrieval has landed; still vacuous-of-hits, no longer vacuous-of-era).
  - [x] Tests in `tests/checks/test_read_path.py`: fires on a planted surface query, fires on a planted `scopes`-taking tenant-only scoped SELECT, passes the real tree, fails closed on `def (:`.

- [x] **Task 3 — The adversarial out-of-scope suite over both engines + the register (AC: 3, 4).**
  - [x] New `tests/security/test_out_of_scope_adversarial.py`. Helper: seed one tenant, two matters — `in-scope` (scope `s-in`) and `out-of-scope` (scope `s-out`) — and plant the **best** matches in the out-of-scope matter.
  - [x] Deterministic (real round-trip on SQLite over `full_text_normalized`, per 3.2): the out-of-scope exact match is absent from the results; `denominator.in_corpus` equals the in-scope count only; `ocr_share` is over the in-scope searched set only; no out-of-scope `piece_id`/filename/snippet appears anywhere in the `ExhaustiveResultSet`.
  - [x] Semantic: assert the compiled `semantic_search_stmt` carries the `matter_scope` pre-filter (join on `(matter, tenant)`, `tenant` on both sides, `scope IN (...)`) — the pre-filter is IN the query, not a post-filter; assert the `core/app/read/semantic.py` entry point performs no post-processing of `results`. Add a `@pytest.mark.skipif`-on-no-DB integration test that plants a higher-similarity out-of-scope chunk in Postgres and asserts it is excluded (the pattern used for pg-only features).
  - [x] Register: after Task 1, assert the fixed `register_all` never returns an out-of-scope entry even when the out-of-scope matter has the most/severe failures.

- [x] **Task 4 — The mutating revoke/grant suite (AC: 5).**
  - [x] In `tests/security/test_out_of_scope_adversarial.py` (or a sibling): through the store's audited `grant_scope`/`revoke_scope` (the FR-49 mutators), assert: grant → a scoped read sees the matter; `revoke_scope` → the next read is empty (old scope never leaks); `grant_scope` mid-run → the next read sees the matter and a read taken before the grant saw nothing. Ground the assertion in AD-13 (scope re-resolved at query time) — no re-index, immediate on the next query.

- [x] **Task 5 — Fail-closed no-scope, admin AND system (AC: 6).**
  - [x] Assert both engines return empty for `scopes=set()` regardless of identity (they take no `is_admin`); assert `register_all(is_admin=True, scopes=set())` returns only matter-less entries and never a scoped matter's; `register_all(is_admin=False, scopes=set())` is empty.
  - [x] Add a static assertion (extend `read_path.py` or a test over the store) that no corpus-read method (over `Piece`/`Chunk`) takes an `is_admin`/super-user bypass argument — there is no whole-corpus admin read.

- [x] **Task 6 — Gate + regression.**
  - [x] `ruff` clean (line-length 100, E/F/I/UP/B); full `pytest` green (no regressions); the check runner shows the new check(s) live; `alembic` head unchanged (no schema change — `register_all` is a query rewrite, not a migration). Confirm README ↔ manifest lockstep and the manifest meta-checks pass; the structural-check count rises by the number of new checks.

## Dev Notes

### The central design decision — reconciling AD-14's literal grep with the hexagonal build

AD-14's "check that decides it" reads: *"No SQL text and no ORM query naming a tenant-owned table appears outside `core/app/read/`, asserted by a grep over `adapters/`, `api/`, `worker/`, `eval/` and `web/`."* Taken literally over `adapters/`, that is impossible in **this** build: the ORM models live in `adapters/store_postgres/models.py`, `core/` must not import them (dependency direction — `core` speaks ports, the adapter speaks SQL), and every read query is constructed against those models inside the store adapter so it can compile to the PostgreSQL dialect in CI (the `<=>` / normalisation work of 3.1–3.2). The **faithful realisation of AD-14's intent** — one auditable read path, no second query path written in good faith, no surface hand-rolling a scoped read — is therefore:

> **The sanctioned read path = `core/app/read/` (the application entry points) + the store adapter's enumerated read-query modules it delegates to (`store.py`, `semantic_query.py`, `deterministic_query.py`). Tenant-owned-table query construction is a build failure ANYWHERE else** — every surface (`api/ web/ worker/ eval/`), `core/` outside `read/`, and any non-read adapter module.

This is decidable, catches the real threat (a route builds its own `select(Piece)` without the scope join), and does not force `core` to import ORM models. Record this reconciliation in the check's module docstring. The *action-registry* leg of AD-14 (per-action read entry point) stays deferred (`deferred-action-registry`, FR-21) — it needs an action inventory that does not exist yet.

### The read surface, as it is today (verified first-hand)

- **Two engines already correct** — `core/app/read/semantic.py` + `deterministic.py` call the reader ports; the SQL builders `adapters/store_postgres/{semantic_query,deterministic_query}.py` both **join `matter_scope`** as a pre-filter with `tenant` on both sides (verified). The reader ports ([`core/ports/read.py`](../../apx/core/ports/read.py)) expose no identifier-only method and no result-set parameter.
- **The one genuine post-filter is `register_all`** ([store.py:1123](../../apx/adapters/store_postgres/store.py#L1123)) — `select(Failure).where(Failure.tenant == tenant)` then a Python `if (f.matter in held) or (f.matter is None and is_admin)`. Fix it (Task 1). It is reached from [app.py:1186](../../apx/api/app.py#L1186) and from the retry paths at [:1258](../../apx/adapters/store_postgres/store.py#L1258)/[:1297](../../apx/adapters/store_postgres/store.py#L1297).
- **Per-matter reads are safe (authorise-then-read), leave them** — `matters` (pre-filters `matter_scope` in the query), `inventory`, `register`, `deduplicate`, `representatives`, `labels`, `sample_discards`, `record_recall_review`, `read_audit` resolve the **named** matter's scope (`select(MatterScope.scope).where(matter==…, tenant==…); if scope not in scopes: raise ScopeDenied`) and then read **only that matter's** rows. No out-of-scope row is ever fetched; these do not leak and are not the target of this story.
- **Tenant-wide aggregate reads are the sanctioned AD-48 path, not a leak** — the content-free projection counts ([store.py:1773](../../apx/adapters/store_postgres/store.py#L1773)–1791) and the chunking-config-immutability existence guard ([store.py:2132](../../apx/adapters/store_postgres/store.py#L2132), `select(Chunk.chunk_id).where(Chunk.tenant==tenant).limit(1)`, returns a boolean, discloses no matter) take **no `scopes`** and produce counts/booleans, never out-of-scope rows or metadata to a user. Auth/admin reads over `User`/`UserScope`/`Session` are tenant-bounded, not matter-scoped (`user_scope` is keyed by the globally-unique `user_id` — explicitly excluded from matter-scoping in [`tenant_isolation.OWNED_TABLES`](../../apx/checks/tenant_isolation.py#L33)). The `scoped_read_puts_scope_in_the_query` check keys on "**takes `scopes`**", so it does not false-positive on these.

### What already exists — do not rebuild

- [`forward_looking.no_post_filter_in_retrieval`](../../apx/checks/forward_looking.py#L219) (AD-14) — the **signature** post-filter (result set + scope in one function). Keep it; this story adds the **internal** fetch-then-filter tooth it cannot see.
- [`tenant_isolation.scoped_access_carries_tenant`](../../apx/checks/tenant_isolation.py#L80) (AD-12) — "scope never without a tenant" (the store-scoped slice of AD-14). Its own docstring names *this* story as "the full single-read-path consolidation."
- [`isolation_harness.no_tenant_identifier_in_source`](../../apx/checks) (AD-24) — no tenant literal branch.
- The engines' empty-scope short-circuit (fail-closed) and the reader ports' no-id-only-method shape.

### Structural-check house pattern (follow exactly — 51 checks today → +N)

`CheckResult(name, ad, ok, detail)`; a check takes injectable `roots`, **fails closed** on an unparseable file, excludes `{checks, fitness, timedrun, __pycache__}` and `node_modules`/`web`; register in [`registry.py`](../../apx/checks/registry.py) `CHECKS`; add a `_p(key, fr, ad, name, callable, inspects)` row in [`manifest.py`](../../apx/checks/manifest.py) `PROPERTY_MANIFEST`; add the matching README row in `<!-- structural-properties:start/end -->` (machine-compared on key/fr/ad/verb/check-`__name__`; the `Inspects` column is human prose). The meta-check `every_structural_property_has_a_registered_check` fails if a manifest row's check is not in `CHECKS`, and `manifest_matches_readme`/`readme_lists_every_property` keep the README in lockstep both ways. **`node_modules` is huge and full of "Chunk"** — exclude it before parsing (mirror [`projection._EXCLUDE_PARTS`](../../apx/checks/projection.py#L32) = `{web, node_modules, __pycache__}`).

### Previous-story intelligence (3.1 / 3.2)

- The truth-status gate (3.1) is **type-anchored**, not name-anchored — a review HIGH taught that a field-name anchor misses a computed `@property`. Anchor the new checks on **types/shapes** (scoped ORM model names, the `scopes` parameter), not fragile names.
- 3.2's keystone was moving normalisation to a **stored `full_text_normalized` column** so the deterministic round-trip is **CI-testable on SQLite** (plain `LIKE`). Reuse that: the deterministic adversarial suite runs **for real** end-to-end on SQLite. The semantic engine's `<=>`/`unaccent` are pg-only → prove the scope pre-filter by **compiling to the postgresql dialect** (the 3.1 pattern) plus a DB-gated integration test.
- 3.2 review lesson: **compute, don't fabricate** (the false `ocr_share = 0.0`). Do not stub a scope guard — prove it with a planted out-of-scope row that would leak if the guard were wrong.
- 3.2 review lesson (AD-38): **never sum a denominator with Python `+`** on the forbidden fields — the adversarial denominator assertions read the six-field `Inventory`, they do not re-add counts.

### Testing standards

`uv`-managed (`.venv/bin/ruff`, `.venv/bin/python` — **no pip**); `ruff` line-length 100, select E/F/I/UP/B. Run pytest with `export PATH="$PWD/.venv/bin:$PATH"` and **never** export `DATABASE_URL` (the SQLite baseline is what CI runs; the pg-only integration test skips without a URL). New tests: `tests/checks/test_read_path.py`, `tests/security/test_out_of_scope_adversarial.py` (new dir). The deterministic/register/mutating suites run for real on SQLite; the semantic pre-filter is compiled-SQL + a DB-gated round-trip.

### Project Structure Notes

- No migration — `register_all` is a query rewrite, `alembic` head stays `0022_deterministic_index`. If a helper query-builder is extracted for `register_all`, it lives in the store adapter (the sanctioned read path), not in `core/`.
- New files: `apx/checks/read_path.py`, `tests/checks/test_read_path.py`, `tests/security/__init__.py` (if the runner needs it) + `tests/security/test_out_of_scope_adversarial.py`. Edits: `store.py` (register_all), `registry.py`, `manifest.py`, `README.md`.
- The `is_admin` matter-less carve-out is FR-49 behaviour (a tenant admin sees `matter IS NULL` register entries — failures that belong to no matter). It is **not** a whole-corpus super-user read (there is no matter to scope) and AD-12 explicitly permits the shape; preserve it, express it in SQL, and assert it discloses only matter-less entries.

### References

- [Source: epics.md#Story-3.3] — the six acceptance criteria (out-of-scope suite over both engines; the static check; the mutating suite; fail-closed admin+system; denominator within scope).
- [Source: ARCHITECTURE-SPINE.md#AD-12] — tenant first then scope, both fail closed; no identity bypasses the predicate; the one AD-48 principal that reads a whole partition without producing a result set.
- [Source: ARCHITECTURE-SPINE.md#AD-13] — scope resolved at query time from one source, joined as a pre-filter, never denormalised; no re-stamping; a change takes effect on the next query.
- [Source: ARCHITECTURE-SPINE.md#AD-14] — exactly one code path reads tenant data (not only retrieval); no result-set post-processing accepts a scope; the grep-based check and its reconciliation above.
- [Source: ARCHITECTURE-SPINE.md#AD-38] — the six-field denominator record; `unknown` never summed (the AC4 denominator assertions).
- [Source: apx/checks/forward_looking.py#L219] — the existing `no_post_filter_in_retrieval` (the signature half of AC2).
- [Source: apx/adapters/store_postgres/store.py#L1123] — `register_all`, the post-filter to fix.

## Dev Agent Record

### Agent Model Used

claude-opus-4-8[1m] (Claude Opus 4.8, 1M context)

### Debug Log References

- TDD red state confirmed before the fix: `scoped_read_puts_scope_in_the_query` fired precisely on `store.py:1132 register_all` ("takes scopes but SELECTs a scoped content table filtered by tenant alone"); `tenant_reads_have_one_entry_point` was green (all content queries live in the sanctioned store adapter). The `register_all` rewrite (scope pre-filter, `Failure.matter` named inline in the SELECT) turned it green.
- **Final gate (frozen artifact, post-review):** ruff clean · **834 passed / 11 skipped** (was 803/10 — +31 passed: 22 read_path check tests + 9 security tests; +1 skip = the pg-gated semantic behavioural test) · **54/54 structural checks** (was 51 — +3 read_path: one-entry-point, scope-in-query, no-admin-bypass) · alembic head unchanged `0022_deterministic_index` (no migration — a query rewrite).

### Completion Notes List

- **Task 1 — `register_all` post-filter → query pre-filter.** [store.py:1123](../../apx/adapters/store_postgres/store.py#L1123) now applies scope in the query: a held-matters `matter_scope` sub-query with `Failure.matter.in_(...)` OR (admin only) `Failure.matter.is_(None)`, named inline in the SELECT so no out-of-scope `Failure` row is fetched. Fail-closed early-return for no-scope-non-admin. FR-49 semantics and the return order preserved; the two retry callers unchanged; 83 register/failure/audit tests still green.
- **Task 2 — the single-read-path gate.** New `apx/checks/read_path.py` with **three** checks: `tenant_reads_have_one_entry_point` (no tenant-content query — ORM `select/query/select_from/join/get` OR raw `text()`/`execute()` SQL — built outside `core/app/read/` + the store adapter), `scoped_read_puts_scope_in_the_query` (a `scopes`-taking function may not SELECT/`select_from` a scoped content table without a `.matter`/`MatterScope.scope`/id-equality predicate — the internal fetch-then-post-filter), and `corpus_read_takes_no_admin_bypass` (no `Piece`/`Chunk` read takes an `is_admin`/super-user flag — AD-12). Each fails closed, takes injectable roots, excludes `node_modules`/`migrations`/build tooling. Registered in `registry.py` + `manifest.py` + README (lockstep meta-checks green); the stale `no-post-filter-retrieval` "vacuous until 3.x" note corrected. The design isolates `register_all` and exempts all 9 authorise-then-read (Shape-B) methods, `resolve_chunk` (id guard-then-read), `read_audit` (per-tenant audit chain, AD-43, sliced to the authorised matter), and `search` (scope applied via `.join(MatterScope)` + a `conds` variable).
- **Task 3/4/5 — the adversarial suite** (`tests/security/test_out_of_scope_adversarial.py`): deterministic out-of-scope exclusion + denominator-within-scope (real SQLite round-trip); register out-of-scope exclusion; both-engines empty-scope; the admin matter-less carve-out with no scope (system sees nothing); the mutating revoke/grant suite (wall moves on the next query, old never leaks — scope re-resolved live via `store.identity`); the semantic scope pre-filter proven to precede the top-k (compiled SQL) + a Postgres-gated behavioural test that a NEARER out-of-scope chunk is excluded.
- **Reconciliation recorded** (module docstring): AD-14's literal "no ORM query outside `core/app/read/`" cannot be met over `adapters/` in this hexagonal build; the faithful realisation is `core/app/read/` + the store adapter's read modules, and a build failure elsewhere. The AD-33 per-action read-entry-point leg stays deferred (`deferred-action-registry`, FR-21).

### File List

- `apx/checks/read_path.py` (new) — the two AD-14 single-read-path structural checks.
- `apx/adapters/store_postgres/store.py` (modified) — `register_all` rewritten to a query pre-filter.
- `apx/checks/registry.py` (modified) — register the two checks.
- `apx/checks/manifest.py` (modified) — two manifest rows; corrected the stale no-post-filter note.
- `README.md` (modified) — two structural-property rows; corrected the stale note.
- `tests/checks/test_read_path.py` (new) — fires on planted violations, passes real tree, fails closed.
- `tests/security/__init__.py` (new) — the security test package.
- `tests/security/test_out_of_scope_adversarial.py` (new) — the Chinese-wall adversarial suite (AC3–AC6).

### Change Log

- 2026-07-30 — Story 3.3 implemented: `register_all` post-filter → query pre-filter; the AD-14 single-read-path gate; the adversarial out-of-scope suite over both engines + the register + the mutating revoke/grant suite + fail-closed no-scope. Status → review.
- 2026-07-30 — Adversarial 3-reviewer pass + fixes: **R2 approved** the `register_all` rewrite (behaviourally equivalent, 8 cases, no cross-tenant leak, no empty-`in_` warning). **R1** (self-completed; the background agent died) closed 3 gate false-negatives — the checks now catch `session.get(Model)`, raw `text()` SQL over content tables, and `select(Piece.id/matter)` column-enumeration (predicate-anchored, not statement-wide). **R3** findings fixed: `ocr_share`-within-scope now asserted (M1); a third check `corpus_read_takes_no_admin_bypass` added (M2); check 2 now requires `MatterScope.scope`, not a bare `.join(MatterScope)` (M3); the "both engines" empty-scope test exercises the semantic engine (L2); the tautological SQL-ordering assertion removed (L3); AC6 "system identity" wording made honest (L1). Final gate on the frozen artifact: ruff clean, **834 passed / 11 skipped**, **54/54 checks**, alembic head unchanged.

## Senior Developer Review (AI)

**Outcome:** Approved after fixes. Three parallel adversarial reviewers (distinct lenses; execution-verified; read-only).

- **Reviewer 2 — `register_all` correctness:** APPROVE, zero defects. Old-vs-new compared across 8 cases + orphan/resolved/cross-tenant/empty-scope adversarial shapes; behaviourally identical, tenant pinned both sides of the sub-query, sort preserved, no SA-2.0 empty-`in_` warning.
- **Reviewer 1 — the gate's teeth (self-completed):** 3 false-negatives found and fixed — `session.get(<ContentModel>)`, raw `text()`/`execute()` SQL naming a content table, and a `scopes`-taking read that SELECTs `Piece.id`/`Piece.matter` as a column while filtering tenant alone (check 2 now anchors on the `.where()`/`.join()` predicate, not the whole statement).
- **Reviewer 3 — adversarial-suite rigor + AC completeness:** mutation-confirmed the deterministic + register + mutating suites are NOT toys (they fail when the wall leaks). Findings fixed: M1 `ocr_share`-within-scope asserted; M2 `corpus_read_takes_no_admin_bypass` structural check added; M3 the `MatterScope` join-without-scope-filter exemption closed; L1/L2/L3 (honest AC6 wording, semantic empty-scope in the "both engines" test, tautological assertion removed). H1 (the gate was being hot-patched during the review) resolved by the final frozen re-gate above.
