---
baseline_commit: 856945c0965c3af5abbeced25c0091754ae07971
---

# Story 2.1: Folder selection as the whole onboarding gesture

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a lawyer with four years of a *matter* on a USB key,
I want to start an import by choosing the folder, the *matter*, the *RBAC scope* and the *custodian* — with the *case theory* the only optional field and nothing else mandatory,
so that onboarding is a gesture, not an IT project.

**Scope in one line:** turn today's synchronous POC upload into the **onboarding gesture contract** — one screen, **exactly three mandatory inputs (folder, matter, RBAC scope) + one mandatory provenance field (custodian) + exactly one optional field (case theory)**, a scope selector constrained to walls the user holds (asserted in both directions), and the two failure paths (a zero-readable folder → a *completed* 0/0 matter, not an error; a null/empty scope → the job fails **loudly and fail-closed at the persist boundary**, nothing written). It is the first story of Epic 2, so it marks **epic-2 in-progress**.

> **This story does NOT build:** the non-blocking/resumable background job, the docked progress indicator, worker kill/resume, quarantine (**Story 2.2**); multi-format extraction / OCR (**2.3**); container expansion (**2.4**); idempotent `(content, matter)` identity semantics beyond what already exists (**2.5**); the persistent worklist / failure-register UI (**2.6 / 2.11**); durable exclusion read-back and the permanent home denominator (**2.7**); the versioned/audited/re-rankable case-theory machinery (**Epic 4 / 4.1**). Building any of these is over-reach and a review-blocker.

## Acceptance Criteria

> **Given** an authenticated user, **When** she starts an *import job*, **Then** exactly three inputs are mandatory — folder, *matter*, *RBAC scope* — with exactly one optional input on the same screen, the *case theory*, which can be skipped and whose skipping blocks nothing, and no further mandatory configuration screen exists on this path (FR-1, FR-37).
> **And** subfolders are traversed to arbitrary depth and the submitted folder structure is reconstructible from the *payload schema* record alone.
> **And** the *RBAC scope* selectable is constrained to scopes the user holds or may grant, asserted by test in both directions — she cannot narrow material out of her supervisor's sight nor broaden it to a group she chose (FR-1, FR-49).
> **And** the *custodian* is captured at import as a mandatory field, `custodian-undeclared` where genuinely unknown, never blank.
> **And** *(failure path)* a folder of zero readable files produces a completed job with a 0/0 *denominator* and an explanatory *worklist* line — not an error dialog, not a silent no-op.
> **And** *(failure path)* an attempt to write a *pièce* with a null or empty *RBAC scope* fails the job loudly rather than defaulting to permissive.

