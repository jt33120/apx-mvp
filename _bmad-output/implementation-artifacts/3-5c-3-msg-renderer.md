---
baseline_commit: 9567991
---

# Story 3.5c-3 — `.msg` renderer: headers · body · reply chain → sanitized inline HTML

**Part of Story 3.5 (the pièce viewer), increment 3 of 4 (`3.5c`), sub-part 3.** The hybrid
rendering choice (Julian, 2026-07-31) renders **email** server-side. This sub-part renders a `.msg`
(Outlook) pièce — its **routing headers, body (with the inline quoted reply chain), and attachment
names** — to **sanitized inline HTML**, **reusing** the 3.5c-2 render port, the `/render` endpoint,
the audit-on-open, the render bound, and the sanitization gate. Its one new concern is the **GPL-
isolated out-of-process worker** (AD-28): `extract-msg` (GPL-3.0-only) is never imported into the
product process, so the render's structured extraction runs in the existing `msg_worker` subprocess.

**Decomposition of `3.5c` (server-side renderers):** 3.5c-1 *(done)* OCR positions · 3.5c-2 *(done,
9567991)* `.docx`/`.xlsx` → HTML · **3.5c-3 *(this)* `.msg` → HTML** · 3.5c-4 scanned-PDF page image
+ OCR overlay.

Status: done

## Story

As the pièce viewer that must let a lawyer **read an email** inside the firm,
I need a `.msg` pièce rendered **server-side to sanitized inline HTML** — its headers, body (with the
inline reply chain), and its attachment names — via the **GPL-isolated** worker, under the same scope
pre-filter + audit + bound + sanitization as the office renderers,
So that opposing counsel's email is read faithfully in the tenant boundary, `extract-msg`'s GPL code
never enters the product process, and no header/body/attachment-name can inject active content.

## Acceptance Criteria

**AC1 — The `.msg` renderer, GPL-isolated.** A `MsgRenderer` (in `adapters/render_html`) implements
the 3.5c-2 `PieceRenderer` port for `.msg`: it obtains the structured email — `from`, `to`, `cc`,
`date`, `subject`, `body`, and attachment **names** — from the **out-of-process** `msg_worker` (a new
`render` mode), then builds HTML. `extract-msg` is imported **only** in `msg_worker` (the existing
GPL boundary — the structural check `no_extract_msg_import_outside_worker` still holds), and the
subprocess call stays inside `adapters/extraction` (`no_subprocess_call_outside_extraction` holds).
A non-`.msg` filename → `None`; a worker crash / timeout / empty / unreadable `.msg` → `None` (offer
the original, FR-44), never a raise, never a 500.

**AC2 — Attachments are named, not embedded.** A `.msg`'s attachments were expanded into their **own
pièces** at ingestion (Story 2.4's `MsgExpander`); this render **lists their names** (so the reader
knows they exist and opens each as its own audited pièce) and does **not** embed their bytes. The
`render` worker mode returns attachment names only — never attachment bytes into the render process.

**AC3 — Sanitized through the ONE site (reuse 3.5c-2's gate).** Every field (headers, body,
attachment names) is HTML-escaped and the assembled HTML is built through the **same** `_rendered`
constructor as the office renderers — so it passes the same nh3 strict allow-list. `MsgRenderer`
constructs **no** `RenderedDocument` of its own (it routes through `_rendered`); the
`rendered_html_is_sanitized` gate is **extended to scan the whole `render_html` package**, so the
one-construction-site invariant now covers the `.msg` path too. Check count unchanged (**58** —
strengthened, not added).

**AC4 — Composed, endpoint unchanged.** A `CompositePieceRenderer` (mirrors `CompositeExtractor`)
dispatches `.docx`/`.xlsx` → `HtmlPieceRenderer`, `.msg` → `MsgRenderer`, first non-`None` wins.
`GET /api/pieces/{id}/render` is **unchanged** — it already renders through the port under scope +
audit + bound; only the composed renderer at the edge (`_piece_renderer`) changes. A `.msg` render
is audited exactly like an office render (one `open-piece`).

**AC5 — Density bounded, honestly.** A pathological body is capped at `max_body_chars` (constructor
bound) with `truncated=True` — the reader's machine is protected, nothing hidden. The gross original
byte bound (3.5b/3.5c-2) is still the first guard.

**AC6 — No over-build.** No scanned-page image / OCR overlay (3.5c-4), no PDF/image (3.5d), no React.
No thread-turn parsing (the body carries the quoted chain inline, as Outlook stores it — faithful
without a parser). No `.msg` HTML-body rendering (plain-text body this increment; the HTML body is a
later refinement). **No new dependency** (`extract-msg` already present, still worker-only), no new
DB column, no migration; alembic head unchanged; `apx/web` untouched.

## Dev Notes

