---
baseline_commit: ebc2bc1763a03ecb7dc2ea20264ebfdc270c861b
---

# Story 2.3: Multi-format extraction — the largest surface

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a lawyer whose *matter* is mostly `.msg` with attachments and scanned PDFs,
I want text and structure extracted from every format a litigation *matter* actually contains,
so that the corpus is the *matter*, not the subset that happened to be easy to read.

## Scope of THIS story (read first)

The format surface is **already largely built** by the slices delivered in stories 2.1/2.2. This
story delivers only the **remaining** surface — chiefly `.msg` — plus the architectural obligations
that were deferred with it. Do **not** rebuild what exists; verify it and lock it with tests.

**Already delivered (verify + lock, do NOT re-implement):**
- Born-digital PDF via `pypdf` — [apx/adapters/extraction/files.py](../../apx/adapters/extraction/files.py) `_pdf`.
- `.docx` via stdlib zip+XML — same file, `_docx`.
- `.eml` body extraction (stdlib) + `.eml` attachment expansion (`EmlExpander` → N+1 pièces) —
  [apx/adapters/expansion/mail.py](../../apx/adapters/expansion/mail.py).
- Scanned-PDF + standalone-image OCR via Tesseract **inside the tenant boundary**, composed by
  `WithOcr` — [apx/adapters/ocr_tesseract/tesseract.py](../../apx/adapters/ocr_tesseract/tesseract.py).
- `custodian` + provenance inheritance through expansion —
  [apx/core/app/ingest.py:146](../../apx/core/app/ingest.py#L146) already threads `custodian` and
  `{prov}/{name}` to every member.
- Extraction **method + version** recorded on every piece — `ExtractOutcome.method/version`
  → `IngestedPiece.extraction_method/extractor_version`.
- Register classes `unsupported-format` / `extracted-empty` / `unreadable` / `extraction-error`
  wired and tested (~27 tests: `tests/adapters/test_extraction.py`, `test_ocr.py`,
  `test_expansion.py`, `tests/app/test_ingest.py`, `test_ingest_expansion.py`).

**This story adds:** (1) `.msg` extraction via **extract-msg 0.56.0 run out-of-process and
GPL-isolated**; (2) `MsgExpander` — `.msg` embedded attachments → N+1 pièces; (3) `.xlsx`
extraction via **openpyxl 3.1.5**; (4) the **structural seal** enforcing AD-28's isolation; (5) the
**subprocess I/O discipline** so a malformed document never leaks into the register.

**Explicitly deferred to Story 2.4** (state so it is not silently under-delivered): recursive
`.msg`-in-`.msg` / nested-container expansion, configurable recursion-depth and expansion-ratio
bounds, and the `container-unopenable` register class with cardinality `unknown`. Story 2.4
("Container expansion and the unit of the denominator") owns these (container three levels deep;
zip-bomb → register entry). This story does **single-level** `.msg` attachment expansion only; the
existing `MAX_DEPTH`/`MAX_MEMBERS` placeholders in `ingest.py` carry recursion until 2.4 formalises it.

**Out of scope (do NOT build):** Docling and `pdfplumber` (AD-28 permits them for layout-heavy PDF,
but no AC here requires them — born-digital `pypdf` + OCR already satisfy the PDF clauses); PyMuPDF
(**AGPL-3.0 — excluded outright** by AD-28); any chunking, retrieval, embedding, or failure-register
**table** work (the register table is Story 2.6; here failures are `IngestedFailure` values as today).

## Acceptance Criteria

**FR-3 (from epics — the format contract):**

1. **Given** *ingestion*, **when** it processes a *pièce*, **then** it extracts `.msg` (headers,
   reply chains, embedded attachments), born-digital PDF, scanned PDF via OCR, `.docx`, `.xlsx`, and
   standalone images via OCR, with OCR running **inside the *tenant* boundary** — no hosted OCR
   service (FR-3, §15; extract-msg out-of-process and GPL-isolated; Tesseract 5.5.2). *[born-digital
   PDF, `.docx`, scanned-PDF/image OCR = DONE; THIS STORY adds `.msg` and `.xlsx`.]*
2. **And** an email with N attachments yields **N+1 *pièces***, each with a stable identifier,
   provenance to its parent, and the parent's *custodian* inherited. *[DONE for `.eml`; THIS STORY
   extends the identical guarantee to `.msg` via `MsgExpander`.]*
