---
baseline_commit: 78183de
---

# Story 3.5c-4 — Scanned-PDF page image + OCR overlay

**Part of Story 3.5 (the pièce viewer), increment 3 of 4 (`3.5c`), sub-part 4 (last).** The hybrid
rendering choice (Julian, 2026-07-31) renders a **scanned PDF** server-side as a **page image** with
an **OCR text layer over it**. This sub-part serves those two things — a rasterised **page image**
per page, and the **OCR word boxes** captured at ingestion (Story 3.5c-1) — so the viewer (3.5d) can
draw the recognised text over the page for selection, highlight, and the passage box. It reuses the
Story 3.5b scope pre-filter + render bound; it is a **different port/endpoint shape** from the HTML
renderers (bytes image + a boxes JSON, not sanitised HTML), so it adds no sanitisation gate.

**Decomposition of `3.5c` (complete after this):** 3.5c-1 *(done)* OCR positions at ingestion ·
3.5c-2 *(done, 9567991)* `.docx`/`.xlsx` → HTML · 3.5c-3 *(done, 78183de)* `.msg` → HTML ·
**3.5c-4 *(this)* scanned-PDF page image + OCR overlay.**

Status: done

## Story

As the pièce viewer that must let a lawyer **read a scanned document** with its recognised text over
the page,
I need each scanned-PDF page **rasterised to an image at the OCR dpi** (so it aligns with the stored
word boxes) and the **OCR layout** (page dims + word boxes + confidence) served for the overlay, both
inside the tenant boundary under the scope pre-filter + bound, opening the scan an audited act,
So that a lawyer reads the scan page-by-page without exhausting their machine, selects/searches the
recognised text positioned over the page, and no re-OCR happens at view time (the boxes were captured
at ingestion).

## Acceptance Criteria