**Design (against the code).**

1. **Worker `render` mode** (`adapters/extraction/msg_worker.py`, UPDATE): a `_render(msg)` returning
   `{ok, from, to, cc, date, subject, body, attachments: [names], method, version}` — the same
   routing headers as `_text`, the plain-text `body` (inline quoted chain), and attachment **names**
   (`_att_name`, no bytes). No headers AND no body → `{ok: false, error_class: "extracted-empty"}`.
   `run(mode, path)` dispatches `mode == "render"`. The GPL isolation + I/O discipline are unchanged
   (extract-msg import + stdout redirect stay inside `run`).
2. **`structured_msg`** (`adapters/extraction/msg.py`, UPDATE): a thin wrapper —
   `structured_msg(path) -> dict | None` — calling `_run_msg_worker(path, "render")` (the existing
   subprocess site, timeout + failure discipline reused). `None` on any failure. `extract-msg` stays
   worker-only; this wrapper touches only the JSON.
3. **`MsgRenderer`** (`adapters/render_html/msg.py`, NEW): implements `PieceRenderer`. For `.msg`:
   `mkstemp` the decrypted bytes to a transient file (the worker reads a path — same pattern as
   ingestion's tmpdir), call `structured_msg`, `unlink` in `finally`; build escaped HTML (a header
   `<table>`, an `<hr>`, the body with `\n`→`<br>`, an attachment `<ul>`), cap the body at
   `max_body_chars` (`truncated`), and return via `_rendered(subject or filename, html, truncated)`.
   Any `OSError`/failure → `None`. Imports `_rendered` from `render_html.renderer` and `structured_msg`
   lazily (no subprocess, no extract-msg import here).
4. **`CompositePieceRenderer`** (`adapters/render_html/composite.py`, NEW): tries each renderer, first
   non-`None` wins (mirrors `CompositeExtractor`). The edge `_piece_renderer()` (`api/app.py`, UPDATE)
   returns `CompositePieceRenderer([HtmlPieceRenderer(), MsgRenderer()])`.
5. **Gate** (`checks/renders_sanitized.py`, UPDATE): scan **every `.py` under `adapters/render_html`**
   (not only `renderer.py`), and check RenderedDocument construction sites across **all** trees are
   inside `_rendered` (the current code only inspects the first tree — fixed). Behavioural leg
   unchanged (office battery + `.xlsx`); the `.msg` path is covered structurally (shared `_rendered`)
   + a `.msg` unit test. Manifest/README `inspects` prose updated to say "package" (machine cells
   unchanged; count stays 58).

**Boundaries / non-goals.** No 3.5c-4/3.5d work. No HTML-body email rendering, no thread-turn
parsing. No new dependency, no column, no migration.

**Files (expected).** `adapters/render_html/msg.py`, `adapters/render_html/composite.py` (NEW);
`adapters/extraction/msg_worker.py`, `adapters/extraction/msg.py`, `adapters/render_html/__init__.py`,
`api/app.py`, `checks/renders_sanitized.py`, `checks/manifest.py`, `README.md` (UPDATE); tests under
`tests/`.

## Tasks / Subtasks

- [x] Worker `render` mode (`_render`) + `run` dispatch + tests (fake msg → structured; empty →
  extracted-empty).
- [x] `structured_msg` wrapper + tests (mock `_run_msg_worker`: ok → dict; failure/None → None;
  non-.msg → None).
- [x] `MsgRenderer` (temp-file + assemble + `_rendered`) + tests (mock the worker: headers/body/
  attachments rendered + sanitized; adversarial fields neutralised; non-.msg → None; worker-None →
  None; body cap → truncated).
- [x] `CompositePieceRenderer` + edge wiring + tests (dispatch office/.msg/unknown).
- [x] `.msg` render endpoint test (mock worker → 200 renderable + sanitized + one audit).
- [x] Extend the gate to scan the render_html package (+ a doctored-msg.py test) + manifest/README
  prose; full gate: ruff, pytest, checks (58), alembic head unchanged, `apx/web` untouched.

## Dev Agent Record

### Completion Notes

- **Worker.** A `render` mode returns the routing headers + plain-text body (the inline quoted reply
  chain, as Outlook stores it) + attachment **names** — never attachment bytes. GPL isolation and the
  stdout-redirect I/O discipline are untouched; `extract-msg` stays imported only in `msg_worker`.
- **`MsgRenderer`.** Writes the decrypted `.msg` bytes to an `mkstemp` file (the worker reads a path;
  `unlink` in `finally`), gets the structure via the GPL-isolated worker, builds fully-escaped HTML
  (header table · body with `<br>` · attachment list), caps the body (`truncated`), and returns
  through the shared `_rendered` — so it is sanitised by the same nh3 allow-list and constructs no
  RenderedDocument of its own. Non-`.msg` / worker-failure → `None` (offer the original).
