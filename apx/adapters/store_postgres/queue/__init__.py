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

import asyncio
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
from apx.adapters.store_postgres.opening import open_store
from apx.adapters.store_postgres.store import ImportJobView, SqlStore
from apx.core.app.ingest import SCHEMA_VERSION, enumerate_units, ingest_one_file
from apx.core.app.rank import LineNotDrawn, identity_inputs, rank_and_draw_the_line
from apx.core.domain.chunking import chunking_config
from apx.core.domain.config import ExpansionBounds, cascade_config, expansion_bounds
from apx.core.ports.embedding import Embedder
from apx.core.ports.extraction import Extractor
from apx.core.ports.judge import Judge
from apx.core.ports.originals import OriginalStore
from apx.core.ports.scorer import SemanticScorer
from apx.wiring import open_judge


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
    live DATABASE_URL) and runs the resumable orchestration.

    Through ``open_store`` since Story 5.9, and the journal is REQUIRED: the worker writes the bulk
    of the record, and every head it advanced without an outside witness was a stretch a later
    truncation could remove undetectably (AD-35)."""
    _run_import(open_store(), job_id)


# ── Story 7.6: the RANKING job (AD-6) ─────────────────────────────────────────────────────────
# AD-6 names ranking by name as a queued job: one model call per uncertain pièce does not belong in
# a request. The shape is the import's — a store-typed orchestration, a thin registered task, and an
# enqueue helper that opens the queue itself — and the places it deliberately diverges are marked.

#: One cascade per job, ever. `run_cascade` is a single monolithic in-memory pass with no
#: checkpoint, so a re-dispatch does not resume anything — it re-pays one model call per uncertain
#: pièce over the whole matter. The import's 100 attempts are safe only because a re-dispatch
#: processes ONLY still-pending units; there is no such unit here.
_RANKING_MAX_ATTEMPTS = 1


def _run_ranking(
    store: SqlStore, job_id: str, *, embedder: Embedder | None = None, judge: Judge | None = None,
    scorer: SemanticScorer | None = None, now: datetime | None = None,
) -> None:
    """Run one queued ranking against the application-owned ledger — pure of Procrastinate, so it is
    driven directly with a SQLite store exactly as ``_run_import`` is.

    **Every exit is a terminal ledger state.** The act cannot raise past this function on a failure
    of the ranking itself, because a raise would be a claim about *availability* over a permanent
    cause, in the direction a caller retries rather than reports — the shape story 7.4 closed at the
    upload route. The lawyer is told what happened, in her language, on a row she can read.

    The wall comes off the ledger row, not from the worker's imagination, and it is re-checked
    **before anything is read**: ``read_case_theory`` answers ``None`` for out-of-scope and for
    absent alike, and a ``None`` theory is also how the act says *rank on intrinsic signals* — so a
    job that lost its wall between enqueue and dispatch would otherwise produce a complete,
    permanently fingerprinted ranking whose header names a deliberate methodology for a theory that
    was simply never fetched.
    """
    stamp = now or datetime.now(UTC)
    job = store.read_ranking_job(job_id)
    if job is None or job.state in ("done", "failed"):
        return  # a re-dispatch of a terminal job is a no-op
    # AD-17: the counter advances in its own committed transaction BEFORE the work, so an OS-level
    # kill still advances it and the cascade is never paid for twice on one job.
    if store.bump_ranking_attempt(job_id, stamp) > _RANKING_MAX_ATTEMPTS:
        store.fail_ranking_job(
            job_id, now=stamp,
            detail="le classement a déjà été lancé une fois et n'est pas relancé automatiquement ; "
                   "relancez-le si vous le souhaitez")
        return
    store.start_ranking_job(job_id, stamp)
    scopes = {job.scope}
    if not store.matter_is_held(tenant=job.tenant, matter=job.matter, scopes=scopes):
        store.fail_ranking_job(
            job_id, now=stamp,
            detail="dossier introuvable sous le périmètre de la demande ; rien n'a été lu")
        return
    try:
        version, _placement = _rank_now(
            store, tenant=job.tenant, matter=job.matter, actor=job.actor, scopes=scopes,
            embedder=embedder, judge=judge, scorer=scorer)
    except LineNotDrawn as exc:
        # The order committed, the cut did not — named, with the version, so the remedy (placing
        # the line over THAT version) is reachable rather than inferable from "the latest".
        store.fail_ranking_job(
            job_id, now=stamp, version_no=exc.version_no,
            detail=f"le classement n° {exc.version_no} est enregistré, la ligne n'a pas été "
                   "tracée ; posez la ligne sur ce classement")
        return
    except Exception as exc:  # noqa: BLE001 — every failure is a ledger state, never a raise
        store.fail_ranking_job(job_id, now=stamp, detail=f"le classement a échoué : {exc}")
        return
    store.finish_ranking_job(job_id, version_no=version.version_no, now=stamp)


def _rank_now(
    store: SqlStore, *, tenant: str, matter: str, actor: str, scopes: set[str],
    embedder: Embedder | None, judge: Judge | None, scorer: SemanticScorer | None,
):  # noqa: ANN202 — (RankingVersion, LinePlacementView | None), both adapter-free core types
    """Assemble the act's arguments and perform it — the same assembly ``manage rank`` makes, and
    for the same reasons: every identity input comes from the thing that actually produced the
    order (the judge this deployment composed, never configuration, which records a preference and
    would name a model that never ran).

    ``rank_and_draw_the_line``, not ``produce_ranking``: a version with no cut leaves the matter
    worse than before the re-rank and silently (story 7.5)."""
    # The three ports the cascade runs on, built at this composition root and injectable here —
    # the same seam ``_run_import`` opens for the embedder and the original store, and for the same
    # reason: a local model and a pgvector session are not things a test can carry (AD-11).
    embedder = embedder or _build_embedder()
    scorer = scorer if scorer is not None else store.semantic_scorer(embedder)
    judge = judge or open_judge(store, tenant)
    get = lambda key: store.get_config(tenant, key)  # noqa: E731 — the config-as-data getter
    theory = store.read_case_theory(tenant=tenant, matter=matter, scopes=scopes)
    current = theory.current if theory is not None else None
    return rank_and_draw_the_line(
        store.cascade_units(matter, tenant, scopes),
        case_theory=current.text if current is not None else None,
        scorer=scorer,
        judge=judge,
        config=cascade_config(get),
        inputs=identity_inputs(
            judge=judge.identity,
            case_theory_version_id=current.version_id if current is not None else None,
            embedder_model_id=embedder.model_id, embedder_model_version=embedder.model_version,
            chunking_config_version=chunking_config(get).version,
            schema_version=SCHEMA_VERSION),
        tenant=tenant, matter=matter, actor=actor, scopes=scopes,
        recorder=store, placer=store)


@app.task(name="apx.run_ranking", retry=RetryStrategy(max_attempts=3, linear_wait=5))
def run_ranking(job_id: str) -> None:
    """The registered ranking task. Builds the store at run time so the worker binds the live
    ``DATABASE_URL``.

    The retry is small and it guards the **bookkeeping**, not the cascade: ``_run_ranking`` turns
    every failure of the ranking itself into a terminal ledger state and returns, so a retry can
    only ever follow a failure of the ledger writes. Should one fire, the ledger's own cap of
    :data:`_RANKING_MAX_ATTEMPTS` marks the job failed without running a second cascade."""
    _run_ranking(open_store(), job_id)


_open_lock = asyncio.Lock()
_opened = False


async def ensure_open() -> None:
    """Open the queue's connection pool, once per process, before anything is deferred.

    **This existed nowhere, and the consequence was that no upload could ever be accepted on a real
    deployment.** ``PsycopgConnector.pool`` raises ``AppNotOpen`` until ``open_async`` has been
    called, ``open_async`` was called only by ``manage worker`` — a *different process* — and the
    upload route wrapped its ``defer`` in ``except Exception`` and answered *« file d'import
    indisponible »*. So the product's front door returned 503 to every submission, and the test
    suite could not see it: ``_connector`` picks the connector from ``DATABASE_URL`` at import time
    and the suite runs on SQLite, which yields the in-memory connector — the one implementation with
    no such guard.

    Opening here rather than only at start-up is deliberate. A start-up hook is a *habit*: it works
    until a second process, a management command or a test harness defers without having run it, and
    that failure is silent in exactly the same way. Deferring opens the queue, so the property
    belongs to the act rather than to whoever remembered to call the hook. The API still opens it at
    boot as well, so a queue that cannot be reached is discovered when the container starts and not
    by the first lawyer who drops a folder on it.
    """
    global _opened
    if _opened:
        return
    async with _open_lock:
        if not _opened:                        # re-checked under the lock: two concurrent uploads
            await app.open_async()             # must not both open the pool
            _opened = True


async def close_queue() -> None:
    """Release the pool on shutdown. Idempotent — a process that never deferred closes nothing."""
    global _opened
    if _opened:
        await app.close_async()
        _opened = False


async def enqueue_import(job_id: str) -> None:
    """Defer the import job onto the queue (non-blocking). Async so it composes with the async
    HTTP handler's event loop; the API calls this after durably creating the ledger row and
    spooling the bytes, then the request returns immediately (AD-6)."""
    await ensure_open()
    await run_import.defer_async(job_id=job_id)


async def enqueue_ranking(job_id: str) -> None:
    """Defer the ranking job onto the queue (non-blocking), opening the queue first.

    ``ensure_open`` is called HERE, in the act's own body, and not by a wrapper: deferring opens the
    queue, so the property belongs to the act rather than to whoever remembered a start-up hook
    (story 7.4). ``every_defer_opens_the_queue`` reads exactly this — an intersection of the calls
    a function makes — so a helper that delegates its opening does not satisfy it."""
    await ensure_open()
    await run_ranking.defer_async(job_id=job_id)
