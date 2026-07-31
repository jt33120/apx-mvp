---
baseline_commit: 8e65763
---

# Story 3.5c-2 — Office & spreadsheet renderers: `.docx` / `.xlsx` → sanitized inline HTML

**Part of Story 3.5 (the pièce viewer), increment 3 of 4 (`3.5c`), sub-part 2.** The hybrid
rendering choice (Julian, 2026-07-31) renders **office** documents **server-side** (PDF/images are
client-side, Story 3.5d). This sub-part builds the first two server-side renderers — `.docx` and
`.xlsx` — as **sanitized inline HTML**, inside the tenant boundary, under the Story 3.5b scope
pre-filter + audit-on-open + render bound. It introduces the pièce-**render port**, the render
**app service**, the `/render` **endpoint** and a **sanitization structural gate** the later HTML
renderers reuse.

**Decomposition of `3.5c` (server-side renderers), by port shape / concern / dependency:**
- **3.5c-1** *(done, 8e65763)* — OCR word boxes captured + stored at ingestion (kind=`ocr-layout`).
- **3.5c-2** *(this)* — `.docx` (mammoth) + `.xlsx` (openpyxl) → **nh3-sanitized HTML**; the render
  port, app service, `/render` endpoint, the sanitization gate. **Adds mammoth + nh3** (pre-approved
  by Julian). All **in-process**.
- **3.5c-3** *(next)* — the `.msg` structured renderer (headers · body · reply chain), **reusing**
  this port / endpoint / gate but adding the **GPL-isolated out-of-process** worker render mode
  (AD-28 subprocess boundary — a distinct review concern). No new dependency.
- **3.5c-4** *(after)* — the **scanned-PDF page image + OCR overlay** (a different endpoint shape: a
  page-image stream + the layout JSON), consuming 3.5c-1's stored `ocr-layout`. No new dependency.

Status: done

## Story

As the pièce viewer that must **render** an office document (not dump its extracted text) inside the
firm,
I need a `.docx` or `.xlsx` pièce rendered **server-side to sanitized inline HTML** — scope-checked,
audited on open, bounded — with **no active content** (no script, no event handler, no `javascript:`
link, no remote resource) able to reach the browser,
So that a lawyer reads the document faithfully in the tenant boundary, and an **adversarial**
document (a `.docx`/`.xlsx` from opposing counsel) can never execute code or phone home when it is
displayed.

## Acceptance Criteria

**AC1 — The render port + the two office renderers.** A `PieceRenderer` port
(`core/ports/render.py`) returns a `RenderedDocument(format, title, html, truncated)` — `format`
is `"html"`, `html` is **already sanitized**, `truncated` says a render bound was hit (honest, never
silent). A `HtmlPieceRenderer` adapter (`adapters/render_html/`) implements it: `.docx` via
**mammoth**, `.xlsx` via **openpyxl** (read-only, values), each producing HTML. A format this
renderer does not handle (`.pdf`, `.png`, `.doc`, `.xls`, …) returns **`None`** — the edge then
offers the original (FR-44: never an empty pane). A **malformed** `.docx`/`.xlsx` also returns
`None` (offer the original), **never** a 500.

**AC2 — Every byte of rendered HTML is sanitized (the security spine).** All HTML the renderer
returns passes through **one** sanitizing constructor (`_rendered`) that runs **nh3** with a
**strict allow-list**: only structural / text-formatting / table tags and `a[href]` with a
`http`/`https`/`mailto` scheme. **Stripped:** `<script>`, every `on*` handler, `javascript:`/`data:`
URLs, `<iframe>`/`<object>`/`<embed>`/`<form>`/`<style>`, and **all images** (embedded figures live
in the original — offered, never inlined, in this increment). A `RenderedDocument` can be
constructed **only** inside `_rendered`, so no render path can emit unsanitized markup (a structural
property, AC6).

**AC3 — Scope pre-filter, audit-on-open, render bound (reuse 3.5b).** `GET
/api/pieces/{id}/render` runs the **scope pre-filter first** (`open_piece`, AD-13/14): out-of-scope
**and** absent return the **same** 404 (existence not disclosed, FR-14/FR-44). A successful render
writes **one** `open-piece` audit entry (FR-45), exactly as `/original` does (reading the rendered
content **is** opening the pièce). Over the **render byte bound** (`APX_PIECE_RENDER_MAX_BYTES`,
Story 3.5b) → **not** rendered: the edge answers `renderable:false` + a reason, offering the original
(never exhausting the client — the 3.5d density rule). An unrenderable format or a decrypt/absent
blob → the same `renderable:false` (no audit — no content was served; the later `/original` fetch is
the audited read).