- **Compose.** `CompositePieceRenderer` dispatches by first-non-None; the `/render` endpoint is
  unchanged (the composite is wired at `_piece_renderer`). A `.msg` render audits once, like an
  office render.
- **Gate.** `rendered_html_is_sanitized` now scans the whole `render_html` package and unions the
  construction sites across all modules (the earlier single-tree check is fixed), so `MsgRenderer`
  (and any future render module) cannot emit unsanitised HTML. Count unchanged (**58**).
- **No new dependency** (extract-msg already present, still worker-only), no column, no migration
  (alembic head unchanged), `apx/web` untouched.

### File List

- `apx/adapters/render_html/msg.py` (NEW)
- `apx/adapters/render_html/composite.py` (NEW)
- `apx/adapters/render_html/__init__.py` (UPDATE — export the new renderers)
- `apx/adapters/extraction/msg_worker.py` (UPDATE — the `render` mode)
- `apx/adapters/extraction/msg.py` (UPDATE — `structured_msg`)
- `apx/api/app.py` (UPDATE — `_piece_renderer` returns the composite)
- `apx/checks/renders_sanitized.py` (UPDATE — scan the package)
- `apx/checks/manifest.py`, `README.md` (UPDATE — the gate's `inspects` prose)
- `tests/adapters/test_msg_render.py`, `tests/adapters/test_composite_renderer.py` (NEW);
  `tests/adapters/test_msg_worker_render.py` (NEW); `tests/api/test_piece_render_endpoint.py`,
  `tests/checks/test_renders_sanitized.py` (UPDATE)

### Change Log

- 2026-07-31 — Story 3.5c-3 implemented. Gate (pre-review): ruff clean, 942 passed / 11 skipped, 58
  structural checks (incl. the 3 AD-28 GPL-isolation gates + the package-scanned sanitisation gate),
  no new dependency, no migration (alembic head unchanged), `apx/web` untouched. (Mid-build: fixed a
  latent `_iter_py` behaviour — it globs a file-root's parent dir — by pointing the gate at the
  package directory and deduping trees by resolved path.)
- 2026-07-31 — 3-reviewer adversarial pass (GPL-isolation/subprocess/temp-file security ·
  architecture/gate-extension/composite · correctness/tests/over-build). Reviewer 1: GPL isolation +
  I/O discipline + temp-file cleanup + attachment-byte exclusion + sanitisation all **verified
  sound** (fragments → stderr → discarded, one JSON to stdout; `.data` never touched — tripwire; 0600
  temp unlinked on every path; 43-vector battery, zero live tags) — **SHIP**. Reviewers 2 & 3:
  reuse/composition/scope-audit + correctness/no-over-build/no-regression **verified correct** —
  **SHIP-WITH-FIXES**. Fixes applied:
  - MED (R2) — the sanitisation gate's static leg was **import-alias-gameable** (`RenderedDocument as
    RD; RD(...)` dodged it) and its behavioural leg covered only the office path. **Fixed:** the
    static leg now resolves each module's local binding of `RenderedDocument` (tracks `ImportFrom`
    asname) and matches against it — so the one-construction-site invariant is ungameable across the
    office, `.msg`, and any future render module (static-proves-routing + behavioural-proves-nh3 =
    airtight). New tests: an aliased bypass, and a second-module bypass named to sort AFTER
    renderer.py (R3's M1 — the old test passed for the wrong reason).
  - LOW (R2/R1) — `MsgRenderer` spooled decrypted `.msg` plaintext to the SYSTEM temp. **Fixed:**
    `mkstemp(dir=$APX_DATA_PATH)` (the encrypted volume, read per-render so the cached renderer stays
    correct), matching the store's on-volume-temp convention (AD-31).
  - LOW (R1) — `MsgRenderer.render` caught only `OSError`, so a non-OSError (a missing nh3, a
    MemoryError) could 500. **Fixed:** broad `except Exception` with the assembly + `_rendered` INSIDE
    the guard (mirrors `_docx`/`_xlsx`) — renderer-level fail-closed to None. New test.
  - LOW (R1) — the render body was materialised whole in the API process before the cap. **Fixed:**
    the ISOLATED worker caps the body (`_RENDER_BODY_MAX`) before it crosses to the product process,
    so a decompression-bomb body spikes only the subprocess (bounded by its timeout).
  - LOW/INFO (R3) — direct `structured_msg` test + `run("render")` dispatch test added; a headers-only
    email no longer emits an empty `<div>`; the `/render` docstring names `.msg`. INFO (R1/R3): the
    `.msg` subject rides `title` as untrusted text (documented contract) — the 3.5d viewer must render
    `title` as a text node (tracked on 3.5d). Re-gate green.