3. **And** every *pièce* records **extraction method and extractor version**, so a transcription is
   distinguishable from a text layer and a re-extraction is detectable. *[Mechanism DONE; THIS STORY
   ensures `.msg` and `.xlsx` set distinct, stable `method`/`version` strings. Per AD-28 the version
   is part of the full text's identity and therefore of every `chunk_id` (AD-40) — do not change it
   casually once shipped.]*
4. **And** *(failure path)* an **unsupported format** enters the register as `unsupported-format`,
   counted in the *denominator*, never silently vanished. *[DONE; verify it still holds once `.msg`
   routing is added — a `.msg` whose parse is impossible is `unreadable`/`extraction-error`, a format
   with no extractor at all is `unsupported-format`.]*
5. **And** *(failure path)* an extraction that yields **no text** — blank scan, empty `.docx`, empty
   `.msg` — enters the register as `extracted-empty` and is **not** counted as in the *corpus*
   (otherwise an absence claim would assert it was searched). *[DONE for existing formats; verify for
   `.msg` and `.xlsx`.]*

**AD-28 (binding architectural obligations — this story must satisfy them even though the epics AC
text does not spell them out; the adversarial review WILL check them):**

6. **Out-of-process crash isolation.** `.msg` extraction runs in a **subprocess with its own
   resource bound** (a timeout). A subprocess that crashes, hangs past the timeout, exits non-zero,
   or returns unparseable output becomes a **failure-register entry** (`unreadable` /
   `extraction-error`), **never a worker death** and never a raise that escapes the adapter — the
   worker survives and the job proceeds (AD-28 + AD-17). *Asserted by test with a deliberately
   malformed `.msg` and with a worker that exceeds the timeout.*
7. **GPL / out-of-process structural seal.** A new static check (modelled on
   `no_queue_import_outside_submodule`) enforces, over the runtime tree, that: (a) `extract_msg` is
   imported **only** inside the designated isolated worker module; (b) a `subprocess` call site
   appears **only** inside `apx/adapters/extraction/`; (c) **no `stderr=None`** appears within the
   extraction adapters (stderr is always captured, never inherited/leaked). Registered in the runner
   + manifest + README, **with a failure-path fixture that actually fires** (AD-28 + AD-33/FR-56).
8. **Subprocess I/O discipline — no document leak.** A subprocess's `stdout`/`stderr` is **never**
   propagated verbatim into a failure-register entry, a log, a diagnostic, or an export. On failure
   the adapter maps to an enumerated `ErrorClass` and **discards** the captured text; it never puts
   subprocess-derived document text into `IngestedFailure.detail`. *Asserted by test: a malformed
   `.msg` carrying a **seeded token** in its body produces a failure whose class is set and whose
   `detail` (and any emitted log) does **not** contain the seeded token* (AD-28 extends AD-26's
   seeded-token discipline to malformed documents fed to each extractor).

## Tasks / Subtasks

- [x] **Task 1 — `.xlsx` extraction (AC: 1, 3, 5).** Add `.xlsx` to the file extractor via
  **openpyxl 3.1.5** (MIT, in-process — no isolation needed; AD-28's named Office tool).
  - [x] Add `openpyxl==3.1.5` to `pyproject.toml` `dependencies` (import it lazily inside the
    adapter method, matching the `pypdf`/OCR pattern, so the app still imports where it is absent).
  - [x] Read every sheet's cell values (read-only mode, `data_only=True` so cached formula values
    are read, not formula text); join to text. Empty workbook / all-blank → `extracted-empty`.
    A corrupt/unreadable file → `unreadable`. Set `method="openpyxl"`, a stable `version` string.
  - [x] *(Considered + rejected: stdlib zip+XML like `_docx`. The `.docx` precedent is stdlib, but
    `.xlsx` shared-strings/inline-strings/multi-sheet parsing is materially more error-prone and
    recall matters on a legal corpus; openpyxl is AD-28's named tool and MIT. If the dev prefers
    zero-dependency stdlib, it is acceptable ONLY if shared-strings + inline-strings + every sheet
    are handled correctly and tested.)*
  - [x] Tests: a real `.xlsx` → text; an empty workbook → `extracted-empty` (not in corpus); a
    truncated/corrupt `.xlsx` → `unreadable`. Method + version recorded.
