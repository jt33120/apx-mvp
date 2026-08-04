---
baseline_commit: 1dd7f20
---

# Story 3.5d-1 — The pièce viewer surface (React)

**Part of Story 3.5 (the pièce viewer), increment 4 of 4 (`3.5d`), sub-part 1 of 2.** The server-side
render engines are complete (3.5a original retention · 3.5b scoped read path · 3.5c-1..c-4 OCR
positions, `.docx`/`.xlsx`/`.msg` → sanitised HTML, scanned-PDF page image + OCR overlay). **This
sub-part is the React surface** that reads those endpoints and lets a lawyer *read the actual
document, at the passage, without a byte leaving the cabinet* — the screen, its chrome (bar · rail ·
canvas · foot), the **four states** (vide / chargement / erreur / densité réelle), the large-file
failure path, and the passage highlight — for every format the existing endpoints **fully** back.

**Decomposition of `3.5d`:** **3.5d-1 *(this)* the viewer surface** — scanned PDF (page image + OCR
box overlay + passage, progressive), `.docx`/`.xlsx`/`.msg` (sandboxed HTML iframe from `/render`),
inline images, and the honest fallback (born-digital PDF, over-bound, unrenderable → offer the
original) + the non-disclosing 404 + audit display + wiring the search hits into the route.
**No new dependency.** · **3.5d-2 *(next, the closer)*** born-digital PDF **inline via PDF.js** (offline
worker + text-layer passage highlight) + the image region box — the one screen that needs a client
dependency, isolated to its own review cycle.

**Contract:** `EXPERIENCE-EPIC3.md` § *The pièce viewer (Story 3.5)* + Flow 7 · tokens: `DESIGN.md` ·
key-screens mock: `mockups/epic-3-piece-viewer.html` (8 screens; this ports 7 of 8 — screen 1,
born-digital PDF at passage, is 3.5d-2). Binds FR-44 / FR-14 / FR-45 · AD-13/AD-14 / AD-29 / AD-31.

Status: done

## Story

As **Maître Claire Fontaine**, who has found a pièce (a suggestive hit, an exhaustive match, a `.msg`
attachment) and must **read it at the exact passage the tool sent her to**,
I need a **viewer route** that renders each format faithfully **inside the cabinet** — the scan as a
page image with its OCR layer, the office/email pièces as sanitised HTML, images inline, and anything
un-renderable as an honest *offer-the-original* — never an empty pane, never a byte to a third party,
the open **consigné**, and an out-of-scope pièce **indistinguishable from absent**,
So that reading happens in the product (*"lu"* becomes true), the passage is reached and washed, the
four density/loading/error/empty states never block or exhaust her machine, and the Chinese wall
holds right into the viewer.

## Acceptance Criteria

