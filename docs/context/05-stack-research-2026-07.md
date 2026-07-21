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

## 6. Authentication and authorisation, self-hosted, no managed identity provider

### The constraint restated, because it changes the usual answer

C2 forbids Supabase Auth and Supabase RLS. C1 forbids a managed IdP. C5 forbids anything
that needs an auth specialist. What is left is: **you own the identity store, and it lives in
the same PostgreSQL 18.4 that already holds the documents, the vectors and the Procrastinate
queue.** That is not a limitation to work around — it is the single fact that makes every
choice below easy, because "look up the session" and "check the matter permission" become
one query against a database the request is already talking to.

### JOSE / JWT libraries — this is where the CVEs are

| Library | Current version | Licence | Verdict |
|---|---|---|---|
| **PyJWT** | **2.13.0 (2026-05-21)** | MIT, Python ≥ 3.9 | **Use this.** Prior: 2.12.1 (2026-03-13), 2.12.0 (2026-03-12), 2.11.0 (2026-01-30), 2.10.1 (2024-11-28). Narrow surface — sign, verify, nothing else |
| **Authlib** | **1.7.2 (2026-05-06)**; maintenance line **1.6.12 (2026-05-04)** | BSD-3-Clause, Python ≥ 3.10 | Use **only** if you need a full OAuth2/OIDC server or client. See the advisory table below before you do |
| **python-jose** | **3.5.0 (2025-05-28)** | MIT | **Rule out.** Three releases in five years: 3.3.0 (2021-06-05), 3.4.0 (2025-02-18), 3.5.0 (2025-05-28). 115 open issues, last push 2026-04-14 |

