"""Story 2.2 / AD-17 resume on the REAL PostgreSQL transaction property — skipped unless
DATABASE_URL points at PostgreSQL (CI sets it). It induces a crash mid-unit at THREE points and
asserts resume from the last committed unit: no piece re-indexed as new, none skipped. This is the
durability the in-memory connector cannot reproduce (it has no transactional rollback).

Honest scope note: this uses an in-process crash (a raised exception) at three points as the
SIGKILL proxy, exercising the real commit/rollback boundary. A true OS-level ``SIGKILL`` of a
subprocess worker — the fullest form of AD-17's "asserted by SIGKILL, not only an exception" — is
a subprocess-harness follow-up; the counter-before-work commit that makes SIGKILL safe is proven
directly in ``tests/worker/test_import_job.py``.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from apx.adapters.store_postgres.models import Base
from apx.adapters.store_postgres.queue import _persist_unit, _run_import
from apx.adapters.store_postgres.store import SqlStore
from apx.core.app.ingest import IngestionResult
from tests.embedding_fakes import FakeEmbedder

_URL = os.environ.get("DATABASE_URL", "")
_IS_PG = _URL.startswith(("postgres://", "postgresql://", "postgresql+psycopg://"))
pytestmark = pytest.mark.skipif(not _IS_PG, reason="no PostgreSQL DATABASE_URL — CI runs this")

_FAKE = FakeEmbedder()  # story 2.8: the embedder injected at the port boundary (never the real one)


class _NoRetention:
    """A no-op OriginalStore (story 3.5a) — this resume test asserts crash/resume, not retention."""

    def put(self, tenant: str, content_hash: str, data: bytes) -> None: ...

    def open(self, tenant: str, content_hash: str) -> bytes:
        raise FileNotFoundError


_ORIG = _NoRetention()

_NOW = datetime(2026, 7, 27, tzinfo=UTC)


@pytest.fixture
def store() -> SqlStore:
    engine = create_engine(_URL, future=True)
    Base.metadata.create_all(engine)
    return SqlStore(sessionmaker(bind=engine, future=True))


def _crash_after(n: int):  # noqa: ANN202 — a work fn that commits n units then crashes
    seen = {"c": 0}

    def work(st, job, uid, prov, *, max_bytes, now):  # noqa: ANN001, ANN202
        if seen["c"] >= n:
            raise RuntimeError("SIGKILL proxy — worker died mid-job")
        seen["c"] += 1
        _persist_unit(st, job, uid, prov, max_bytes=max_bytes, now=now, embedder=_FAKE,
                      original_store=_ORIG)

    return work


def test_resume_at_three_points_never_duplicates_or_skips(tmp_path, store) -> None:
    spool = tmp_path / "spool"
    spool.mkdir(parents=True, exist_ok=True)
    for i in range(9):
        (spool / f"p{i}.txt").write_text(f"piece {i}", encoding="utf-8")
    store.save(IngestionResult(), "w", "Me A", matter="mpg", tenant="tpg", audit=False)
    job_id = "job-pg"
    store.create_import_job(
        job_id=job_id, tenant="tpg", matter="mpg", scope="w", actor="Me A", custodian="M. Martin",
        case_theory=None, spool_path=str(spool), owns_spool=False, now=_NOW)

    for kill_after in (3, 6, 8):                    # three induced crashes, each committing more
        with pytest.raises(RuntimeError):
            _run_import(store, job_id, work=_crash_after(kill_after), now=_NOW)
    _run_import(store, job_id, now=_NOW)            # the final clean resume finishes the job

    assert store.inventory("mpg", "tpg", {"w"}).in_corpus == 9   # all nine, none re-indexed
    prog = store.import_progress(job_id)
    assert prog.state == "done" and prog.processed == 9 and prog.pending == 0
