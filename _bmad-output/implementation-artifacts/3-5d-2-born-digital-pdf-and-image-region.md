---
baseline_commit: 329ee70
---

# Story 3.5d-2 — Born-digital PDF inline (PDF.js) — the viewer's closer

**Part of Story 3.5 (the pièce viewer), increment 4 of 4 (`3.5d`), sub-part 2 of 2 — the last.** 3.5d-1
shipped the viewer surface for every format the server endpoints fully back (scan, office/`.msg`,
image, fallback). This sub-part adds the **one screen that needs a client dependency**: a
**born-digital PDF rendered inline** — page-by-page to a canvas, **at the passage**, via **PDF.js**
(`pdfjs-dist`), entirely **inside the browser / tenant boundary** (no byte to any third party). It
makes the flagship flow real (Claire reads *« Bail commercial.pdf »* at Article 4, in the product).
With it, **Story 3.5 — the pièce viewer — is complete.**

**Decomposition of `3.5d`:** 3.5d-1 *(done, 329ee70)* the viewer surface · **3.5d-2 *(this)* born-digital
PDF via PDF.js.** *(The EXPERIENCE matrix's "image region box if the position resolves" is **N/A**: a
plain image gets no OCR layout at ingestion — there is no position source — so there is no region box
to draw. Dropped honestly, not deferred.)*

**Contract:** `EXPERIENCE-EPIC3.md` § *The pièce viewer* — the fidelity matrix's **Born-digital PDF**
row ("the pages · a text span scrolled-to + washed · page thumbnails") + Flow 7's climax beat. Binds
FR-44 · AD-29 (offline, no CDN/beacon) · AD-13/14 (scope pre-filter, already server-side) · FR-45.

Status: done

## Story

As **Maître Claire Fontaine**, opening a **born-digital PDF** (the most common legal format) at the
passage a search sent her to,
I need the PDF **rendered inline, page-by-page, with the passage scrolled-to and washed in gold**,
rendered **in my browser** with **no byte leaving the cabinet** and **no network call to any CDN**,
So that the flagship "read the actual document at the exact clause" flow is real for born-digital PDFs
(not just an offer-the-original fallback), while the tenant-boundary and offline guarantees hold.

## Acceptance Criteria

**AC1 — Born-digital PDF renders inline via PDF.js.** A `pdf` pièce with **no OCR layer** (`ocr:false`
— born-digital, the 3.5d-1 fallback bucket) now renders through a `PdfCanvas`: the bytes come from
`GET /api/pieces/{id}/original` (a same-origin `ArrayBuffer` — this fetch **is** the audited open,
FR-45), fed to `pdfjs.getDocument({ data })`. Each page renders to a `<canvas>`; the page rail lists
the page count; navigation renders one page at a time (progressive — the passage page first, the rest
on demand). The scanned-PDF path (`ocr:true`, `/page`+`/layout`) is unchanged.

**AC2 — Offline, in the tenant boundary (AD-29).** PDF.js makes **zero** network calls: the worker is
**bundled** (Vite `?url`, same-origin — never a CDN), `getDocument` is given the in-memory `data`
(no range/streaming fetch), and no `cMapUrl`/`standardFontDataUrl` points anywhere external (embedded
fonts render exactly; a rare un-embedded standard-14 font uses a metric fallback — **still no
network**). `enableScripting:false` + `isEvalSupported:false`: a malicious PDF's embedded JS never
runs; parsing happens in the isolated worker. No pièce byte leaves for any service.

