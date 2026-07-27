---
baseline_commit: 1ab5fdc
---

# Story 1.10: The content-free projection primitive

Status: review

## Story

As APX supporting an installation I can never see into,
I want a single audited primitive that emits counts, versions, error classes and redacted diagnostics and provably no *tenant* content,
So that "only code travels" is one enforceable mechanism reused three times, not a promise repeated in three places.

**Scope in one line:** build the **one** mechanism for emitting information *about* a *tenant*'s data without emitting the data (`apx/core/projection.py`) — a **registry of named projectors**, each declaring the **shape** it emits (a value kind from a content-free set; a text-deriving projector additionally declares its **attestation floor** — min *pièces* AND min *matters*); make content-freedom a **structural property** in three parts: (i) a **seeded-token test** over **every** registered projector *and the union of all projectors' output for one tenant* asserts no seeded content token or secret value appears; (ii) an **emission path outside the registry fails the build** (the projection result type is sealed — constructed only by the registry — a static check, so a projector cannot be added by writing one); (iii) a projector whose value derives from *pièce*/*chunk* text that does **not** declare its attestation counts fails the build. Ship the **first consumers' machinery** — three content-free projectors (corpus counts, error-class histogram, version identifiers) behind an admin diagnostic endpoint — and prove the **AD-45 egress check lives in the uncuttable checks unit**, not in this (predicted-to-be-dropped) projection unit. **Not** the full client-pushed diagnostic export packaging/push (story 6.2); **not** the style extractor (next increment); **not** the cockpit UI (front-end, AD-29).

> An adversarial architecture review named the content-free projection among the components most likely to be quietly dropped under pressure — it is load-bearing for the sovereignty claim ("only code travels"). AD-26 therefore split the egress enumeration (AD-45) OFF this unit so the *no-fourth-egress-path* check survives even if this unit is cut. 1.10 builds the primitive so "only code travels" is one enforceable mechanism, tested for content-freedom, rather than a promise repeated in three places.

## Acceptance Criteria

> **Given** the *content-free projection* (FR-31), **When** it emits anything — a client-pushed diagnostic export, a cockpit signal, or the style-profile output of a later increment, **Then** the output passes an assertion that seeded content tokens and seeded secret values do not appear in it, and the content-freedom is enforced by a structural property rather than by an allow-list that a later field could quietly break (FR-31, AD's open-registry-with-attestation decision).
> **And** the egress check lives in a unit that cannot be cut from the build (per AD-45, moved off the unit an adversarial review predicted would be dropped).
> **And** *(failure path)* adding a new projected field without an attestation that it is content-free turns the build red.

1. **AC1 — One registry, open by construction (AD-26/FR-31).** All emission of information *about* a *tenant*'s data goes through **one** registry of named projectors (`apx/core/projection.py`). Each projector declares the **shape** of what it emits — a value kind from the content-free set (count, version, error-class, timing, redacted-diagnostic, opaque-id, attested-aggregate). The registry is a registry, **not a closed list of value kinds**: a new projector (the next increment's style extractor) is added by registering it, not by amending an enumeration.
2. **AC2 — Content-freedom is a structural property, in three parts.** (i) A **seeded-token test** seeds a *corpus* with a unique content token AND a secret value, runs **every** registered projector, and asserts neither appears in any projector's output — **and** asserts the same for the **union** of all projectors' output for one *tenant* (the attestation floor is not composable). (ii) The projection result type is **sealed**: a static check asserts it is constructed only inside the registry module, so an emission path outside the registry fails the build (a projector cannot be added by writing one). (iii) A projector whose value kind is **attested-aggregate** (derived from *pièce*/*chunk* text) must declare its attestation counts (min *pièces* AND min *matters*) machine-readably — one that does not **fails the build**.
3. **AC3 — The first consumers' projectors are content-free (FR-31).** Three registered projectors emit what the client-pushed diagnostic export needs today — **corpus counts** (*pièces*, failures, matters — counts only), an **error-class histogram** (enumerated classes → counts), and **version identifiers** (distinct schema/extractor versions) — with **no** filename, path, *matter* name, user name, content or query text. An admin, tenant-scoped diagnostic endpoint returns the registry's projection for the caller's *tenant* (inside the *tenant* boundary; never cross-*tenant*).
4. **AC4 — The egress check cannot be cut (AD-45).** The *no-fourth-egress-path* / outbound-adapter check lives in the checks harness (`apx/checks/`), **not** in this projection unit — a test asserts it is registered in the harness and that deleting `apx/core/projection.py` would leave it intact. This is the explicit AD-26→AD-45 split: dropping the projection unit must not drop the egress guarantee.
5. **AC5 — Failure paths fire.** A projector with an attested-aggregate value and no declared floor turns the build red (a fixture proves it). A construction of the projection result type outside the registry turns the build red (a fixture proves it). A projector that leaks a seeded token is caught by the seeded-token test.
6. **AC6 — Green and honest.** All existing tests pass; `ruff` + `python -m apx.checks` + `pytest` + fitness green; README documents the projection primitive; no diagnostic-export packaging (6.2), style-extractor (next increment) or cockpit (AD-29) over-build.

