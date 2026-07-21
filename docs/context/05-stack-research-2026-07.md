# Stack Research — On-Premise Legal Document Triage (July 2026)

> **Purpose.** Grounds an Architecture Decision Record for an on-premise, single-machine,
> offline-capable document-triage system for law firms.
> **Method.** Web search + direct fetch of upstream release pages, PyPI, and GitHub APIs
> during the week of 2026-07-21. Every version claim below carries a source.
> Where a claim could not be confirmed against a primary source it is marked **unverified**.

## Binding constraints (the fitness test every recommendation is judged against)

| # | Constraint | Consequence |
|---|-----------|-------------|
| C1 | Runs **unmodified on one machine, no internet** | No cloud calls, no license servers, no telemetry, no model download at runtime |
| C2 | Also runs on a hosted dev tier (Supabase / Vercel / Railway) with **no hard dependency** | Plain PostgreSQL only. **Supabase Auth and Supabase RLS are forbidden.** No Postgres extension that a managed provider may not have — or the extension must be optional |
| C3 | EU-only, zero-retention, no client data leaves the firm | Rules out all hosted embedding/LLM APIs for production data |
| C4 | 100 000 documents per matter, mostly `.msg` with attachments + scanned PDF | ~3–8 M chunks; extraction is the dominant engineering cost, not retrieval |
| C5 | One non-hands-on technical lead + AI coding agents | Boring, heavily-adopted, well-documented > clever. Anything needing specialist ops is a liability |

**Reading of C1 + C2 together:** the deployment must be *the same artefact* in both places.
Any component that exists only on-prem (a second database, a Redis, a GPU) is a divergence
between dev and prod and therefore a defect-generator for a one-person team.

---

## 1. Vector storage on a single on-prem machine (~100k docs / a few million chunks)

### Scale we are actually sizing for

100 000 documents, mostly `.msg` email. Email is short; attachments are long. A realistic
chunk yield is **3–8 M chunks per matter**. At 1024 dimensions in `float32` the raw vectors
alone are 4 KB each → **12–32 GB of raw vectors**. This number, not query latency, is what
drives the architecture. Every option below is really being judged on *how it behaves when
the vectors do not fit in RAM*.

### pgvector