**AC4 — The tenant boundary + no active content on the wire.** Rendering happens **in-process**
(mammoth pure-Python, openpyxl, nh3 — all local, offline, EU-safe): **no** pièce byte is sent to any
third-party rendering/conversion service (the EXPERIENCE contract's load-bearing promise). The
sanitized HTML is returned in a **JSON envelope** (a string field), not served as a top-level
`text/html` document from an app URL, so it never executes in the app origin; the SPA (3.5d) embeds
it sandboxed. The response carries `Cache-Control: no-store` (AD-29: a tenant-data response is never
cached; the systematic per-route sweep is a later deploy story, but attacker-derived content sets it
now).

**AC5 — Density is bounded, honestly.** A large `.xlsx` renders at most `max_rows`×`max_cols` per
sheet and `max_sheets` sheets (renderer constructor bounds), setting `truncated:true` when a bound
is hit — the reader's machine is protected and **nothing is hidden** (the truncation is declared).
The gross byte bound (AC3) is the first guard; these grid bounds are the second.

**AC6 — The sanitization gate.** A new structural check `rendered_html_is_sanitized` (AD-29/AD-33):
- **static** — in the render adapter, `RenderedDocument(...)` is constructed **only** inside
  `_rendered`, and `_rendered` calls `nh3.clean` (the one sanitizing choke point; mirrors the
  `one_chunk_writer` pattern).
- **behavioural (ungameable)** — the real `_sanitize` strips an **XSS battery** (`<script>`,
  `onerror`/`onclick`, `javascript:`, `<iframe>`, `<img>`), **and** a real end-to-end `.xlsx` built
  with adversarial cell values renders to HTML carrying none of them.

Registered in lock-step (registry + manifest + README) with the meta-checks green. Check count
**57 → 58**.

**AC7 — No over-build.** No `.msg` renderer (3.5c-3), no scanned-page image / OCR overlay (3.5c-4),
no PDF/image rendering (client-side, 3.5d), no React. New dependencies **exactly** mammoth + nh3
(pre-approved). No new DB column, no migration; alembic head unchanged; `apx/web` untouched.

## Dev Notes

**Design (against the code).**

1. **Port — `core/ports/render.py`** (NEW): frozen `RenderedDocument(format: str, title: str,
   html: str, truncated: bool)` + `PieceRenderer` Protocol with
   `render(self, *, filename: str, data: bytes) -> RenderedDocument | None`. Pure core; imports only
   stdlib/typing (no adapter — AD-4).
2. **Adapter — `adapters/render_html/renderer.py`** (NEW): `HtmlPieceRenderer(max_rows=2000,
   max_cols=64, max_sheets=32)`. `render` dispatches on the filename suffix: `.docx` → `_docx`,
   `.xlsx` → `_xlsx`, else `None`. mammoth / openpyxl / nh3 imported **lazily** inside the methods
   (house pattern: the app imports where a wheel is absent; a missing nh3 makes `_sanitize` raise →
   the render returns `None` → **fail-closed**, never unsanitized). The ONE constructor
   `_rendered(title, raw_html, truncated=False)` calls `_sanitize` (nh3 strict allow-list) — the
   only place `RenderedDocument` is built. `_docx`/`_xlsx` catch broadly and return `None` on any
   malformed input (offer the original), never raise.
3. **App service — `core/app/read/render.py`** (NEW): `render_piece(*, tenant, scopes, piece_id,
   reader, originals, renderer, max_bytes) -> RenderOutcome | None`. `open_piece` first (scope
   pre-filter; `None` → out-of-scope/absent → the edge 404s). Then the byte bound (via
   `originals.size`), then `originals.open` (fail-closed on absent/tampered → offer original), then
   `renderer.render`. Returns a frozen `RenderOutcome(matter, piece_id, document | None, reason)` —
   `document is None` means in-scope-but-offer-the-original. Imports core ports + `crypto`
   `DecryptionError` (core→core, allowed).
4. **Edge — `apx/api/app.py`** (UPDATE): `PieceRenderOut(piece_id, renderable, format?, title?,
   html?, truncated, reason?)`; `_piece_renderer()` (cached singleton, like `_original_store`);
   `GET /api/pieces/{id}/render` — `render_piece(...)`; `None` → 404 (`_PIECE_ABSENT`); a document →
   `audit_piece_open` + `renderable:true` + the sanitized html; no document → `renderable:false` +
   reason. Sets `Cache-Control: no-store`. Reuses `_render_bound()` (3.5b).
5. **Gate — `checks/renders_sanitized.py`** (NEW): `rendered_html_is_sanitized` (static: one
   `RenderedDocument` construction site, inside `_rendered`, which calls `nh3.clean`; behavioural:
   the XSS battery + a real `.xlsx` end-to-end). Registered in `registry.py`, `manifest.py`
   (`_p(...)`) and the README block. Count 57 → 58.
6. **Dependencies — `pyproject.toml`** (UPDATE): add **mammoth** (`.docx` → HTML; pure-Python, MIT;
   its one dep `cobble`) and **nh3** (HTML sanitiser; Rust/ammonia bindings, MIT; no Python deps) —
   both **local, offline, in-process, lazily imported** in the render adapter, like openpyxl/py7zr.
   `uv.lock` updated. `openpyxl` already present (Story 2.3).

**Why a JSON envelope, not `text/html`.** `/original` (3.5b) deliberately serves as
`application/octet-stream` + `nosniff` so uploaded markup cannot execute in the app origin. The
render endpoint returns the sanitized HTML as a **JSON string**, never a live top-level HTML
document at an app URL — so even a sanitizer miss cannot execute in-origin; the SPA embeds it in a
sandboxed frame (3.5d). Defense in depth: sanitize (server) + sandbox (client) + the app CSP.

**Boundaries / non-goals.** No `.msg` (3.5c-3), no scan image / overlay (3.5c-4), no PDF/image
(3.5d), no React. No image inlining (offered via the original). No new column, no migration.

**Files (expected).** `core/ports/render.py`, `core/app/read/render.py`,
`adapters/render_html/__init__.py`, `adapters/render_html/renderer.py`,
`checks/renders_sanitized.py` (NEW); `apx/api/app.py`, `apx/checks/registry.py`,
`apx/checks/manifest.py`, `README.md`, `pyproject.toml`, `uv.lock` (UPDATE); tests under `tests/`.

## Tasks / Subtasks

- [x] Add mammoth + nh3 (uv); reformat the pyproject entries house-style (licence + offline +
  lazy-import note), exact pins; `uv.lock` updated.
- [x] `RenderedDocument` + `PieceRenderer` port (core); `HtmlPieceRenderer` adapter: `_sanitize`
  (nh3 strict allow-list), the one `_rendered` constructor, `_docx` (mammoth), `_xlsx` (openpyxl,
  read-only, bounded) + tests (round-trip, malformed → None, unhandled suffix → None, XSS neutered,
  bound → truncated).
- [x] `render_piece` app service + `RenderOutcome` + tests (out-of-scope → None, over-bound → offer
  original, unrenderable → offer original, decrypt/absent → offer original, rendered → document).
- [x] `/api/pieces/{id}/render` endpoint: 404 non-disclosing, audit-on-render, `renderable:false`
  fallback, `no-store` + tests (scope, audit entry, fallback, a real docx/xlsx round-trip).
- [x] `rendered_html_is_sanitized` gate (static + behavioural) + registry/manifest/README lock-step
  + tests; full gate: ruff, pytest, checks (57 → **58**), alembic head unchanged, `apx/web`
  untouched.

## Dev Agent Record

### Completion Notes

- **Port + adapter.** `RenderedDocument(format, title, html, truncated)` is built at exactly ONE
  site — `_rendered(title, raw_html, truncated)` — which sanitises `raw_html` through nh3 with a
  strict allow-list before it is stored, so no render path can emit unsanitised markup. `_docx`
  (mammoth) and `_xlsx` (openpyxl, `read_only=True, data_only=True`, bounded rows/cols/sheets) both
  route through it; an unhandled suffix or any malformed input returns `None` (offer the original,
  FR-44) — never a raise. mammoth/openpyxl/nh3 are imported lazily; a missing nh3 makes `_sanitize`
  raise, so the render fails **closed** (returns None), never unsanitised.
- **Sanitiser.** Allowed: block/inline text tags, headings, lists, tables, `a[href,title]` with
  `http`/`https`/`mailto`. Stripped: script, every `on*`, `javascript:`/`data:` URLs, iframe/object/
  embed/form/style, and all `<img>` (embedded figures stay in the original — offered, not inlined).
- **App service.** `render_piece` runs `open_piece` first (scope pre-filter — out-of-scope is
  indistinguishable from absent), then the byte bound, then a fail-closed `originals.open`, then the
  renderer. `RenderOutcome(matter, piece_id, document|None, reason)`: `document is None` means
  in-scope-but-offer-the-original; the whole call returns `None` only for out-of-scope/absent.
- **Edge.** `GET /api/pieces/{id}/render` → 404 (non-disclosing) for out-of-scope/absent;
  `renderable:true` + sanitised html + `audit_piece_open` on a real render; `renderable:false` +
  reason (offer the original) over-bound / unrenderable / blob-unavailable, with **no** audit.
  `Cache-Control: no-store` (AD-29). Reuses the 3.5b render bound.
- **Gate.** `rendered_html_is_sanitized` (AD-29): static (one construction site, inside `_rendered`,
  which calls `nh3.clean`) + behavioural (the XSS battery neutered, and a real adversarial `.xlsx`
  end-to-end carries no script/handler/js-scheme/img). Registered lock-step; **58** checks.
- **No new column, no migration** (alembic head unchanged), `apx/web` untouched. New dependencies
  exactly **mammoth 1.12.0 + nh3 0.3.6** (+ mammoth's `cobble 0.1.4`), pre-approved.

### File List

- `apx/core/ports/render.py` (NEW)
- `apx/core/app/read/render.py` (NEW)
- `apx/adapters/render_html/__init__.py`, `apx/adapters/render_html/renderer.py` (NEW)
- `apx/checks/renders_sanitized.py` (NEW)
- `apx/api/app.py` (UPDATE — the render endpoint + `_piece_renderer`)
- `apx/checks/registry.py`, `apx/checks/manifest.py`, `README.md` (UPDATE — the gate, lock-step)
- `pyproject.toml`, `uv.lock` (UPDATE — mammoth + nh3)
- `tests/adapters/test_render_html.py`, `tests/app/test_render_piece.py`,
  `tests/api/test_piece_render_endpoint.py`, `tests/checks/test_renders_sanitized.py` (NEW)

### Change Log

- 2026-07-31 — Story 3.5c-2 implemented. Gate (pre-review): ruff clean, 926 passed / 11 skipped, 58
  structural checks (new `rendered_html_is_sanitized`, AD-29), no new migration (alembic head
  unchanged), no dependency beyond mammoth + nh3, `apx/web` untouched.
- 2026-07-31 — 3-reviewer adversarial pass (security/sanitisation · architecture/scope+audit ·
  correctness/tests/gate). Reviewer 3 died producing injection-shaped text (ignored as DATA); its
  correctness/gate lens was **self-completed by scratchpad probes — clean** (edge cases, bounds/
  truncated, gate ungameability, no over-build, deps scoped). Reviewer 1: the HTML-body
  sanitisation (the crux) is **airtight**, proven end-to-end against a real adversarial `.docx`
  through mammoth (javascript: hrefs stripped, base64 `data:` images removed, scheme obfuscation
  defeated, reverse-tabnabbing neutralised, the one `_rendered` site is the only builder in the
  tree, fail-closed-for-XSS confirmed). Reviewer 2: layering, single scoped read path,
  non-disclosure, audit-on-open all **verified correct**. Both verdicts **SHIP-WITH-FIXES**. Fixes
  applied:
  - MED (all three) — `.xlsx` was not fail-closed on a sanitiser/nh3 failure (its `_rendered` call
    sat outside the guard → a 500, contrary to AC1, asymmetric with `.docx`). **Fixed:** the
    `_rendered` call now sits inside `_xlsx`'s `try/except → None` (symmetric with `_docx`), AND
    `render_piece` wraps `renderer.render(...)` so any renderer that violates its no-raise contract
    still fails closed to offer-the-original — never a 500, never unsanitised. New tests: both
    renderers → None (not a raise) when the sanitiser fails; a raising renderer → offer-original.
  - LOW (R1/R2) — `RenderedDocument.title` (the untrusted pièce filename) is returned unsanitised.
    **Documented the contract** (port + adapter + `PieceRenderOut`): `title` is untrusted text the
    SPA renders as a text node, never innerHTML (same contract as `filename`); only `html` is
    embed-safe. Not escaped at source (that would corrupt a legitimate `Facture & Devis.xlsx`).
  - INFO (R1/R2): `Cache-Control: no-store` already covers both content responses (verified);
    scheme-less/relative `<a href>` are click-through nav, within the display-safety promise
    (`rel="noopener noreferrer"` set, images stripped). 3.5d must sandbox the render frame and
    render `title` as text (tracked on the 3.5d increment). Re-gate green.
