---
baseline_commit: c208c2e
---

# Story 3.5c-1 — OCR word positions captured at ingestion, stored encrypted at rest

**Part of Story 3.5 (the pièce viewer), increment 3 of 4, sub-part 1 of 2.** The hybrid rendering
choice (Julian, 2026-07-31) renders a scanned PDF server-side as a page image with an **OCR text
overlay**; the overlay needs per-word **bounding boxes**, which ingestion did not keep (it stored
only the OCR text). Julian chose to **store the positions at ingestion** (not re-OCR at render).
This sub-part captures + stores them; the renderers that consume them are 3.5c-2.

Status: done

## Story

As the pièce viewer that must draw an OCR overlay on a scanned page,
I need the **per-word bounding boxes** of every OCR'd pièce captured at ingestion and stored
encrypted at rest, content-addressed like the original,
So that a later render can position the recognised text (and highlight a passage) over the page
image, without re-running OCR at view time.

## Acceptance Criteria

**AC1 — Boxes captured (one OCR pass).** The Tesseract extractor produces, alongside the text, an
`OcrLayout`: per page, the page-image dimensions + DPI and each recognised word with its `text`,
bounding box (`left/top/width/height`, page-image pixel space) and `confidence`. It runs **one** OCR
pass (`image_to_data`), reconstructing the text from the same word data — no doubled OCR cost (the
`fr-fold-v1` normalisation makes the search index robust to whitespace-reconstruction differences).
A non-OCR extractor (pypdf/docx/…) produces **no** layout (`None`).

**AC2 — Stored encrypted, content-addressed, at rest (AD-31/AD-40).** When an OCR'd pièce is
ingested, its `OcrLayout` is stored via the `OriginalStore` as a second **kind** of blob keyed by
the SAME `content_hash` as the original — application-encrypted (AES-256-GCM), tenant-partitioned,
inside the tenant boundary. The **AAD binds the kind**, so an `ocr-layout` blob can neither be read
as the `original` nor relocated to another identity.

**AC3 — Only for OCR'd pièces.** A born-digital pièce (no OCR) stores **no** layout blob. A
retention failure on the layout is a register entry (never an escape), like the original's (AC6 of
3.5a). The original is still retained exactly as before.

**AC4 — Round-trips.** The stored layout is retrievable by `(tenant, content_hash, kind="ocr-layout")`
and deserialises back to the same `OcrLayout` (words, boxes, dims). Fail-closed on a missing/tampered
blob.

**AC5 — Encryption gate covers it.** The Story 3.5a `originals_are_encrypted_at_rest` gate is
extended so its behavioural leg proves a **kind** blob (not only the original) is ciphertext at rest.
Structural-check count unchanged (the check is strengthened, not added).

**AC6 — No over-build.** No renderers, no page-image rasterisation, no overlay drawing, no endpoint,
no React — those are 3.5c-2 / 3.5d. No new dependency (pytesseract's `image_to_data` already exists;
`pdf2image`/`pillow` already present). No new DB column, no migration (the layout is a blob keyed by
`content_hash`); alembic head unchanged.

## Dev Notes

**Design (against the code).**

1. **Domain — `core/domain/ocr_layout.py`** (NEW): frozen `OcrWord(text, left, top, width, height,
   confidence)`, `OcrPage(width, height, words)`, `OcrLayout(pages, dpi)` + `to_json()/from_json()`
   (a stable JSON shape for the blob). Pure domain, store-independent.
2. **`ExtractOutcome`** (`core/domain/extraction.py`, UPDATE): add `layout: OcrLayout | None = None`
   (defaulted, so every non-OCR caller and the `WithOcr` stub tests are unchanged; `WithOcr` returns
   the OCR outcome verbatim, so the layout passes through).