## Tasks / Subtasks

- [x] **Task 1 — The registry + attestation model** (AC: #1, #2) — `apx/core/projection.py` (pure core): `ValueKind` (the content-free kinds), `Attestation` (kinds + optional min_pieces/min_matters), a sealed `Projection` result type constructed only here, a `Projector` (name + attestation + fn), a `REGISTRY` with `register()`, and `project_all(snapshot)` — the one emit path. Pure `redact(text, secrets)` for the redacted-diagnostic kind (core imports no logging — the edge supplies the secret list).
- [x] **Task 2 — The content-free snapshot + three projectors** (AC: #3) — `store.projection_snapshot(tenant)` gathers ONLY content-free facts (counts, error-class histogram, distinct version identifiers) — no names/paths/content. Register `corpus_counts`, `error_class_histogram`, `versions` projectors over the snapshot.
- [x] **Task 3 — The admin diagnostic endpoint** (AC: #3) — `GET /api/admin/diagnostics` (require_admin, tenant from session) returns `project_all(store.projection_snapshot(tenant))`. The registry's first consumer; the full push/packaging is 6.2.
- [x] **Task 4 — Structural checks** (AC: #2, #4, #5) — `apx/checks/projection.py`: `projection_emitted_only_by_registry` (AST: `Projection(...)` constructed only in `projection.py`), `projectors_declare_attestation` (every registered projector has a valid attestation; a text-deriving one declares its floor). Registered in the harness. A test asserts the AD-45 egress check is in the harness (`import_contracts.run`) and not in the projection unit.
- [x] **Task 5 — Seeded-token test + fixtures** (AC: #2, #5) — `tests/core/test_projection.py` (registry, attestation, redact), `tests/adapters/test_projection_content_free.py` (seed a content token + secret into a tenant's pieces/failures/matter, assert absent from every projector AND the union), `tests/checks/test_projection_checks.py` + fixtures under `tests/_fixtures/projection_violations/` (an out-of-registry `Projection(...)`; an undeclared attested-aggregate projector built inline).
- [x] **Task 6 — Green + docs** (AC: #6) — README: the projection primitive. `ruff` + `python -m apx.checks` + `pytest` + fitness green.

## Dev Notes

- **Why the registry is core and the snapshot is the store's.** The registry, the attestation model and the sealed `Projection` type are pure domain (`apx/core/projection.py`, no adapter import). The *raw* content-free facts (counts, error-class histogram, distinct versions) are gathered by the store (`projection_snapshot`) because they are queries; the projectors are pure functions from that snapshot to a `Projection`. The seeded-token test seeds real content into the store and asserts the snapshot-plus-projectors path leaks none of it — so the test exercises the actual gathering, not a hand-built content-free input. [Source: ARCHITECTURE-SPINE.md#AD-26; AD-4]
- **"Emission outside the registry fails the build" = a sealed result type.** FR-31(ii) wants "a projector cannot be added by writing one." The decidable structural form: the `Projection` result type is constructed **only** inside `apx/core/projection.py` (an AST check across `apx/`, the same shape as the one-chunk-writer and encrypted-column checks). Any code that fabricates a projection payload elsewhere fails the build; a legitimate consumer (the diagnostic endpoint, later the 6.2 export) **receives** a `Projection` from `project_all`, it never constructs one. The AD-45 egress deny-list is the network-level backstop for an actual fourth outbound path. [Source: prd FR-31; ARCHITECTURE-SPINE.md#AD-26, #AD-45]
- **The attestation floor is the structural form of content-freedom for text-derived values.** A projector emitting a value derived from *pièce*/*chunk* text (the style extractor's phrasebook) may emit only values **attested across a configured minimum number of *pièces* AND *matters*** — never one traceable to a single *matter*. The floor is declared machine-readably on the projector; `projectors_declare_attestation` fails the build on an attested-aggregate projector with no floor, because the property is otherwise undecidable. No text-deriving projector ships in 1.10 (that is the next increment); the machinery + the failing fixture do. [Source: prd FR-31(iii); ARCHITECTURE-SPINE.md#AD-26]
- **The union test catches joint identification.** Two projectors each above the floor can jointly identify; so the seeded-token test asserts absence in each projector's output AND in the union of all projectors' output for one tenant. [Source: ARCHITECTURE-SPINE.md#AD-26(i)]
- **The egress check already lives in the uncuttable unit (AD-45 split).** The *no-fourth-egress-path* check is `import_contracts.run` in the checks harness (story 1.1/1.8), NOT in the projection unit — exactly the AD-26→AD-45 split ("dropping the projection unit must not drop the check that no fourth egress path exists"). 1.10 adds a test that pins this: the egress check is registered in `CHECKS` and the projection module contains no egress logic. [Source: ARCHITECTURE-SPINE.md#AD-45; apx/checks/import_contracts.py]
- **Redacted diagnostics reuse 1.8.** The redacted-diagnostic value kind passes a string through 1.8's `SecretRedactor` (secrets) — the seeded-token test additionally seeds a secret value and asserts it is absent, tying FR-31 to FR-51. 1.10 ships the `redact()` primitive and the REDACTED kind; a projector that emits a *tenant*'s failure detail is deferred to the 6.2 diagnostic export where the redaction is exercised on real detail. [Source: apx/api/logging.py; prd FR-31]
- **What this story does NOT do.** The client-pushed diagnostic **export** (packaging, signing, the push act, its audit entry as a named egress) is story 6.2; 1.10 builds the primitive it will consume and one endpoint to exercise it. The **style extractor** is the next increment. The **cockpit** signal UI is the front-end (AD-29). [Source: epics.md 6.2; ARCHITECTURE-SPINE.md#AD-26, #AD-29]
- **Structural-check + fixture pattern (AD-33).** Reuse the 1.3–1.9 pattern: `CheckResult`, registered in `CHECKS`, explicit `roots`/injectable registry, fail closed on unparseable, fixtures AST/text-scanned and `ruff`-clean. [Source: apx/checks/payload_schema.py, apx/checks/configuration.py]

### Project Structure Notes

- New: `apx/core/projection.py`, `apx/checks/projection.py`, `tests/core/test_projection.py`, `tests/adapters/test_projection_content_free.py`, `tests/checks/test_projection_checks.py` (+ fixtures under `tests/_fixtures/projection_violations/`).
- Modified: `apx/adapters/store_postgres/store.py` (`projection_snapshot`), `apx/api/app.py` (diagnostic endpoint), `apx/checks/__main__.py` (register 2), `README.md`.
- No new dependency; no schema change (projections are read-only over existing tables).

### References

- ARCHITECTURE-SPINE.md#AD-26 (one content-free projection registry), #AD-45 (three egress paths; the split), #AD-4 (layering), #AD-33 (structural checks), #AD-29 (SPA deferred).
- prd FR-31 (the content-free projection primitive), FR-56 (structural properties in one artefact), FR-51 (secrets never emitted).
- epics.md Story 1.10; Story 6.2 (the diagnostic export consumer).

## Dev Agent Record

### Context Reference

Architecture: AD-26 (one content-free projection registry), AD-45 (three egress paths; the split OFF this unit), AD-4 (layering), AD-33 (structural checks), AD-29 (SPA deferred). PRD FR-31, FR-56, FR-51.

### Completion Notes

- **The registry is pure core; the raw facts are the store's.** `apx/core/projection.py` holds `ValueKind`, `Attestation`, the sealed `Projection`, the `REGISTRY` + `register()`, `project_all` (the one emit path), `projection_strings` (the union flattener) and a pure `redact(text, secrets)`. The store's `projection_snapshot(tenant)` gathers the content-free facts (counts, error-class histogram, distinct versions) — so the seeded-token test exercises the real gather-plus-project path, not a hand-built content-free input.
- **"Emission outside the registry fails the build" = a sealed result type.** `Projection` is constructed only in `project_all`; `projection_emitted_only_by_registry` (AST, across `apx/`, excluding the registry file + vendored trees) fails the build on a `Projection(...)` anywhere else. A consumer (the diagnostic endpoint, later 6.2) constructs `ProjectionOut`, never `Projection`. Failure-path fixture: `tests/_fixtures/projection_violations/out_of_registry/emit.py`.
- **The attestation floor is the text-derived content-freedom.** `projectors_declare_attestation` fails the build on an `ATTESTED_AGGREGATE` projector with no floor (min pièces AND matters). No text-deriving projector ships (that is the style extractor, next increment); the machinery + a failing inline fixture do.
- **The union is tested, not just each projector** (AD-26 i, the floor is not composable): the seeded-token test asserts absence in each projector's output AND in `projection_strings(project_all(...))` (keys + values flattened). It seeds a unique content token into every content-bearing field (matter/tenant/actor/full_text/custodian/provenance_path/failure filename+detail) AND a secret value into the env, and asserts neither surfaces (FR-31 ↔ FR-51).
- **The egress check lives in the uncuttable unit (the AD-26→AD-45 split).** The no-fourth-egress-path check is `import_contracts.run`, registered in the harness (`__module__ == "apx.checks.import_contracts"`), NOT in `apx/core/projection.py` — a test pins this, so dropping the (predicted-to-be-dropped) projection unit leaves the egress guarantee intact.
- **Deliberately deferred:** the client-pushed diagnostic **export** (packaging, the push act as a named egress, its audit entry) is story 6.2 — 1.10 builds the primitive + one endpoint to exercise it; the **style extractor** is the next increment; the **cockpit** signal UI is the front-end (AD-29). The REDACTED value kind + `redact()` ship as primitives; a projector emitting a *tenant*'s (redacted) failure detail is deferred to 6.2 where the redaction is exercised on real detail.
- **Gate:** ruff clean · `python -m apx.checks` **21/21** (+2) · `pytest` **397 passed, 8 skipped** (+16) · fitness green.

### File List

- **New:** `apx/core/projection.py`, `apx/checks/projection.py`, `tests/core/test_projection.py`, `tests/adapters/test_projection_content_free.py`, `tests/checks/test_projection_checks.py`, `tests/_fixtures/projection_violations/out_of_registry/emit.py`.
- **Modified:** `apx/adapters/store_postgres/store.py` (`projection_snapshot`), `apx/api/app.py` (diagnostic endpoint + `ProjectionOut`), `apx/checks/__main__.py` (register 2), `README.md`.

### Change Log

- 2026-07-27 — Story 1.10 implemented: the content-free projection registry (sealed emit type, attestation floor, seeded-token + union test) + admin diagnostic endpoint + two structural checks; egress check pinned in the uncuttable unit (AD-26/AD-45/FR-31). 21 checks, 397 tests green.