**AC3 — The passage — "the tool sent you here."** The route's `?passage=` term is located in the PDF's
**text layer** (`page.getTextContent()`): the first page carrying it opens, the matching text run is
**washed in the `{components.passage-highlight}` gold** (a positioned overlay over the canvas, scaled
by the canvas viewport), and **scrolled into view** + made the **first focus stop** (keyboard-reachable
— the a11y floor). No match → the first page, no wash (the PDF still opens). The reading canvas is a
labelled region naming the pièce + format (as 3.5d-1's canvases).

**AC4 — The CSP admits PDF.js (and fixes the 3.5d-1 image path).** The backend's global CSP is
extended, minimally, to admit the offline viewer: `worker-src 'self' blob:` (the bundled PDF.js
worker), `'wasm-unsafe-eval'` in `script-src` (PDF.js's WASM image decoders — WASM only, **not** JS
eval), and `blob:` in `img-src` (the PDF.js/ canvas + **the 3.5d-1 inline-image `blob:` object-URL,
which the old `img-src 'self' data:` silently blocked**). `connect-src` stays `'self'` (**no external
origin is ever added** — the offline/tenant guarantee is intact); `frame-ancestors 'none'`,
`default-src 'self'`, `form-action 'self'`, `base-uri 'self'` are unchanged. A test asserts the new
sources are present **and** that no non-`'self'` `connect-src`/host source crept in.

**AC5 — Real density + failure paths (unchanged discipline).** A large born-digital PDF renders
**page-by-page** (never the whole document at once); over the 3.5d-1 render bound
(`renderable_inline:false`) it is **still** offered as the original (`FallbackCanvas`) — PDF.js is only
reached for an in-bound born-digital PDF. A corrupt/undecodable PDF → the honest offer-the-original,
never a blank pane or a crash. The 3.5d-1 `ImageCanvas` gains an `onError` → fallback (belt for a
decode/CSP failure).

**AC6 — No over-build / no regression.** PDF.js is **lazy-loaded** (dynamic `import()`, Vite code-split)
so the main bundle is unaffected until a born-digital PDF is opened. `pdfjs-dist` is the **only** new
dependency (pinned exact). No backend change beyond the CSP header (no new endpoint, no migration,
`apx/` Python logic untouched apart from the CSP string + its test). No PDF form-filling, annotations,
printing, or text selection beyond the passage highlight; no image region box (N/A, above).

## Dev Notes

**Design (against the code).**

1. **`apx/web/package.json`** — add `pdfjs-dist` (exact pin). MIT; bundled at build time; no Node
   runtime ships (AD-29).
2. **`apx/web/src/pdf.ts`** (NEW) — the PDF.js seam: lazy `loadPdfjs()` that dynamic-imports
   `pdfjs-dist`, sets `GlobalWorkerOptions.workerSrc` to the bundled worker URL
   (`pdfjs-dist/build/pdf.worker.min.mjs?url`), once. `openPdf(data)` → a document proxy;
   `findPassagePage(doc, passage)` scans page text for the term; helpers to render a page to a canvas
   and to get the passage run's viewport rect. All offline options set here.
3. **`apx/web/src/viewer.tsx`** (UPDATE) — a `PdfCanvas` component (fetch `/original` → ArrayBuffer →
   `openPdf` → render current page to canvas + passage overlay + rail); `classify` routes a born-digital
   PDF (`pdf ∧ ¬ocr ∧ renderable_inline`) to `PdfCanvas` (over-bound still → fallback). `ImageCanvas`
   gains `onError`.
4. **`apx/api/app.py`** (UPDATE) — extend `_CSP` (AC4). No other backend change.
5. **`tests/api/…`** (UPDATE) — assert the CSP admits the PDF.js worker/wasm/blob **and** keeps
   `connect-src 'self'` with no external host.

**Offline / security invariants (honour).** Worker bundled same-origin (never a CDN); `getDocument`
fed in-memory `data` (no fetch); no external cMap/font URL; `enableScripting:false`,
`isEvalSupported:false`; parsing in the worker; the passage overlay + filename rendered as
text/positioned nodes (never innerHTML). The `/original` fetch is the single audited open.

**Boundaries / non-goals.** No image region box (N/A — no position source), no text selection beyond
the passage, no annotations/forms/printing, no bundled standard-font data (offline fallback metrics),
no thumbnails endpoint, no backend logic change beyond the CSP.

**Files (expected).** `apx/web/src/pdf.ts` (NEW); `apx/web/src/viewer.tsx`, `apx/web/package.json`,
`apx/web/package-lock.json`, `apx/api/app.py` (UPDATE); a CSP test (UPDATE).

## Tasks / Subtasks

- [x] Add `pdfjs-dist` (exact pin 6.2.108); worker bundles offline (Vite `?url` → `/assets/pdf.worker.min-*.mjs`, same-origin); `vite build` green, PDF.js code-split into a lazy chunk (main bundle +4 kB only).
- [x] `pdf.ts` — lazy loader + worker config + `openPdf`→`{doc,destroy}` + `findPassagePage` (bounded, accent-insensitive) + `passageRectOnPage` (offline options; no external URL).
- [x] `viewer.tsx` — `PdfCanvas` (fetch→open→render+passage overlay+rail, render-cancel lifecycle), `classify` born-digital → PdfCanvas (over-bound → fallback), shared `PageThumbs` rail, `ImageCanvas` onError.
- [x] `app.py` — extend `_CSP` (worker-src 'self' blob:, 'wasm-unsafe-eval', img-src blob:) + test (new sources present, connect-src still 'self', no external host, no 'unsafe-eval'); backend gate green.
- [x] Gate: `tsc` + `vite build` (offline verified) green; ruff + 974 pytest + structural checks green; adversarial Workflow review; secret scan; commit.

## Dev Agent Record

### Completion Notes

- **Born-digital PDF inline.** A `pdf` pièce with no OCR layer (`ocr:false`, in-bound) renders through
  `PdfCanvas`: `/original` → `ArrayBuffer` (the single audited open) → `openPdf` (PDF.js, lazy). Each
  page renders to a `<canvas>` at a capped crisp scale; the page rail is the shared `PageThumbs`; the
  passage is located in the text layer, its page opened, its run **washed in gold** (a positioned
  overlay, fraction-of-canvas, scrolled-to + first focus stop). The scan path (`ocr:true`) is unchanged.
- **Offline / tenant boundary.** PDF.js is lazy-loaded (Vite code-splits the ~450 kB lib + emits the
  worker as a same-origin `/assets/…mjs` asset — never a CDN); `getDocument` is fed in-memory bytes
  with no external cMap/font URL; the built bundle's only `http(s)` strings are XML-namespace
  identifiers / license text (never fetched). `enableScripting` off (no scripting manager wired),
  `isEvalSupported:false`, parsing in the worker. **No pièce byte leaves the cabinet.**
- **CSP.** Extended minimally — `worker-src 'self' blob:`, `'wasm-unsafe-eval'` (WASM only, JS eval
  stays barred), `blob:` in `img-src` (this also **fixes the 3.5d-1 inline image**, which the old
  `img-src 'self' data:` silently blocked). `connect-src` stays `'self'` — no external origin, ever.
- **No over-build.** `pdfjs-dist` is the only new dependency; the CSP is the only backend change (no
  new endpoint, no migration, no logic change); the image region box is N/A (no OCR layout for a plain
  image → no position source), bundled font data is out of scope (offline fallback metrics).

### File List

- `apx/web/src/pdf.ts`, `apx/web/src/vite-env.d.ts` (NEW)
- `apx/web/src/viewer.tsx`, `apx/web/package.json`, `apx/web/package-lock.json`, `apx/api/app.py`,
  `tests/api/test_ingest_api.py` (UPDATE)

### Change Log

- 2026-08-04 — Story 3.5d-2 implemented. Gate (pre-review): tsc clean, vite build clean (PDF.js
  lazy-split, worker bundled same-origin), ruff clean, 974 passed / 12 skipped, pdfjs-dist the only new
  dependency, CSP the only backend change.
- 2026-08-04 — adversarial review as a **Workflow** (3 lenses — security/offline, correctness/state,
  contract/a11y — each finding skeptic-verified). **14 findings → 5 confirmed / 9 refuted** (6 of the
  refuted were INFO assurance passes verifying the offline / CSP / no-eval / single-audit / blob-fix
  invariants hold; the WASM-allowance-is-dead and canvas-inaccessible claims were refuted with
  grounds). The 5 confirmed collapsed to three real issues (one found by all three lenses):
  - HIGH (correctness) — a **superseded page render was never cancelled**: pdfjs forbids two renders
    on one canvas and throws on the *new* render, so under rapid rail navigation the wrong/blank page
    could win; interior-page decode errors were unhandled rejections. **Fixed:** hold the `RenderTask`,
    `cancel()` it in the effect cleanup (newest page wins), and wrap the whole render run in a
    try/catch so an undecodable interior page degrades to offer-the-original (rail stays navigable).
  - LOW — the **passage box was not cleared on navigation** (stale overlay over the new page during
    its render). **Fixed:** `setBox(null)` at the start of each render.
  - LOW — `findPassagePage` **parsed every page** for an absent term (slow open on a big PDF).
    **Fixed:** bound the scan to 80 pages; and (a refuted-but-valid consistency nit) made the passage
    match **accent-insensitive** (NFD-strip), matching the scan path's `normalise`.
  Re-gate green (tsc + vite build). Integrity manifest verified: the four files untouched by the fixes
  are byte-identical to the pre-review snapshot (the reviewers mutated nothing).