Sources: [pyjwt on PyPI](https://pypi.org/pypi/pyjwt/json), [authlib on PyPI](https://pypi.org/pypi/authlib/json),
[python-jose on PyPI](https://pypi.org/pypi/python-jose/json), [mpdavis/python-jose (GitHub API)](https://api.github.com/repos/mpdavis/python-jose).

**python-jose is the trap that legacy FastAPI tutorials still lead people into.** It carries
**CVE-2024-33663** — algorithm confusion with OpenSSH ECDSA keys and other key formats, which
is an authentication-bypass class bug — and **CVE-2024-33664**, a "JWT bomb" DoS via a crafted
JWE with a high compression ratio. Both affect ≤ 3.3.0; 3.4.0 fixed the first.
Sources: [Red Hat bug 2277297 (CVE-2024-33663)](https://bugzilla.redhat.com/show_bug.cgi?id=2277297),
[CVE-2024-33664](https://vulert.com/vuln-db/CVE-2024-33664).
The library sat unmaintained for **three and a half years** with a known auth bypass. It is
back from the dead, not healthy. Do not start a 2026 product on it.

**Authlib's 2026 has been genuinely bad.** The GitHub Advisory Database lists **twelve**
advisories for the package. The recent ones:

| CVE | Severity | Published | Affected | Patched |
|---|---|---|---|---|
| **CVE-2026-27962** — JWS JWK header injection, signature verification bypass | **Critical, CVSS 9.1** | 2026-03-15 | ≤ 1.6.8 | 1.6.9 |
| CVE-2026-28498 — fail-open crypto verification in OIDC hash binding (`at_hash`/`c_hash`) | High | 2026-03-15 | ≤ 1.6.8 | 1.6.9 |
| CVE-2026-28490 — JWE RSA1_5 Bleichenbacher padding oracle | High | 2026-03-15 | ≤ 1.6.8 | **patched version unverified** |
| CVE-2026-28802 — `alg: none` with blank signature passes verification | High | Feb 2026 | 1.6.5–1.6.6 | 1.6.7 |
| CVE-2026-41425 — CSRF when using cache-backed OAuth clients | Moderate | 2026-04-16 | < 1.6.11 | 1.6.11 |
| CVE-2026-44681 — OIDC implicit/hybrid open redirect | Moderate | 2026-05-07 | ≤ 1.6.11, ≤ 1.7.0 | 1.6.12 / 1.7.1 |
| CVE-2026-41479 — unauthenticated open redirect on unsupported `response_type` | Moderate | 2026-06-08 | < 1.6.6 → HEAD | 1.6.10 / 1.7.1 |

Plus, in the preceding twelve months: CVE-2025-59420 (High, JWS/JWT accepts unknown `crit`
headers), CVE-2025-61920 (High, DoS via oversized JOSE segments), CVE-2025-62706 (Moderate,
JWE `zip=DEF` decompression bomb), CVE-2025-68158 (Moderate, 1-click account takeover), and
CVE-2024-37568 (High, algorithm confusion with asymmetric public keys).
Sources: [GitHub Advisory Database — authlib](https://github.com/advisories?query=authlib),
[lepture/authlib security advisories (GitHub API)](https://api.github.com/repos/lepture/authlib/security-advisories),
[GHSA-wvwj-cvrp-7pv5 / CVE-2026-27962](https://github.com/lepture/authlib/security/advisories/GHSA-wvwj-cvrp-7pv5),
[ARMO on CVE-2026-28802](https://www.armosec.io/blog/authlib-cve-2026-28802-jwt-signature-verification-bypass/).

**Read this correctly.** It is not "Authlib is bad code" — it is a small maintainer team
carrying the largest JOSE/OAuth/OIDC surface in Python, and that surface is under active
research. The correct inference for us is **do not deploy that surface at all.** Every one of
the four High/Critical bugs above is in JWS/JWE/OIDC verification paths we would not use if we
never issue a JWT to a browser. **Under C1 there is no air-gapped machine that will pick up a
1.6.9 patch on the day it ships.** An unpatched CVSS 9.1 auth bypass sitting on a law firm's
document server for six months is the worst outcome in this entire document.

### Password hashing

| Library | Current version | Licence | Verdict |
|---|---|---|---|
| **argon2-cffi** | **25.1.0 (2025-06-03)** | MIT, Python ≥ 3.8 | The reference Argon2 binding. Quiet because it is finished — prior 23.1.0 (2023-08-15) |
| **pwdlib** | **0.3.0 (2025-10-25)** | MIT, Python ≥ 3.10 | Thin wrapper over argon2-cffi and bcrypt with a hash-upgrade path. By François Voron (the FastAPI-Users author) |
| **bcrypt** | 5.0.0 (2025-09-25) | Apache-2.0 | Fine, but Argon2id is the 2026 default |
| **passlib** | **1.7.4 (2020-10-08)** | BSD | **Rule out.** Nearly six years without a release |

Sources: [argon2-cffi on PyPI](https://pypi.org/pypi/argon2-cffi/json), [pwdlib on PyPI](https://pypi.org/pypi/pwdlib/json),
[bcrypt on PyPI](https://pypi.org/pypi/bcrypt/json), [passlib on PyPI](https://pypi.org/pypi/passlib/json).

**The strongest available signal on all of the above:** the *official* FastAPI security
tutorial now installs `pyjwt` and `pwdlib[argon2]`. It no longer teaches python-jose or
passlib. Source: [FastAPI — OAuth2 with JWT tutorial](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/).
Under C5, "what the framework's own documentation tells an AI coding agent to write" is worth
more than any benchmark on this page.

### FastAPI-Users — the obvious pick, and why it is now a liability

**15.0.5, released 2026-03-27.** MIT, Python ≥ 3.10. 6 200 stars, still actively pushed
(2026-07-20). It ships registration, login, password reset, email verification, OAuth2 flows,
pluggable password validation, SQLAlchemy and Beanie backends, and JWT/database/Redis strategies.

**But it entered maintenance mode at v15.0.1 (2025-10-25):** *"While we'll continue to provide
security updates and dependency maintenance, no new features will be added."* The maintainers
state they are working on a successor toolkit that will supersede it.
Sources: [fastapi-users releases (GitHub API)](https://api.github.com/repos/fastapi-users/fastapi-users/releases),
[fastapi-users on PyPI](https://pypi.org/pypi/fastapi-users/json).

Two more facts matter. **v15.0.0 dropped Python 3.9 and Pydantic v1** — a real migration if you
are not already on Pydantic 2. And **v15.0.2 (2025-12-19) shipped a CSRF fix in the OAuth2
authorize flow** — i.e. the library has its own vulnerability history, and adopting it means
tracking that history on an air-gapped install.

The deeper objection is fit. FastAPI-Users is built around **JWT-issuing, multi-strategy,
OAuth2-social-login, self-service registration** — a public SaaS signup funnel. This product
has none of that. A law firm has a fixed roster of named users provisioned by an administrator;
there is no registration, no email verification (there is no mail server on an air-gapped box),
no social login, no password-reset email. **You would adopt a maintenance-mode dependency and a
JWT strategy layer to get roughly two hundred lines of code you actually need.**

### Sessions vs JWT for a single-tenant on-prem install — the honest answer

The case for stateless JWT is exactly one thing: *validating a token must not require a shared
store, because the services validating it cannot reach one.* That is a horizontal-scale,
multi-service, multi-region argument.

**Here there is one machine, one database, and one application process.** The premise is absent.
And the costs are not:

- **No revocation.** A paralegal removed from a matter — or fired — keeps their access until
  the token expires. For a product whose non-negotiables include *RBAC by matter (Chinese walls)*
  and *full audit trail*, that is a compliance defect, not an inconvenience.
- **You build refresh-token rotation anyway**, which is a server-side revocable-token store —
  i.e. you build sessions, badly, in addition to JWT.
- **The whole algorithm-confusion / `alg:none` / JWK-header-injection bug class** listed above
  simply does not exist if there is no signed token to confuse.
- **It does not save the database round-trip.** Matter-level permissions change and must be
  authoritative, so every request hits Postgres for the matter scope regardless. Once you are
  querying per request, a session lookup on a primary-key index is free. **This is the decisive
  point:** the stateless benefit is cancelled by the Chinese-walls requirement.

**Note on Starlette's `SessionMiddleware`:** it is a *signed cookie*, backed by itsdangerous
2.2.0 (2024-04-16) — client-side state, not a server-side session, and not revocable. It is fine
for flash messages and CSRF nonces. It is not a session store.
(Starlette 1.3.1, 2026-06-12 — the 1.0 line landed in May 2026.)
Source: [starlette on PyPI](https://pypi.org/pypi/starlette/json).

**What to build instead** — and it is genuinely small:

1. `POST /login` verifies the Argon2id hash, then mints **256 bits from `secrets.token_urlsafe`**.
2. Store **SHA-256 of the token** in a `session` table (`user_id`, `created_at`, `last_seen_at`,
   `expires_at`, `revoked_at`, `user_agent`, `ip`). Hash at rest so a database leak is not a
   credential leak.
3. Return it in a cookie: `HttpOnly`, `Secure`, `SameSite=Lax`, `Path=/`.
4. One FastAPI dependency resolves cookie → `Principal`. Revocation is `UPDATE … SET revoked_at`.
5. The session table **is** the login audit trail, and `pg_dump` already backs it up.

JWT keeps exactly one job: short-lived internal service tokens (worker → API), symmetric HS256,
with `algorithms=["HS256"]` passed explicitly to `jwt.decode` — never inferred from the header.

### Per-request authorisation

C2 forbids **Supabase** RLS. It does not forbid **PostgreSQL** RLS, which is core Postgres and
available on every managed tier. That distinction is worth stating explicitly, because it is the
one place a clever option is genuinely on the table.

- **Primary enforcement: application layer.** One `Principal`, one FastAPI dependency, and a
  repository layer in which **every query function takes a matter scope as a mandatory
  positional argument**. Make it impossible to write a query without one — that is a code-review
  and type-checking property an AI agent will respect, whereas "remember to filter" is not.
- **Defence in depth: native Postgres RLS**, with policies reading `current_setting('app.actor_id')`
  set by `SET LOCAL` inside the request's transaction. Real value: a missed `WHERE` clause returns
  zero rows instead of another matter's documents.
  **The footgun:** `SET LOCAL` is transaction-scoped, and with a pooled connection — or a
  Procrastinate worker that reuses connections across jobs — a leaked GUC leaks a Chinese wall.
  Adopt it **only** behind a test that opens two concurrent pooled sessions and proves the GUC
  does not cross. If that test is not written, do not enable RLS; a false sense of containment
  is worse than none.
- **Policy engines (Casbin/pycasbin, OPA)** — considered and rejected. They add a policy DSL and
  a second place where authorisation lives. A `matter_membership(user_id, matter_id, role)` table
  plus one dependency is smaller, faster, auditable in SQL, and something the technical lead can
  read. Under C5 that wins.

### Passkeys / WebAuthn — and the constraint that nobody sees coming

**`webauthn` (py_webauthn, Duo Labs) 3.0.0, released 2026-06-29.** BSD-3-Clause, Python ≥ 3.10.
Prior: 2.8.0 (2026-06-13), 2.7.1 (2026-02-11), 2.7.0 (2025-09-04). 1 053 stars, actively pushed,
not archived. Four functions: `generate_registration_options`, `verify_registration_response`,
`generate_authentication_options`, `verify_authentication_response`.
Sources: [webauthn on PyPI](https://pypi.org/pypi/webauthn/json), [duo-labs/py_webauthn (GitHub API)](https://api.github.com/repos/duo-labs/py_webauthn).
The library is fine. The library is not the problem.

**WebAuthn only runs in a secure context.** Browsers permit it over HTTPS, with `localhost` as
the sole exemption — **a bare LAN IP address is blocked by the specification**, self-signed
certificates are a development-only escape, and the credential is bound at registration time to
a **relying-party ID derived from the origin's effective domain**.
Sources: [MDN — Web Authentication API](https://developer.mozilla.org/en-US/docs/Web/API/Web_Authentication_API),
[Corbado — testing passkeys from localhost](https://www.corbado.com/blog/test-passkeys-localhost-ngrok).

Translated into this deployment:

- Users reaching the app at `https://192.168.1.40` **cannot use passkeys at all.**
- It works only if the firm has an internal DNS name (`apx.cabinet.local`) *and* a certificate
  those workstations trust — which means the firm's own internal CA, or a real certificate for a
  name they control. That is a Windows-domain task on the customer's side, and it is the single
  most likely thing to go wrong during an install.
- **If the firm ever renames the host, every registered passkey is dead.** On an air-gapped
  machine with no remote access, you cannot fix that for them.

**So: build password + Argon2id + TOTP first.** TOTP (`pyotp` 2.10.0, 2026-06-14, MIT) has no
domain binding, no certificate requirement, no network, and works from any phone offline —
it is the only second factor that is unconditionally deployable here. Design the
`credential` table polymorphically (`type` ∈ `password | totp | webauthn`) so passkeys are an
additive row, and enable WebAuthn per site once the FQDN and certificate exist.

> ### Recommendation 6 — **Own the auth: opaque server-side sessions in PostgreSQL, Argon2id via `pwdlib[argon2]`, PyJWT 2.13.x for internal service tokens only, TOTP via `pyotp` as the second factor, `py_webauthn` 3.0.x as an additive credential type behind a per-site FQDN + certificate gate. No FastAPI-Users. No Authlib unless a customer forces OIDC. Never python-jose or passlib.**
> **Strongest reason:** it removes the entire JOSE attack surface from a machine that cannot be
> patched. Every High/Critical CVE in this section — `alg:none`, JWK header injection, algorithm
> confusion, fail-open hash binding — is unreachable if no signed token is ever presented by a
> browser. And because the Chinese-walls requirement forces a database read on every request
> anyway, statelessness buys literally nothing while costing revocation, which the product's own
> non-negotiables require.
> **Main risk:** you are writing security code instead of importing it, and a one-person team
> plus AI agents writing session handling is exactly how timing-unsafe token comparison, missing
> `HttpOnly`, absent CSRF protection on state-changing routes, and session-fixation-on-privilege-
> change get shipped. Mitigate by keeping the surface tiny (one login route, one dependency, one
> table), hashing tokens at rest, and writing the four adversarial tests **first**: revoked
> session rejected, expired session rejected, cross-matter read returns zero rows, GUC does not
> leak across pooled connections.
> **Second risk, and it is the more likely one:** the assumption that the firm has no identity
> provider. A firm large enough to buy this runs Microsoft 365 or an on-prem AD, and their
> security questionnaire will ask for SSO. That is not incompatible with C1 — ADFS/Entra on the
> LAN is reachable from an air-gapped machine — but it drags Authlib, with the advisory record
> above, onto the critical path. **Keep the `Principal` resolution behind one interface** so an
> OIDC backend can be added without touching any route.

---

## 7. Packaging an offline install, and updating it later

### What "offline install" has to mean here

Three separate problems that get confused with one another: **(a)** getting several gigabytes of
container images and model weights onto a machine with no network; **(b)** proving to a law
firm's IT contact that what arrived is what you sent; **(c)** changing the database schema on a
machine you cannot log into, without breaking it, and being able to undo it. Only (a) is about
packaging. (b) and (c) are what actually determine whether one person can support several sites.

### Option A — Docker Compose bundle with pre-pulled images

**Docker Engine 29.6.2 (2026-07-16); Docker Compose v5.3.1 (2026-07-07).**
Sources: [moby/moby releases (GitHub API)](https://api.github.com/repos/moby/moby/releases),
[docker/compose releases (GitHub API)](https://api.github.com/repos/docker/compose/releases).

The mechanism is `docker save` on the build side producing a tar of all images, transferred by
USB/DVD, then `docker load` on the target, with the `compose.yaml` and a `.env` alongside.
Sources: [Preparing Docker images for air-gapped installation (RepoFlow)](https://docs.repoflow.io/Self-Hosting/air-gapped-preparation),
[Air-gapped deployment with Docker Compose (RepoFlow)](https://docs.repoflow.io/Self-Hosting/Installation/docker-compose/air-gapped-deployment),
[docker-compose-offline-install](https://github.com/DevinKott/docker-compose-offline-install).

What this gets right for us specifically:

- **It is the same artefact in dev and prod (C1 + C2).** The Compose file that a developer runs
  against a hosted Postgres is the Compose file the firm runs, minus one service.
- pgvector arrives *inside* the `pgvector/pgvector:pg18` image — §1 already noted this is zero
  extra install steps.
- Model weights, `tessdata` and Docling artifacts are image layers, so §3's and §4's offline
  requirements are satisfied by the same mechanism.
- The IT contact's job is: copy a directory, run one script. That is the ceiling of what is
  realistic.

The cost is honest: Docker must be installed and permitted. Some firms' IT policy forbids it.
Note also that Podman is a drop-in for air-gapped use if Docker is refused.
Source: [Using Podman in air-gapped environments](https://oneuptime.com/blog/post/2026-03-18-use-podman-air-gapped-environments/view).

### Option B — a single binary

Genuinely excellent when it applies: one file, no runtime, no Docker, atomic updates, and the
frontend embedded via `go:embed`.
Source: [Embedding frontend assets in Go binaries](https://leapcell.io/blog/embedding-frontend-assets-in-go-binaries).

**It does not apply.** The bundle is PostgreSQL 18.4 with the pgvector extension, a Python
application, Procrastinate workers, Tesseract, and a vLLM or Ollama inference server plus
multi-gigabyte model weights. A single binary cannot sensibly contain PostgreSQL, and Python's
freezers (PyInstaller, Nuitka) produce fragile artefacts once native extensions —
`psycopg`, `argon2-cffi`, `torch`, OCR bindings — are involved. This is ruled out by the shape of
the stack, not by preference. If the stack were Go + SQLite it would be the right answer.

### Option C — Tauri / Electron desktop wrapper

**Tauri 2.11.5, released 2026-07-01** (2.11.4, 2026-06-30). Source: [tauri-apps/tauri releases (GitHub API)](https://api.github.com/repos/tauri-apps/tauri/releases).

There is one real, non-obvious benefit: **a desktop shell serves from `localhost`, which is a
secure context — it dissolves §6's WebAuthn problem and the whole internal-TLS-certificate
problem in one move.** That is worth naming, because it is the only argument for this option
that is not aesthetic.

Everything else is against it:

- It does not replace the server. Postgres, the workers and the inference server still ship. It
  is **additive** complexity.
- A second toolchain (Rust, platform SDKs) and **per-OS code-signing certificates** — Apple
  Developer ID, Windows Authenticode — which expire, cost money annually, and whose renewal
  failure breaks installs at every site simultaneously.
- The product is multi-user with matter-level Chinese walls. A desktop wrapper means N installs
  and N updates instead of one server the firm's existing browsers point at. For a one-person
  team that is strictly worse arithmetic.

Rule out as the distribution mechanism. Revisit only as an optional thin client if passkeys
become contractual.

### Signing and verification that works with no internet

**cosign 3.1.2 (2026-07-17).** Source: [sigstore/cosign releases (GitHub API)](https://api.github.com/repos/sigstore/cosign/releases).

The critical detail: **keyless signing does not work air-gapped** — it needs Fulcio and Rekor.
Use a **key pair**. On the connected side, `cosign sign --key cosign.key`, then
`cosign save $IMAGE --dir ./bundle`; on the air-gapped side,
`cosign verify --key cosign.pub --offline --local-image ./bundle`. The verification material
travels as an annotation on the image manifest, so `--offline` is a genuine offline verify.
Sources: [sigstore/cosign](https://github.com/sigstore/cosign),
[Verifying cosign signatures offline](https://some-natalie.dev/blog/cosign-disconnected/),
[cosign issue #3437 — fully air-gapped sign and verify](https://github.com/sigstore/cosign/issues/3437).

Two rules that matter more than the tool choice:

1. **The public key must arrive by a different channel than the bundle.** Publish the fingerprint
   on your website and put it in the contract. A signature verified with a key that travelled on
   the same USB stick proves nothing.
2. **The installer verifies, and refuses to continue on failure.** If verification is a step in a
   PDF, it will be skipped. Also ship a `SHA256SUMS` with a detached signature for the humans who
   want a second check they understand.

### Migrations on an unattended upgrade — the part that actually breaks

**Alembic 1.18.5 (2026-06-25)**, MIT, Python ≥ 3.10; the 1.18 line opened 2026-01-09.
Source: [alembic on PyPI](https://pypi.org/pypi/alembic/json).

The upgrade script must, in this order and failing closed at every step:

1. **`pg_dump -Fc` before anything.** Verify the exit code *and* that the file is non-trivial in
   size. **If the backup fails, do not migrate.** This is the single most important line in the
   installer.
2. **Record the currently-running image digests** to a file next to the backup. Without this,
   rollback is guesswork.
3. Run `alembic upgrade head` on a connection with **`lock_timeout` and `statement_timeout` set**.
   Without them, a migration that cannot get its lock queues every application query behind it
   and the firm experiences a total outage with no error message.
   Source: [Zero-downtime Alembic migrations on PostgreSQL](https://goldlapel.com/grounds/replication-scaling-cloud/alembic-zero-downtime-migrations).
4. Only then start the new containers.

Three disciplines make this survivable:

- **Expand/contract, always.** A release that removes a column ships at least one release *after*
  the code that stopped reading it. This is what makes step 3 reversible without a restore.
- **Lint migrations in CI.** Squawk flags `ADD COLUMN` with a `DEFAULT` (table lock) and
  `CREATE INDEX` without `CONCURRENTLY` — exactly the two mistakes an AI agent makes.
- **Rehearse against real shapes.** `alembic upgrade head --sql` lets you review the SQL before it
  runs — but you cannot review anything on an unattended install, so the review happens in *your*
  CI against a restored dump of a representative database. Not on the customer's machine.
  Source: [Applying and rolling back migrations](https://www.stacklesson.com/react-fastapi/fastapi-alembic/ch25-lesson-03-applying-and-rolling-back/).

**Rollback: do not use `alembic downgrade` on a customer machine.** Downgrade functions are the
least-exercised code in any repository, they are frequently wrong, and `downgrade base` drops
everything. The rollback that actually works is: **stop containers → restore the pre-upgrade
`pg_dump` → re-tag the recorded previous image digests → start.** One documented command,
tested in CI on every release. Keep writing `downgrade()` bodies for local development; never
run them in production.

### What comparable on-premise products actually ship in 2026

- **Kubernetes-shaped enterprise tooling exists and is mature.** Replicated/KOTS builds an
  `.airgap` bundle containing manifests and images plus a `kotsadm.tar.gz`, and **requires a
  private container registry inside the air-gapped network**; KOTS rewrites image names and pushes
  to it. Updates are new `.airgap` bundles uploaded through an admin console. Their April 2026
  release added Helm v4 support and browser-based air-gap bundle downloads. Zarf occupies the same
  niche. Sources: [Replicated — air gap install in existing clusters](https://docs.replicated.com/enterprise/installing-existing-cluster-airgapped),
  [Replicated — distribute to air-gapped environments](https://www.replicated.com/air-gap).
  **This is the wrong shape for us.** It presumes Kubernetes and a registry the firm operates.
- **For single-machine on-prem, the pattern is Docker Compose plus an offline image tarball plus a
  shell installer**, with Helm/KOTS reserved for customers who already run Kubernetes. Plane, for
  example, advertises Docker, Kubernetes or fully air-gapped deployment with signed offline
  bundles. Source: [Plane self-hosted](https://plane.so/self-hosted).
- A comprehensive 2026 survey of what GitLab, Metabase, Mattermost and SonarQube specifically ship
  for air-gap could not be confirmed against primary sources — **unverified**. The Compose +
  tarball + installer pattern is nonetheless the consistent answer across every vendor
  documentation page reviewed.

### No telemetry, no remote access — as build-time properties

Zero telemetry cannot be a policy; it has to be baked in and tested. In the image:
`NEXT_TELEMETRY_DISABLED=1`, `DO_NOT_TRACK=1`, `SCARF_NO_ANALYTICS=1` (§3), `HF_HUB_OFFLINE=1`
and `TRANSFORMERS_OFFLINE=1`. Then the **network-disabled CI test from §3 becomes the
acceptance test for the whole bundle**, not just for Docling: bring the stack up with no network
namespace, ingest a fixture, run a query, verify a login. If anything reaches for the internet,
the build fails.

No remote access means diagnostics must be a **support bundle**: one command producing a tarball
of versions, image digests, the current Alembic revision, container health, disk and RAM,
row counts, and log tails **with document content stripped**. It must be readable plain text —
a law firm will not email you anything they cannot inspect first. Design the redaction now;
it is the difference between a 20-minute diagnosis and a site visit.

### What is realistic for one person across several sites

- **Support exactly two versions, N and N−1, and write that into the contract.** Three concurrent
  versions is where a one-person team stops being able to reproduce bugs.
- **Pin image digests, never tags.** Keep a `versions.lock` per site in your own repository — it
  is the only record of what is actually running somewhere you cannot log into.
- **One `preflight` command** checking Docker version, disk, RAM, GPU presence and PostgreSQL
  reachability, which refuses to proceed rather than half-installing.
- **`install.sh` and `upgrade.sh`, both idempotent, both taking a bundle path**, both safe to
  re-run after a failure. The IT contact's recovery action must always be "run it again".

> ### Recommendation 7 — **Ship a Docker Compose bundle: a `docker save` image tarball signed with a cosign key pair and verified `--offline` by the installer, plus an `upgrade.sh` that takes a `pg_dump` before every Alembic migration and rolls back by restoring the dump and re-tagging recorded image digests. Two supported versions, everything pinned by digest, one redacted support bundle command. No single binary, no desktop wrapper.**
> **Strongest reason:** it is the only option where the air-gapped install and the hosted dev tier
> are the same artefact (C1 + C2), where the IT contact's entire job is "copy a directory and run
> one script", and where pgvector, model weights, `tessdata` and the inference server all arrive
> as image layers rather than as five separate install procedures a non-specialist can get wrong.
> **Main risk:** the rollback path is the least-exercised code you will ship and it will be
> executed for the first time by someone you cannot talk to, under time pressure, on a machine
> you cannot see. Mitigate by running the full restore-and-re-tag path in CI on **every** release
> against a restored production-shaped dump — not as a documented procedure, as an automated test.
> **Second risk:** a customer whose IT policy forbids Docker, or who wants a VM appliance (OVA)
> instead. Mitigate cheaply by keeping the Compose file free of Docker-specific extensions so a
> Podman `podman compose` path stays open, and by never letting install steps live anywhere other
> than the two scripts.

---

## 8. Backend and frontend framework sanity check

### Backend — Python/FastAPI is still right, with two footnotes

| Component | Current stable | Date | Note |
|---|---|---|---|
| **FastAPI** | **0.139.2** | 2026-07-16 | 0.139.1 same day; 0.139.0 (2026-07-01), 0.138.1 (2026-06-25), 0.138.0 (2026-06-20) |
| **Starlette** | **1.3.1** | 2026-06-12 | The **1.0 line landed May 2026** — 1.0.1 (2026-05-21), 1.2.0 (2026-05-28), 1.3.0 (2026-06-11) |
| **Uvicorn** | **0.51.0** | 2026-07-08 | 0.50.2 (2026-07-06), 0.50.0 (2026-07-04) |
| **Pydantic** | **2.13.4** | 2026-05-06 | 2.14.0a1 (2026-05-22) is alpha — do not ship |
| **SQLAlchemy** | **2.0.51** | 2026-06-15 | **2.1.0b3 (2026-06-27) is beta — do not ship** |
| **psycopg** | **3.3.4** | 2026-05-01 | **LGPL-3.0-only** — see below |
| **Alembic** | **1.18.5** | 2026-06-25 | §7 |
| **Python** | **3.13.14** | 2026-06-10 | 3.14.6 same date; **3.10 reaches EOL 2026-10-31** |

Sources: [fastapi releases (GitHub API)](https://api.github.com/repos/fastapi/fastapi/releases),
[starlette](https://pypi.org/pypi/starlette/json), [uvicorn](https://pypi.org/pypi/uvicorn/json),
[pydantic](https://pypi.org/pypi/pydantic/json), [sqlalchemy](https://pypi.org/pypi/sqlalchemy/json),
[psycopg](https://pypi.org/pypi/psycopg/json), [Python end-of-life data](https://endoflife.date/api/python.json).

**Migration traps, concretely:**

- **Starlette reached 1.0 in May 2026 and FastAPI pins it in a narrow range.** Do not upgrade
  Starlette independently of FastAPI; a Starlette major has historically forced a FastAPI bump.
  Pin both exactly and move them together.
- **FastAPI is still 0.x after seven years.** That is a versioning convention, not instability —
  but it means a *minor* bump can carry a breaking change. Pin the exact version in the lockfile
  and read the release notes for each bump. On an air-gapped product this is not optional.
- **Target Python 3.13, not 3.14.** The C-extension dependencies this stack leans on — psycopg,
  argon2-cffi, torch, OCR bindings — lag a major release, and free-threaded builds are not
  something a one-person team should be debugging. Anything still on 3.10 must move before
  2026-10-31.
- **psycopg 3 is LGPL-3.0-only.** For a proprietary on-prem product this is almost certainly
  fine — dynamic import of an unmodified library — but §3 already committed to counsel review
  for extract-msg's GPL. **Put psycopg on the same list.** It costs nothing to ask both questions
  in one email; it is expensive to discover the answer late.

**The one serious counter-argument: Django.** It ships sessions, password hashing, permissions,
an admin, and migrations — four of the things §6 and §7 require and that we just decided to
build or bolt on. And §2 noted Procrastinate has **first-class Django integration**. For a
non-hands-on lead plus AI agents, "the framework already did the boring 20%" is a real argument.
What defeats it: Pydantic-typed request/response contracts and streaming responses are the shape
of this application, AI coding agents produce markedly better FastAPI than Django REST Framework
in 2026, and the async story for LLM streaming is cleaner. **Record it as a genuine near-miss,
not a non-starter.** Litestar and Flask both fail C5 on adoption and typing respectively.

### Frontend — is Next.js sound for a machine with no internet?

**Current stable: Next.js 16.2.11 and 15.5.21, both published 2026-07-21** — both are security
releases covering advisories in Server Actions, middleware, rewrites and image optimization.
Next.js 16.0 shipped **2025-10-21**.
Sources: [vercel/next.js releases (GitHub API)](https://api.github.com/repos/vercel/next.js/releases),
[Next.js 16 announcement](https://nextjs.org/blog/next-16).

**Answering the literal question first: does production mode have an external dependency? No.**

- `next start` / `output: 'standalone'` runs on a Node.js server with **no outbound calls**.
  Standalone produces a self-contained `.next/standalone` with only the dependencies actually
  used and no `node_modules` at runtime.
- **Image optimization** "works self-hosted with zero configuration when deploying using
  `next start`" — it uses `sharp` locally, not a service.
- **Fonts are not a runtime dependency:** with `next/font`, "CSS and font files are downloaded at
  build time and self-hosted with the rest of your static assets, with no requests sent to Google
  by the browser." The download happens on *your* build machine.
- **Telemetry is real but build-time.** It is **on by default** and collected during `next build`,
  `next dev` and `next export` — command invoked, Next.js version, machine info, plugins, build
  duration, page count. Not during `next start`. Disable with `NEXT_TELEMETRY_DISABLED=1` or
  `next telemetry disable`. Since we build in CI and ship an image, the firm's machine never runs
  a telemetry-emitting command — **set the variable in the Dockerfile anyway** (§7).
  Sources: [Next.js self-hosting guide](https://nextjs.org/docs/app/guides/self-hosting),
  [Next.js telemetry](https://nextjs.org/telemetry).

So Next.js *works* offline. The question is whether it is **earned**, and here the answer is no.

**What Next.js costs on this specific deployment:**

- **A second language runtime in the bundle**, with its own CVE stream. Next.js shipped security
  fixes for both the 15 and 16 lines on 2026-07-21 alone. On an air-gapped machine you cannot push
  those, and neither can the firm. Every Node dependency is a patch you now owe someone (§7's
  two-supported-versions problem, doubled).
- **Node.js 20.9+ minimum**; the current LTS is 24.18.0 (2026-06-23, "Krypton"), current release
  26.5.0 (2026-07-08) — another runtime version matrix to track across sites.
  Source: [Node.js release index](https://nodejs.org/dist/index.json).
- **Next.js 16's breaking-change list is long**: async `params`/`searchParams`/`cookies()`/
  `headers()`/`draftMode()`, `middleware.ts` → `proxy.ts`, AMP removed, `next lint` removed,
  `serverRuntimeConfig`/`publicRuntimeConfig` removed, `revalidateTag()` signature changed,
  parallel routes now require explicit `default.js` or the build fails, `next/image` defaults
  changed (`qualities`, `minimumCacheTTL`, `imageSizes`), Turbopack the default bundler. That is a
  large migration surface for a product with a multi-year on-prem support horizon.
- **Every feature Next.js 16 is architected around is dead weight or a hazard here.** Cache
  Components, PPR, ISR, CDN caching, streaming through a reverse proxy, multi-instance cache
  coordination, `NEXT_SERVER_ACTIONS_ENCRYPTION_KEY`, `deploymentId` version-skew handling — this
  is an authenticated LAN tool for perhaps 5–50 users with **zero** SEO requirement. Caching
  stale legal-triage results is a defect, not a feature.
- **Server Actions create a second server-side execution context**, which means authorisation and
  matter-scope checks must be correct in *two* places instead of one. Given §6's Chinese-walls
  requirement and C5's "AI agents write the code", that is a defect generator with a compliance
  consequence.

**`output: 'export'` is not the rescue.** It does produce static files and would let a
Next.js-fluent team keep their tooling — but static export disables proxy/middleware, ISR, Server
Actions and the default image optimizer. You would carry Next.js's entire build complexity and
breaking-change cadence to get a static bundle. Say it plainly: that is the worst of both.

### The simpler frontend, said plainly

**Build a Vite SPA and serve the static output from the reverse proxy that already exists.**

- **Vite 8.1.5 (2026-07-16)**; the 8.x stable line opened April 2026.
  Source: [vite on npm](https://registry.npmjs.org/vite).
- **React Router 8.2.0 (2026-07-08)** in declarative/data mode, or TanStack Router.
  Source: [react-router on npm](https://registry.npmjs.org/react-router).
  TanStack Start reached v1.0 in March 2026 but is a full-stack framework we do not need
  (*release date from secondary sources — treat the exact date as unverified*).
  Source: [TanStack Start overview](https://tanstack.com/start/latest/docs/framework/react/overview).

What this deletes, concretely: **the Node.js runtime disappears from the shipped bundle entirely.**
No Node container, no Node CVE stream, no Node version matrix across sites, no second place where
authorisation can be wrong. The build output is `index.html` plus hashed assets — files nginx
serves. It is one fewer deployable, which is the same argument §1 used to keep vectors in
Postgres and §2 used to delete Redis. The consistency is not accidental: **every constraint in
this document points the same way, and Next.js is the one place the earlier reasoning was about
to be contradicted.**

What you give up: SSR and SEO, worth exactly zero for an authenticated internal tool; and initial
page weight, which is irrelevant on a LAN.

> ### Recommendation 8 — **Keep Python 3.13 / FastAPI 0.139.x (pinned exactly, with Starlette moved only in lockstep). Replace Next.js with a Vite 8 SPA plus React Router 8, built in CI to static files and served by the same reverse proxy that fronts the API.**
> **Strongest reason:** Next.js is technically offline-capable but structurally wrong for this
> shape — it adds a Node.js runtime and its patch obligations to an air-gapped bundle, a second
> server-side execution context where matter-level authorisation can be wrong, and an entire
> caching architecture whose every feature is a liability in a legal-triage tool. A Vite SPA
> deletes a deployable and leaves exactly one place where auth is enforced.
> **Main risk:** hiring and AI-agent fluency. Next.js is the default that models and contractors
> produce best; a Vite SPA means owning routing, data fetching, auth-token handling and build
> configuration yourself, and there is more low-quality Next.js training data than good Vite-SPA
> training data. Mitigate by choosing conventional, heavily-documented pieces inside the SPA
> (React Router in data mode, TanStack Query, one component library) rather than assembling
> something bespoke, and by generating the API client from FastAPI's OpenAPI schema so the
> contract between the two halves is machine-checked rather than hand-written.
> **Note on Django:** the backend near-miss above is worth revisiting if §6's self-built session
> and permission code turns out to be larger than estimated. That is the trigger to reopen it —
> not taste.

---

## Open risks across all eight areas

Three decisions in this document are more likely than the rest to look wrong by July 2027. Each
is stated with the single observation that would falsify it, because a risk you cannot test is
just anxiety.

**1. Recommendation 1 — pgvector as the only vector store.** The entire memory argument rests on
an *assumed* chunk yield of 3–8 M for a 100 000-document matter, on a corpus nobody has seen. The
escape hatch (pgvectorscale StreamingDiskANN) breaks C2 by being unavailable on the managed dev
tier, so being wrong means an on-prem-only code path — the exact divergence C2 exists to prevent.
> **Falsified by:** measuring actual chunk yield on a real 100k-document `.msg` + PDF corpus. If
> it exceeds ~8 M chunks, or if HNSW p95 query latency on a matter-scoped filter exceeds ~2 s, or
> if the index build cannot complete within `maintenance_work_mem` on a 64 GB machine, the
> single-store decision is wrong. **This measurement must happen before any retrieval code is
> written** — it is the cheapest and highest-value test in the whole plan.

**2. Recommendation 6 — that the firm has no identity provider.** Self-built sessions are correct
*if* identity stops at the application boundary. Firms large enough to buy this run Microsoft 365
or an on-prem AD, and enterprise security questionnaires ask for SSO as a matter of routine. Being
wrong here does not merely add work — it puts Authlib, with a **CVSS 9.1 signature-verification
bypass patched only in March 2026** and eleven other advisories, onto the critical path of an
unpatchable machine.
> **Falsified by:** the first real customer's security questionnaire or IT review requiring
> SAML/OIDC federation. Watch for it during the first pilot, not at contract signature. Cheap
> insurance now: keep `Principal` resolution behind one interface, and never let a route import
> the session table directly.

**3. Recommendation 5 — that one machine carries the whole workload.** §3 sized OCR, §4 sized
embedding, and §5 sized LLM inference **independently, each assuming the CCBE €2 000 machine**.
Nobody added them up. Tesseract at ~25 pages/min, BGE-M3 at 4 800 passages/s, and a 24B model
doing 150 M prefill tokens are three jobs contending for the same 24 GB of VRAM and the same CPU,
and the estimates are engineering arithmetic rather than measurements. There is also no headroom
for the fact that a firm will want to work on matter B while matter A ingests.
> **Falsified by:** an end-to-end timed run of 5 000 real documents on the target hardware with
> OCR, embedding and LLM judgement all active concurrently. If wall-clock ingest exceeds one
> weekend for 100 000 documents, or if the scanned-PDF proportion pushes Tesseract past the LLM as
> the bottleneck, the hardware recommendation and the €2 000 sales story are both wrong. **The
> §5 cascade design — dedup and retrieval filters before LLM judgement — is the mitigation, and
> it should be built first, not last.**