- [x] **Task 2 — the `.msg` subprocess worker: the GPL/out-of-process boundary (AC: 1, 6, 8).**
  - [x] New module `apx/adapters/extraction/msg_worker.py` — a `python -m` entry point. It is the
    **only** place `extract_msg` is imported. It reads a `.msg` path + a mode from argv, parses with
    extract-msg, and writes a single **structured JSON** object to **stdout only**
    (`{ok, method, version, text, error_class, attachments:[{name, b64}]}`), routing extract-msg's
    own warnings/logging to **stderr** so stdout stays pure. Text mode = headers (from/to/cc/date/
    subject) + reply chain + body; attachments mode = the embedded attachments. It never prints
    document text to stderr.
  - [x] `text` reconstructs: routing headers, the reply/quote chain, and the body (extract-msg
    handles RTF-compressed bodies, TNEF, and charset recovery internally — that is *why* we take the
    GPL dependency instead of hand-rolling compound-file parsing). Empty body + no headers → signal
    `extracted-empty` in the JSON.
  - [x] Add `extract-msg==0.56.0` to `pyproject.toml` `dependencies` with a comment mirroring the
    psycopg LGPL note: **GPL-3.0-only, invoked out-of-process, never imported into the product
    process; distribution obligation (offer source, GPL §6) — to counsel per AD-28.**