3. **`TesseractExtractor._ocr`** (`adapters/ocr_tesseract/tesseract.py`, UPDATE): switch to
   `pytesseract.image_to_data(page, lang, output_type=DICT)` per page; build an `OcrPage` (words with
   bbox + conf, filtering blanks/`conf < 0`) and reconstruct the page text (group by block/par/line,
   join). Aggregate pages into an `OcrLayout(dpi=200)`; return
   `ExtractOutcome(text, "tesseract", version, layout=…)`. Degrade paths unchanged.
4. **`OriginalStore` port + `FilesystemOriginalStore`** (UPDATE): add `kind: str = "original"` to
   `put`/`open` (and the private path/AAD). Path namespaces by kind
   (`{root}/{sha(tenant)}/{ch[:2]}/{ch}` for original, `…/{ch}.{kind}` for others). AAD becomes
   `apx-original:v1:{kind}:{content_hash}:{tenant}` — the kind is bound (no cross-kind relocation).
   *(No persisted blobs exist yet, so changing the AAD shape is free — no migration.)*
5. **Ingest** (`core/app/ingest.py`, UPDATE): after the original `put`, when `outcome.layout` is not
   None, `original_store.put(tenant, ch, layout.to_json().encode(), kind="ocr-layout")` — same
   `except OSError → RESOURCE_EXHAUSTED register` guard (a layout we cannot retain fails the pièce
   closed, like the original).
6. **Gate** (`checks/originals_encrypted.py`, UPDATE): the behavioural leg also puts a
   `kind="ocr-layout"` blob and asserts its on-disk bytes are ciphertext (the sweep already covers
   the whole root; add a kind-blob to the probe).

**Boundaries / non-goals.** No rasterisation, no overlay, no render endpoint, no React (3.5c-2/d). No
new dependency, no DB column, no migration.

**Files (expected).** `core/domain/ocr_layout.py` (NEW); `core/domain/extraction.py`,
`adapters/ocr_tesseract/tesseract.py`, `core/ports/originals.py`, `adapters/originals_fs/store.py`,
`core/app/ingest.py`, `checks/originals_encrypted.py` (UPDATE); tests under `tests/`.

## Tasks / Subtasks

- [x] `OcrLayout` domain value + JSON round-trip + tests.
- [x] `ExtractOutcome.layout`; Tesseract `_ocr` → `image_to_data` (boxes + reconstructed text, one
  pass) + tests (mocked `image_to_data`, and the real-OCR test still lenient).
- [x] `OriginalStore` `kind` (port + adapter, AAD binds the kind) + tests (kind round-trip, cross-kind
  relocation fails closed).
- [x] Ingest stores the layout for an OCR'd pièce (via the port); non-OCR → none; retention failure →
  register (existing guard) + tests.
- [x] Extend the encryption gate's behavioural leg to a kind blob; full gate: ruff, pytest, checks
  (unchanged 57), `tsc -b` unchanged, alembic head unchanged.

## Dev Agent Record

### Completion Notes

- **Domain**: `OcrLayout(pages, dpi)` / `OcrPage(width, height, words)` / `OcrWord(text, box, conf)`,
  with a stable, unicode-safe, compact `to_json`/`from_json`. `ExtractOutcome` gains
  `layout: OcrLayout | None = None` (defaulted — every non-OCR caller and the `WithOcr` stub tests
  are unchanged; `WithOcr` returns the OCR outcome verbatim so the layout passes through).
- **Tesseract**: `_ocr` now runs ONE `image_to_data(output_type=DICT)` pass per page, building the
  word boxes AND reconstructing the text from the same words (grouped into lines by
  block/paragraph/line) — no doubled OCR cost; `image_to_string` is gone. `fr-fold-v1` normalisation
  absorbs any whitespace-reconstruction difference in the search index.
- **OriginalStore**: a `kind: str = "original"` on `put`/`open`/`size` (port + adapter). The AAD is
  now `apx-original:v1:{kind}:{content_hash}:{tenant}` — the **kind is bound**, so an `ocr-layout`
  can never be read as (or relocated onto) the `original`. Path: `{ch}` for original, `{ch}.{kind}`
  for a derived kind; a `_SAFE_KIND` guard on the token. (No blobs persisted yet → the AAD-shape
  change is free.)
