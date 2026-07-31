---
baseline_commit: 37ee207
---

# Story 3.5b — The pièce read path (scope pre-filter · audit-on-open · large-file bound)

**Part of Story 3.5 (the pièce viewer), increment 2 of 4.** Increment 1 (3.5a) retains each pièce's
original at rest, encrypted. This increment builds the **read path** that serves a pièce's metadata
and original bytes to a caller — through the one sanctioned read path, behind the RBAC scope
pre-filter, recording the open in the audit record. The per-format *rendering* is 3.5c; the React
viewer is 3.5d.

Status: done

## Story

As a lawyer opening a pièce in the product,
I want the pièce's content served only when it is within my scope, with the open recorded,
So that a pièce outside my wall is never renderable, never downloadable, and its existence is not
even disclosed — and a *validation act* I perform after reading is provably distinct from one from
the list.

## Acceptance Criteria

**AC1 — One read path, scope as a query pre-filter.** The pièce read is constructed only in the
sanctioned read path (`core/app/read/` + the store read module, AD-14), and scope is a **query
pre-filter** (AD-13): a pièce is returned iff its *matter*'s scope is held (a `matter_scope`
sub-query), never a Python post-filter. Enforced by the existing Story 3.3 gates.

**AC2 — The non-disclosing denial (FR-14/FR-44).** A pièce outside the caller's scope is **not
renderable, not downloadable, and its existence is not disclosed**: the read returns `None`, and the
endpoint's response is **byte-identical** to a genuinely-absent pièce (a 404 with the same body — no
name, size, scope, format, or matter leaks). A caller with **no scope** reads nothing — there is
**no admin bypass** (a Piece read is scoped like any other; the Story 3.3 gate
`corpus_read_takes_no_admin_bypass` forbids `is_admin` on a Piece read; fail-closed, AD-12).

**AC3 — Opening the content is an audited act (FR-45).** Serving a pièce's **original** records an
`audit_record` entry (actor, the pièce, its matter) — the fact that distinguishes a validation act
performed **after reading** from one performed from the list. The audit chain stays verifiable
(AD-43). A cross-tenant / out-of-scope attempt is **not** served and writes **no** disclosing entry.

**AC4 — The original is served from within the tenant boundary.** The `/original` endpoint decrypts
the retained blob (3.5a `OriginalStore.open`) and returns the bytes — no pièce content sent to any
third-party service. A pièce whose blob is missing (a register-failed orphan, or never retained) is
reported honestly (the original is unavailable), never a 500.

**AC5 — Metadata for the viewer.** `GET /api/pieces/{id}` returns the pièce's viewer metadata IF in
scope: the pièce id, matter, the representative filename, a coarse `media_kind`
(pdf/email/spreadsheet/document/image/other), whether its text is from **OCR** (the honesty flag),
the original's `byte_size`, and `renderable_inline` (size ≤ the configured render bound). Out of
scope → the same 404 as AC2.

**AC6 — The large-file bound.** The metadata carries `byte_size` + `renderable_inline` against a
configured render bound (`APX_PIECE_RENDER_MAX_BYTES`, default 25 MB) so the viewer (3.5d) can offer
the original / progressive load instead of exhausting the client. Serving `/original` is bounded by
the ingest per-unit cap (no retained blob exceeds it), so it never loads an unbounded blob.
*(On-prem sizing note, per review: there is no chunk-streaming decrypt — AES-GCM authenticates the
whole blob — so per-request memory is bounded by the ingest per-unit cap (200 MB default), and
aggregate resident memory scales with concurrent opens. Callers are authenticated, in-scope lawyers,
not an anonymous DoS surface; chunk-encrypted streaming is a future refinement.)*

**AC7 — No over-build.** No per-format rendering, no passage highlight, no React — those are 3.5c/d.
No new DB column; `media_kind`/`ocr`/`filename` are **derived** at read time from existing columns
(`extraction_method`, `provenance_path`). No migration (alembic head unchanged).

## Dev Notes

**Design (against the code).**

1. **Port** (`core/ports/read.py`, extend) — a `PieceView` dataclass + a `PieceReader` protocol:
   `read_piece(*, tenant, scopes, piece_id, is_admin) -> PieceView | None` (identifier ALWAYS with
   tenant + scopes — AD-14; no post-filter). `PieceView` = piece_id, matter, content_hash, filename
   (decrypted representative provenance basename), media_kind, ocr, plus the original's byte_size /
   renderable_inline filled at the edge (the DB read fills identity + format; size comes from the
   OriginalStore stat).