**AC1 — The page-image endpoint (scan-gated, pixel-bounded).** *(Tightened after review.)* `GET
/api/pieces/{id}/page/{n}` rasterises page `n` (0-indexed) of a **scanned** PDF to a **PNG**, via a
`PageRasterizer` port (`Pdf2ImageRasterizer` adapter, poppler via pdf2image — already present, no new
dependency), at the **OCR dpi** (`_DPI=200`, the same dpi Story 3.5c-1 rasterised for OCR, so the
image pixel space matches the stored boxes). Scope pre-filter first (AD-13/14): out-of-scope OR
absent → **404** (FR-14/FR-44). Then three guards, **before poppler is invoked or the file loaded**:
it must be a **scan** (a stored OCR layer — a born-digital / no-layout PDF is client-rendered from
`/original`); the page must be **in range** and not a **pixel bomb** (its `width × height`, from the
stored layout, ≤ the pixel bound — so a tiny file declaring a giant page can't spike poppler); and the
file must fit the **scan byte bound**. Any of those, a missing/tampered blob, or poppler absent →
**409** (in-scope but not served here), never a 500. **One page at a time.**

**AC2 — The OCR overlay endpoint.** `GET /api/pieces/{id}/layout` serves the **stored** `OcrLayout`
JSON (kind=`ocr-layout`, Story 3.5c-1) — page dims + per-word boxes + confidence + dpi + the page
count — as `application/json`, decrypted within the tenant boundary. Scope pre-filter first:
out-of-scope, absent, **or no layout** (a born-digital / non-OCR pièce) → the **same 404** (discloses
nothing); a tampered blob → **409**. No re-serialisation — the stored, authenticated bytes are served
as-is.

**AC3 — Serving a page is an audited open (FR-45).** *(Revised after review — see the Change Log.)*
`/page` serves the document's **readable content**, so — like `/original` and `/render` — every
served page writes an `open-piece` audit entry. The one-per-open *granularity* is satisfied (FR-45
needs ≥1 entry per open); binding the sole audit to `/layout` was the defect (bypassable, and
**absent** for born-digital PDFs whose pages `/page` still served). The `/layout` fetch is overlay
**metadata** (word coordinates), not readable content, so it is **not** audited. So there is no
unaudited content path: a scan's pages audit on `/page`; a born-digital PDF is refused by `/page`
(AC1) and read via the audited `/original`.

**AC4 — Two server bounds.** A scan larger than `APX_SCAN_RENDER_MAX_BYTES` (config-as-data, default
128 MiB — above the 25 MiB inline bound, so a many-page scan renders page-by-page while a huge archive
is offered as the original) → 409, never loaded. **And** a page whose raster would exceed
`APX_SCAN_MAX_PIXELS` (default 100 Mpx) → 409 (the *pixel-bomb* guard, added after review — the byte
bound alone does not bound raster cost). Both protect the **server**; the client's per-page protection
is that it fetches one page at a time.

**AC5 — Tenant boundary + no active content.** Rasterising happens **in-process/on-box** (poppler
is a local binary in the image); decrypted bytes + poppler's temp output stay on the **encrypted data
volume** (`APX_DATA_PATH`, AD-31 — the Story 3.5c-3 lesson), removed after. The page is served as
`image/png` + `nosniff`; the layout as `application/json` + `nosniff`; both `Cache-Control: no-store`
(AD-29). A page image is inert (no active content); the layout is our own authenticated JSON.

**AC6 — No over-build.** No React (3.5d), no thumbnails endpoint, no passage-box drawing (the client
does that from the boxes), no re-OCR (the boxes are the stored ones), no `.docx`/`.xlsx`/`.msg` change.
No image rasterisation on the page endpoint (images are client-rendered from `/original`; only PDFs
rasterise). **No new dependency** (pdf2image/pillow already present), no new DB column, no migration;
alembic head unchanged; `apx/web` untouched. No new structural check (no sanitisation surface — the
scope/audit/read-path invariants are covered by existing gates). *(The `.msg` renderer is touched only
by the mechanical DRY extraction of the shared `spool_dir` — no behaviour change; the .msg tests are
unchanged in behaviour and still pass.)*

## Dev Notes

**Design (against the code).**

1. **Port — `core/ports/rasterize.py`** (NEW): `PageRasterizer` Protocol,
   `rasterize(self, *, data: bytes, page: int) -> bytes | None` — PNG bytes for page `n`, or `None`
   for a non-PDF / out-of-range page / any failure (the edge offers the original).
2. **Adapter — `adapters/render_image/rasterizer.py`** (NEW): `Pdf2ImageRasterizer(dpi=_DPI)`. Writes
   the decrypted bytes to a temp `.pdf` on the encrypted volume (`_spool_dir` — reads `APX_DATA_PATH`,
   as Story 3.5c-3), then `convert_from_path(path, dpi, first_page=n+1, last_page=n+1, fmt="png",
   output_folder=<vol tmp>)`, saves the one page to PNG bytes, cleans up both temps in `finally`.
   pdf2image/PIL imported lazily; a non-PDF, an out-of-range page, or absent poppler → `None`
   (fail-closed, offer the original). `_DPI` mirrors `ocr_tesseract._DPI` so image ↔ boxes align.
3. **App service — `core/app/read/scan.py`** (NEW): `read_scan_page(*, tenant, scopes, piece_id,
   page, reader, originals, rasterizer, max_bytes) -> ScanPageOutcome | None` — `open_piece` first
   (scope; `None` → 404), the scan byte bound (offer original over it — never loaded), a fail-closed
   `originals.open`, then `rasterizer.rasterize`. `ScanPageOutcome(matter, piece_id, png | None,
   reason)`: `png is None` → in-scope-offer-original; the whole call `None` → out-of-scope/absent.
   Mirrors `render_piece`.
4. **Edge — `apx/api/app.py`** (UPDATE): `_page_rasterizer()` (cached singleton); `_scan_bound()`
   (`APX_SCAN_RENDER_MAX_BYTES`, default 128 MiB). `GET /api/pieces/{id}/page/{n}` — `read_scan_page`;
   `None`→404, `png is None`→409, else `image/png` + `no-store` + `nosniff` (**no audit** — a tile).
   `GET /api/pieces/{id}/layout` — inline (mirrors `get_piece_original`): `open_piece`→404; a missing
   layout blob→404 (non-disclosing); a tampered blob→409; else `application/json` + `no-store` +
   `nosniff`, and **`audit_piece_open`** (the one audited open, FR-45).

**Boundaries / non-goals.** No React/3.5d, no thumbnails, no passage-box drawing, no re-OCR, no image
rasterisation on the page endpoint, no HTML-renderer change. No new dependency, column, migration, or
gate.

**Files (expected).** `core/ports/rasterize.py`, `core/app/read/scan.py`,
`adapters/render_image/__init__.py`, `adapters/render_image/rasterizer.py` (NEW); `apx/api/app.py`
(UPDATE); tests under `tests/`.

## Tasks / Subtasks

- [x] `PageRasterizer` port; `Pdf2ImageRasterizer` adapter (encrypted-volume temp, `_DPI`, fail-closed)
  + tests (mock pdf2image: page→PNG, out-of-range→None, non-PDF→None, poppler-absent→None; a real
  poppler test skipped if the binary is absent).
- [x] `read_scan_page` app service + `ScanPageOutcome` + tests (out-of-scope→None no read, over-bound
  →offer-original no load, absent/tampered blob→offer-original, non-rasterisable→offer-original,
  page→bytes).
- [x] `/api/pieces/{id}/page/{n}` endpoint: 404 non-disclosing, 409 offer-original, image/png +
  no-store + nosniff, **no audit** + tests.
- [x] `/api/pieces/{id}/layout` endpoint: 404 (out-of-scope/absent/no-layout), 409 tampered, JSON +
  no-store + nosniff, **audit-on-open** + tests; full gate: ruff, pytest, checks (58 unchanged),
  alembic head unchanged, `apx/web` untouched.

## Dev Agent Record

### Completion Notes

- **Rasteriser.** `Pdf2ImageRasterizer` rasterises page `n` of a PDF at `_DPI=200` (the OCR dpi, so
  the image pixel space matches the stored word boxes). The decrypted bytes and poppler's temp output
  stay on the **encrypted data volume** (`_spool_dir` → `APX_DATA_PATH`, AD-31), removed in `finally`.
  pdf2image/PIL are lazy; a non-PDF, an out-of-range page, or absent poppler → `None` (offer the
  original). One page per call — never the whole PDF beyond the read.
- **App service.** `read_scan_page` runs `open_piece` first (scope; empty scope reads nothing), then
  the scan byte bound (never loads an over-bound scan), then a fail-closed `originals.open`, then the
  rasteriser. Out-of-scope → `None` (→404); in-scope-can't-produce → `png=None` (→409, offer the
  original). Mirrors `render_piece`.
