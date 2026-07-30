---
baseline_commit: 055e219
---

# Story 3.4: Every result set declares its truth status

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a lawyer,
I want finding and proving to be visibly and permanently distinct, carried by the data,
so that the distinction survives into an export a court reads without the system.

## Scope note — FULL-STACK, polished (Julian's ratified cut): the truth status made real and enforced everywhere a result set is surfaced

The truth-status **data contract exists** (Story 3.1 `SuggestiveResultSet`, 3.2 `ExhaustiveResultSet` — `truth_status` a constant per engine, `init=False`, frozen; gated by `truth_status_is_constant_per_engine` + `exhaustive_engine_takes_no_limit`). But **it is surfaced nowhere**: the only search endpoint `/api/search` is the bounded `LIKE` **preview** (`store.search`), falsely docstringed *"Deterministic exhaustive search"*, carrying **no** `truth_status`; the two real engines have **zero** API call sites; the React `CorpusSearch` renders a flat hit list under the false prose *"Déterministe et exhaustif"*; there is **no** search-result export; and a **query is not audited**. This story makes FR-15 real, end to end, and **enforced by a new gate** — per the ratified **full-stack, polished** cut, following the Epic-3 UX contract.

**What this story builds (CI-verifiable where the stack allows):**

- **Two distinct API endpoints, each serialising its truth status, never combined** — `/api/search/suggestive` composes `_embedder()` + `store.search_semantic` → `search_semantic` → a `SuggestiveOut` carrying `truth_status`, `k`, `similarity_threshold`, the non-completeness `wording`, and the results; `/api/search/exhaustive` composes `store` → `search_exhaustive` → an `ExhaustiveOut` carrying `truth_status`, the **scoped denominator** (AD-38 six-field `Inventory`), `ocr_share`, `below_quality_share`, `register_hits` (separate, AD-21), `normalization`, and the results. Two endpoints, two response models — the "never combined" guarantee is structural. The mislabeled `/api/search` prose is **corrected** (an honest "bounded preview", or removed once the UI moves off it).
- **The query is an audited act** (AD-14: every read is recorded with its scope) — each search writes one `_append_audit` entry naming the **term**, the **engine (truth status)**, the **scope**, and — for exhaustive — the **denominator** at that moment, on the tenant chain (`matter=None`, a scope-wide read).
- **A search-result export carrying the truth status** (the distinction **survives** a court-readable document) — a suggestive export whose head carries the **non-completeness** wording; an exhaustive export whose head carries the **scoped denominator** + the four AD-42 qualifications + the presence/absence claim. Data-first (the export payload + a print-ready client view), one `export-search` audit entry (mirroring `export_register`).
- **A NEW structural gate** — today only *construction* is gated; this adds *serialisation*: **a search response / export model carries its truth status**, and **no response model merges the two engines**. Registered + manifest + README, in lockstep.
- **The redesigned React search screen** (per the mockup) — one field + an **explicit mode** (Suggestions / Preuve), two **distinctly-framed** result panels (`≈ SUGGESTIF` dashed-open / `= EXHAUSTIF` solid-closed), never combined; the suggestive **"les N plus proches"** wording + proximity; the exhaustive **denominator** + the **absence-statement seal** with the four qualifications; **register-hits shown separately**; the moving-population **refusal**; a **print-ready export**. On the design tokens (`tokens.css` extended with the Epic-3 vocabulary from `DESIGN.md`). Verified by `tsc -b` + the backend serialisation gate (there is **no** frontend test harness — AD-29 ships no Node runtime; this story does not add one).