2. **Core read path** (`core/app/read/piece.py`) — `open_piece(*, tenant, scopes, piece_id, reader,
   is_admin=False) -> PieceView | None`: fail-closed on empty scope + not admin; else delegate to
   the reader (the pre-filter is in the query). Pure read, no side-effect.
3. **Store read** (`adapters/store_postgres/*`) — implement `read_piece`: `select(Piece).where(id ==
   piece_id, tenant == tenant, matter.in_(held_matters))` (or all tenant matters when `is_admin`),
   `held_matters = select(MatterScope.matter).where(tenant, scope.in_(scopes))` — the same
   pre-filter shape as `register_all` (3.3). Derive `media_kind` from the filename extension +
   `extraction_method`; `ocr` from the extraction method; decrypt the representative
   `provenance_path` to a basename.
4. **Audit-on-open** — `store.audit_piece_open(*, tenant, matter, actor, piece_id, now=None)`
   appends ONE `_append_audit(..., action="open-piece", detail=piece_id ...)` on the (tenant,
   matter) chain (AD-43), mirroring `audit_query` (3.4). Called by the `/original` endpoint after a
   successful in-scope read (content access = the FR-45 "read" act); the metadata GET is an
   unaudited peek.
5. **Endpoints** (`api/app.py`) —
   - `GET /api/pieces/{id}` → the `PieceView` metadata (200) or the SAME 404 body for
     out-of-scope/absent (AC2). Fills byte_size/renderable_inline from `OriginalStore` (stat) when
     the blob exists.
   - `GET /api/pieces/{id}/original` → the decrypted bytes as a download (media type + filename),
     scope-checked (open_piece), **audited** (audit_piece_open). Blob missing → an honest 404/409
     "original unavailable", never a 500.
   The render bound is `_int_env`/config `piece_render_max_bytes` (default e.g. 25 MB for inline).
6. **Structural coverage** — no NEW gate: the Story 3.3 read-path gates
   (`tenant_reads_have_one_entry_point`, `scoped_read_puts_scope_in_the_query`) already require the
   scope pre-filter on the new read (the store method is a scopes-taking read of a scoped table).
   Behavioural tests carry non-disclosure, audit-on-open, fail-closed, and the bound.

**Boundaries / non-goals.** No renderers, no passage highlight, no React, no new column, no
migration. `full_text` is not served here (the text/render surface is 3.5c/d); this increment serves
the ORIGINAL bytes + metadata.

**Files (expected).** `core/ports/read.py` (UPDATE), `core/app/read/piece.py` (NEW),
`adapters/store_postgres/{store.py or a read module}` (UPDATE — `read_piece` + `audit_piece_open`),
`api/app.py` (UPDATE — the two endpoints + a `PieceView` response model), tests under
`tests/{app,api,adapters}/`.

## Tasks / Subtasks

- [x] `PieceView` + `PieceReader` port; `open_piece` core read path (fail-closed) + tests.
- [x] Store `read_piece` (scope pre-filter, derive media_kind/ocr/filename) + `audit_piece_open` + tests.
- [x] `GET /api/pieces/{id}` (metadata or non-disclosing 404) + `GET /api/pieces/{id}/original`
  (decrypt + serve + audit + blob-missing honesty) + the render bound + tests.
- [x] Adversarial tests: out-of-scope is byte-identical to absent; audit-on-open writes exactly one
  entry and keeps the chain verifiable; empty-scope fail-closed; blob-missing honest.
- [x] Full gate: ruff, pytest, structural checks (unchanged 57 — covered by 3.3 gates), `tsc -b`
  unchanged, alembic head unchanged.

## Dev Agent Record

### Completion Notes

- **Port + core**: `PieceView` + `PieceReader` (`read_piece(*, tenant, scopes, piece_id)` — id
  ALWAYS with tenant+scopes, AD-14; **no admin bypass** — a Piece read takes no `is_admin`, so the
  Story 3.3 `corpus_read_takes_no_admin_bypass` gate stays green). `open_piece` fail-closes on an
  empty scope BEFORE the reader.
