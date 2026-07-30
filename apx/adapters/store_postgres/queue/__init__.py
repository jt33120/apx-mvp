"""The queue edge — the ONLY module that touches Procrastinate's connector and queue tables
(AD-17 structural property). Everything above reads the application-owned import ledger
(``import_job`` / ``import_unit``), never Procrastinate's job table, so two readers can never
disagree on the *processed-against-submitted* figure.

The resumable, idempotent ingestion the worker runs is a transaction property of the
PostgreSQL-backed queue (AD-5): each *pièce* is one unit committed against the ledger, keyed by
its identity; the per-unit attempt counter is advanced in its own transaction **before** the
unit's work begins (so an OS ``SIGKILL`` still advances it and resume never loops onto a poison
forever), and a poison unit is quarantined in a transaction **independent** of the failing
unit's (so an exception handler cannot roll the quarantine back with the failure).
"""

from __future__ import annotations

import functools
import os
import shutil
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from procrastinate import App, PsycopgConnector, RetryStrategy, testing

from apx.adapters.embedder_bgem3.bgem3 import Bgem3Embedder
from apx.adapters.expansion.archives import SevenZipExpander, ZipExpander
from apx.adapters.expansion.composite import CompositeExpander
from apx.adapters.expansion.mail import EmlExpander, MboxExpander
from apx.adapters.expansion.pdf import PdfPortfolioExpander
from apx.adapters.extraction.composite import CompositeExtractor
from apx.adapters.extraction.files import FileExtractor
from apx.adapters.extraction.msg import MsgExpander, MsgExtractor
from apx.adapters.ocr_tesseract.tesseract import TesseractExtractor, WithOcr
from apx.adapters.originals_fs import FilesystemOriginalStore
from apx.adapters.store_postgres.admission import admit
from apx.adapters.store_postgres.engine import make_session_factory
from apx.adapters.store_postgres.store import ImportJobView, SqlStore
from apx.core.app.ingest import enumerate_units, ingest_one_file
from apx.core.domain.config import ExpansionBounds, expansion_bounds
from apx.core.ports.embedding import Embedder
from apx.core.ports.extraction import Extractor
from apx.core.ports.originals import OriginalStore


def _conninfo(database_url: str) -> str:
    """A libpq conninfo from the SQLAlchemy URL — strip the ``+psycopg`` driver marker (AD-5:
    the worker's queue is the same PostgreSQL as the store)."""
    return (
        database_url.replace("postgresql+psycopg://", "postgresql://")
        .replace("postgres://", "postgresql://")
    )


def _connector() -> PsycopgConnector | testing.InMemoryConnector:
    """The real PostgreSQL connector against the same ``DATABASE_URL`` as the store, or the
    in-memory connector for tests / when no PostgreSQL is configured (sqlite, unset)."""
    url = os.environ.get("DATABASE_URL", "")
    if url.startswith("postgres") and "sqlite" not in url:
        return PsycopgConnector(conninfo=_conninfo(url))
    return testing.InMemoryConnector()


app = App(connector=_connector())


def _build_extractor() -> Extractor:
    """Compose the extractor at the worker edge (same shape as the API edge): .msg routes to the
    out-of-process, GPL-isolated MsgExtractor, everything else to FileExtractor, and — where the
    image sets APX_OCR (Tesseract installed) — scans and images fall back to OCR. The born-digital
    path never pays the OCR cost (AD-28)."""
    primary = CompositeExtractor([MsgExtractor(), FileExtractor()])
    if os.environ.get("APX_OCR", "").strip().lower() in ("1", "true", "yes"):
        return WithOcr(primary, TesseractExtractor())
    return primary


def _build_expander(bounds: ExpansionBounds) -> CompositeExpander:
    """The container chain (Story 2.4), each expander config-bounded (AD-17): archives (.zip/.7z),
    mailbox (.mbox), email (.eml) + PDF portfolios, and .msg (nested). The composition root wires
    the adapters — that is not an adapter importing another adapter (AD-4)."""
    return CompositeExpander([
        ZipExpander(bounds), SevenZipExpander(bounds), MboxExpander(bounds),
        EmlExpander(bounds), PdfPortfolioExpander(bounds), MsgExpander(bounds)])


def _build_embedder() -> Embedder:
    """The ONE embedder (AD-11), built ONCE at the composition root — never per unit (a local model
    is expensive to construct). Tests inject a fake at this seam instead (AD-11)."""
    return Bgem3Embedder()


def _build_original_store() -> OriginalStore:
    """The retained-original store (Story 3.5a), built ONCE at the composition root from the data
    volume + the encryption key — the pièce viewer renders from these encrypted, content-addressed
    blobs in a later increment. Tests inject a filesystem store on a tmp root at this seam."""
    return FilesystemOriginalStore.from_env()