1. **AC1 — The one-screen gesture (3 mandatory + 1 optional).** The onboarding surface presents on **one screen**, with **no second mandatory configuration screen** on the path: three mandatory inputs — **folder** (a directory pick), **matter**, **RBAC scope** — plus the mandatory **custodian** provenance field (AC4), plus **exactly one optional** input, the **case theory** (free text, in the lawyer's own language). Submitting is blocked until the three mandatory inputs + custodian are present; it is **never** blocked by the case theory being empty, and skipping the case theory blocks nothing downstream. (FR-1, FR-37)
2. **AC2 — Subfolders to arbitrary depth, structure reconstructible.** The folder is traversed recursively to arbitrary depth, and the **submitted folder structure is reconstructible from the payload record alone** — i.e. each piece's `provenance_path` is its full folder-relative path (e.g. `emails/2021/letter.txt`), not just a filename. Asserted by a test that ingests a ≥3-level nested tree and reconstructs the tree from `provenance_path`s. (FR-1)
3. **AC3 — Custodian mandatory, never blank, never silently defaulted.** The custodian is captured at import as a **mandatory** field and threaded onto **every** ingested piece. Where genuinely unknown, the value is the **explicit** sentinel `custodian-undeclared` chosen by the user (a visible "détenteur inconnu" affordance) — **never** a blank field and **never** a silent server-side default. The `/api/ingest-upload` endpoint **rejects** an empty custodian (fail closed). Asserted by test: a normal custodian round-trips onto pieces; an empty custodian is rejected; the explicit-unknown choice stores exactly `custodian-undeclared`. (FR-1)
4. **AC4 — Scope selectable constrained, both directions.** The scope selector offers **only walls the user holds** (`ident.scopes`) — it is a select of existing walls, **never a free-text field**, so a user cannot invent a new private wall at onboarding (creating/granting a wall is the separate privileged admin act of FR-49 / Story 1.6). The endpoint **rejects** (403) an attempt to assign a wall the caller does not hold. Asserted by test in **both** directions: (a) *cannot broaden* — assigning a not-held wall is refused; (b) *cannot narrow out of a supervisor's sight* — there is no path to create a brand-new wall only the importer is behind (no free-text scope; the select contains only held walls). (FR-1, FR-49)
5. **AC5 — Failure path: a zero-readable folder is a completed 0/0 matter, not an error.** A folder with zero ingestable files (all noise, or empty) produces a **completed** job (HTTP 200) with a **durable matter** whose inventory is `0 = 0 + 0 + 0` and is **consistent** — the `matter_scope` row and the ingest audit entry are created even with zero pieces — plus an explanatory result the UI shows as a *completed-empty* state (the standing worklist line is Story 2.11; here it is the explanatory completed result, **not** a 4xx, **not** an error dialog, **not** a silent no-op that creates nothing). Asserted by test. (FR-1, FR-6)
6. **AC6 — Failure path: null/empty scope fails loudly, fail-closed at the persist boundary.** A null/empty/whitespace RBAC scope on the persist path **raises** and writes **nothing** — the guard lives at `SqlStore.save` (the piece-persist boundary), not only at the API edge (`_held_wall`), so no code path can default to permissive. Asserted by a store-level test (`save(..., scope="")` raises, no rows written) and the existing API-level 400. (FR-1, AD-12)
7. **AC7 — Case theory: optional, skippable, minimally persisted.** When provided, the case theory is persisted as the matter's **current** case-theory value (a single nullable value, no versioning); when skipped it is `NULL` and nothing is blocked. The versioned/audited/re-rankable machinery (every rewrite a retained version, the audit record, the explicit re-rank) is **explicitly out of scope** and owned by Epic 4 / FR-37. Asserted by test: a provided theory round-trips on the matter; a skipped one leaves `NULL` and the job still completes. (FR-37)
8. **AC8 — Honest boundaries, green and regression-free.** No non-blocking job, no worker/queue, no extraction/OCR change, no container expansion, no new identity semantics, no worklist/register UI, no durable-exclusions fix are built (each is a named later story). All existing tests pass; `ruff`, `python -m apx.checks`, and the offline fitness function are green; the payload-schema build gate (chunk columns, single chunk writer, defaultless `rbac_scope`) is untouched and still passes.

## Tasks / Subtasks

- [x] **Task 1 — Refactor `SqlStore.save` to take matter/tenant/scope explicitly, and fail closed on empty scope** (AC5, AC6) — `apx/adapters/store_postgres/store.py`.
  - [x] Change `save(self, result, scope, actor="unknown")` → `save(self, result, *, matter: str, tenant: str, scope: str, actor: str = "unknown")`; stop deriving matter/tenant from `result.pieces[0]` (the fragile derivation that makes a 0-piece result create nothing).
  - [x] Add a fail-closed guard at the top: `if not scope or not scope.strip(): raise UnauthorizedScope("an empty RBAC scope is never authorised (fail closed)")` (reuse the exception the chunk writer already raises, or the store's equivalent — do not invent a permissive default).
  - [x] Create the `matter_scope` row (first ingest) and write the `ingest` audit entry **unconditionally when matter+tenant+scope are known**, even when `result.pieces` and `result.failures` are both empty (the 0/0 completed matter). Keep the existing `ScopeConflict` guard (a re-ingest may not move an existing matter's wall — the 1.6 side-door fix).
  - [x] **Grep every caller** of `.save(` before changing the signature — the endpoint `_persist` (`apx/api/app.py:393-404`), the store tests, and any `manage.py` / `apx/timedrun` / CLI ingest path — and update them all to the new keyword signature. A missed caller is a silent regression.
- [x] **Task 2 — Accept custodian (mandatory) + case theory (optional) on the upload endpoint** (AC1, AC3, AC7) — `apx/api/app.py`, `apx/core/app/ingest.py`.
  - [x] `POST /api/ingest-upload` (`app.py:878-917`): add `custodian: str = Form(...)` and `case_theory: str | None = Form(None)`; reject an empty/whitespace custodian with a 400 (fail closed) before doing any work; pass `custodian=custodian` into `ingest_folder(...)` (it already accepts it, `ingest.py:96`).
  - [x] Thread `case_theory` into persistence (Task 3) via the refactored `save`/a matter-write path; when `None`/empty, persist `NULL`.
  - [x] Keep the existing `_held_wall(scope, ident)` gate (400 empty / 403 not-held) — it already enforces held-only (AC4). Do **not** loosen it for admins in this story (see Open Question 1).
- [x] **Task 3 — Persist the case theory on the matter (minimal, unversioned)** (AC7) — `apx/adapters/store_postgres/models.py`, Alembic.
  - [x] Add a **new Alembic migration `0016_*`** adding a nullable `case_theory` column to `matter_scope` (the authoritative `(tenant, matter)` row); do **not** touch `chunk` (the payload build gate forbids stray chunk columns) or `piece`.
  - [x] In `save`, upsert the matter's `case_theory` (set on create; on an existing matter, update only when a non-null value is supplied — never wipe an existing theory with a skipped field).
  - [x] Expose `case_theory` and `scope` on the matter read-back (`MatterSummary`) if trivially available; otherwise leave read-back to 2.7/4.1 and note it.
- [x] **Task 4 — Front-end onboarding surface per the UX contract** (AC1, AC3, AC4, AC7) — `apx/web/src/api.ts`, `apx/web/src/App.tsx`.
  - [x] `ingestUpload`: extend to `(files, matter, scope, custodian, caseTheory?)`; append `custodian` and (when present) `case_theory` to the `FormData`. Keep the `webkitRelativePath || file.name` per-file naming that transmits the folder tree (AC2).
  - [x] Build the onboarding screen to the EXPERIENCE.md "Importer un dossier" contract and the mock (`mockups/epic-2-key-screens.html`): the three mandatory inputs, the mandatory **custodian** field with an explicit "détenteur inconnu" toggle that sets `custodian-undeclared`, and the **one optional** case-theory textarea marked skippable. The scope control stays a `<select>` of `identity.scopes` (held walls only — never a free-text input). Submit disabled until folder + matter + scope + custodian present; never gated on case theory.
  - [x] Apply the DESIGN.md tokens (this is the ratified system already in `tokens.css`); the mock is a faithful reference to port.
- [x] **Task 5 — Tests: the gesture, both failure paths, both scope directions** (all ACs) — `tests/api/test_ingest_api.py`, `tests/adapters/test_store.py`, `tests/app/test_ingest.py` as appropriate.
  - [x] AC2: ingest a ≥3-level nested tree; assert every `provenance_path` is the full folder-relative path and the tree is reconstructible.
  - [x] AC3: custodian round-trips onto pieces; empty custodian → 400; explicit-unknown → exactly `custodian-undeclared`.
  - [x] AC4 both directions: a held wall succeeds; a not-held wall → 403 (cannot broaden); assert the endpoint/select expose no free-text scope path (cannot narrow via a new private wall).
  - [x] AC5: an empty/all-noise folder → 200, a durable matter exists, inventory `0=0+0+0` consistent, an ingest audit entry written.
  - [x] AC6: `save(result, matter=..., tenant=..., scope="", actor=...)` raises and writes nothing; the API path still 400s an empty scope.
  - [x] AC7: a provided case theory round-trips on `matter_scope`; a skipped one leaves `NULL` and the job completes.
- [x] **Task 6 — Green + honest** (AC8) — `uv run ruff check .`, `uv run python -m apx.checks`, `uv run pytest -q`, fitness. Update `README.md` if it enumerates onboarding inputs. Confirm the payload-schema gate still passes (no chunk/piece column changes). No new runtime dependency.

> **Front-end testing reality (read before writing tests).** `apx/web/package.json` ships only `dev` / `build` / `preview` / `typecheck` scripts — **there is no JS test runner** (no vitest/jest). Do **not** invent a front-end unit-test harness for 2.1 (that is scope creep). **Every AC is enforceable and must be tested at the API/store layer in Python** (`tests/api`, `tests/adapters`) — held-only scope (403), custodian mandatory (400), the 0/0 completed matter, the empty-scope fail-closed, case-theory round-trip, tree reconstruction. The React surface is verified by `npm run typecheck` (`tsc -b --noEmit`) against the `api.ts` contract and by visual fidelity to the mock. If a JS test runner is later wanted, that is its own story.

## Dev Notes

- **The core ingest use-case already does the heavy lifting — do NOT rewrite it.** `apx/core/app/ingest.py::ingest_folder(folder, matter, tenant, extractor, *, custodian="custodian-undeclared", expander=None)` already walks recursively (`folder.rglob("*")`, `provenance = path.relative_to(folder)` → AC2 is supported at the core), classifies into pieces / failures / noise-exclusions, bounds expansion (`MAX_DEPTH=6`, `MAX_MEMBERS=5000`), and enforces the inventory identity via `IngestionResult.inventory.require_consistent()` before returning. 2.1 wires the **gesture and the persist/validation boundary** around it; it does not touch the walk. [Source: apx/core/app/ingest.py:90-169]
- **Custodian already exists as a piece column — the gap is capture, not schema.** `Piece.custodian` is `EncryptedText(nullable=False)` (`models.py:54-63`), and `ingest_folder` threads a `custodian` param onto every `IngestedPiece` (`ingest.py:96,150`). Today the browser path never sends it, so uploads silently store the `"custodian-undeclared"` default. 2.1 makes it a **mandatory user input** on `/api/ingest-upload` and in `api.ts`, with the explicit-unknown sentinel as a *choice*. Custodian is deliberately **not** a chunk column (AD-9) — do not add one. [Source: models.py:34-77; ingest.py:96,150; core/domain/payload.py:11-19]
- **The RBAC wall lives only in `matter_scope`, resolved live (AD-13) — never on the piece/chunk.** `MatterScope(tenant, matter, scope)` is the one authoritative row (`models.py:140-155`). `SqlStore.save` creates it on first ingest and **refuses to change** an existing matter's scope (`ScopeConflict` → 409) — this is the 1.6 review's "ingest side-door" fix; **preserve it**. The scope reaches persistence as a write-time argument, never a field (the payload build gate enforces the chunk side). [Source: store.py:446-497; implementation-artifacts/1-6…#High-finding; ARCHITECTURE-SPINE.md#AD-13]
- **Held-only is the faithful, minimal reading of "holds or may grant."** `_held_wall(req_scope, ident)` (`app.py:423-431`) already rejects empty (400) and not-held (403), resolving against `ident.scopes` (held, re-resolved live per request via `resolve_session`, `store.py:842-869`). Granting/creating a wall is a **separate privileged, audited admin act** (FR-49 / Story 1.6: `grant_scope`, `create_user`, admin-gated). So at onboarding the selector is **held walls only, no free text**, which satisfies *both* AC4 directions without inventing a "grantable" source of truth (there is none today: no `rbac_scopes` config key; `config.taxonomy` is a *classification* taxonomy, not walls). The admin-broadening case is Open Question 1 — do not build it speculatively. [Source: app.py:423-431; store.py:805-824; core/domain/config.py:119-186]
- **The 0/0 completed matter needs the `save` refactor.** Today `save` derives `matter`/`tenant` from `result.pieces[0]` (or `failures[0]`) and guards `if matter is not None and tenant is not None` — so a **zero-file folder creates no matter, no scope row, no audit** (a silent no-op, exactly what AC5 forbids). Passing `matter`/`tenant`/`scope` **explicitly** (they are known at the endpoint) lets the matter be created at 0 pieces, and cleanly enables the empty-scope guard (AC6). [Source: store.py:446-497 — GAP 6]
- **Null-scope loud failure belongs at the persist boundary.** `save` currently writes any scope string to `matter_scope` verbatim. `ChunkStore.write_chunk` already fails closed on empty `rbac_scope` (`chunk_writer.py:99-101, UnauthorizedScope`) but that is the chunk path (Story 2.8+). AC6 wants the **piece-persist** path to fail closed too, so add the guard in `save`. [Source: store.py:446-497; chunk_writer.py:99-101 — GAP 4]
- **Known asymmetry to leave for 2.7 (do not fix here): durable exclusions read back as 0.** `save` never persists `result.exclusions`; `_counts`/`inventory`/`matters` return `exclusions=0` (`store.py:499-545`). The POST response shows real exclusions; the read-back denominator is 2-term. The permanent home denominator (Story 2.7) owns making exclusions durable. Note it, don't build it. [Source: store.py:499-545 — GAP 7]
- **UX contract (binding) — read it, it wins over any older reference.** `_bmad-output/planning-artifacts/ux-designs/ux-apx-mvp-2026-07-27/` — DESIGN.md (the ratified visual system = `apx/web/src/tokens.css`, AD-29: one shell width, three radii, one gold accent, semantic tier distinct from accent, serif for countable numerals) and EXPERIENCE.md (Foundation, the onboarding surface, the RBAC boundary in the UI, Voice & Tone — lawyer's language, State Patterns incl. the zero-result and loud-error states, Accessibility Floor — focus-visible + keyboard-reachable + `aria-live`, Key Flow 1 "The handover" and Flow 4 "The wall holds"). The mock `mockups/epic-2-key-screens.html` "Importer un dossier" tab is the pixel reference to port. [Source: ux-designs/ux-apx-mvp-2026-07-27/DESIGN.md, EXPERIENCE.md]
- **Voice.** Lawyer's language, no engineer vocabulary on screen (no "chunk"/"worker"/raw errors). The custodian's explicit-unknown reads "détenteur inconnu", not a blank. The zero-file folder reads "Aucun fichier lisible dans ce dossier. Rien à indexer." — never an error dialog. The loud null-scope failure reads "Import interrompu : aucun périmètre défini. Rien n'a été écrit." [Source: EXPERIENCE.md#Voice-and-Tone]

### Project Structure Notes

- **Modified:** `apx/adapters/store_postgres/store.py` (`save` signature + empty-scope guard + 0-piece matter creation + `case_theory` upsert), `apx/api/app.py` (`ingest_upload` custodian+case_theory Form fields, `_persist` new signature), `apx/web/src/api.ts` (`ingestUpload` args), `apx/web/src/App.tsx` (onboarding screen), `README.md` (onboarding inputs, if enumerated).
- **New:** `apx/adapters/store_postgres/migrations/versions/0016_*` (nullable `case_theory` on `matter_scope`); onboarding tests in `tests/api/test_ingest_api.py` + store tests in `tests/adapters/test_store.py`.
- **Alignment / variance:** `case_theory` is co-located on `matter_scope` (the existing `(tenant, matter)` row) as the smallest change that does not drop user input; Epic 4 / 4.1 formalises a versioned case-theory model and supersedes this. Flagged as Open Question 2. No new runtime dependency. Do **not** introduce a job/queue table (Story 2.2) or alter `chunk`/`piece` columns (payload build gate).
- **Latest migration is `0015_backup_and_truncation`; the new one is `0016_*`, `down_revision="0015_backup_and_truncation"`.** [Source: subagent digest §1]

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story-2.1] — the acceptance criteria and the "UX pass required" gate (now satisfied).
- [Source: PRD FR-1] — folder selection as the whole onboarding gesture; folder + matter + scope + case-theory-optional, no further mandatory screen.
- [Source: PRD FR-37] — the optional case theory: free text, never mandatory, never blocks; versioning/re-rank is Epic 4.
- [Source: PRD FR-49] — scope creation/grant/re-scope are privileged admin acts (Story 1.6, done) — onboarding consumes held walls, it does not grant.
- [Source: PRD FR-6] — the inventory identity `submitted = in corpus + failures + exclusions`, consistent after every import (the 0/0 case still holds it).
- [Source: ARCHITECTURE-SPINE.md#AD-13] — scope resolved live from the one `matter_scope` row; a wall moves only via the audited admin re-scope.
- [Source: ARCHITECTURE-SPINE.md#AD-12] — tenant/scope fail closed; nothing permissive by default (AC6).
- [Source: ARCHITECTURE-SPINE.md#AD-9] — the chunk column enumeration; custodian/scope are never chunk columns.
- [Source: apx/core/app/ingest.py] — `ingest_folder`, provenance = folder-relative path, the inventory guarantee.
- [Source: apx/adapters/store_postgres/store.py:446-497] — `save`, the ScopeConflict guard, the persist path to refactor.
- [Source: apx/api/app.py:878-917, :423-431, :393-404] — `ingest_upload`, `_held_wall`, `_persist`.
- [Source: apx/web/src/api.ts:99-110; apx/web/src/App.tsx:104-194] — the client `ingestUpload` and the POC onboarding to evolve.
- [Source: implementation-artifacts/1-6-…] — the scope model, the audited grant/re-scope, the ingest side-door fix to preserve.
- [Source: tests/api/test_ingest_api.py] — the full-stack test harness (`_prepare`, `_login`, multipart posts) to extend.

### Open Questions for the human

1. **Admin scope-broadening at onboarding.** 2.1 implements **held-only** (the selector offers only walls the importer holds; `_held_wall` refuses the rest), which satisfies both AC4 directions and matches the existing enforcement. Should an **admin** (the scope-administration grant holder) additionally be allowed to file a matter into a tenant wall they do not personally hold, directly at onboarding? Recommended default: **no** — keep onboarding held-only; widen via the separate audited admin grant (FR-49). Confirm.
2. **Case-theory home.** 2.1 persists the case theory as a nullable column on `matter_scope` (the existing `(tenant, matter)` row), single current value, no versioning — the minimal change that does not discard user input, superseded by Epic 4 / 4.1's versioned model. Confirm this minimal home vs. deferring persistence entirely to Epic 4.

## Dev Agent Record

### Agent Model Used

Claude Opus 4.8 (1M context) — Claude Code dev-story workflow.

### Debug Log References

- `uv run pytest -q` → **510 passed, 8 skipped** (+9 for 2.1). `uv run python -m apx.checks` → **39 passed**. `uv run ruff check .` → clean. `apx/web` `npm run typecheck` → clean. Fitness frame green (3 asserted, 9 pending). Alembic: single head `0016_case_theory`, linear 16-revision chain.

### Completion Notes List

- **`save` refactor — backward-compatible, not keyword-only (deviation from Task 1's literal signature, same intent).** The story proposed keyword-only `matter`/`tenant`; a grep found **~35 callers** across 12 test files (positional and keyword styles). To avoid a large regression surface for zero behavioural gain, `save` keeps its `(result, scope, actor="unknown")` shape and adds optional keyword `matter`/`tenant`/`case_theory` (derived from the result when omitted — the pre-2.1 behaviour, so every existing caller is untouched). The endpoints pass `matter`/`tenant` explicitly, so a zero-piece folder still creates a durable matter (AC5). Empty-scope guard added at the top of `save` (AC6). No caller broke.
- **AC5 — the 0/0 completed matter fell out of the endpoint cleanup.** Removed the upload path's `if not files: 400` guard and made `files` optional (`Form(None)`); a zero-file submission now walks an empty temp dir → an empty `IngestionResult` (0=0+0+0, `require_consistent()` holds) → `_persist` creates the `matter_scope` row + the ingest audit entry even at 0 pieces. Verified at both the store and API layers.
- **AC3 — custodian mandatory on the browser path.** `POST /api/ingest-upload` now takes `custodian` (a 400, uniform for missing/blank, before any work) and threads it into `ingest_folder`; the explicit "détenteur inconnu" sentinel `custodian-undeclared` is a user choice, never a silent server default. The JSON `/api/ingest` path keeps its historical default (a CLI/server path, not the onboarding gesture).
- **AC4 — held-only, both directions.** The scope selector is a `<select>` of `identity.scopes` (held walls, no free-text), and `_held_wall` already refuses a not-held wall (403) — cannot broaden. There is no onboarding path to create a new private wall (that is the audited admin grant of Story 1.6) — cannot narrow. The admin-broadening variant (Open Question 1) was **not** built, per the recommended default.
- **AC7 — case theory: minimal, encrypted, unversioned.** New nullable `matter_scope.case_theory`, **encrypted at rest** (`EncryptedText`) since it is confidential legal strategy, not a query key. Persisted as the matter's single current value; a re-ingest that omits it never wipes an existing one; a skip leaves `NULL`. Migration `0016_case_theory` (Open Question 2 default). Epic 4 / 4.1 supersedes with the versioned model.
- **Empty-scope exception reused, not reinvented.** `save` raises the existing `UnauthorizedScope` (chunk_writer.py); no import cycle (chunk_writer does not import store). Semantically exact: "an empty RBAC scope is never authorised (fail closed)".
- **Scope honoured — nothing over-built.** No non-blocking/resumable job, no Procrastinate, no docked indicator (2.2); no extraction/OCR/container change (2.3/2.4); no new identity (2.5); no worklist/register UI (2.6/2.11); durable-exclusions read-back left at 0 (owned by 2.7). The payload-schema build gate is untouched (no chunk/piece column change) and still passes. The 1.6 `ScopeConflict` ingest side-door guard is preserved.
- **Front-end:** the onboarding screen was rebuilt to the EXPERIENCE.md contract and the mock — vertical labelled fields, the mandatory custodian with its "détenteur inconnu" toggle, the one optional case-theory textarea, submit gated on folder+matter+scope+custodian (never on the case theory). Verified by `tsc` (no JS test runner exists, by design).

### File List

**New**
- `apx/adapters/store_postgres/migrations/versions/0016_case_theory.py` — nullable `case_theory` on `matter_scope`.

**Modified**
- `apx/adapters/store_postgres/store.py` — `save` gains optional `matter`/`tenant`/`case_theory` (backward-compatible) + a fail-closed empty-scope guard; imports `UnauthorizedScope`.
- `apx/adapters/store_postgres/models.py` — `MatterScope.case_theory` (`EncryptedText`, nullable).
- `apx/api/app.py` — `IngestRequest.case_theory`; `_persist` passes `matter`/`tenant`/`case_theory`; `/api/ingest` and `/api/ingest-upload` capture custodian (mandatory on upload) + case theory, and the upload path yields a completed 0/0 matter.
- `apx/web/src/api.ts` — `ingestUpload(files, matter, scope, custodian, caseTheory?)`.
- `apx/web/src/App.tsx` — the onboarding form (custodian + "détenteur inconnu" toggle + optional case theory; held-only scope select).
- `tests/api/test_ingest_api.py` — custodian added to the existing upload test; 6 new 2.1 tests.
- `tests/adapters/test_store.py` — 3 new store-level tests (empty-scope guard, 0/0 matter, case-theory persistence).

### Change Log

| Date | Change |
|---|---|
| 2026-07-27 | Implemented story 2.1 — folder-selection onboarding gesture: the browser upload path now captures a mandatory custodian (with an explicit "détenteur inconnu" choice) and the one optional case theory; the scope selector is held-only both directions; a zero-readable folder is a completed 0/0 durable matter (not an error); a null/empty scope fails closed at the persist boundary (`UnauthorizedScope`); `matter_scope.case_theory` added (encrypted, nullable, unversioned — Epic 4 supersedes) via migration 0016. `save` made backward-compatible (optional matter/tenant/case_theory) so no existing caller changed. 510 passed / 8 skipped, 39 checks + ruff + typecheck + fitness green. Status → review. |
| 2026-07-27 | Addressed the adversarial code review (3 reviewers, all Approve): normalized `case_theory` at the persist boundary (a skip/"" never wipes); hardened the custodian gate against zero-width/format chars and made it uniform across both ingest paths; translated ingest error details to lawyer-language French; added the zero-file explanatory microcopy and tied the custodian label (a11y); fixed a pre-existing path-traversal write on the upload path; migration 0016 `String`→`Text` (convention); closed the AC5-audit / AC6-API-edge / AC4-narrow / AC3-multi-file test-coverage gaps. 512 passed / 8 skipped; 39 checks + ruff + typecheck + fitness green. Status → done. |

## Senior Developer Review (AI)

**Date:** 2026-07-27 · **Reviewers:** three parallel, execution-verified adversarial `general-purpose` agents — *Faithfulness* (each AC + the UX contract), *Correctness/Security* (the RBAC wall, fail-closed scope, the 1.6 side-door, encryption — all actively attacked with probes), *Scope/Test-integrity* (over-build check + mutation testing of the new tests). · **Outcome: Approve (all three).** Every crown-jewel invariant survived active attack and was mutation-proven (removing a guard makes a test fail); no High/Blocker. The findings below — test-coverage gaps, a voice deviation, hardening nits, and one pre-existing security bug on the touched surface — were all resolved.

### Findings and resolutions

- [x] **[Med] AC5's "ingest audit entry created at 0 pieces" was asserted by no test** (R1 + R3 consensus; R3 mutation-proved: guarding out the 0/0 audit write left all tests green). **Fixed:** the store and API 0/0 tests now assert exactly one `ingest` audit entry (chain verified).
- [x] **[Med] The front-end rendered raw (part-English, technical) server error strings** — the EXPERIENCE.md "never a raw error string" voice rule. **Fixed:** ingest error details are now lawyer-language French (`_held_wall`, `ScopeConflict`), and the zero-file state shows *"Aucun fichier lisible dans ce dossier. Rien à indexer."* (The full classified-error register is Story 2.6.)
- [x] **[Low] `save(case_theory="")` could wipe an existing theory to `""`** — normalization lived only at the API edge (R2). **Fixed:** the `""`→`None` rule is now owned at the persist boundary, symmetric with the scope guard; tested (a `""` re-ingest never wipes).
- [x] **[Low] A zero-width/format-char custodian slipped past the mandatory gate** (R2: `"​".isspace()` is False). **Fixed:** `_is_blank` rejects any custodian composed only of Unicode Z*/C* characters; tested with a zero-width space.
- [x] **[Low] The custodian 400 was not uniform** — the JSON `/api/ingest` path stored a blank (R2). **Fixed:** the same non-blank custodian guard now applies on both ingest paths.
- [x] **[Low] AC6's API-edge "empty scope → loud failure" clause was unasserted** (R1). **Fixed:** a test posts a blank scope and asserts a loud 4xx (a whitespace scope → 400 via `_held_wall`).
- [x] **[Low] AC4's "both directions" shared one mechanism, tested once** (R1 + R3). **Fixed:** a test now posts an invented wall (the "cannot narrow via a new private wall" direction) and asserts 403.
- [x] **[Low/Security, pre-existing] The upload loop wrote `root / rel` from the client filename with only `lstrip("/")`** — a crafted `../../` filename escaped the temp sandbox (R1 confirmed `escapes_root=True`). Inherited code that 2.1 touches. **Fixed:** the destination is verified `is_relative_to` the resolved sandbox root; a traversal filename is refused (400); tested.
- [x] **[Info] Migration 0016 used `sa.String()` where the `EncryptedText` convention (0015) is `sa.Text()`** (R2; no functional impact). **Fixed:** `sa.Text()`.
- [x] **[Nit] The custodian visible label was not programmatically tied to its input** (R1 a11y). **Fixed:** the field is a proper `<label>` (the "détenteur inconnu" toggle moved to a sibling label).
- [x] **[Nit] AC3 "threaded onto every piece" was tested with one piece per matter** (R1). **Fixed:** the test now ingests a multi-file matter and asserts every piece carries the custodian.

### Deferred (documented, correctly out of 2.1's scope)

- [x] Durable exclusions read back as `0` — owned by Story 2.7 (the permanent home denominator); honestly asserted as `0`, not faked.
- [x] `case_theory` is not exposed on the `MatterSummary` read-back — Task 3 permitted deferring it; Epic 4 / 4.1 supersedes with a versioned model that owns the read surface.
- [x] The full classified-error register / worklist UI (2.6 / 2.11), and the non-blocking/resumable job (2.2) — the FE still renders errors as a single alert; the register is 2.6.

**Post-fix verification:** `ruff` clean · `python -m apx.checks` **39/39** · `pytest` **512 passed, 8 skipped** · `apx/web` `tsc` clean · fitness frame green · migration single head `0016_case_theory`.