- **Store**: `read_piece` = `select(Piece).where(id, tenant, matter.in_(held_matters))` — the same
  scope PRE-FILTER shape as `register_all` (3.3), so an out-of-scope pièce is never fetched (not a
  post-filter). Derives `media_kind` (from the filename ext), `ocr` (`extraction_method ==
  "tesseract"`), `filename` (the decrypted representative provenance basename). `audit_piece_open`
  writes ONE `open-piece` entry on the (tenant, matter) chain (AD-43), mirroring `audit_query`.
- **Originals**: added `size()` (plaintext byte size from the on-disk token minus the fixed cipher
  overhead — no decryption) for the render-bound decision.
- **Endpoints**: `GET /api/pieces/{id}` → `PieceMetaOut` (id, matter, filename, media_kind, ocr,
  byte_size, renderable_inline) or the **same 404** for out-of-scope AND absent (non-disclosing). A
  peek — unaudited. `GET /api/pieces/{id}/original` → the decrypted bytes as an **attachment +
  octet-stream + nosniff** (a crafted `.html`/`.svg` can never execute in the app origin — safe
  inline rendering is 3.5c/d); the content access is the **audited** read (FR-45); a missing/unreadable
  blob → an honest **409**, never a 500; out-of-scope → the same 404, no audit.
- **The read bound**: `renderable_inline = byte_size ≤ APX_PIECE_RENDER_MAX_BYTES` (default 25 MB),
  so the viewer (3.5d) can offer the original / progressive load. Serving is bounded by the ingest
  per-unit cap (no retained blob exceeds it).
- **No new structural check** — the Story 3.3 read-path gates (`tenant_reads_have_one_entry_point`,
  `scoped_read_puts_scope_in_the_query`, `corpus_read_takes_no_admin_bypass`) already cover the read;
  behavioural tests carry non-disclosure, audit-on-open, fail-closed, and the bound. No DB column, no
  migration; `apx/web` untouched.

### File List

- `apx/core/ports/read.py` (UPDATE — `PieceView` + `PieceReader`)
- `apx/core/app/read/piece.py` (NEW — `open_piece`)
- `apx/adapters/store_postgres/store.py` (UPDATE — `read_piece`, `audit_piece_open`,
  `_media_kind`/`_basename`/`_MEDIA_KIND_BY_EXT`)
- `apx/adapters/originals_fs/store.py` (UPDATE — `size()`)
- `apx/api/app.py` (UPDATE — `PieceMetaOut`, `get_piece`, `get_piece_original`, `_render_bound`,
  `_sanitize_filename`, `DecryptionError` import)
- `tests/app/test_read_piece.py`, `tests/api/test_piece_endpoints.py` (NEW)

### Change Log

- 2026-07-30 — Story 3.5b implemented. Gate (pre-review): ruff clean, new tests green, 57 structural
  checks (3.3 read-path gates cover the new read), alembic head unchanged, `apx/web` untouched.
- 2026-07-31 — 3-reviewer adversarial pass (RBAC/non-disclosure · architecture/audit ·
  correctness/tests). **Verdict, all three: the wall HOLDS, the design is SOUND, the tests PROVE the
  claims (mutation-verified), no over-build.** No HIGH/MED — every attack (out-of-scope byte-identical
  to absent, cross-tenant, admin bypass, filename injection, unaudited disclosure, 500-on-missing-blob)
  failed under execution. LOW/NOTE findings resolved:
  - LOW (R1+R2+R3) — accented FR/LU download filenames were ASCII-dropped (`reçu.pdf`→`ru.pdf`).
    **Fixed:** RFC 6266 `filename*=UTF-8''…` preserves the name (with an ASCII fallback), both legs
    injection-safe; + an accented-name test and a header-injection test.
  - NOTE (R2) — `PieceView.byte_size`/`renderable_inline` were dead (filled at the edge). **Removed**
    from the port dataclass.
  - LOW (R3) — the `piece.py` module docstring said "empty scope reads nothing unless admin" (a stale
    copy-paste trap — the code has no admin bypass). **Corrected.**
  - NOTE (R2) — AC2 wording implied an admin might read with no scope. **Corrected** (no admin bypass).
  - LOW (R2) — `/original` has no chunk-streaming decrypt (AES-GCM whole-blob auth); per-request
    bounded by the ingest cap, aggregate scales with concurrency. **Documented** as an on-prem sizing
    note (callers are authenticated in-scope lawyers; streaming is a future refinement).
  Re-gate green.