**What is deferred (honestly — carried as truthful zeros/absence, not faked):**
- **`below_quality_share`** stays `0.0` and **`register_hits`** stays `[]` — the store already carries them honestly (there is no OCR-quality signal, and register name-match search is not built). The surface renders them as *absent / "—"*, never a fabricated number; the *seal wording* accommodates zero qualifications.
- **The AD-33 action-registry assertion** (AD-42's "asserted over the action registry, which names the read entry point per action") stays **deferred** (`deferred-action-registry`, FR-21) — the actions do not exist as a registry yet; this story's gate asserts serialisation at the response/export type, the enforceable half.
- **The semantic behavioural test is Postgres-gated** (the embedder + halfvec `<=>` are pg-only) — the suggestive endpoint's shape/serialisation is tested with a fake embedder + reader; its end-to-end run is skipped without a DB, as in 3.1/3.3.
- **The pièce viewer (Story 3.5)** — a result row's *open-at-passage* target is stubbed to the existing provenance affordance; the rendered viewer is 3.5.

## Acceptance Criteria

1. **Every result set declares its truth status — in the interface, in every export, and in the audit record — the two statuses visually and verbally distinct, surviving export (FR-15).** Each engine has its own API endpoint returning a response that **serialises `truth_status`** (suggestive: `k` + `similarity_threshold` + the non-completeness `wording`; exhaustive: the scoped `denominator` + `ocr_share` + `below_quality_share` + `register_hits` + `normalization`). Running either search writes **one audit entry** carrying the term, the engine (truth status), the scope, and (exhaustive) the denominator. The React screen renders the truth-status badge (`≈ SUGGESTIF` / `= EXHAUSTIF`) on every result set, visually (glyph + frame + tone) and verbally (the word) distinct. *(tests: the two endpoints serialise `truth_status` and their engine-specific fields; the query is audited with its truth status + scope; `tsc -b` compiles the badge/rendering; the new gate is green.)*

2. **No interface element combines results from both engines into one undifferentiated list (FR-15).** The two engines are two distinct endpoints with two distinct response models; the React screen renders two **separately-framed** panels (never interleaved), reached by an explicit mode; and a **structural check** asserts no response/export model carries results from both engines (no union type, no field mixing `SemanticResult` and `DeterministicResult`). *(tests: the gate fires on a fixture response model merging both engines; passes the real tree; the UI renders one framed panel per engine.)*

3. **An exported suggestive set carries wording that cannot be read as completeness; an exported exhaustive set carries its denominator (FR-15, AD-38, AD-42).** The search-result export carries the truth status on its face: a **suggestive** export head says *"SUGGESTIONS — liste non exhaustive, classée par proximité ; ne constitue pas une preuve d'absence"*; an **exhaustive** export head carries the **scoped denominator** + the four AD-42 qualifications + the presence/absence claim (the FR-23 banned phrasing barred). The distinction is visible on a document read **without the system**. *(tests: the exhaustive export payload carries the denominator + qualifications and the absence/presence claim; the suggestive export carries the non-completeness wording and no completeness total; an `export-search` audit entry is written; the gate asserts the export model serialises its truth status.)*

## Tasks / Subtasks

- [x] **Task 1 — The two engine endpoints, each serialising its truth status (AC: 1, 2).**
  - [x] `apx/api/app.py`: add `GET /api/search/exhaustive` (q, ident) composing `store` → `search_exhaustive(tenant, scopes, query, reader=store)`, returning a new `ExhaustiveOut` (Pydantic) serialising `truth_status` ("exhaustive"), `denominator` (a `DenominatorOut` over the six-field `Inventory`), `ocr_share`, `below_quality_share`, `register_hits` (a `RegisterHitOut` list — separate), `normalization`, and `results` (`DeterministicResultOut`: matter, piece_id, snippet). Catch `MovingPopulation` → a typed 409/refusal payload naming the job (never a partial set).
  - [x] Add `GET /api/search/suggestive` composing `_embedder()` + `store` → `search_semantic(...)`, returning `SuggestiveOut` serialising `truth_status` ("suggestive"), `k`, `similarity_threshold`, `wording` (the domain `@property`), and `results` (`SemanticResultOut`: piece_id, chunk_id, similarity). Empty scope → fail-closed empty set (the engine already short-circuits).
  - [x] Keep `search(tenant, scopes, query)` shape (AD-14 pre-filter — the live `no_post_filter_in_retrieval` gate forbids a `(results, scope)` signature). **Correct** the mislabeled `/api/search` docstring to an honest "bounded preview" (no truth-status claim), or remove it once the UI is off it.
  - [x] Tests (`tests/api/…`): the exhaustive endpoint (real, SQLite) serialises `truth_status` + the six-field denominator + `ocr_share` + `normalization`; a moving population 409s naming the job; empty scope → empty. The suggestive endpoint's shape is tested with a fake embedder + fake reader (its behavioural run is pg-gated).

- [x] **Task 2 — The query is an audited act (AC: 1).**
  - [x] A store method (or the endpoint) writes **one** `_append_audit(session, tenant, matter=None, actor, "search", detail, now)` per query, `detail` naming the term, the engine (truth status), the scope, and — exhaustive — the denominator. Scope-wide read → the tenant chain (`matter=None`), mirroring scope grants. One entry per query (not per hit).
  - [x] Test: running each engine writes exactly one `search` audit entry carrying the truth status + scope; the exhaustive one carries the denominator.

- [x] **Task 3 — The search-result export carrying the truth status (AC: 3).**
  - [x] A store/endpoint export (mirror `export_register` + its one `export-register` audit entry): `GET /api/search/exhaustive/export` and `/api/search/suggestive/export` (or one export taking the engine) returning an export payload whose **head carries the truth status**: suggestive → the non-completeness wording; exhaustive → the scoped denominator + the four qualifications + the presence/absence claim. Writes one `export-search` audit entry.
  - [x] The client renders a **print-ready** view (print CSS) so the exported page is court-readable without the system.
  - [x] Tests: the exhaustive export payload carries the denominator + qualifications + the claim; the suggestive export carries the non-completeness wording and no completeness total; one `export-search` audit entry is written.

- [x] **Task 4 — The serialisation gate (AC: 1, 2, 3).**
  - [x] New check(s) (a new `apx/checks/…` module, e.g. `truth_status_surface.py`): **a result-set response/export model serialises its truth status** — any Pydantic (or serialised) model that carries retrieval results (`SemanticResult`/`DeterministicResult` shapes, or a `hits`/`results` field fed by an engine) must also carry a `truth_status` field; and **no response/export model merges both engines** (a single model naming both `SemanticResult`-ish and `DeterministicResult`-ish fields, or a union of the two result sets, fails). Fail-closed, injectable roots, house pattern.
  - [x] Register in `registry.py` + `manifest.py` + README (lockstep meta-checks green); fixtures that fire on a results-carrying model without `truth_status` and on a merged model; passes the real tree.

- [x] **Task 5 — The redesigned React search screen (AC: 1, 2, 3) — per the Epic-3 UX contract.**
  - [x] `apx/web/src/tokens.css`: add the Epic-3 vocabulary from `DESIGN.md` (`truth-status-badge` ≈/=, the suggestive dashed-open frame, the exhaustive solid frame, the `absence-statement` seal kept/review, the `proximity-indicator`). No new colour; reuse the palette.
  - [x] `apx/web/src/api.ts`: typed `SuggestiveResult` / `ExhaustiveResult` responses carrying `truth_status` + each engine's fields; two calls (`searchSuggestive`, `searchExhaustive`), + the export calls.
  - [x] `apx/web/src/App.tsx` `CorpusSearch`: one field + an **explicit mode** (Suggestions / Preuve); render the chosen engine's result set in its **own framed panel** with the truth-status badge, never combined. Suggestive: `≈ SUGGESTIF`, the **"les N plus proches"** count (never "N résultats"), per-row proximity + snippet + open-at-passage (stub to provenance until 3.5). Exhaustive: `= EXHAUSTIF`, the **denominator** (reuse the equation pattern), the **absence-statement seal** with the four qualifications (kept/review-toned; zero qualifications handled), **register-hits separate**, the moving-population **refusal**, and an **Exporter…** action → the print-ready view. Remove the false "Déterministe et exhaustif" prose.
  - [x] `tsc -b` compiles clean; the screen matches the mockup's structure.

- [x] **Task 6 — Gate + regression.**
  - [x] `ruff` clean; full `pytest` green (no regressions); `tsc -b` (frontend) clean; the check runner shows the new check(s) live; README ↔ manifest lockstep; `alembic` head unchanged (no schema change — endpoints/audit/export are reads + one audit row). Confirm the structural-check count rises by the number of new checks.

## Dev Notes

### The surface reality (verified first-hand + subagent-corroborated)

- **The truth-status contract EXISTS, its surfacing is ABSENT.** `apx/core/domain/retrieval.py` defines all six types with `truth_status` a constant per engine. `truth_status`/`SuggestiveResultSet`/`ExhaustiveResultSet` appear **only** in `domain/retrieval.py`, `core/app/read/{semantic,deterministic}.py`, `core/ports/read.py`, and the two checks — **nothing in `apx/api/` or `apx/web/`**. The status is constructed + gated, never emitted.
- **The one search endpoint is the preview.** [app.py:1122](../../apx/api/app.py#L1122) `GET /api/search` → `store.search` (the `LIKE` preview, capped, truncating), response `SearchResultsOut` (query/total/returned/hits) — **no `truth_status`**; its docstring falsely says "Deterministic exhaustive search". The real engines have **zero** API call sites. [store.py:1504](../../apx/adapters/store_postgres/store.py#L1504) itself admits: *"This is NOT the exhaustive engine — it carries no truth status and it truncates."*
- **The store readers EXIST** — `store.search_semantic` ([store.py:1052](../../apx/adapters/store_postgres/store.py#L1052)), `store.exact_search` ([:1570](../../apx/adapters/store_postgres/store.py#L1570)), `store.open_import_jobs` ([:1560](../../apx/adapters/store_postgres/store.py#L1560)) — and the core engines `search_semantic`/`search_exhaustive` are wired to them; only the **API composition** is missing.
- **The embedder is already composed at the API edge** — `_embedder()` ([app.py:492](../../apx/api/app.py#L492)), the one cached `Bgem3Embedder`, test-replaceable, used by ingest/judge. The suggestive endpoint reuses it (mirroring `admit(store, _embedder(), …)` at [app.py:481](../../apx/api/app.py#L481)).
- **A query is NOT audited.** `store.search` writes no `_append_audit`; no `search` audit action exists. `_append_audit(session, tenant, matter: str|None, actor, action, detail, now)` ([store.py:570](../../apx/adapters/store_postgres/store.py#L570)) takes `matter=None` for tenant-level acts (scope grants) — a scope-wide query audits on the tenant chain the same way. Mirror `export_register` ([store.py:1301](../../apx/adapters/store_postgres/store.py#L1301)), which writes one `export-register` entry.
- **The frontend search UI is a real POC to redesign** — `CorpusSearch` ([App.tsx:496](../../apx/web/src/App.tsx#L496)), token-styled (`apx-panel`/`apx-list`/`apx-item`/`apx-num`/`apx-mono`), calling `searchCorpus` → `/api/search`; it renders a flat hit list with the false prose "Déterministe et exhaustif — rien n'est caché" and **no** truth-status/denominator. `api.ts` types `SearchResults` with **no** truth_status.

### The UX contract is the design authority

Follow **[EXPERIENCE-EPIC3.md](../../_bmad-output/planning-artifacts/ux-designs/ux-apx-mvp-2026-07-27/EXPERIENCE-EPIC3.md)** and **[DESIGN.md](../../_bmad-output/planning-artifacts/ux-designs/ux-apx-mvp-2026-07-27/DESIGN.md)** (the Epic-3 truth-status vocabulary) + the mock **[epic-3-truth-status.html](../../_bmad-output/planning-artifacts/ux-designs/ux-apx-mvp-2026-07-27/mockups/epic-3-truth-status.html)**. Binding points: the two-truths model (a different axis from the triage tier, never blurred, never gold); suggestive = `≈` neutral **dashed-open** frame + "les N plus proches"; exhaustive = `=` **solid** frame + the denominator + the **absence-statement seal** carrying the four qualifications in words (`kept`-toned clean / `review`-toned qualified); register-hits **separate** (AD-21); the moving-population **refusal**; export survives to a court-readable page; the query is an **audited** act; the FR-23 banned phrasing stays barred.

### Frontend reality — no test harness; `tsc` + the gate are the verification

`apx/web` is Vite + React 19 + TS; `build` = `tsc -b && vite build`; **there is no `test` script, no vitest/jest** (AD-29: no Node runtime ships). So the React work is verified by **`tsc -b`** (types compile), the **backend serialisation gate** (the API can't drop `truth_status` or merge engines), and the UX contract — **not** by component tests. Do not add a frontend test harness in this story. Keep the React change tightly scoped to the truth-status declaration; the badge/frame/seal come from `tokens.css` classes so the visual language is token-governed, not ad-hoc inline styles.

### Structural-check house pattern (54 checks today → +N)

`CheckResult(name, ad, ok, detail)`; injectable `roots`; **fail closed** on an unparseable file; exclude `{checks, fitness, timedrun, __pycache__}` + `node_modules` + `migrations`; register in [`registry.py`](../../apx/checks/registry.py) `CHECKS`; add a `_p(...)` row in [`manifest.py`](../../apx/checks/manifest.py); add the README `<!-- structural-properties -->` row (machine-compared on key/fr/ad/verb/check-`__name__`). The new gate targets **serialisation** (a results-carrying response/export model must carry `truth_status`; no model merges both engines) — complementing `truth_status_is_constant_per_engine` (construction). Anchor on **types/shapes** (a model with a `results`/`hits` field of a `SemanticResult`/`DeterministicResult` shape), not fragile names — the 3.1/3.3 lesson.

### Previous-story intelligence (3.1 / 3.2 / 3.3)

- **Wire the engine, don't re-implement it.** `search_semantic`/`search_exhaustive` already do the scoped, truth-status-carrying work; the endpoints only *compose + serialise*. Do not add a limit to the exhaustive path (`no_truncation` gate) and keep the `(tenant, scopes, query)` pre-filter shape (`no_post_filter_in_retrieval` gate).
- **The 3.3 wall is already proven** — the endpoints inherit the scope pre-filter (results, denominator, and every qualification figure are scoped; `corpus_read_takes_no_admin_bypass` forbids an `is_admin` corpus read). Do not add an `is_admin` to a search endpoint.
- **Compute, don't fabricate** (the 3.2 lesson) — `ocr_share` is real (`_scoped_ocr_share`); `below_quality_share`/`register_hits` are honest zeros/empty (no signal yet) — surface them as absent, never a made-up figure.
- **Type/shape anchors, fail-closed checks, README↔manifest lockstep** — every check story so far.

### Testing standards

`uv`-managed (`.venv/bin/ruff`, `.venv/bin/python`; no pip); `ruff` line-length 100, E/F/I/UP/B. Run pytest with `export PATH="$PWD/.venv/bin:$PATH"`; **never** export `DATABASE_URL` (SQLite baseline — the exhaustive endpoint + audit + export + the gate run for real; the suggestive endpoint's behavioural run is pg-gated, its shape tested with fakes). Frontend: `cd apx/web && npm run build` (or `tsc -b`) must compile — run it to verify the React change (no unit-test harness).

### Project Structure Notes

- No migration — endpoints + one `search`/`export-search` audit row + reads; `alembic` head stays `0022_deterministic_index`.
- New: `apx/checks/truth_status_surface.py` (+ test); `tests/api/test_search_endpoints.py` (+ export/audit); frontend edits to `App.tsx`/`api.ts`/`tokens.css`. Edits: `app.py` (2 endpoints + export + the corrected preview docstring), `store.py` (the query audit + the search export, mirroring `export_register`), `registry.py`/`manifest.py`/`README.md`.
- The moving-population refusal (`MovingPopulation`, 3.2) surfaces as a typed 409 + the UI refusal — never a partial exhaustive set.

### References

- [Source: epics.md#Story-3.4] — the three acceptance criteria (truth status in interface/export/audit, distinct + surviving export; no combined list; suggestive non-completeness wording / exhaustive denominator).
- [Source: EXPERIENCE-EPIC3.md] + [DESIGN.md] + [epic-3-truth-status.html] — the UX contract and the truth-status vocabulary (the design authority for Task 5).
- [Source: ARCHITECTURE-SPINE.md#AD-42] — the exhaustive set's four qualifications bind every surface + export; the AD-33 action-registry assertion (deferred).
- [Source: ARCHITECTURE-SPINE.md#AD-38] — the six-field denominator (the `DenominatorOut`).
- [Source: ARCHITECTURE-SPINE.md#AD-20] — one construction site per engine; an exhaustive set is never truncated.
- [Source: apx/core/domain/retrieval.py] — the six types the endpoints serialise.
- [Source: apx/api/app.py#L1122] — the mislabeled preview endpoint to correct + the `_embedder()` composition pattern.

## Dev Agent Record

### Agent Model Used

claude-opus-4-8[1m] (Claude Opus 4.8, 1M context)

### Debug Log References

- Final gate (post-review, frozen artifact): ruff clean · **853 passed / 11 skipped** (was 834/11 — +19: 8 search-endpoint tests + 11 surface-gate tests) · **56/56 structural checks** (was 54 — +2 truth-status-surface) · frontend `tsc -b` clean · alembic head unchanged `0022_deterministic_index` (endpoints + reads + audit rows, no schema change).

### Completion Notes List

- **Task 1 — two engine endpoints, each serialising its truth status.** `apx/api/app.py`: `GET /api/search/exhaustive` (real, SQLite) → `ExhaustiveOut` (truth_status, the six-field `DenominatorOut`, ocr_share, below_quality_share, register_hits, normalization, results); `GET /api/search/suggestive` → `SuggestiveOut` (truth_status, k, similarity_threshold, wording, results), composing the cached `_embedder()`. `MovingPopulation` → 409. The mislabeled `/api/search` docstring corrected to an honest "bounded PREVIEW … NOT a truth-status set … TRUNCATES". Two endpoints, two response models — never combined.
- **Task 2 — the query is an audited act.** `SqlStore.audit_query` writes one entry (`search` / `export-search`) on the tenant chain (`matter=None`) naming the term, engine (truth status), scope, and — exhaustive — the denominator.
- **Task 3 — the search export.** `/api/search/{suggestive,exhaustive}/export` → the payload + a `header` carrying the truth status on its face (suggestive: the non-completeness wording; exhaustive: `_exhaustive_header` = the scoped denominator + qualifications + the presence/absence claim), + one `export-search` audit entry.
- **Task 4 — the serialisation gate.** New `apx/checks/truth_status_surface.py` (2 checks): `result_set_response_serialises_truth_status` (a response/export model carrying engine result items must declare `truth_status`) and `no_response_merges_the_two_engines`. Fail-closed, injectable roots, registered (registry + manifest + README lockstep). Complements the construction gate (3.1/3.2). 54 → 56 checks.
- **Task 5 — the redesigned React screen.** `tokens.css` +the Epic-3 vocabulary (badge ≈/=, dashed/solid frames, absence seal, proximity meter); `api.ts` +the typed responses + `searchSuggestive`/`searchExhaustive` + export URLs; `App.tsx` `CorpusSearch` rewritten — one field + explicit mode (Suggestions / Preuve), two distinctly-framed panels (`SuggestivePanel` / `ExhaustivePanel`) never combined, the "les N plus proches" wording, the scoped denominator, the absence-statement seal with its four qualifications, register-hits separate, the moving-population refusal, a print-ready export link. `tsc -b` clean.
- **Honest deferrals surfaced, not faked:** `below_quality_share`=0.0 and `register_hits`=[] (the store carries them honestly — no OCR-quality signal, no register name-match search yet); the seal wording accommodates zero qualifications. The semantic behavioural run is pg-gated (the endpoint's serialisation is proven on SQLite via the fail-closed empty-scope path + a fake embedder). The viewer (3.5) open-at-passage is stubbed. No frontend test harness (AD-29) — `tsc` + the backend gate verify the React.

### File List

- `apx/api/app.py` (modified) — the 2 engine endpoints + 2 export endpoints, the 8 Pydantic models, the DRY payload/header helpers, the corrected preview docstring, the Inventory import.
- `apx/adapters/store_postgres/store.py` (modified) — `SqlStore.audit_query` (the query/export audit).
- `apx/checks/truth_status_surface.py` (new) — the two serialisation-gate checks.
- `apx/checks/registry.py`, `apx/checks/manifest.py`, `README.md` (modified) — register the gate (lockstep).
- `apx/web/src/api.ts` (modified) — the truth-status types + `searchSuggestive`/`searchExhaustive` + export URLs; the corrected preview comment.
- `apx/web/src/App.tsx` (modified) — `CorpusSearch` rewritten + `SuggestivePanel`/`ExhaustivePanel`/`_pips`.
- `apx/web/src/tokens.css` (modified) — the Epic-3 truth-status CSS vocabulary.
- `tests/api/test_search_endpoints.py` (new) — the endpoints/audit/export tests.
- `tests/checks/test_truth_status_surface.py` (new) — the gate fixtures.

### Change Log

- 2026-07-30 — Story 3.4 implemented (full-stack): two truth-status-carrying engine endpoints (never combined) + the query audit + the search export carrying the distinction + a new serialisation gate + the redesigned React truth-status search screen per the Epic-3 UX contract. Status → review.
- 2026-07-30 — Adversarial 3-reviewer pass + fixes. **R1** (backend, self-completed) clean: scope pre-filter holds through the endpoints, the audit chain still verifies after the `matter=None` search entry (AD-43), the search term is encrypted at rest, one entry per query. **R2** (gate) closed 3 evasions + 1 false positive: the gate is now inheritance-aware, forward-ref-aware, and catches an untyped `results` container (+4 fixture tests). **R3** (frontend/UX): **H1** the export is now a real **print-ready HTML document** (`text/html`, `@media print`), not raw JSON — a court-readable page; M1 an empty scope renders "aucun périmètre — rien n'a été recherché" (never a green proof of absence); M2 "N pièce(s) contenant" (not "occurrences"); M4 the 409 refusal is branched on `ApiError.status` and shown in French (no raw English); M6 a scope chip names the wall; M3 a visual "ouvrir au passage →" stub (the viewer is 3.5); M5 the rank ordinal added; L1 the below-quality share surfaced when > 0; L2 the dead preview client binding removed. Final gate: ruff clean, 853 passed / 11 skipped, 56/56 checks, tsc clean.

## Senior Developer Review (AI)

**Outcome:** Approved after fixes. Three parallel adversarial reviewers (backend / gate / frontend-UX; execution-verified; read-only).

- **Reviewer 1 — backend API (self-completed; the background agent died):** verified clean — the endpoints inherit the 3.3 scope pre-filter (out-of-scope pièces excluded from results and denominator); the query audit does **not** corrupt the per-tenant audit chain (AD-43, `verified` still true after a `matter=None` search/export entry); `audit_record.detail`/`actor` are encrypted at rest (the term is never plaintext); exactly one audit entry per query/export; no FR-23 phrasing. Two LOW notes (embedder eager-load on an empty-scope suggestive call — process-cached; an embedder failure → generic 500).
- **Reviewer 2 — the serialisation gate:** found real teeth-gaps (untyped `results` containers, inheritance blindness with a false positive that would block a DRY refactor, forward-ref evasions) — all fixed: the gate is now inheritance-aware (union own + inherited fields/types), reads whole- and nested forward-ref strings, and catches a bare `results` sequence. +4 fixture tests; the false positive (a DRY `truth_status` base) now passes.
- **Reviewer 3 — frontend + UX + AC honesty:** affirmed AC1/AC2 strong (two framed panels, explicit mode, the structural gate), the voice clean (no FR-23, "les N plus proches", the absence seal never a bare "introuvable"), the audit correct. **HIGH H1** — the flagship "court-readable export" was raw JSON — fixed to a real print-ready HTML document. MEDs fixed: the empty-scope green-absence mis-seal (M1), the "occurrences"/pièce mislabel (M2), the raw-English 409 refusal (M4), the missing scope chip (M6), the rank ordinal (M5), a visual open-at-passage stub (M3). Honest corrections: the suggestive row has **no snippet** (the 3.1 `SemanticResultOut` carries only piece_id/chunk_id/similarity — enriching it is out of scope); the open-at-passage is a **visual stub** pending the Story 3.5 viewer.