**AC1 — The viewer route + chrome.** A focused route `/piece/:pieceId` (react-router, already mounted)
gated by the owned session (`me()`; unauthenticated → the login/console at `/`). It renders the
`.pv` shell from the mock: **bar** (‹ retour · pièce name *as a text node* · format badge with the
**OCR honesty** variant when `ocr` · scope chip · *ouvert · consigné HH:MM* · ⤓ original · ×),
**structure rail** (adapts per format), **canvas** (the reading plane — the one surface allowed past
the 60 rem shell, per the contract's deliberate exception), and **foot** (*"Rendu dans le périmètre
du cabinet — aucun contenu n'a quitté l'infrastructure"*). Metadata comes from `GET /api/pieces/{id}`
(`filename`, `media_kind`, `ocr`, `byte_size`, `renderable_inline`).

**AC2 — Format dispatch (7 of 8 mock screens), each honest.** Driven by `media_kind` + `ocr` +
endpoint responses:
- **Scanned PDF** (`media_kind=pdf` ∧ `ocr` ∧ `/layout` 200) → **page image** (`/page/{n}` PNG) with
  the **OCR box overlay** (`/layout`), **progressive** (page 1 first, rail navigable, the rest fetched
  on demand), page-thumbnail rail + the **OCR-quality note**. The passage is a **box on the image**.
- **`.docx` / `.xlsx` / `.msg`** (`/render` `renderable:true`) → the sanitised `html` embedded in a
  **sandboxed iframe** (`sandbox=""` — no `allow-scripts`, no `allow-same-origin`: defence-in-depth
  over the server's nh3 sanitisation), styled to the mock's paper look. Rail: best-effort (a doc gets
  an *"ouvrir l'original"* affordance; the server render is a single HTML body).
- **Image** (`media_kind=image`) → the image inline (`<img>` from a same-origin **blob** of
  `/original`; the fetch is the audited open). No region box in 3.5d-1 (→ 3.5d-2).
- **Everything else** — born-digital PDF (`pdf` ∧ ¬`ocr`), an over-bound render, an un-renderable
  format — → the **honest fallback** (mock screens 5/8): name the limit, **offer the original**
  (FR-44), never an empty pane.

**AC3 — The four states (frontend-quality discipline).**
- **Vide / un-renderable** — never an empty pane: the centred *offer-the-original* panel; the "no pièce"
  resting state invites, never blanks.
- **Chargement** — **progressive**: the rail is navigable and page 1 renders while the rest streams; a
  skeleton keeps the chrome live. **Never a full-screen block, never a client exhausted.**
- **Erreur / hors-périmètre** — the **non-disclosing denial**: an out-of-scope OR absent pièce is the
  **same** *"Pièce introuvable"* (404) — no name, size, scope, or format leaks (FR-14/FR-44). A blob
  that no longer resolves (409) is shown as **degraded** (offer the original), never as though it
  resolves.
- **Densité réelle** — a 340-page scan reads page-by-page without exhaustion; **over the configured
  render bound** the viewer *refuses to render* and offers the original / a page-by-page read — the
  bound protects the machine and hides nothing.

**AC4 — The passage — "the tool sent you here."** Carried from the source (a chunk / a term) via the
route's `?passage=` (text) and/or `?page=` (0-indexed) query. For a **scan** the passage is the
**tested planted passage**: the OCR words matching the passage text are **boxed** with the
`{components.passage-highlight}` gold wash (the deliberate echo of the app's `::selection`), the box
**scaled by the rendered-image ÷ layout-page ratio** (image pixels ≠ layout pixels in general), and
**scrolled into view** by the parent (the canvas is the scroll container — no in-frame JS needed). The
passage is the **first focus stop** (keyboard-reachable). *(Highlight inside the sandboxed HTML frame,
and the born-digital-PDF text span, are 3.5d-2 — the scan box is the AC's planted passage here.)*

**AC5 — Opening is an audited act, surfaced (FR-45).** The content fetch **is** the audited open —
`/render` (renderable), `/page` (served), or `/original` (fallback / image blob) each write one
`open-piece` entry server-side (already built, 3.5c). The bar shows *"ouvert · consigné HH:MM"* once
the content has loaded, so Claire sees the act is recorded. Opening a `.msg` **attachment** navigates
to that attachment **as its own pièce** — its **own** audited open (a fresh `/piece/:id` route). The
metadata peek (`/api/pieces/{id}`) is **not** a content read and does not audit (server contract).

**AC6 — The tenant boundary + no active content.** No pièce byte (page image, OCR text, HTML, original)
is sent to any third party: `/render` HTML rides a JSON envelope into a **sandboxed** frame (never a
live top-level document); `/original` is fetched **same-origin** into an in-memory blob for `<img>`;
the foot line states the promise. The server already sets `no-store` + `nosniff` on every content
response (AD-29); the client adds no caching of pièce bytes.

**AC7 — Wiring + no over-build.** The search hits' inert *"ouvrir au passage →"* placeholders
(`SuggestivePanel` / `ExhaustivePanel`) become links to `/piece/:pieceId?passage=…`. **No new npm
dependency** (no PDF.js yet — 3.5d-2), no backend change, no new endpoint, no migration, `apx/` Python
untouched. No PDF.js, no inline born-digital-PDF, no image region box, no export-from-viewer, no
thumbnails endpoint (the rail derives from the layout page count) — all out of scope or 3.5d-2.
Verification is **`tsc -b --noEmit` + `vite build`** (the frontend carries no unit-test framework —
introducing one is a separate, dependency-bearing decision) **+ the frontend-quality visual loop**
(the 8-screen mock is the reviewed visual truth; a states-preview Artifact + a written cross-width
critique stands in for the headless-browser screenshot loop, which is unavailable in this
environment).

## Dev Notes

**Design (against the code).**

1. **`apx/web/src/api.ts`** (UPDATE) — viewer client + types: `PieceMeta`, `PieceRender`, `OcrLayout`
   (mirrors the server JSON: `{dpi, pages:[{width,height,words:[{t,l,o,w,h,c}]}]}`); `getPiece`,
   `getRender` (JSON), `getLayout` (JSON, 404 = not-a-scan), `pieceOriginalUrl`, `piecePageUrl`
   (the `<img src>` for a page). `ApiError.status` (already present) branches 404 (denial) vs 409
   (degraded / offer-original).
2. **`apx/web/src/viewer.tsx`** (NEW) — `ViewerRoute` (auth gate + `useParams`/`useSearchParams` +
   `useNavigate`) and `Viewer` (the `.pv` shell + the four states + format dispatch): `ScanCanvas`
   (progressive pages + `OverlayBox` scaled by `renderedW/layoutW`, `renderedH/layoutH`), `HtmlCanvas`
   (sandboxed iframe, `srcdoc` = a minimal wrapper + the sanitised html), `ImageCanvas` (blob `<img>`),
   `FallbackCanvas` (offer-original), `DenialCanvas` (404), `LoadingCanvas` (skeleton). The passage box
   is the first focus stop.
3. **`apx/web/src/main.tsx`** (UPDATE) — add `{ path: "/piece/:pieceId", element: <ViewerRoute/> }`.
4. **`apx/web/src/App.tsx`** (UPDATE) — the two hit lists' *"ouvrir au passage →"* become `Link`s to
   `/piece/:pieceId?passage=<term/snippet>`.
5. **`apx/web/src/tokens.css`** (UPDATE) — the viewer classes (`.pv`, `.pv-bar`, `.pv-rail`,
   `.pv-canvas`, `.pv-foot`, `.scan`/`.ocr`, `.sheet`, `.thumbs`/`.thumb`, `.center`, `.sk`,
   `.apx-passage`), aligned to the mock; the passage wash echoes `::selection`.

**Security notes carried from the 3.5c reviews (honour in this surface).**
- **Sandbox the render HTML frame.** `sandbox=""` (no scripts, no same-origin) is the belt to the
  server's nh3 braces — a bypass still cannot script the app origin or reach the session cookie.
- **`title` / `filename` / email `subject` are UNTRUSTED text metadata** — render as **text nodes**
  (React `{value}`), **never** `dangerouslySetInnerHTML`. Only the server's `html` is embed-safe (and
  even that is sandboxed).
- **Scale the OCR overlay by the image ÷ layout ratio** — the page image is rasterised at the OCR dpi
  so the spaces usually match, but the client MUST compute the ratio from the rendered `<img>`'s
  natural size and the layout page dims, never assume 1:1.
- **`/page` is scan-only** — a born-digital PDF returns 409; the client renders it from `/original`
  (3.5d-2 makes that inline via PDF.js; here it is the honest fallback).

**Boundaries / non-goals.** No PDF.js, no inline born-digital PDF, no image region box, no
export-from-viewer, no thumbnails endpoint, no frontend unit-test framework, no backend/Python change.

**Files (expected).** `apx/web/src/viewer.tsx` (NEW); `apx/web/src/api.ts`, `apx/web/src/main.tsx`,
`apx/web/src/App.tsx`, `apx/web/src/tokens.css` (UPDATE).

## Tasks / Subtasks

- [x] `api.ts` — `PieceMeta`/`PieceRender`/`OcrLayout` types + `getPiece`/`getRender`/`getLayout`/
  `pieceOriginalUrl`/`piecePageUrl`; 404 vs 409 branching.
- [x] `viewer.tsx` — `ViewerRoute` (auth gate, params, query) + `Viewer` (`.pv` shell, four states,
  format dispatch: scan / html / image / fallback / denial / loading), the OCR box overlay scaled by
  the image÷layout ratio, the passage as first focus stop.
- [x] `main.tsx` route `/piece/:pieceId`; `App.tsx` wire the two hit lists to the viewer route.
- [x] `tokens.css` — the viewer classes + the passage wash; align to the mock.
- [x] Gate: `tsc -b --noEmit` clean, `vite build` clean; visual verification (Artifact + cross-width
  critique); no new dependency; `apx/` Python untouched (backend gate unchanged from 1dd7f20).

## Dev Agent Record

### Completion Notes

- **The surface.** A focused route `/piece/:pieceId` (auth-gated by the owned session; unauthenticated
  → `/`) renders the `.pv` shell (bar · rail · canvas · foot). `getPiece` drives dispatch: **scan**
  (`pdf` ∧ `ocr`) → page image (`/page/{n}`) + OCR box overlay (`/layout`) + passage box, page-number
  rail + mean-confidence OCR note, progressive; **html** (`document`/`spreadsheet`/`email`) → the
  sanitised `/render` HTML in a **`sandbox=""` iframe** (no scripts, no same-origin) with a restrictive
  in-frame **CSP** and the passage washed via a safe `<mark>` splice; **image** → an inline `<img>`
  from a same-origin blob of `/original`; **else** (born-digital PDF, over-bound, un-renderable) → the
  honest **offer-the-original** fallback. The four states (vide / chargement / erreur-hors-périmètre /
  densité) are all present; the out-of-scope pièce is the **same non-disclosing 404** as absent.
- **Untrusted text** (`filename`) is rendered as **text nodes** only; the sole HTML embed is the
  server-sanitised render, sandboxed + CSP'd. **Audit-on-open** is the server's content fetch
  (`/render`/`/page`/`/original`); the bar's *"ouvert · consigné HH:MM"* is set only when real content
  loads (the fallback shows none until the original is fetched). The metadata peek does not audit.
- **No new dependency** (no PDF.js — 3.5d-2), no backend/Python change, no new endpoint, no migration.
  `apx/` Python untouched. Gate: `tsc -b --noEmit` clean, `vite build` clean.
- **Verification.** tsc + build (the frontend carries no unit-test framework, by design); the reviewed
  8-screen mock is the visual truth; a states-gallery Artifact + a written cross-width critique stood
  in for the (unavailable) headless-browser screenshot loop.

### File List

- `apx/web/src/viewer.tsx` (NEW)
- `apx/web/src/api.ts`, `apx/web/src/main.tsx`, `apx/web/src/App.tsx`, `apx/web/src/tokens.css` (UPDATE)

### Change Log

- 2026-08-04 — Story 3.5d-1 implemented. Gate (pre-review): tsc clean, vite build clean, no new
  dependency, `apx/` Python untouched.
- 2026-08-04 — adversarial review as a **Workflow** (3 lenses — security / correctness-state /
  contract-a11y — each finding independently skeptic-verified). **13 findings → 5 confirmed (1 an INFO
  assurance note), 8 refuted** (the egress/CSP concern, the StrictMode dev-only double-audit, the
  markFirst-sandbox note, etc. refuted with grounds). Fixes applied:
  - MED (correctness) — opening a scan at a passage on page N>0 mounted `<img src=/page/0>` before
    `current` corrected, and the server audits every served page → a **phantom `open-piece` entry** for
    page 0. **Fixed:** resolve the opening page synchronously in the `getLayout` `.then` (batched with
    `setState`), so ScanPage's first render targets the passage page — exactly one `/page` audit.
  - MED (a11y) — the reading canvas was not a **labelled region**. **Fixed:** `role="region"` +
    `aria-label` (filename + format + *ouvert au passage*) on the scan / html / image canvases.
  - LOW (contract) — the **loading** bar reused the denial phrase *"Pièce introuvable"*. **Fixed:** a
    neutral `emptyName` placeholder; *"Pièce introuvable"* is reserved for the genuine denial.
  - LOW (correctness) — `markFirst` could wash an earlier/wrong span. **Fixed:** search the raw text
    for the whole passage first, fall back to the first token.
  - Defense-in-depth (from the refuted egress finding) — added a restrictive **CSP** to the sandboxed
    srcdoc (`default-src 'none'`), so no rendered pièce can beacon a byte out even if nh3 ever regressed.
  Re-gate green (tsc clean, vite build clean). Integrity manifest verified: the four files I did not
  touch during fixes are byte-identical to the pre-review snapshot (the reviewers mutated nothing).