- [x] **Task 3 — `MsgExtractor` + `MsgExpander` adapters over the subprocess (AC: 1, 2, 6, 8).**
  - [x] `apx/adapters/extraction/msg.py`: a shared `_run_msg_worker(path, mode)` helper that is the
    **single `subprocess` call site** (`subprocess.run([sys.executable, "-m",
    apx.adapters.extraction.msg_worker, mode, str(path)], capture_output=True, text=False,
    timeout=<config>)` — `capture_output=True` guarantees stderr is captured, never `None`). On
    non-zero exit / `TimeoutExpired` / JSON-decode error → return a clean failure signal; **discard
    stdout/stderr text** (AC8). Both classes live in `adapters/extraction` so the subprocess call
    site stays inside `adapters/extraction` (AD-28) while `MsgExpander` is still wired into the
    expander chain by the composition root (no adapter imports another adapter — AD-4).
  - [x] `MsgExtractor.extract(path)` (Extractor port): non-`.msg` → `unsupported-format`; `.msg` →
    run worker `text` mode, map JSON to `ExtractOutcome` (`ok` / `extracted-empty` / `unreadable`).
  - [x] `MsgExpander.members(path)` (Expander port): non-`.msg` → `None`; `.msg` → run worker
    `attachments` mode, return `[(name, bytes), ...]`; a worker failure is a broken container the
    ingestion use case already records as a failure (do not crash). Custodian + provenance are
    inherited automatically by `ingest._ingest_one` — do not re-implement that.
  - [x] Wire both into the composition root in **both** edges (keep them identical):
    [apx/adapters/store_postgres/queue/__init__.py:55](../../apx/adapters/store_postgres/queue/__init__.py#L55)
    `_build_extractor`/`_build_expander` and
    [apx/api/app.py:443](../../apx/api/app.py#L443) `_extractor`/`_expander`. Introduce a small
    `CompositeExtractor` (mirror `CompositeExpander`: first extractor returning a non-
    `unsupported-format` outcome wins) so `.msg` routes to `MsgExtractor` and everything else to
    `FileExtractor`, then wrap in `WithOcr`. Add `MsgExpander()` to the `CompositeExpander([...])`
    chain. *(A shared builder used by both edges is a welcome refactor but keep behaviour identical.)*
- [x] **Task 4 — the structural seal (AC: 7).** Add to
  [apx/checks/isolation_harness.py](../../apx/checks/isolation_harness.py), modelled on
  `no_queue_import_outside_submodule`:
  - [x] `no_extract_msg_import_outside_worker` — `extract_msg` (and `extract_msg.*`) imported only in
    `apx/adapters/extraction/msg_worker.py`.
  - [x] `no_subprocess_call_outside_extraction` — a `subprocess` import/call site appears only under
    `apx/adapters/extraction/` (AD-28's literal rule). *(Note: the existing `subprocess` use in
    `apx/checks/import_contracts.py` is build-time tooling, already excluded from the runtime tree by
    `_RUNTIME_EXCLUDE`, so it will not trip this.)*
  - [x] `no_stderr_none_in_extraction` — no `subprocess.*(..., stderr=None, ...)` (explicit or by
    omission where it matters) within `adapters/extraction`; stderr must be captured.
  - [x] Register each in [apx/checks/registry.py](../../apx/checks/registry.py), add a `_p(...)` row
    per check in [apx/checks/manifest.py](../../apx/checks/manifest.py) keyed to **FR-3 / AD-28**,
    and add matching lines to the README structural-properties block (the README↔manifest meta-checks
    will fail the build otherwise).
  - [x] Each check must **fail closed** on an unparseable file and accept injectable `roots`; add a
    **failure-path fixture** under `tests/_fixtures/structural_violations/` (mirror the existing
    `queue_leak/` fixture) that actually fires each check, plus a passing-tree assertion.
- [x] **Task 5 — subprocess I/O discipline test: no document leak (AC: 8).** A malformed `.msg`
  (and, if cheap, one malformed input per subprocess-backed extractor) carrying a **seeded token**
  in its body/name produces a failure whose `ErrorClass` is set and whose `IngestedFailure.detail`
  and any emitted log do **not** contain the seeded token. Assert the adapter puts **no** subprocess-
  derived text into `detail`.
- [x] **Task 6 — end-to-end + regression (AC: all).**
  - [x] An ingestion of a folder mixing `.msg` (with attachments), `.xlsx`, PDF, `.docx`, image,
    and an unsupported extension lands the correct counts: pieces in corpus, `unsupported-format` and
    `extracted-empty` in the register (counted in `submitted`), N+1 for the `.msg`, custodian
    inherited on members, `require_consistent()` holds.
  - [x] Full gate green: `.venv/bin/ruff check` (line-length 100, E/F/I/UP/B), `.venv/bin/python -m
    pytest`, `.venv/bin/python -m apx.checks` (all structural checks incl. the 3 new), the web
    typecheck if any web file is touched (none expected), alembic single head (no migration expected
    — this story adds no columns), fitness driver green.

## Dev Notes

### Governing architecture — AD-28 (read the section: ARCHITECTURE-SPINE.md `### AD-28`)

**AD-28 — "Extraction adapters run out-of-process and licence-isolated."** This is the spine that
owns this story. Verbatim load-bearing points:
- Each extraction engine sits behind the `Extractor`/`Ocr` ports and **runs in a subprocess with its
  own resource bound; a crash is a failure-register entry, never a worker death (AD-17).**
- **`extract-msg` 0.56.0 is invoked out-of-process and GPL-isolated.** PyMuPDF is **excluded** —
  AGPL-3.0. Permitted set this increment: `pypdf` 6.14.2 + `pdfplumber` 0.11.10 (born-digital),
  Docling 2.114.0 + Tesseract 5.5.2 (scanned/layout), `python-docx` 1.2.0 + **`openpyxl` 3.1.5**
  (Office). *(Web-verified 2026-07-27: extract-msg 0.56.0 is the current release, GPL v3;
  openpyxl 3.1.5 exists, MIT. Both pins are current + resolvable.)*
- Every extracted *pièce* records the extraction **method and extractor version**, and that version
  is **part of the full text's identity and therefore of every `chunk_id` (AD-40)** — a transcription
  is distinguishable from a text layer; a re-extraction under a new engine produces new *chunks*
  rather than mutating evidence under an existing citation. **Consequence: choose stable
  `method`/`version` strings and do not churn them.**
- **Licence position (stated completely, do not re-litigate — it is counsel's call, recorded by the
  architect):** `extract-msg` GPL-3.0 → out-of-process, **no import into the core**; PyMuPDF AGPL →
  excluded; `psycopg` LGPL → the one unavoidable in-process copyleft (the DB driver). The process
  boundary keeps `extract-msg` a *separate program* (aggregation, not a derivative work); the only
  residual obligation is offering extract-msg's source on distribution (GPL §6) — an on-prem
  packaging task, **not** contamination of proprietary code.
- **Subprocess I/O discipline (Rule):** stdout/stderr are **never** propagated verbatim into a
  register entry, log, diagnostic, or export — `pdfplumber`, `pypdf`, Docling and `extract-msg` all
  emit **document fragments, object streams and filenames** on malformed input, and malformed input
  is the *normal* case at the design target while the register is exportable. Map to an enumerated
  error class and **discard the text**; where a free-text diagnostic is genuinely needed, truncate it
  and pass it through the register's redaction function ([`redact`](../../apx/core/projection.py#L186)),
  whose output is inside AD-26's seeded-token test — extended by this story to seed tokens **inside
  malformed documents fed to the extractor**. Simplest safe choice for `.msg`: **store no
  document-derived free text at all** on failure.
- **Enforced as a structural property:** *"no `subprocess` call outside `adapters/extraction`, and no
  `stderr=None` within it."* That sentence is your AC7 check, verbatim from the spine.

### Other architecture constraints

- **AD-4 (dependency direction, checked):** `core/app/ingest.py` depends on the `Extractor`/`Expander`
  **ports** only, never on an adapter. **No adapter imports another adapter.** → Put `MsgExtractor`
  and `MsgExpander` in the **same** adapter package (`adapters/extraction/msg.py`) sharing one
  subprocess helper; the **composition root** (queue edge + API edge) is what imports adapters and
  assembles the composites — that is not an adapter→adapter import and is how the existing builders
  already work (they import `ZipExpander`, `EmlExpander`, `FileExtractor`, `TesseractExtractor`).
- **AD-17 (unit of work):** the out-of-process boundary is *also* the crash/hang isolation — a
  malformed compound file that would segfault or hang the parser dies in the subprocess and becomes a
  register entry; the worker's resumable loop + quarantine (Story 2.2) handle a unit that keeps
  killing the subprocess. Keep the adapter's failure path **non-raising** so a clean extraction
  failure is a register row, not a worker crash (a hard crash is what quarantine is for).
- **AD-33/FR-56 (structural properties):** *"a property with no check is not a property."* The three
  new checks must be registered in the runner **and** the manifest **and** the README, or the
  manifest meta-checks (`every_structural_property_has_a_registered_check`,
  `every_registered_check_is_in_the_manifest`, the README↔manifest pair) fail the build. Use verb
  `structural`. FR-3 is **not** in the FR-56 floor-of-13, so no floor membership to manage.

### Source tree — what to touch

- **NEW:** `apx/adapters/extraction/msg_worker.py` (GPL boundary, `python -m` entry, imports
  `extract_msg`), `apx/adapters/extraction/msg.py` (`MsgExtractor` + `MsgExpander` + `_run_msg_worker`
  subprocess helper), `apx/adapters/extraction/composite.py` (`CompositeExtractor`, mirror of
  `expansion/composite.py`), and `tests/_fixtures/structural_violations/*` fixtures + new tests
  (`tests/adapters/test_msg_extraction.py`, `tests/adapters/test_msg_expansion.py`,
  `tests/adapters/test_xlsx_extraction.py`, `tests/checks/test_extraction_isolation.py`).
- **UPDATE:** `apx/adapters/extraction/files.py` (add `.xlsx`), `apx/checks/isolation_harness.py`
  (+3 checks), `apx/checks/registry.py`, `apx/checks/manifest.py`, the checks README block,
  `apx/adapters/store_postgres/queue/__init__.py` (`_build_extractor`/`_build_expander`),
  `apx/api/app.py` (`_extractor`/`_expander`), `pyproject.toml` (+extract-msg, +openpyxl).
- **DO NOT TOUCH** (contract-frozen or other stories): `core/domain/extraction.py` (the
  `ExtractOutcome` value is sufficient), the payload schema, chunking, migrations (no DB change).

### Existing behaviour that must keep working (verify, don't break)

- `_ingest_one` routes to pieces/failures/exclusions with recursive expansion, threading `custodian`
  and `{prov}/{name}` provenance to members ([ingest.py:146](../../apx/core/app/ingest.py#L146)); the
  per-unit `max_bytes` guard fires **before** extraction (an oversized `.msg` is `resource-exhausted`
  before any subprocess runs). `WithOcr` tries the primary, then OCR only on `extracted-empty` /
  `unsupported-format` — make sure a `.msg` routed to `MsgExtractor` and returning `extracted-empty`
  does not then get sent to Tesseract as if it were a scan (Tesseract returns `unsupported-format`
  for `.msg`, so `WithOcr` keeps the primary result — verify with a test).
- Pre-existing note for the reviewer (not this story to fully fix): `ingest.py:136,156` set
  `detail=str(exc)` for a generic in-process extractor crash — a latent AD-28 concern for 2.6's
  register work. The `.msg` adapter must NOT rely on that path: it catches subprocess failure
  internally and returns a clean `ExtractOutcome`, carrying **no** document text.

### Testing standards

- `uv`-managed: `.venv/bin/python -m pytest`, `.venv/bin/ruff check` (line-length 100, select
  E/F/I/UP/B), `.venv/bin/python -m apx.checks`. No `pip`. Red-green-refactor per subtask.
- extract-msg / openpyxl import **lazily** inside the adapter/worker so the suite runs where the
  libraries or system binaries are absent; a test that needs a real `.msg`/`.xlsx` should build a
  tiny fixture or `pytest.importorskip` the library, mirroring how the OCR tests guard Tesseract.
- The isolation checks are pure AST over source — test them by pointing `roots` at a violating
  fixture (an `extract_msg` import outside the worker; a `subprocess` call under `core/`; a
  `stderr=None` in a fake extraction module) and asserting the check returns `ok=False`, plus a
  passing-tree assertion. This is exactly the pattern the 2.2 queue-seal test used; do **not** leave
  it vacuous (a check that passes even when the violation is present is the review's #1 target).

### Project Structure Notes

- Adapters under `apx/adapters/<family>/`; ports under `apx/core/ports/`; use cases under
  `apx/core/app/`; structural checks under `apx/checks/`. The `.msg` worker + adapters both live under
  `adapters/extraction/` specifically to satisfy AD-28's "subprocess only in `adapters/extraction`"
  while `MsgExpander` is composed into the expander chain by the edge builders (AD-4-clean).

### References

- [Source: ARCHITECTURE-SPINE.md#AD-28 — Extraction adapters run out-of-process and licence-isolated]
- [Source: ARCHITECTURE-SPINE.md#AD-4 — Dependency direction is one-way and checked]
- [Source: ARCHITECTURE-SPINE.md#AD-17 — The unit of work is one pièce]
- [Source: ARCHITECTURE-SPINE.md#AD-33 — Structural properties are static checks over source]
- [Source: ARCHITECTURE-SPINE.md#AD-40 — payload schema; extractor version ∈ full-text identity ∈ chunk_id]
- [Source: ARCHITECTURE-SPINE.md#AD-26 / core/projection.py `redact` — seeded-token content-free discipline]
- [Source: epics.md#Story-2.3 (FR-3) and #Story-2.4 (the deferred container/recursion surface)]
- [Source: apx/adapters/extraction/files.py, apx/adapters/expansion/{mail,archives,composite}.py,
  apx/adapters/ocr_tesseract/tesseract.py, apx/core/app/ingest.py — the existing extraction surface]
- [Source: apx/checks/isolation_harness.py::no_queue_import_outside_submodule — the seal to model]

## Dev Agent Record

### Agent Model Used

claude-opus-4-8[1m]

### Debug Log References

- Baseline (HEAD ebc2bc1) shows 6 failures when pytest runs without `.venv/bin` on PATH — a PATH
  artefact only: `import_contracts` shells out to `lint-imports` via `shutil.which`. With
  `PATH="$PWD/.venv/bin:$PATH"` the baseline is green (526 passed). All gates were run with that PATH.
- `apx/core/ports/embedding.py` is an untracked port for a future story (2.8, the embedder); it is
  clean and benign and was kept **out** of this story's changes (still `??`).

### Completion Notes List

- **`.xlsx` (Task 1):** added to `FileExtractor` via **openpyxl 3.1.5** (MIT, in-process, lazy
  import), `read_only=True, data_only=True` so cached values are read, never formula text; all
  sheets joined; empty → `extracted-empty`, corrupt → `unreadable`. Kept inside `FileExtractor`
  (method `"xlsx"`, existing `files/2` version — no churn to other formats' recorded version).
- **`.msg` surface (Tasks 2–3):** `msg_worker.py` is the sole `extract_msg` importer, run
  **out-of-process** (`python -m …`); headers + inline reply chain + body in `text` mode, top-level
  byte attachments in `attachments` mode; parse-time stdout redirected to stderr so stdout is pure
  JSON. `msg.py` holds the **one** `subprocess` call site (`capture_output=True` → stderr always
  captured), maps crash/timeout/garbage → `unreadable`, and **discards** the subprocess text (no
  document fragment reaches the outcome, a log, or the register). `MsgExpander` returns `None` when
  there are **no** attachments so an empty `.msg` becomes `extracted-empty` via the extractor rather
  than vanishing as a transparent-empty container (AC5); an embedded `.msg` attachment (a nested
  container) is left for Story 2.4. Wired at **both** edges (worker + API) via a new
  `CompositeExtractor` (`.msg` → `MsgExtractor`, else `FileExtractor`, wrapped in `WithOcr`).
- **Structural seal (Task 4):** three new AD-28 checks in `isolation_harness.py` —
  `no_extract_msg_import_outside_worker`, `no_subprocess_call_outside_extraction`,
  `no_stderr_none_in_extraction` — registered in the runner + manifest + README, each with a firing
  fixture. A dedicated test proves the GPL seal is **not vacuous** (green only because the worker is
  exempt; it fires when the exemption is removed).
- **No-leak (Tasks 5–6):** a seeded token in a malformed `.msg` reaches neither the register
  `detail` nor any log (real subprocess). A mixed-folder e2e (`.msg`+attachment, `.xlsx`, `.docx`,
  image, unknown ext) lands 4 in corpus / 2 `unsupported-format`, custodian inherited, member
  provenance recorded, inventory consistent.
- **Deferred to 2.4 (stated, not silently dropped):** recursive `.msg`-in-`.msg` / nested-container
  expansion, depth/ratio bounds, and the `container-unopenable` register class.
- **Known limitation (honest):** a VALID Outlook `.msg` cannot be synthesised from the standard
  library, so the *success* path is covered by (a) the worker's transform logic against a fake
  message object, (b) the adapter's mapping with the subprocess mocked, and (c) verification that
  every attribute the worker reads (`openMsg`, `.sender/.to/.cc/.date/.subject/.body/.attachments/
  .close`, attachment `.data/.longFilename/.shortFilename`) exists in the installed extract-msg
  0.56.0. What remains UNVERIFIED against the real library is the end-to-end *semantics* on a valid
  file (that `.body` carries the reply chain inline, that a real parse keeps stdout pure). The
  failure/crash/no-leak paths ARE exercised against the real subprocess.
- **Dependencies:** `openpyxl==3.1.5` (MIT) and `extract-msg==0.56.0` (**GPL-3.0**, out-of-process
  only) added to `pyproject.toml` + `uv.lock` via `uv add`; web-verified both pins are current.
- **Gate:** ruff clean (`apx tests`); **557 passed, 9 skipped** (+31 over baseline, no regressions);
  `python -m apx.checks` all green incl. the 3 new AD-28 checks + manifest/README meta-checks; no
  migration (no DB change) — alembic head unchanged at `0017`; no `apx/web` change → no JS typecheck.

### File List

**New (product):**
- `apx/adapters/extraction/msg_worker.py` — the GPL isolation boundary (out-of-process worker)
- `apx/adapters/extraction/msg.py` — `MsgExtractor` + `MsgExpander` + the one subprocess call site
- `apx/adapters/extraction/composite.py` — `CompositeExtractor` (routes `.msg` → `MsgExtractor`)

**New (tests / fixtures):**
- `tests/adapters/test_xlsx_extraction.py`
- `tests/adapters/test_msg_extraction.py`
- `tests/adapters/test_msg_expansion.py`
- `tests/adapters/test_multiformat_ingest.py`
- `tests/checks/test_extraction_isolation.py`
- `tests/_fixtures/structural_violations/extract_msg_leak/leaker.py`
- `tests/_fixtures/structural_violations/subprocess_leak/runner.py`
- `tests/_fixtures/structural_violations/stderr_none/leaky.py`

**Modified:**
- `apx/adapters/extraction/files.py` — `.xlsx` via openpyxl
- `apx/adapters/store_postgres/queue/__init__.py` — wire `.msg` extractor + expander at the worker edge
- `apx/api/app.py` — wire `.msg` extractor + expander at the API edge
- `apx/checks/isolation_harness.py` — three AD-28 structural checks
- `apx/checks/registry.py` — register the three checks
- `apx/checks/manifest.py` — three AD-28 manifest rows
- `README.md` — three AD-28 rows in the structural-properties block
- `pyproject.toml` — `openpyxl==3.1.5`, `extract-msg==0.56.0`
- `uv.lock` — resolved lock for the two new dependencies
- `tests/checks/test_structural_harness_checks.py` — the three checks in the green/fires harness

### Change Log

- 2026-07-28 — Implemented Story 2.3 (the remaining multi-format surface): `.xlsx` (openpyxl) and the
  `.msg` surface (extract-msg out-of-process + GPL-isolated, `MsgExtractor`/`MsgExpander`), sealed by
  three AD-28 structural checks, with the subprocess I/O no-leak discipline. Nested `.msg`-in-`.msg`
  deferred to 2.4. Status → review.
- 2026-07-28 — Addressed the adversarial 3-reviewer code review: 11 findings resolved (2 High, 4 Med,
  5 Low). Status → done.

## Senior Developer Review (AI)

**Reviewed:** 2026-07-28 — adversarial three-reviewer pass, each execution-verified against a fresh
tree, distinct lenses: **R1** AD-28 isolation/licence/subprocess-security, **R2** correctness &
data-integrity, **R3** test-quality/honesty/scope. **Outcome: Changes Requested** — implemented
behaviour was correct and the gate honestly green, but binding AD-28 guarantees were under-locked
and two seal checks were narrower than the property they claimed. All findings resolved below.

**Confirmed correct by the reviewers (no change):** extract-msg 0.56.0 attribute names verified
against the installed library (the valid-`.msg` success-path risk is retired); AC2 N+1 / custodian /
provenance; AC5 empty-`.msg` handling (the `MsgExpander→None` design); Composite/OCR routing;
edge-builder non-duplication (AST-identical); AD-40 method+version; licence honesty; crash/hang/
timeout isolation and the no-leak path (empirically proven); scope discipline (no over-build); the
2.4 deferral is genuine per Story 2.4's own ACs.

### Action Items — all resolved

**High**
- [x] **R2:** `_xlsx` did not catch `ET.ParseError` (valid-zip/malformed-sheet-XML `.xlsx` escaped
  → misclassified `extraction-error` and routed into ingest's `str(exc)` leak path). Fixed: a broad
  catch in `_xlsx_read` maps every openpyxl failure to `unreadable`, never leaking `str(exc)`; test
  `test_xlsx_with_malformed_sheet_xml_is_unreadable`.
- [x] **R3:** AC8 "stderr never inherited" was **unproven** — a mutation that inherited stderr
  reintroduced a real fd2 document leak and stayed green. Fixed: (a) a `capfd` fd-level test locks
  it; (b) the check now requires every extraction subprocess call to **capture** stderr.

**Medium**
- [x] **R2/R3:** `.xlsx` `data_only=True` silently dropped non-cached formula content (a false *not
  in corpus*) and the test that named it was vacuous (a literal, not a formula). Fixed: dual-read
  fallback (empty under `data_only` → re-read formulas/labels so the sheet is searchable — recall
  over precision); the test now uses a real formula and a formula-only fallback case is added.
- [x] **R3:** AC6's required "worker that exceeds the timeout" test was absent. Added
  `test_a_worker_that_exceeds_the_timeout_is_unreadable_not_an_outage` (real `TimeoutExpired`).
- [x] **R1:** `no_subprocess_call_outside_extraction` was import-only (missed `os.system`/`exec*`/
  `spawn*`/`pty.spawn`). Added a call-site leg; corrected the false "cannot exec without importing"
  docstring.
- [x] **R1:** the stderr seal matched only literal `stderr=None` (missed omission / `sys.stderr` /
  `subprocess.STDOUT` / raw fd). Strengthened to require capture and **renamed**
  `extraction_subprocess_captures_stderr` for honesty; evasion tests added.

**Low**
- [x] **R2:** `MsgExtractor` trusted present-but-empty worker fields; `.ok` used `bool(text)` not
  `.strip()`. Added a guard (whitespace-only text → `extracted-empty`; empty method/version →
  constants).
- [x] **R1:** the GPL seal missed dynamic `importlib.import_module`/`__import__("extract_msg")`.
  Added a dynamic-import scan.
- [x] **R1:** the vestigial `isolation_harness.run()` (4 stale checks) was deleted (the registry is
  authoritative).
- [x] **R3:** honesty — a "Known limitation" line about the untested valid-`.msg` *semantics* was
  added to the Completion Notes (previously only in test docstrings).
- [x] **R3:** `msg_worker` imported `extract_msg` OUTSIDE the `redirect_stdout` guard (a latent
  stdout-corruption on the success path). Moved inside the guard.

**Process note (not a code defect):** the three reviewers shared one working tree and mutation-tested
concurrently, briefly corrupting each other's gate runs. Future adversarial passes should run each
reviewer in an isolated git worktree.