- **Current version 0.8.5, released 2026-07-08.** Prior: 0.8.4 (2026-06-30), 0.8.3
  (2026-06-17), 0.8.2 (2026-02-25), 0.8.1 (2025-09-04), 0.8.0 (2024-10-30).
  Source: [pgvector CHANGELOG](https://github.com/pgvector/pgvector/blob/master/CHANGELOG.md)
- The 0.8.3–0.8.5 line is almost entirely **HNSW vacuum correctness and IVFFlat build memory**:
  0.8.3 "Fixed possible index corruption with HNSW vacuuming"; 0.8.4 "Fixed `hnsw graph not
  repaired` error with HNSW vacuuming" and "Fixed memory exceeding `maintenance_work_mem` with
  IVFFlat index builds"; 0.8.5 "Reduced memory usage for small tables for IVFFlat index builds".
  Source: same CHANGELOG.
  **Read this as maturity, not instability** — the feature surface has been frozen since 0.8.0
  and the work is hardening. That is exactly the profile you want for a component a
  non-hands-on lead must operate.
- **0.8.2 fixed CVE-2026-3172**, a buffer overflow in parallel HNSW index builds that could
  leak data from other relations or crash the server.
  Source: [PostgreSQL news, pgvector 0.8.2 released](https://www.postgresql.org/about/news/pgvector-082-released-3245/).
  **Action: pin ≥ 0.8.3 (0.8.5 preferred). Do not ship 0.8.0/0.8.1 in an offline bundle** —
  an air-gapped firm will not patch it for you.
- Index types available: **HNSW** (default choice), **IVFFlat**, plus `halfvec` (fp16),
  `bit`/binary and sparse vector types. Iterative index scans (0.8.0) fixed the long-standing
  "filtered query returns too few rows" problem, which matters here because every query is
  scoped to a matter.
- **Memory at our scale is the real constraint.** Published figures cluster around
  **~10–11 GB of effective memory per million 1536-dim vectors** including graph overhead,
  and a practical ceiling around **5–10 M vectors** on a normal single instance.
  Sources: [ClickHouse — scaling vector search in Postgres](https://clickhouse.com/resources/engineering/scale-vector-search-postgres),
  [Instaclustr pgvector performance](https://www.instaclustr.com/education/vector-database/pgvector-performance-benchmark-results-and-5-ways-to-boost-performance/).
  **Mitigation that changes the arithmetic:** use a 1024-dim model and store `halfvec`
  (fp16) → 2 KB/vector, roughly halving both index and heap. 5 M chunks at 1024-dim halfvec
  is ~10 GB of raw vectors, which fits a 64 GB machine comfortably and a 32 GB machine tightly.
- **Offline install:** `apt`/`yum` package, or bundled in the `pgvector/pgvector:pg18` Docker
  image. In a Compose bundle it is a layer inside an image you already ship — **zero extra
  install steps for the firm's IT contact**.
- **Managed-tier parity (C2):** pgvector is present on Supabase, Neon, RDS/Aurora, Railway.
  It is the *only* option in this list that is genuinely the same component in dev and prod.

### pgvectorscale (Timescale/TigerData) — the tempting upgrade

- Adds **StreamingDiskANN** (designed for larger-than-RAM datasets), statistical binary
  quantization, and label-aware filtering. It complements rather than replaces pgvector.
  Source: [Postgres vector search compared, 2026](https://www.web3aiblog.com/blog/postgres-vector-search-compared-pgvector-pgvectorscale-paradedb-lantern-2026).
- **It breaks C2.** Reported as available on Timescale Cloud and self-managed Postgres, **not**
  on RDS, and **not listed among Supabase's supported extensions**.
  Sources: as above, and [PostgreSQL extensions on Supabase](https://1bench.dev/extensions/postgresql/on-supabase).
  Shipping it would mean dev and prod run different index types — the exact divergence C2 forbids.
- **Verdict:** keep as a documented escape hatch for a firm whose matter genuinely exceeds RAM,
  behind a config flag, on the on-prem profile only. Do not make it the default.

### Qdrant

- **Current version v1.18.3, released 2026-07-17**; v1.18.0 2026-05-11, v1.17.1 2026-03-27.
  Source: [Qdrant releases (GitHub API)](https://github.com/qdrant/qdrant/releases). Apache-2.0.
- Runs perfectly well as a **single process, no cluster required**, with mmap-backed on-disk
  storage — this is a real strength and it is genuinely good at larger-than-RAM via
  quantization + mmap.
- **Qdrant Edge** (true in-process embedded, shares storage format with the server) is
  **in private beta as of 2026** and gated on partner selection.
  Source: [Qdrant Edge documentation](https://qdrant.tech/documentation/edge/),
  [Qdrant Edge blog](https://qdrant.tech/blog/qdrant-edge/).
  **A private-beta component cannot be the storage layer of an air-gapped legal product.**
- The Python client's "local mode" (`:memory:` or a path) is a *test double*, not the server
  engine, and is explicitly positioned for testing/small deployments — do not size a matter on it.
- **Cost under our constraints:** a second stateful service, a second backup story, a second
  upgrade path, a second thing to explain to the firm's IT contact, and no managed dev-tier
  equivalent that comes free with the Postgres we already have.

### LanceDB

- **Latest stable Python `lancedb` 0.34.0**, Apache-2.0, Python ≥ 3.10.
  Source: [lancedb on PyPI](https://pypi.org/pypi/lancedb/json).
  Node/Rust line is at **v0.32.0-beta.2 (2026-07-14)**; Python **0.35.0-beta.2 (2026-07-14)**.
  Source: [lancedb releases (GitHub API)](https://github.com/lancedb/lancedb/releases).
- **Genuinely embedded** — a library, not a server. No process to deploy, no port to open.
  Files on disk. This is the strongest offline story of any option here.
- Built on the **Lance columnar format** (v2.2 adds Blob V2, nested schema evolution, Map type).
  DuckDB can now read Lance datasets directly.
  Sources: [LanceDB docs](https://docs.lancedb.com/), [DuckDB — test-driving Lance](https://duckdb.org/2026/05/21/test-driving-lance).
- **Two problems for us.** (a) The release cadence is fast and heavily beta-tagged — version
  0.3x with weekly betas is not a stability profile a one-person team wants to track across
  air-gapped customer installs. (b) It is a *second* store: matter metadata, job state, audit
  trail and permissions all live in Postgres anyway, so LanceDB means keeping two data stores
  transactionally consistent by hand. That is the single most expensive kind of bug for an
  AI-agent-written codebase.

### Other credible options considered

- **ParadeDB / Lantern** — Postgres extensions, same C2 managed-availability problem as
  pgvectorscale. ParadeDB's real draw is BM25 full-text inside Postgres, which is worth
  revisiting *for hybrid search*, not for vector storage.
- **SQLite + sqlite-vec** — best-in-class offline story, but abandons Postgres for the whole
  app, breaking C2 outright. Not viable.
- **Chroma / Weaviate / Milvus** — Milvus needs etcd + object storage in any serious mode;
  Weaviate is a second server; Chroma's operational maturity at multi-million scale is
  **unverified**. All fail "one fewer component".

### What "keeping vectors inside PostgreSQL" is actually worth

It removes an entire deployable: one service, one backup (`pg_dump`/PITR covers vectors and
metadata in the *same consistent snapshot*), one upgrade, one set of credentials, one
network surface. It also makes the hosted dev tier and the on-prem install **the same
schema and the same queries**, which is the only way a one-person team keeps both working.
Crucially it makes "chunk row + its vector + its permission scope" a single transactional
object — you cannot end up with an embedding that outlives the document it came from.

> ### Recommendation 1 — **pgvector ≥ 0.8.5 on PostgreSQL 18.x, HNSW index, 1024-dim `halfvec`.**
> **Strongest reason:** it is the only option that is literally the same component in the
> hosted dev tier and in the air-gapped install, and it deletes an entire stateful service
> from a deployment that a non-specialist has to operate and back up.
> **Main risk:** HNSW memory at the top of the range — a genuinely large matter (>8 M chunks)
> on a small box will degrade badly, and the escape hatch (pgvectorscale StreamingDiskANN)
> is not available on the managed dev tier, so it would be an on-prem-only code path.
> Mitigate by measuring chunk yield on a real 100k-document corpus **before** committing,
> and by keeping the vector column type behind a migration you can change.
>
> Corollary: PostgreSQL **18.4** (released 2026-05-14) is the version to target;
> 18.4 fixed 11 security vulnerabilities and 60+ bugs. PostgreSQL 19 is at Beta 2
> (2026-07-16) — **do not ship a beta into a law firm**.
> Sources: [PostgreSQL 18.4 release announcement](https://www.postgresql.org/about/news/postgresql-184-1710-1614-1518-and-1423-released-3297/),
> [PostgreSQL versioning policy](https://www.postgresql.org/support/versioning/).

---

## 2. Single-process job queue and worker model in Python

### The requirement, stated precisely

Ingesting 100 000 `.msg` files is a **long, restartable, idempotent batch**, not a stream of
web-request-triggered tasks. The failure mode that matters is: *the machine reboots at
document 61 402 and the paralegal restarts the job.* Nothing may be lost, nothing may be
processed twice, and progress must be visible. This is a **durable state** problem, and the
queue is really a table of work items with a status column.

### Redis-backed options

| Library | Current state | Verdict under C1/C2 |
|---|---|---|
| **Celery** | v5.6.x current, v6.0 in planning. Actively maintained, dominant. Source: [Celery docs](https://docs.celeryq.dev/) and [Abilian job-queue survey](https://lab.abilian.com/Tech/Python/Useful%20Libraries/Job%20queues/) | Requires a broker (Redis/RabbitMQ) = **a third deployed component**. Also the classic "task lost on worker kill unless `acks_late` + visibility timeout are configured exactly right" trap — precisely the kind of subtle config an AI-agent-written codebase gets wrong silently |
| **Dramatiq** | v2.1.x, active. Positioned as "a simpler, more reliable Celery"; the right pick when losing a task is unacceptable. Source: [Abilian survey](https://lab.abilian.com/Tech/Python/Useful%20Libraries/Job%20queues/) | Genuinely better reliability defaults than Celery, but still needs RabbitMQ or Redis |
| **RQ** | v2.x active; scheduling added in v2.5. Sync-only, ~5 minutes to set up | Simplest, but Redis-only and sync-only |
| **arq** | **Maintenance-only, "effectively dead"**; users directed to SAQ or Streaq. Source: [Abilian survey](https://lab.abilian.com/Tech/Python/Useful%20Libraries/Job%20queues/) | **Rule out.** Do not start a 2026 project on it |
| **SAQ / Streaq / TaskIQ** | All active (SAQ release Jan 2026; TaskIQ updated Mar 2026; Streaq v6.0.x supports free-threaded 3.14). Source: [Abilian survey](https://lab.abilian.com/Tech/Python/Useful%20Libraries/Job%20queues/) | Newer, smaller communities — fails the "heavily adopted, well documented" test in C5 |

**The common disqualifier:** every one of these adds Redis (or RabbitMQ) as a separately
deployed, separately backed-up, separately explained process. On a hosted dev tier that is a
paid add-on; in an air-gapped firm it is another container the IT contact can break. And
Redis is *volatile by default* — the natural configuration loses your queue on power failure,
which is the exact scenario we are designing for.

### PostgreSQL-backed options

Both leading libraries use the same two primitives: `SELECT … FOR UPDATE SKIP LOCKED` for
contention-free parallel dequeue, and `LISTEN/NOTIFY` for sub-second wake-up without polling.

- **Procrastinate — v3.9.0, released 2026-06-20.** MIT, Python ≥ 3.10, PostgreSQL 13+.
  Steady release cadence through 2026 (3.7.0 Jan, 3.8.0 Apr, 3.9.0 Jun). Depends on
  `psycopg[pool]`. Ships **retries, periodic tasks, and arbitrary task locks**; sync and async;
  first-class Django integration; documented for ASGI.
  Sources: [procrastinate on PyPI](https://pypi.org/pypi/procrastinate/json),
  [release history](https://pypi.org/project/procrastinate/#history),
  [Procrastinate docs — discussions](https://procrastinate.readthedocs.io/en/stable/discussions.html).
- **PgQueuer — v1.2.0, released 2026-07-15.** MIT, Python ≥ 3.10, PostgreSQL 12+.
  Reached 1.0.0 only on 2026-05-11. Transactional enqueue, `SKIP LOCKED`, `LISTEN/NOTIFY`,
  built-in cron-style recurring jobs, no `celery-beat` equivalent needed.
  Sources: [pgqueuer on PyPI](https://pypi.org/pypi/pgqueuer/json),
  [release history](https://pypi.org/project/pgqueuer/#history), [PgQueuer docs](https://janbjorge.github.io/pgqueuer/).
- Reported difference: **Procrastinate has more built-in features for retries and async
  workflows**; PgQueuer is the more minimal option with recurring tasks built in.
  Source: [pgqueuer discussion #298 — how it differs from Celery](https://github.com/janbjorge/pgqueuer/discussions/298).

### The crash-resume story, which is the deciding factor

Neither library's queue semantics alone solve "resume at document 61 402". The correct design
here is **not** "enqueue 100 000 jobs". It is:

1. An **`ingest_item` table** — one row per source file, with a content hash as the natural
   idempotency key, a `status` enum, an attempt counter and a last-error column. This is the
   durable ledger, and it is *yours*, not the queue library's.
2. The queue's job is only to **drive workers over that table** in batches, claiming rows with
   `FOR UPDATE SKIP LOCKED`.
3. Because the ledger and the extracted content commit **in the same Postgres transaction**,
   a hard kill can only leave a row in `processing` — recovered by a startup sweep that resets
   stale claims older than N minutes.

This is the decisive argument for a Postgres-backed queue: **the queue and the ledger are in
the same database, so "claim the item" and "record the result" are one transaction.** With
Redis they are two systems and exactly-once becomes an application-level reconciliation problem
you will get wrong. It also means `pg_dump` backs up in-flight job state alongside the data.

> ### Recommendation 2 — **Procrastinate 3.9.x over PostgreSQL, driving an application-owned `ingest_item` ledger keyed by content hash.**
> **Strongest reason:** it removes Redis entirely, so the queue is atomic with the data it
> produces and crash-resume is a transaction property rather than a configuration you have to
> get right. Same component on the hosted dev tier and in the air-gapped install.
> **Main risk:** a queue in your primary database competes with it for connections and
> generates churn/bloat; heavy `LISTEN/NOTIFY` and high job-turnover tables need autovacuum
> tuning that nobody on the team will think about until it bites. Mitigate with a separate
> connection pool for workers, a modest concurrency cap, and an aggressive autovacuum setting
> on the job tables from day one.
> **Secondary note:** PgQueuer is a defensible alternative and slightly simpler, but it hit
> 1.0.0 only in May 2026 — under C5, Procrastinate's longer track record and richer retry
> semantics win.

---

## 3. Document extraction

> **Two filters dominate this section and they are not about accuracy.**
> **(a) Licence** — this is a commercial product sold to law firms. GPL/AGPL and
> "free under $5M revenue" model weights are contamination risks, not footnotes.
> **(b) Phone-home** — nearly every modern ML-based parser downloads weights from
> HuggingFace on first use. In an air-gapped firm that is not "slow", it is **a crash**.
> Every model must be baked into the image and every library pinned to a local artifacts path.

### `.msg` — Outlook messages, attachments, nested containers

- **extract-msg 0.56.0, released 2026-07-18** (previous release 0.55.0, 2025-08-12 — so the
  project is alive but not fast-moving). Python ≥ 3.8.
  Sources: [extract-msg on PyPI](https://pypi.org/pypi/extract-msg/json),
  [release history](https://pypi.org/project/extract-msg/#history).
- Handles exactly what C4 requires: attachments, **embedded `.msg` files** (`--extract-embedded`,
  `--skip-embedded`), hidden/inline attachments (`--skip-hidden`), and multiple body encodings
  (HTML / RTF / plain). Nested containers are the hard part of email discovery and this is the
  only mature Python library that does it.
- **⚠ Licence: GPL-3.0.** Source: [extract-msg on PyPI](https://pypi.org/pypi/extract-msg/json).
  For a proprietary on-prem product this is a genuine legal question, not a formality. The
  clean, well-established mitigation is to **run it out-of-process** — a separate CLI/worker
  invoked over a pipe or a subprocess boundary, exchanging JSON — so it is aggregation rather
  than linking. **This must be a deliberate architectural boundary, decided now, not later.**
  Get it confirmed by counsel; it is cheap to design in and expensive to retrofit.
- No network access, no models, fully offline. No telemetry observed.
- **Note on scope:** `.msg` is single-message. If the firm hands over `.pst`/`.ost` archives
  you need a different tool (`libpff`/`readpst`, or `libratom`). Confirm the actual export
  format with the client before building — this is the highest-value clarifying question in
  this whole document.

### PDF — born-digital text

| Library | Version | Licence | Note |
|---|---|---|---|
| **pypdf** | **6.14.2 (2026-06-23)** | **BSD-3-Clause** | Actively released (6.13.2 on 2026-06-10, three releases in June alone). Pure Python, zero native deps, trivial to vendor offline. Source: [pypdf release history](https://pypi.org/project/pypdf/#history) |
| **pdfplumber** | 0.11.7 (2025-06-12) | **MIT** | Best table extraction of the permissive options; visibly better on financial documents. **8–12× slower** than PyMuPDF (~18 pages/s vs ~180 pages/s). Source: [PyMuPDF vs pdfplumber benchmark](https://pdfmux.com/blog/pymupdf-vs-pdfplumber/) |
| **pypdfium2** | 4.30.1 (2024-12-19) | Apache-2.0 / BSD-3 | Chromium's PDFium. Fast, permissive, strong word-order preservation. Slower release cadence |
| **PyMuPDF** | 1.26.1 (2025-06-12) | **AGPL-3.0** | Fastest and best quality — and **the AGPL makes it unusable** in a proprietary product without buying Artifex's commercial licence. Source: [PyMuPDF vs pdfplumber](https://pdfmux.com/blog/pymupdf-vs-pdfplumber/) |

Independent academic comparison confirms PyMuPDF and pypdfium lead on text-extraction fidelity
(highest BLEU-4, best word-order preservation).
Source: [A Comparative Study of PDF Parsing Tools](https://arxiv.org/html/2410.09871v1).

**Practical shape:** `pypdf` for the fast path (text present, no tables), `pdfplumber` only when
a page is table-heavy. Both permissive, both pure-Python-ish, both trivially offline.
Avoid PyMuPDF unless you buy the licence.

### Scanned PDF — OCR

| Engine | Version / date | Licence | Offline | Hardware |
|---|---|---|---|---|
| **Tesseract** | **5.5.2 (2025-12-26)** | **Apache-2.0** | Fully. `tessdata`/`tessdata_fast` are static files you ship | CPU only. ~25 pages/min CPU-bound |
| **PaddleOCR** | **3.7.0**, Apache-2.0, Python ≥ 3.8 | **Apache-2.0** | Yes, but models must be pre-fetched | ~120 pages/min on an RTX 3090 |
| **Surya** | **0.17.1** | ⚠ **Code Apache-2.0, weights modified AI Pubs Open Rail-M — "free for research, personal use, and startups under $5M funding/revenue"** | Yes, weights pre-fetched | GPU strongly preferred (650M params) |
| **docTR** | version **unverified** | Apache-2.0 | Yes | Pretrained models **primarily target English and French** — unusually well-aligned with a French-first product |

Sources: [Tesseract releases](https://github.com/tesseract-ocr/tesseract/releases),
[paddleocr on PyPI](https://pypi.org/pypi/paddleocr/json),
[surya-ocr on PyPI](https://pypi.org/pypi/surya-ocr/json),
[IntuitionLabs — non-LLM OCR engines](https://intuitionlabs.ai/articles/non-llm-ocr-technologies),
[Best open-source OCR tools 2026](https://unstract.com/blog/best-opensource-ocr-tools/).

Accuracy context: PaddleOCR-VL-1.5 reported 94.5% on OmniDocBench v1.5 (Jan 2026) and
PaddleOCR-VL-1.6 reports 96.33% — **vendor-reported, not independently verified**.
Surya is described as the best cost-accuracy trade-off among VLM-based OCR.
Tesseract remains the fastest to deploy: ~0.77 s/page on CPU, ~10 MB binary.
Sources: [CodeSOTA OCR benchmarks](https://www.codesota.com/ocr),
[IntuitionLabs](https://intuitionlabs.ai/articles/non-llm-ocr-technologies).

**The Surya licence is the trap.** Surya is the engine inside Marker. Adopting Marker adopts
Surya's weight licence. A law-firm software vendor will cross $5M revenue or funding, and
the licence is on *model weights*, which cannot be swapped out without changing the product.

### Whole-document parsers (layout-aware)

- **Docling — 2.114.0, released 2026-07-20. MIT licence.** Python ≥ 3.10. Extremely fast
  cadence (2.105.0 on 2026-06-22 → 2.114.0 on 2026-07-20 — roughly nine releases in a month).
  Now hosted by the **Linux Foundation**, shipping **Granite-Docling-258M (Apache-2.0)**.
  Modular extras: `feat-ocr-tesserocr`, `feat-ocr-rapidocr-onnx`, `feat-ocr-easyocr`,
  `models-onnxruntime`. Handles PDF, DOCX, XLSX, PPTX, HTML into one `DoclingDocument`.
  Sources: [docling on PyPI](https://pypi.org/pypi/docling/json),
  [release history](https://pypi.org/project/docling/#history),
  [Best PDF parsers 2026](https://www.firecrawl.dev/blog/best-pdf-parsers).
  **This is the only best-in-class parser with a genuinely clean licence (MIT code +
  Apache-2.0 weights).** That single fact outweighs small accuracy differences here.
  - **Offline is supported but historically fiddly.** `docling-tools models download`
    pre-fetches into `$HOME/.cache/docling/models`; `artifacts_path` in pipeline options points
    at a local directory; the serve env var is `DOCLING_SERVE_ARTIFACTS_PATH` (**not**
    `DOCLING_ARTIFACTS_PATH`) and must point at the *parent* directory. There is a visible
    trail of offline bugs — issue #232, discussions #924/#2217/#2724, issue #2555 (v2.60.0
    ignoring the artifacts path in Docker and looking in `/tmp`).
    Sources: [Docling advanced options](https://docling-project.github.io/docling/usage/advanced_options/),
    [issue #232](https://github.com/docling-project/docling/issues/232),
    [issue #2555](https://github.com/docling-project/docling/issues/2555).
    **Action: an automated "no-network" CI test is mandatory** — build the image, drop the
    network, parse a fixture. Do not trust that offline works because it worked on your laptop.
- **Marker — marker-pdf 2.0.0.** Code Apache-2.0; **weights under the same modified AI Pubs
  Open Rail-M "$5M funding/revenue" restriction as Surya**. Converts PDF/DOCX/PPTX/XLSX/HTML/EPUB;
  GPU, CPU and Apple MPS. Frequently called the safest single default parser of 2026.
  Sources: [marker-pdf on PyPI](https://pypi.org/pypi/marker-pdf/json),
  [Marker vs Docling vs MinerU](https://themenonlab.blog/blog/best-open-source-pdf-to-markdown-tools-2026).
  **Rule out on licence.**
- **unstructured — Apache-2.0.** Telemetry is via **Scarf**; reported as **off by default**,
  opt-in with `UNSTRUCTURED_TELEMETRY_ENABLED=true`; opt-out via `DO_NOT_TRACK` or
  `SCARF_NO_ANALYTICS` set to any non-empty value, and opt-out takes precedence.
  Sources: [unstructured issue #3459](https://github.com/Unstructured-IO/unstructured/issues/3459),
  [unstructured LICENSE.md](https://github.com/Unstructured-IO/unstructured/blob/main/LICENSE.md).
  **Default-off is a 2026 change from earlier default-on behaviour — treat as unverified and
  set `DO_NOT_TRACK=1` and `SCARF_NO_ANALYTICS=1` in the image regardless.** The bigger issue
  is strategic: unstructured has pivoted to a cloud API platform, so the OSS library is no
  longer the company's product. Under C5 that is a maintenance-risk signal.

### `.docx` and `.xlsx`

- **python-docx 1.2.0 (2025-06-16), MIT.** Source: [python-docx history](https://pypi.org/project/python-docx/#history).
- **openpyxl 3.1.5 (2024-06-28), MIT.** Source: [openpyxl history](https://pypi.org/project/openpyxl/#history).
- Both are quiet, stable, permissive, offline, no models. openpyxl's two-year gap looks alarming
  but reflects a finished library, not an abandoned one. Docling also handles both formats —
  prefer Docling where layout matters (e.g. a contract in `.docx`), the native libraries where
  you just need cell values or paragraph text at speed.

> ### Recommendation 3 — **extract-msg (out-of-process, GPL-isolated) for `.msg`; pypdf + pdfplumber for born-digital PDF; Docling with Tesseract 5.5.2 for scanned PDF and layout-heavy documents; python-docx / openpyxl for Office.**
> **Strongest reason:** it is the only combination that is simultaneously best-in-class,
> **cleanly licensed for a commercial product** (MIT / BSD / Apache throughout, with GPL
> confined behind a process boundary), and fully operable with no network.
> **Main risk:** Docling's offline model-artifact handling has a documented history of
> breaking in Docker, and its ~9-releases-a-month cadence means an upgrade can silently
> reintroduce a network fetch. Mitigate with a pinned version, vendored model artifacts in the
> image, and a **network-disabled integration test in CI that fails the build** if anything
> reaches for the internet.
> **Second risk:** GPU. If scanned-PDF volume is high, Tesseract's ~25 pages/min CPU becomes
> the bottleneck for 100k documents (see §5 for the same machine's LLM budget) — measure the
> scanned proportion early, because it determines whether the firm needs a GPU at all.

---

## 4. Multilingual (French-first) embedding models that run locally

### The licence filter kills most of the leaderboard

Before any benchmark: this is a **commercial product**, so `CC-BY-NC-4.0` and research-only
licences are disqualifying, not merely inconvenient. That removes:

- **Jina v3, v4 and the entire v5 family.** v4 (3.8B, 2048-dim, released 2025-06-24) is built
  on Qwen2-VL under the **Qwen Research License** — research and non-commercial use only;
  Jina themselves state they cannot offer it commercially for self-hosting.
  The 2026 v5 line — `jina-embeddings-v5-text-nano` (239M, 768-dim) and `-text-small`
  (677M, 1024-dim), both released **2026-02-18**, and the omni variants (1.04B/1.74B,
  **2026-05-07**) — are all **CC-BY-NC-4.0**.
  Sources: [Jina model index (llms.txt)](https://jina.ai/models/llms.txt),
  [jina-embeddings-v4 on Hugging Face](https://huggingface.co/jinaai/jina-embeddings-v4).
  **Technically excellent, commercially unusable self-hosted. Rule out.**
- **NVIDIA NV-Embed** — CC-BY-NC-4.0. Rule out.
  Source: [Embedding models 2026 benchmark, 2026-04-21](https://app.ailog.fr/en/blog/news/embedding-models-2026).
- **KaLM-Embedding-Gemma3-12B** — currently **#1 on MMTEB at 72.32** (11.76B params, 3840-dim),
  but under a bespoke `tencent-kalm-embedding-community` licence and far too large for a
  single shared on-prem box. Source: [MTEB leaderboard, data dated 2026-05-17](https://www.codesota.com/benchmarks/mteb).
- **All API models** — Mistral Embed (1024-dim, ~$0.10/M tokens), Codestral Embed
  (`codestral-embed-2505`, ~$0.15/M tokens, Matryoshka dimensions down to 256 with int8),
  Cohere embed-v4, OpenAI, Gemini, Voyage. **C1 and C3 rule all of them out for production
  data** regardless of zero-retention claims — an air-gapped machine cannot call an API.
  Sources: [Mistral models overview](https://docs.mistral.ai/models/overview),
  [Codestral Embed](https://mistral.ai/news/codestral-embed/).
  *Mistral Embed remains defensible for the hosted dev tier on synthetic/public data only —
  EU-headquartered, but it must never be on the production path.*

### The commercially usable shortlist

| Model | Params | Dims | Licence | Notes |
|---|---|---|---|---|
| **Qwen3-Embedding-8B** | 8B | 4096 (MRL-truncatable) | **Apache-2.0** | MMTEB **70.58**, French **69.8**. Best open quality |
| **Qwen3-Embedding-4B** | 4B | 2560 | **Apache-2.0** | MMTEB **69.45** — within 1.1 pts of the 8B at half the size |
| **Qwen3-Embedding-0.6B** | 0.6B | 1024 | **Apache-2.0** | Same family/tokeniser, GGUF available. The CPU-viable member |
| **BGE-M3** | 568M | 1024 | **MIT** | MTEB ~63.0–63.2. 8k context. **Dense + sparse + multi-vector in one model**, 100+ languages |
| **multilingual-e5-large-instruct** | 560M | 1024 | **MIT** | 94+ languages, 24 layers. ONNX weights published — matters for CPU |
| **EmbeddingGemma** | 308M | 768 | Gemma terms (**verify**) | Highest-ranking open multilingual model under 500M on MTEB; runs on-device in **<200 MB RAM** via QAT; available in Ollama |
| **nomic-embed-text-v2** | 137M | 768 | Apache-2.0 | Fastest, lowest quality of the set |

Sources: [Qwen3-Embedding blog](https://qwenlm.github.io/blog/qwen3-embedding/),
[Qwen3-Embedding-0.6B model card](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B),
[MTEB leaderboard 2026](https://www.codesota.com/benchmarks/mteb),
[Embedding models 2026 comparison](https://app.ailog.fr/en/blog/news/embedding-models-2026),
[multilingual-e5-large-instruct model card](https://huggingface.co/intfloat/multilingual-e5-large-instruct),
[BentoML open-source embedding models guide](https://www.bentoml.com/blog/a-guide-to-open-source-embedding-models).
Qwen3-Embedding supports **100+ languages** and **Matryoshka (MRL)** dimension truncation
across the family — you can store 1024 dims from a model that natively emits 4096.

### Measured local throughput and memory — the numbers that decide this

Benchmarked on an M5 Max via MLX, batch 64, 512-token passages, published **2026-06-23**:

| Model | Passages/sec | Memory (fp16) | BEIR nDCG@10 |
|---|---|---|---|
| nomic-embed-text-v2 | **14 200** | 0.4 GB | 47.2 |
| **bge-m3** | **4 800** | **1.4 GB** | **51.8** |
| Qwen3-Embedding-8B | **580** | 18 GB | 56.4 |

Source: [Local embeddings on Apple Silicon (2026-06-23)](https://contracollective.com/blog/local-embeddings-apple-silicon-nomic-bge-qwen3-m5-max-2026).
A separate source puts Qwen3-Embedding-8B's practical requirement at **~40 GB VRAM / 32 GB RAM**
in a serving configuration — higher than the 18 GB of raw fp16 weights, because activations and
batching dominate. Source: [Embedding models 2026](https://app.ailog.fr/en/blog/news/embedding-models-2026).
Treat 18 GB as the floor and ~40 GB as the realistic serving figure.

**Apply this to 5 M chunks:**

- **bge-m3 @ 4 800 passages/s → ~17 minutes** of pure embedding compute. Free, effectively.
- **Qwen3-8B @ 580 passages/s → ~2.4 hours**, and only on a machine with ~40 GB of VRAM
  that the firm probably does not have.
- **On CPU-only**, divide these by roughly 10–30× (**unverified** — no CPU-specific benchmark
  found at this scale, and this must be measured, not assumed). bge-m3 on CPU is plausible
  overnight; Qwen3-8B on CPU is not a product.

**This is the whole argument.** The 4.6-point BEIR gap between bge-m3 and Qwen3-8B costs an
8× throughput penalty and a 13× memory penalty, on the same machine that also has to run
the LLM in §5. On a €2 000–20 000 box the LLM is the scarce resource, not the embedder.

### The dimension decision, which is also the pgvector decision

§1 recommended 1024-dim `halfvec`. That is not a coincidence — **bge-m3 and
multilingual-e5-large-instruct both emit exactly 1024 dims natively**, and
Qwen3-Embedding-0.6B does too. So the vector column, the index sizing, and the model choice
are mutually consistent, and you can swap between all three without a schema migration.
Choosing Qwen3-8B would mean 4096 dims (4× the storage and index memory) or MRL truncation
that gives away part of the quality advantage you paid for.

> ### Recommendation 4 — **BGE-M3 (568M, 1024-dim, MIT) as the default embedder, with `multilingual-e5-large-instruct` as a drop-in fallback and Qwen3-Embedding-0.6B as the same-family upgrade path.**
> **Strongest reason:** MIT-licensed, 1.4 GB, 4 800 passages/s, 100+ languages with solid
> French, and its 1024 dimensions match the pgvector `halfvec` column exactly — it is the only
> choice that leaves the machine's RAM and GPU free for the LLM, which is where the real
> constraint is.
> **Main risk:** it is a 2024-generation model and measurably behind the 2026 frontier
> (51.8 vs 56.4 BEIR). If retrieval quality turns out to be the binding constraint on triage
> recall — which for legal discovery it might be — you will want Qwen3-Embedding-4B/8B and
> the hardware to run it. Mitigate by treating the embedder as a **versioned, swappable
> component from day one**: store `model_id` and `model_version` on every chunk row so a
> re-embed is a background migration, not a rebuild.
> **Bonus worth taking:** BGE-M3 produces dense **and sparse** vectors from one pass. Sparse
> retrieval on legal French (names, references, article numbers) is where dense-only RAG
> classically fails, and getting it from a model you are already running is close to free.

---

## 5. Serving a local LLM for per-document relevance judgement

### The workload, stated as arithmetic

100 000 short classification calls. Assume ~1 500 input tokens per call (one chunk or email
plus a compact prompt) and ~30 output tokens (a label plus a one-line justification):

- **~150 M input (prefill) tokens**
- **~3 M output (decode) tokens**

Prefill dominates by 50:1. **This is a batch throughput problem, not a latency problem** — and
that single observation decides the serving engine, because the engines differ by an order of
magnitude precisely on batch throughput.

### Serving engines

| Engine | Current version | Model for our workload |
|---|---|---|
| **vLLM** | **v0.25.1 (2026-07-14)**; v0.25.0 (2026-07-11) made "Model Runner V2 the default for all dense models" and removed legacy PagedAttention, with 550+ commits from 230+ contributors. Source: [vLLM releases (GitHub API)](https://github.com/vllm-project/vllm/releases) | **PagedAttention + continuous batching.** Reported at roughly **16–20× Ollama's concurrent throughput**; one head-to-head recorded **~793 aggregate tok/s vs Ollama's ~41** under simultaneous load |
| **Ollama** | **v0.32.1 (2026-07-16)**, v0.32.0 (2026-07-11); v0.32.2-rc0 (2026-07-20). Source: [Ollama releases (GitHub API)](https://github.com/ollama/ollama/releases) | Built on llama.cpp, **processes requests sequentially** — each generation runs to completion before the next starts. At batch size 1 it is within ~20% of vLLM and often *better* on first-token latency |
| **llama.cpp / llamafile** | Version **unverified** | The right drop-down for odd hardware, CPU-only, or a single-binary distribution. Widest hardware compatibility, lowest ceiling on concurrency |
| **LM Studio / MLX** | — | Desktop and Apple-silicon tooling; not a server product |

Sources: [Ollama vs vLLM vs llama.cpp 2026](https://d-central.tech/ollama-vs-vllm-vs-llama-cpp/),
[vLLM vs Ollama with real concurrency numbers](https://runaihome.com/blog/vllm-vs-ollama-when-each-wins-2026/),
[llama.cpp vs Ollama vs vLLM — one user vs many](https://insiderllm.com/guides/llamacpp-vs-ollama-vs-vllm/).

**Both projects ship weekly and both are pre-1.0.** Every release has changed scheduling,
KV-cache handling or backend kernels. For an air-gapped install this means **pin the exact
image digest and never auto-update** — a "minor" bump can change throughput or break a model.

### French-capable open-weight models, 7B–32B, mid-2026

Everything below is **Apache-2.0 or MIT** — no licence traps in this tier, unusually.

| Model | Size | Q4_K_M VRAM | Licence | French |
|---|---|---|---|---|
| **Mistral Small 3.2 24B** | 24B | **~14 GB** | Apache-2.0 | Mistral trains on more French than any other lab; explicitly strong across European languages |
| **Ministral 3** (14B / 8B / 3B) | 14B/8B/3B | — | Apache-2.0 | **Released 2025-12-02.** Base, instruct and reasoning variants at each size; **40+ languages natively**; built for edge/consumer hardware |
| **Qwen3.6-27B** | 27B | ~16 GB | Apache-2.0 | Qwen 3.5/3.6 support **201 languages** — broadest coverage available |
| **Qwen3-32B** | 32B | ~18–20 GB | Apache-2.0 | Strongest general-purpose default on a 24 GB desktop |
| **Gemma 4 26B** | 26B MoE | — | Apache-2.0 | **140+ languages**; QAT variant cuts memory ~3× |
| **gpt-oss-20b** | 21B (3.6B active) | ~14 GB | Apache-2.0 | — |
| **DeepSeek-R1-Distill-Qwen-32B** | 32B | ~18–20 GB | MIT | — |

Sources: [Best local LLMs on a single 24GB GPU, 2026-07-19](https://www.marktechpost.com/2026/07/19/best-local-llms-you-can-run-on-a-single-24gb-gpu-in-2026-qwen-gemma-mistral-deepseek-compared/),
[Introducing Mistral 3](https://mistral.ai/news/mistral-3/),
[Llama 4 vs Qwen 3.5 vs Mistral, 2026](https://tech-insider.org/llama-4-vs-qwen-vs-mistral-2026/),
[Qwen 3 vs Mistral 2026](https://www.kunalganglani.com/blog/qwen-3-vs-mistral-2026).
Consensus in these sources: **Qwen wins on benchmarks at 32B+; Mistral wins on French, EU
compliance posture and low-VRAM deployment.** For a French law firm the second column is the
one that matters, and "the model is from a French company" is a real, non-technical asset
in the sales conversation.

⚠ **MoE caveat that catches people:** "every expert stays resident in VRAM even when only a
few route per token" — size MoE models by **total**, not active, parameters.

### What the CCBE actually says about law-firm hardware — primary source

**CCBE technical guide on the use of AI tools and models by lawyers, Edition 2026,
dated 27 March 2026, 19 pages.**
Source: [CCBE technical guide (PDF)](https://www.ccbe.eu/fileadmin/speciality_distribution/public/documents/IT_LAW/ITL_Guides_recommendations/EN_ITL_20260327_CCBE-technical-guide-on-the-use-of-AI-tools-and-models-by-lawyers.pdf)
(text extracted directly from the PDF; quotations lightly de-hyphenated).

**Speed thresholds — quotable, and useful for setting client expectations:**
> "the generation speed below 5 tps is too slow for any interactive use, while the speed above
> 20 tps outpaces an average lawyer's reading speed. Speed of around 100 tps exceeds typical
> skim read speed"

**Budget tiers:**

| Budget | What it buys (Sept 2025 prices, ex-VAT) | What it runs |
|---|---|---|
| Existing PC | €0 | Small models; "deepseek-r1:14b at the patient speed of 2.5 tps" — i.e. unusable |
| **~€2 000** | "a motherboard with 128GB of RAM and a fast CPU, as well as a couple of inexpensive GPUs and **24GB VRAM** (e.g. two to four GPUs)" | "**20–40B parameter text-only models at a comfortable speed**" |
| Mid | Single better GPU, e.g. RTX Pro 6000 96 GB (≈€8 000 for the 96 GB card) | GPT-OSS-120B; deepseek-r1:14b reaches **114 tps** on this GPU at limited token length |
| **€20 000** | Server/workstation class | "some of the most capable open-weight models (like an 8-bit quantised 671B DeepSeek V3 or a Qwen3-235B-A22B, even if slowly)" or **GPT-OSS-120B shared across several concurrent users** with larger context windows. CPU-only €20 000 machines run the giants at **5–8 tps** |
| Beyond | DGX H100 ≈€350 000; GB300 NVL72 up to €3 M | Out of scope for a law firm |

**The CCBE's own use-case table (Table 4) maps almost exactly onto this product:**
> "Drafting and revision (suitable for simpler changes in supported languages): LLM **7B–8B**,
> **CPU sufficient**"
> "Long-context RAG (200–500pp): LLM **13B–34B + embeddings**"

**Quantisation rule of thumb (CCBE Table 2):** FP16 = 1.0× RAM, baseline accuracy;
**INT8 ≈ 0.5× RAM, +10–30% speed, "close enough to original on most tasks — good default for
local servers"**; INT4 ≈ 0.25× RAM, +20–50% speed, moderate loss, for long context.

### Throughput estimate for 100 000 classification calls

Combining the workload arithmetic with the cited figures. **These are engineering estimates
derived from published numbers, not measurements — treat as order-of-magnitude only.**

On the **CCBE €2 000 machine** (24 GB VRAM, 24B model at Q4, vLLM with continuous batching):

- Prefill 150 M tokens at an assumed 2 000–4 000 tok/s → **10–21 hours**
- Decode 3 M tokens at an assumed ~300 tok/s aggregate → **~3 hours**
- **Total ≈ 13–24 hours — one overnight-to-weekend run.** Acceptable for a discovery workflow.

On a **single RTX Pro 6000 96 GB** (the CCBE's mid tier), using the guide's own measured
figure of **10 000 tps input processing**: prefill of 150 M tokens ≈ **4.2 hours**. Comfortably
within a working day, and enough headroom to run a 32B model at INT8 rather than INT4.

**With Ollama instead of vLLM**, at the reported 16–20× penalty on batched throughput, the same
job goes from ~a day to **two to three weeks**. That is the whole decision, in one line.

**The design note that matters more than the engine choice:** do not send all 100 000 documents
to the LLM. Cascade — cheap deterministic filters (dedup by content hash, sender/date rules,
attachment type) → vector + BM25 retrieval → LLM judgement only on the survivors. Cutting the
LLM's workload by 10× is far cheaper than buying 10× the GPU, and it is the difference between
the €2 000 machine and the €20 000 one.

> ### Recommendation 5 — **vLLM (pinned digest) serving Mistral Small 3.2 24B at INT8/Q4 on a single 24 GB GPU, with Ollama kept only as the low-end/CPU fallback profile.**
> **Strongest reason:** the workload is 150 M prefill tokens, and continuous batching is worth
> 16–20× on exactly that — it converts a three-week job into an overnight one on the €2 000
> machine the CCBE says a law firm can buy, using an Apache-2.0 model from a French company.
> **Main risk:** vLLM is pre-1.0, ships weekly, and demands NVIDIA/AMD GPU plumbing that a
> firm's IT contact cannot debug. If the firm's machine has no suitable GPU, vLLM is not
> merely slower — it may not run at all. Mitigate by shipping **two serving profiles behind one
> OpenAI-compatible HTTP interface** (`vllm` and `ollama`) selected by a config flag, so the
> application code never knows which is behind it, and by treating vLLM's version as a frozen,
> hand-tested artefact per release.

---

