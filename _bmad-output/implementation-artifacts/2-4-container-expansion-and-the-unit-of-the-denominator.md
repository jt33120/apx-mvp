---
baseline_commit: cd4bbe5acd6f4845ead6ac511cef0ce1eb6cdb01
---

# Story 2.4: Container expansion and the unit of the denominator

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a lawyer,
I want archives, PDF portfolios and nested messages expanded, with every hidden *pièce* counted,
so that a `.zip` of 500 documents is not recorded as one missing file.

## Scope of THIS story (read first)

Recursive container expansion **already partly exists**; this story formalises its bounds as
configuration, adds the remaining container formats, and introduces the **`container-unopenable` /
cardinality-`unknown`** denominator concept. Do not rebuild the recursion — build on it.

**Already delivered (verify + build on, do NOT re-implement):**
- [apx/core/app/ingest.py](../../apx/core/app/ingest.py) `_ingest_one` already recurses through the
  `Expander` port, threading `{prov}/{name}` provenance and inheriting `custodian` to every member,
  bounded by **hard-coded** `MAX_DEPTH = 6` and `MAX_MEMBERS = 5000` (line 38-39) — these become
  config in this story. A zip-in-zip already expands.
- `ZipExpander` (`.zip`, with a per-member byte guard) —
  [apx/adapters/expansion/archives.py](../../apx/adapters/expansion/archives.py).
- `EmlExpander` (`.eml` attachments) — [apx/adapters/expansion/mail.py](../../apx/adapters/expansion/mail.py).
- `MsgExpander` (`.msg` attachments, **single-level** — it SKIPS an embedded `.msg` whose payload is
  a Message, explicitly deferred to THIS story in 2.3) —
  [apx/adapters/extraction/msg.py](../../apx/adapters/extraction/msg.py).
- `CompositeExpander` (the chain) — [apx/adapters/expansion/composite.py](../../apx/adapters/expansion/composite.py).
- The 2.2 ledger freezes `submitted` at **top-level** enumeration (`record_enumeration` ←
  `enumerate_units`) with a `provisional` flag on `ImportProgress`.
- The domain `Inventory` enforces `submitted = in_corpus + failures + exclusions` as ints —
  [apx/core/domain/inventory.py](../../apx/core/domain/inventory.py).

**This story adds:** (1) the remaining container formats — `.7z`, PDF portfolio, `.mbox`, and
nested `.msg`-in-`.msg`; (2) config-bounded depth / member-count / **expansion-ratio** /
attachments-per-message; (3) `ErrorClass.CONTAINER_UNOPENABLE` + `unknown_cardinality_entries` on
the domain `Inventory` (never summed, rendered in words); (4) the pièce counted **after** expansion,
`submitted` provisional while expansion is in progress.

**Explicitly deferred (state so; do NOT build or silently drop):**
- The **permanent on-screen denominator**, AD-38's full six-field record (`submitted_pieces`,
  `in_corpus`, `open_register_entries`, `excluded_as_noise`, `retired`, `unknown_cardinality_entries`),
  the **"denominator has no `int` representation in source" structural property**, the invariant test
  after every import/retry at the design target, filesystem-noise-as-a-named-line, and the home
  screen — **all Story 2.7** ("The inventory guarantee and the permanent denominator").
- The **full failure-register table** (resolution state, retry action, bulk retry, export) — **Story
  2.6**. Here a `container-unopenable` is an `IngestedFailure` value, as the other classes are today.