def _persist_unit(
    store: SqlStore, job: ImportJobView, unit_id: str, provenance: str, *,
    max_bytes: int, now: datetime, embedder: Embedder, original_store: OriginalStore,
) -> None:
    """The default unit work: extract one file, RETAIN each pièce's original at rest (Story 3.5a —
    content-addressed, encrypted, so the viewer can render it later), EMBED each piece (Story 2.8 —
    a precondition of corpus admission: an embedder failure moves the piece to the *failure register*
    with its class, never a Piece and never a chunk), persist idempotently (``audit=False`` — one
    job-level audit entry at completion), write the chunk(s), and mark the unit committed. A clean
    extraction OR embedder failure is a register row, not a raise; only a hard crash (SIGKILL/OOM in
    reality) escapes, which the resumable loop and quarantine handle."""
    path = Path(job.spool_path) / provenance
    bounds = expansion_bounds(lambda k: store.get_config(job.tenant, k))
    noise_patterns = store.get_config(job.tenant, "exclusion_list")  # config-as-data (FR-6)
    result = ingest_one_file(
        path, provenance, job.matter, job.tenant, _build_extractor(),
        custodian=job.custodian, expander=_build_expander(bounds), original_store=original_store,
        now=now, max_bytes=max_bytes, bounds=bounds, noise_patterns=noise_patterns)
    admit(
        store, embedder, result, scope=job.scope, actor=job.actor, matter=job.matter,
        tenant=job.tenant, audit=False)
    store.mark_unit_committed(unit_id)


UnitWork = Callable[..., None]


def _process_unit(
    store: SqlStore, job: ImportJobView, unit_id: str, provenance: str, *,
    max_bytes: int, max_attempts: int, now: datetime, work: UnitWork,
) -> None:
    # AD-17 (a): advance the attempt counter in its own committed transaction BEFORE the work,
    # so an OS-level kill still advances it and resume never loops onto the poison forever.
    attempts = store.bump_import_attempt(unit_id)
    if attempts > max_attempts:
        store.quarantine_unit(
            unit_id=unit_id, provenance=provenance, matter=job.matter, tenant=job.tenant, now=now,
            custodian=job.custodian)
        return
    try:
        work(store, job, unit_id, provenance, max_bytes=max_bytes, now=now)
    except Exception:  # noqa: BLE001 — a hard, escaping failure (a crash proxy), not a register row
        if attempts >= max_attempts:
            # AD-17 (b): quarantine in a transaction INDEPENDENT of the failing unit's, so an
            # exception handler cannot roll the quarantine back and retry the poison forever.
            store.quarantine_unit(
                unit_id=unit_id, provenance=provenance, matter=job.matter, tenant=job.tenant,
                now=now, custodian=job.custodian)
            return
        raise  # leave it pending; the job re-dispatches and the (committed) counter advances


def _run_import(
    store: SqlStore, job_id: str, *, work: UnitWork | None = None,
    embedder: Embedder | None = None, original_store: OriginalStore | None = None,
    now: datetime | None = None,
) -> None:
    """The resumable orchestration (AD-17) — pure of Procrastinate, so it is tested directly with
    a SQLite store. Enumerate (freeze submitted, idempotent), process each pending unit, finish
    with one job-level audit entry, then drop the spool. A re-dispatch after a kill re-enumerates
    (idempotent) and processes only the still-pending units — resume. The ONE embedder and the ONE
    original store are built once here and threaded into the default unit work (Story 2.8/3.5a); a
    test injects fakes instead. The uploaded spool is still dropped on completion — the ORIGINALS now
    live in the retained-original store, encrypted and content-addressed, not in the spool."""
    embedder = embedder if embedder is not None else _build_embedder()
    if work is None:
        originals = original_store if original_store is not None else _build_original_store()
        work = functools.partial(_persist_unit, embedder=embedder, original_store=originals)
    stamp = now or datetime.now(UTC)
    job = store.read_import_job(job_id)
    if job is None or job.state == "done":
        return  # a re-dispatch of a completed job is a no-op — never re-enumerate a consumed spool
    folder = Path(job.spool_path)
    if job.owns_spool and not folder.is_dir():
        # A missing OWNED spool for a not-yet-done job is a fault, not an empty import: fail closed
        # so the queue retries, rather than freezing the job at a false, silent 0/0 (AD-17).
        raise RuntimeError(f"import {job_id}: the owned spool {folder} is missing")
    provenances = enumerate_units(folder) if folder.is_dir() else []
    store.record_enumeration(job_id, provenances, stamp)
    max_bytes = int(store.get_config(job.tenant, "import_unit_max_bytes"))
    max_attempts = int(store.get_config(job.tenant, "import_max_attempts"))
    for unit_id, provenance in store.pending_units(job_id):
        _process_unit(
            store, job, unit_id, provenance, max_bytes=max_bytes, max_attempts=max_attempts,
            now=stamp, work=work)
    store.finish_import(job_id, stamp)
    if job.owns_spool:
        # the uploaded spool is consumed; pieces AND their retained originals persist (Story 3.5a —
        # each original is now an encrypted, content-addressed blob in the original store, not here).
        shutil.rmtree(folder, ignore_errors=True)


@app.task(name="apx.run_import", retry=RetryStrategy(max_attempts=100))
def run_import(job_id: str) -> None:
    """The registered ingestion task. Builds the store at run time (so the worker binds the
    live DATABASE_URL) and runs the resumable orchestration."""
    _run_import(SqlStore(make_session_factory()), job_id)


async def enqueue_import(job_id: str) -> None:
    """Defer the import job onto the queue (non-blocking). Async so it composes with the async
    HTTP handler's event loop; the API calls this after durably creating the ledger row and
    spooling the bytes, then the request returns immediately (AD-6)."""
    await run_import.defer_async(job_id=job_id)