- **Ingest**: after the original `put`, an OCR'd pièce (`outcome.layout is not None`) also
  `put(…, kind="ocr-layout")` under the SAME `except OSError → RESOURCE_EXHAUSTED register` guard. A
  born-digital pièce stores no layout.
- **Gate**: the `originals_are_encrypted_at_rest` behavioural leg now puts a `kind="ocr-layout"` blob
  too and proves BOTH kinds are ciphertext at rest (the root sweep + a wrong-key open per kind).
  Structural-check count unchanged (**57** — strengthened, not added).
- **No new dependency** (`pytesseract.image_to_data` + `pdf2image`/`pillow` already present), no DB
  column, no migration (alembic head unchanged), `apx/web` untouched.

### File List

- `apx/core/domain/ocr_layout.py` (NEW)
- `apx/core/domain/extraction.py` (UPDATE — `layout` field)
- `apx/adapters/ocr_tesseract/tesseract.py` (UPDATE — `image_to_data` + `_words_and_text`)
- `apx/core/ports/originals.py`, `apx/adapters/originals_fs/store.py` (UPDATE — the `kind` param)
- `apx/core/app/ingest.py` (UPDATE — store the layout)
- `apx/checks/originals_encrypted.py` (UPDATE — behavioural leg covers a kind blob)
- `tests/domain/test_ocr_layout.py` (NEW); `tests/adapters/test_originals_fs.py`,
  `tests/adapters/test_ocr.py`, `tests/app/test_ingest_originals.py` (UPDATE)

### Change Log

- 2026-07-31 — Story 3.5c-1 implemented. Gate (pre-review): ruff clean, new tests green, 57
  structural checks (behavioural leg now covers a kind blob), no new dependency, alembic head
  unchanged, `apx/web` untouched.
- 2026-07-31 — 3-reviewer adversarial pass (crypto/kind-binding · OCR/reconstruction/architecture ·
  correctness/tests). Reviewer 1 died producing injection-shaped text (ignored as DATA); its
  crypto/kind lens was **self-completed by scratchpad probes — clean** (AAD injective under
  adversarial tenants/kinds, cross-kind relocation fails closed, `_SAFE_KIND` rejects traversal,
  layout ciphertext at rest, `from_json` fail-closed, original round-trips under the new AAD).
  Reviewer 2: *reconstruction faithful, boxes correct, architecture clean, no search regression*
  (proved `normalize(reconstruction) == normalize(image_to_string)`). Reviewer 3: **SHIP**, no
  HIGH/MED, every claim mutation-proven, no over-build. All LOW findings resolved:
  - LOW (R2) — the raster `dpi` was stamped `200` for every input, false for native-resolution
    images. **Fixed:** `dpi` threaded into `_ocr` (`_DPI` for PDFs, `0` = native for images);
    `_pdf_pages` now uses `_DPI` (one source of truth).
  - LOW (R2) — a non-numeric `conf` cell could discard the whole document's OCR. **Fixed:** a robust
    `conf` parse skips only that word, never the doc.
  - MED test-gap (R2) — the real-OCR path's layout was untested. **Fixed:** the real-OCR test now
    asserts the produced layout (boxed words, native `dpi=0`).
  - LOW (R3) — `from_json` fail-closed was unasserted. **Fixed:** a malformed-shape `pytest.raises`
    test. LOW (R3) — the layout retention-failure path was untested. **Fixed:** a layout-only
    failing store → the OCR pièce is a `RESOURCE_EXHAUSTED` register entry.
  - INFO/NIT (R2/R3) — the `_FailingStore` fake gained the `kind` param; the one-pass test now
    asserts `image_to_data` ran exactly once. Re-gate green.