- **`.pst` / `.ost`** Outlook stores — OUT of scope: they need `libpff`/`libratom` and a
  client-confirmed export format (per `docs/context/05-stack-research-2026-07.md:264`, "the
  highest-value clarifying question"). "Mailbox export" here is **`.mbox`** (stdlib). Note `.pst`
  as deferred; do not attempt it.

## Acceptance Criteria

**FR-57 (from epics):**

1. **Given** a container — `.zip`, `.7z`, PDF portfolio, mailbox export, `.msg` nested in `.msg` —
   **when** it is ingested, **then** members become *pièces* carrying provenance **through** the
   container and inheriting its *custodian*, asserted with a container **three levels deep** (FR-57).
   *[`.zip` recursion DONE; THIS STORY adds `.7z`, PDF portfolio, `.mbox`, and nested `.msg`.]*
2. **And** recursion depth and expansion ratio are **bounded by configuration**, and a container
   exceeding either enters the register as `container-unopenable` **with the reason** — a zip bomb is
   a register entry, not an outage.
3. **And** a container that cannot be opened is **one entry with cardinality `unknown`**, and every
   *denominator* and absence claim states the unknown explicitly — *"1 archive unopened, contents
   unknown"*, **never** "· 1 not indexed".
4. **And** the unit of the inventory guarantee is the *pièce* counted **after expansion**, and
   *submitted* is frozen at completion of enumeration-and-expansion, declaring itself **provisional**
   while expansion is in progress.

**AD-17 / AD-38 (binding architectural obligations — the review will check these):**

5. **Bounds are configuration-as-data, never hard-coded (AD-17/AD-24).** `MAX_DEPTH`/`MAX_MEMBERS`
   become config keys, joined by `container_max_expansion_ratio` and `attachments_per_message_max`;
   each default preserves the guarantee; each surfaces as a `container-unopenable` register class,
   **never** an outage or OOM. Asserted with a zip-bomb (high ratio) and an over-deep container.
6. **`unknown_cardinality_entries` is never summed (AD-38).** It is added to the domain `Inventory`
   as a parallel annotation (the count of `container-unopenable` open entries); the invariant
   `submitted = in_corpus + failures + exclusions` continues to hold over **known** pièces (the
   container itself is one submitted unit / one failure); the field is **never** part of that sum and
   is rendered **in words**. Asserted by test: a folder with an unopenable container has a consistent
   inventory AND a non-empty unknown-cardinality phrase.

## Tasks / Subtasks

- [x] **Task 1 — config-bound the expansion (AC: 2, 5).** In
  [apx/core/domain/config.py](../../apx/core/domain/config.py), extend the *import-job capacity
  bounds* block (AD-17) with: `container_max_depth` (int, default 6 — today's `MAX_DEPTH`),
  `container_max_members` (int, default 5000 — today's `MAX_MEMBERS`), `container_max_expansion_ratio`
  (int, default e.g. 100 — total expanded bytes ÷ container bytes), `attachments_per_message_max`
  (int, default e.g. 1000). Each with a `valid=` range and a `governs=` string. Add matching rows to
  the README `<!-- config-keys -->` block (the reverse-completeness check fails the build otherwise).
- [x] **Task 2 — enforce the bounds in the use case (AC: 2, 3, 5).** In `ingest.py`, replace the
  module-level `MAX_DEPTH`/`MAX_MEMBERS` constants with values read from config (threaded through
  `ingest_folder`/`ingest_one_file`, like `max_bytes` already is). When a container **exceeds depth
  or the expansion ratio**, record it as **one** `IngestedFailure(error_class=CONTAINER_UNOPENABLE,
  detail=<reason>)` and stop expanding it (never recurse past the bound, never read a bomb whole).
  Track running expanded bytes vs the container's own size for the ratio. A container that raises on
  open is already a failure — make its class `container-unopenable` where it is a *container* (not a
  leaf `unreadable`).
- [x] **Task 3 — `ErrorClass.CONTAINER_UNOPENABLE` + `Inventory.unknown_cardinality_entries`
  (AC: 3, 6).** Add `CONTAINER_UNOPENABLE = "container-unopenable"` to
  [apx/core/domain/failures.py](../../apx/core/domain/failures.py). Add
  `unknown_cardinality_entries: int = 0` to `Inventory` — **NOT** part of `is_consistent`'s sum — and
  a helper that renders the words (`"N archive(s) unopened, contents unknown"`, or `""` when 0).
  `IngestionResult.inventory` computes it as the count of failures whose class is
  `CONTAINER_UNOPENABLE`. Keep `submitted = in_corpus + failures + exclusions` intact (the container
  is one submitted unit / one failure).
- [x] **Task 4 — `.7z` expander (AC: 1).** A `SevenZipExpander` (Expander port) via **py7zr 1.1.3**
  (LGPL-2.1-or-later, in-process — like psycopg; verify current version + offline install; note the
  LGPL position in `pyproject.toml`, imported lazily). Yields `(name, bytes)` members; a corrupt or
  password-protected `.7z` is a failure the use case records (a `.7z` bomb hits the ratio bound). Put
  it with the archive family (`adapters/expansion/`), wired into `CompositeExpander`.
- [x] **Task 5 — PDF portfolio / embedded files (AC: 1).** A `PdfPortfolioExpander` via **pypdf**
  (already a dep): read `/Names /EmbeddedFiles` from the catalog and yield each embedded file as a
  member. A plain PDF (no embedded files) yields `None` (a leaf — its text is a piece via the
  FileExtractor, unchanged). Import pypdf lazily.
- [x] **Task 6 — `.mbox` expander (AC: 1).** An `MboxExpander` via the stdlib `mailbox` module (no
  dependency): each message in the mbox becomes a member (a `.eml`-shaped `message/rfc822` byte
  payload the existing `.eml` path then handles, including its own attachments — recursion). `.pst`
  is NOT attempted (deferred). Put it with the email family (alongside `EmlExpander`).
- [x] **Task 7 — nested `.msg`-in-`.msg` (AC: 1).** UN-defer the `MsgExpander` skip: an embedded
  message attachment (worker `_attachments` currently drops a non-bytes `.data`) must become a member
  `.msg` so the ingestion use case recurses into it (its own attachments are then grandchildren,
  depth-bounded by Task 2). This requires the out-of-process worker to serialise an embedded message
  back to bytes — investigate extract-msg's embedded-message API (`Attachment.type`/`.data` is a
  `Message`; find the bytes path, e.g. `.save`/raw stream). Keep the GPL isolation (all extract-msg
  use stays in `msg_worker.py`). If a robust bytes path does not exist, record the embedded `.msg` as
  `container-unopenable` (cardinality unknown) rather than silently dropping it.
- [x] **Task 8 — provisional submitted (AC: 4).** The pièce is already counted post-expansion
  (members are pieces). Ensure the denominator **declares provisional while expansion is in progress**
  using the existing `ImportProgress.provisional` flag; keep the top-level unit count for processing
  progress. The permanent post-expansion `submitted_pieces` freeze + the full AD-38 record is 2.7 —
  do not build it here; just do not regress the provisional signal.
- [x] **Task 9 — tests + gate (AC: all).**
  - [x] A container **three levels deep** (e.g. `.zip` → `.7z` → `.eml`+attachment, or `.msg` nested
    in `.msg` nested in `.zip`) yields the innermost pièces with provenance through every layer and
    custodian inherited (FR-57).
  - [x] A **zip bomb** (declared/expanded size over the ratio) → one `container-unopenable` entry with
    the reason, worker survives, inventory consistent, unknown-cardinality phrase non-empty. An
    **over-deep** container likewise.
  - [x] Each new expander: happy path (members) + corrupt/broken (a recorded failure, never a raise).
    `.mbox` → N messages; PDF portfolio → embedded files; `.7z` → members; nested `.msg` → the
    embedded message becomes a member and recurses.
  - [x] `Inventory` with an unopenable container: `is_consistent()` holds AND
    `unknown_cardinality_entries == 1` AND the words phrase is non-empty; the field is never in the sum.
  - [x] Full gate: `.venv/bin/ruff check apx tests`, `.venv/bin/python -m pytest`, `.venv/bin/python
    -m apx.checks`, alembic single head (NO migration — no DB columns), fitness green. Run pytest with
    `export PATH="$PWD/.venv/bin:$PATH"` (else `import_contracts` fails on a missing `lint-imports` —
    a PATH artefact, not a real failure).

## Dev Notes

### Governing architecture

- **AD-38 — the denominator is a record of disjoint counts; `unknown` never enters a total** (read
  `### AD-38`). A `container-unopenable` entry **stands for an unknown number of pièces** and carries
  cardinality `unknown`. The full record's fields are `submitted_pieces` (post-expansion, frozen at
  enumeration completion), `in_corpus`, `open_register_entries`, `excluded_as_noise`, `retired`,
  `unknown_cardinality_entries`; the invariant is `submitted_pieces = in_corpus + open_register_entries`
  over **known** pièces; **`unknown_cardinality_entries` is never summed and is rendered in words**;
  and (2.7) *the denominator has no `int` representation anywhere in source*. **THIS story** introduces
  only the `container-unopenable` class + the `unknown_cardinality_entries` annotation on the current
  `Inventory` and its words-rendering; the full six-field permanent record + the no-int structural
  property are **2.7**. Do not collapse the denominator to an int; do not render an unknown as a
  number ("· 1 not indexed" is the exact anti-pattern AC3 forbids).
- **AD-17 — capacity bounds are configuration** (read `### AD-17`): *"Capacity bounds — pièce size,
  container depth, expansion ratio, attachments per message, … — are configuration with defined
  defaults, and each surfaces as a failure-register class rather than as an outage. The submitted set
  is frozen at the completion of enumeration-and-expansion."* This story turns the two hard-coded
  bounds into config and adds ratio + attachments-per-message. **A bound is a register entry, never a
  crash or an OOM** — do not read a bomb whole to measure it; use the declared/streamed size.
- **AD-4 — dependency direction, checked:** `ingest.py` depends on the `Expander` **port** only; the
  **composition root** (`queue/__init__.py` `_build_expander`, `api/app.py` `_expander`) wires the
  adapters. No adapter imports another adapter. New expanders implement the port and are added to the
  `CompositeExpander([...])` chain in **both** edges (keep them identical — the 2.2/2.3 reviews
  checked this).
- **AD-24 — configuration-as-data:** every bound is a `ConfigKey` with a default that preserves the
  guarantee; no `os.getenv`/literal bound in the runtime. The core never branches on a tenant.

### Existing code to touch — current state / change / preserve

- **`ingest.py`** — `_ingest_one` (line ~98) routes to pieces/failures/exclusions with recursive
  expansion; `MAX_DEPTH`/`MAX_MEMBERS` (38-39) and a `counter` bound members; `_ingest_one` already
  threads `custodian` + `{prov}/{name}`. **Change:** read bounds from config (thread them like
  `max_bytes`); add the expansion-ratio accounting; on a depth/ratio breach append **one**
  `container-unopenable` failure and stop expanding that container. **Preserve:** the three-way
  routing, the `max_bytes` guard firing before extraction, `require_consistent()`, the
  `elif not expanded` empty/leaf semantics (the 2.3 review confirmed these are correct — do not
  regress the `.msg`/`.eml` empty-container handling).
- **`inventory.py`** — a frozen `Inventory(submitted, in_corpus, failures, exclusions)` with
  `is_consistent`. **Change:** add `unknown_cardinality_entries: int = 0` (defaulted, so existing
  constructions still work) NOT in the sum; add a words helper. **Preserve:** `is_consistent` /
  `require_consistent` semantics — the sum must not change.
- **`failures.py`** — the enumerated `ErrorClass`. **Change:** add `CONTAINER_UNOPENABLE`. **Preserve:**
  the existing members (2.6 owns the full set + register table; a single class here matches how 2.2
  added `resource-exhausted`/`quarantined`).
- **`queue/__init__.py` + `api/app.py`** — `_build_expander`/`_expander` build
  `CompositeExpander([ZipExpander(), EmlExpander(), MsgExpander()])`. **Change:** add the new
  expanders; thread the config bounds into `ingest_one_file`/`ingest_folder`. **Preserve:** the
  builders stay behaviour-identical across the two edges.
- **`adapters/extraction/msg.py` + `msg_worker.py`** — `MsgExpander` skips embedded-message
  attachments (2.3). **Change:** surface an embedded `.msg` as a member (bytes from the worker),
  keeping all extract-msg use inside `msg_worker.py` (the AD-28 GPL seal — the structural check will
  fail if extract_msg leaks out; the subprocess-capture-stderr check still applies).

### New dependencies

- **py7zr 1.1.3** (LGPL-2.1-or-later) — `.7z`. In-process (LGPL, like psycopg — dynamic use of an
  unmodified LGPL library; to counsel with the extract-msg/psycopg note, AD-28's licence position).
  Fully offline once installed. **It pulls a heavy transitive tree** (pycryptodomex, pyppmd, pybcj,
  brotli, inflate64, multivolumefile, texttable) — declare with a licence comment, import lazily.
- No dep for `.mbox` (stdlib `mailbox`) or PDF portfolio (pypdf, already pinned 6.14.2).

### Testing standards

- uv-managed: `.venv/bin/python -m pytest`, `.venv/bin/ruff check` (line-length 100, select
  E/F/I/UP/B), `.venv/bin/python -m apx.checks`. No `pip`. Red-green-refactor per task.
- py7zr imports **lazily**; a test needing it `pytest.importorskip("py7zr")`. Build real fixtures:
  `.zip`/`.7z`/`.mbox` are writable from Python; a PDF portfolio can be built with pypdf's
  `add_attachment`. Nested `.msg` cannot be synthesised from stdlib — test the worker's embedded-msg
  transform against a fake message object + the adapter with the subprocess mocked (the 2.3 pattern),
  and the recursion mechanics through `ingest` with a mocked worker.
- Assert the **three-levels-deep** provenance string end-to-end and that custodian is on every leaf.
- The zip-bomb test must NOT actually allocate the bomb — assert the ratio bound fires on declared
  sizes before expansion (never read whole).

### Project Structure Notes

- Expanders under `apx/adapters/expansion/` (archive + email families) except the `.msg` one, which
  stays under `adapters/extraction/` for the AD-28 subprocess boundary. Config under
  `core/domain/config.py`. The use case stays `core/app/ingest.py` (port-only deps).

### References

- [Source: ARCHITECTURE-SPINE.md#AD-38 — the denominator is a record of disjoint counts; `unknown` never in a total]
- [Source: ARCHITECTURE-SPINE.md#AD-17 — capacity bounds are configuration; submitted frozen at enumeration-and-expansion]
- [Source: ARCHITECTURE-SPINE.md#AD-4 — dependency direction; the composition root wires adapters]
- [Source: ARCHITECTURE-SPINE.md#AD-24 — configuration-as-data]
- [Source: epics.md#Story-2.4 (FR-57), #Story-2.7 (the deferred permanent denominator), #Story-2.6 (the register table)]
- [Source: docs/context/05-stack-research-2026-07.md:264 — .pst/.ost need libpff/libratom + client confirmation (deferred)]
- [Source: apx/core/app/ingest.py, apx/core/domain/{inventory,failures,config}.py, apx/adapters/expansion/*, apx/adapters/extraction/msg*.py]

## Dev Agent Record

### Agent Model Used

claude-opus-4-8[1m]

### Debug Log References

- Run pytest with `export PATH="$PWD/.venv/bin:$PATH"` (else `import_contracts` fails on a missing
  `lint-imports` — a PATH artefact, not a real failure). `apx/core/ports/embedding.py` is a clean
  untracked port for a future story (2.8) — kept out of this story (still `??`).
- py7zr read: there is no `read`/`readall` on `SevenZipFile`; in-memory extraction is `extractall`
  to a temp dir + read back (already size-bounded before extraction). `FileInfo` exposes
  `.filename`/`.is_directory`/`.uncompressed`; `writestr(data, arcname)`.

### Completion Notes List

- **Container formats (Tasks 4–7):** `.7z` via **py7zr 1.1.3** (LGPL-2.1, in-process, lazy); PDF
  portfolio via pypdf's `.attachments`; `.mbox` via stdlib `mailbox` (each message → a member
  `.eml` that recurses, incl. its own attachments); nested `.msg`-in-`.msg` un-deferred — the
  GPL-isolated worker serialises an embedded message back to `.msg` bytes via extract-msg's `save`
  (an unserialisable one is surfaced with empty bytes and recorded as a failure, never dropped).
- **Config-bounded expansion (Tasks 1–2):** four AD-17 config keys (`container_max_depth`,
  `container_max_members`, `container_max_expansion_ratio`, `attachments_per_message_max`), an
  `ExpansionBounds` value object built from a tenant's config by both edges. The **ratio / member /
  attachment** breaches are checked against **declared** sizes/counts INSIDE the expanders, BEFORE
  decompressing — so a zip bomb is refused, never read whole — and raised as `ContainerUnopenable`;
  the **depth** breach is enforced in the use case. A corrupt / encrypted / unsupported archive is
  likewise `container-unopenable` (its contents unknown), and its reason names only the exception
  type — never a document fragment.
- **`container-unopenable` + cardinality `unknown` (Task 3):** `ErrorClass.CONTAINER_UNOPENABLE`;
  `Inventory.unknown_cardinality_entries` is a **subset annotation of `failures`**, NEVER summed
  into `submitted = in_corpus + failures + exclusions` (`is_consistent` also asserts `0 ≤ unknown ≤
  failures`), and rendered **in words** (`"N archive(s) unopened, contents unknown"`), never as
  "· N not indexed".
- **The unit is post-expansion; submitted provisional (Task 8):** members are pieces (already the
  unit); the ledger's `provisional` flag (Story 2.2) is unchanged and untouched — the permanent
  AD-38 six-field record + the no-`int` structural property are Story 2.7.
- **Wiring:** both edge builders (`queue/__init__.py::_build_expander`, `api/app.py::_expander`)
  build the identical bounded chain; the worker/API read the bounds from the tenant's config
  (`store.get_config`), the sync path defaulting when no store is configured. The `.msg` GPL seal
  and the subprocess-capture-stderr checks still hold (all extract-msg use stays in `msg_worker.py`).
- **Deferred (stated):** the permanent on-screen denominator, the full AD-38 record, the no-`int`
  structural property, and the invariant test at the design target — Story 2.7. The full failure
  register table — Story 2.6. `.pst`/`.ost` stores — out of scope (need libpff/libratom + a
  client-confirmed export format).
- **Gate:** ruff clean; **582 passed, 9 skipped** (+17, no regressions); `python -m apx.checks` all
  green (incl. config-defaults / documented-keys / reference-complete for the 4 new keys); NO
  migration (config keys are data, `ErrorClass`/`Inventory` are code) — alembic head unchanged 0017.

### File List

**New (product):**
- `apx/adapters/expansion/pdf.py` — `PdfPortfolioExpander` (pypdf embedded files)

**New (tests):**
- `tests/domain/test_inventory.py` — `unknown_cardinality` never summed + words phrase
- `tests/adapters/test_container_expansion.py` — the expanders, the bound breaches, three-levels-deep

**Modified (product):**
- `apx/core/domain/failures.py` — `ErrorClass.CONTAINER_UNOPENABLE`
- `apx/core/domain/inventory.py` — `unknown_cardinality_entries` (never summed) + words helper
- `apx/core/domain/config.py` — 4 container config keys + `ExpansionBounds` + `expansion_bounds`
- `apx/core/ports/expansion.py` — the `ContainerUnopenable` signal
- `apx/core/app/ingest.py` — config-bounded depth/members, `container-unopenable`, `bounds` threaded
- `apx/adapters/expansion/archives.py` — `ZipExpander` bounded + `SevenZipExpander` (py7zr)
- `apx/adapters/expansion/mail.py` — `EmlExpander` attachment cap + `MboxExpander`
- `apx/adapters/extraction/msg.py` — `MsgExpander` attachment cap + bounds
- `apx/adapters/extraction/msg_worker.py` — embedded-message serialisation (nested `.msg`)
- `apx/adapters/store_postgres/queue/__init__.py` — `_build_expander(bounds)`, config-read in `_persist_unit`
- `apx/api/app.py` — `_expander(bounds)`, config-read in `/api/ingest`
- `README.md` — 4 config-keys rows
- `pyproject.toml` / `uv.lock` — `py7zr==1.1.3`

**Modified (tests):**
- `tests/adapters/test_msg_expansion.py` — the embedded-message test updated for the un-defer

### Change Log

- 2026-07-28 — Implemented Story 2.4: container expansion (`.7z`/PDF portfolio/`.mbox`/nested `.msg`),
  config-bounded depth/members/expansion-ratio/attachments (a zip bomb is a `container-unopenable`
  register entry of cardinality `unknown`, refused by declared sizes before decompressing), and
  `Inventory.unknown_cardinality_entries` never summed + rendered in words (AD-38/AD-17). The
  permanent denominator + no-`int` property deferred to 2.7. Status → review.