- **Endpoints.** `/page/{n}` serves `image/png` (nosniff, no-store), **no audit** (a visual tile of an
  already-opened pièce). `/layout` serves the stored, authenticated `OcrLayout` JSON (no
  re-serialisation), **audits the open once** (FR-45: the viewer fetches the layout exactly once per
  scan-open, so a paginated scan is one open / one record). Out-of-scope, absent, and no-layout all →
  the same non-disclosing 404; a tampered blob → 409.
- **No new dependency** (pdf2image/pillow already present), no column, no migration (alembic head
  unchanged), no new structural check (no sanitisation surface), `apx/web` untouched.

### File List

- `apx/core/ports/rasterize.py`, `apx/core/app/read/scan.py` (NEW)
- `apx/adapters/render_image/__init__.py`, `apx/adapters/render_image/rasterizer.py` (NEW)
- `apx/adapters/spool.py` (NEW — the shared encrypted-volume spool, DRY-extracted from the .msg
  renderer); `apx/adapters/render_html/msg.py`, `tests/adapters/test_msg_render.py` (UPDATE — use it)
- `apx/api/app.py` (UPDATE — the page + layout endpoints, `_page_rasterizer`, `_scan_bound`,
  `_scan_pixels_bound`)
- `tests/adapters/test_rasterizer.py`, `tests/app/test_read_scan_page.py`,
  `tests/api/test_scan_endpoints.py` (NEW)

### Change Log

- 2026-08-04 — Story 3.5c-4 implemented. Gate (pre-review): ruff clean, 966 passed / 12 skipped, 58
  structural checks, no new dependency (pdf2image/pillow already present), no migration, `apx/web`
  untouched. Also DRY-extracted the decrypted-plaintext spool dir into `apx/adapters/spool.py` (shared
  by the .msg renderer and the rasteriser — a security invariant in one place).
- 2026-08-04 — adversarial review as a **Workflow** (3 lenses — security/temp-file, architecture/audit,
  correctness/tests — each finding independently skeptic-verified). 10 findings → **4 confirmed, 6
  refuted** (false positives/cosmetic filtered by the verify stage). Fixes applied:
  - MED (security) — the byte bound did not bound RASTER cost: a tiny PDF declaring a giant page is a
    *pixel bomb* (poppler allocates GBs under the 128 MiB byte bound). **Fixed:** `read_scan_page`
    reads each page's exact dimensions from the stored OCR layout and refuses (`APX_SCAN_MAX_PIXELS`,
    default 100 Mpx) **before** poppler is invoked. + tests.
  - HIGH (architecture) + MED (security) — `/page` served readable content with **no audit**, and
    (worse) rasterised **born-digital / no-layout** PDFs whose only content path it was, leaving zero
    trail; the sole audit was bound to `/layout`, which is bypassable and 404s for those PDFs.
    **Fixed:** audit every served `/page` (content, like `/original`/`/render`); **gate `/page` to a
    stored OCR layer** (born-digital → 409, client renders `/original`); drop the `/layout` audit
    (metadata). No unaudited content path remains. + tests (born-digital 409, audit counts flipped).
  - MED (correctness) — AC2's "tampered layout → 409" had no firing test. **Fixed:** a test corrupts
    the on-disk `ocr-layout` blob and asserts `/layout` → 409, unaudited.
  - LOW/INFO (refuted, but addressed cheaply): documented the DRY refactor touches `msg.py` (AC6 note);
    the no-read paths now assert `originals.opened is False`. Re-gate green.
