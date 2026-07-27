"""The resumable import job (Story 2.2, AD-17), tested against in-memory SQLite.

The orchestration ``_run_import`` is pure of Procrastinate, so the load-bearing mechanics are
tested directly: per-unit idempotent commit, resume from the last committed unit, the attempt
counter advanced BEFORE the work (so an OS kill still advances it), poison-unit quarantine in an
independent transaction, and the bounded-memory `resource-exhausted` class. One test drives the
real enqueue→worker→ledger path over Procrastinate's in-memory connector. The TRUE OS-``SIGKILL``
durability guarantee — resume as a PostgreSQL transaction property — is the Postgres-leg test in
``tests/adapters/test_import_resume_postgres.py`` (skipped without a PostgreSQL DATABASE_URL).
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from apx.adapters.store_postgres.models import Base, Failure, ImportUnit
from apx.adapters.store_postgres.queue import _persist_unit, _run_import
from apx.adapters.store_postgres.store import SqlStore
from apx.core.app.ingest import IngestionResult

_NOW = datetime(2026, 7, 27, 12, 0, tzinfo=UTC)


@pytest.fixture
def store() -> SqlStore:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return SqlStore(sessionmaker(bind=engine, future=True))


def _job(store: SqlStore, tmp_path: Path, files: dict[str, bytes], *, matter: str = "m") -> str:
    """Spool ``files`` (relative path → bytes), create the matter and the import-job ledger row,
    and return the job id — the shape the API's enqueue produces, minus Procrastinate."""
    spool = tmp_path / f"spool-{matter}"
    for rel, content in files.items():
        dest = spool / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(content)
    store.save(IngestionResult(), "w", "Me Actor", matter=matter, tenant="t", audit=False)
    job_id = f"job-{matter}"
    store.create_import_job(
        job_id=job_id, tenant="t", matter=matter, scope="w", actor="Me Actor",
        custodian="M. Martin", case_theory=None, spool_path=str(spool), owns_spool=True, now=_NOW)
    return job_id


def _classes(store: SqlStore) -> set[str]:
    with store._sf() as s:
        return {f.error_class for f in s.scalars(select(Failure)).all()}


def test_import_processes_units_finishes_and_writes_one_audit_entry(tmp_path, store) -> None:
    job_id = _job(store, tmp_path, {"a.txt": b"lettre", "sub/b.txt": b"note", "empty.txt": b""})
    _run_import(store, job_id, now=_NOW)
    inv = store.inventory("m", "t", {"w"})
    assert inv.in_corpus == 2 and inv.failures == 1          # a, b are pieces; empty → a failure
    prog = store.import_progress(job_id)
    assert prog.state == "done" and prog.submitted == 3 and prog.processed == 3
    assert prog.pending == 0 and not prog.provisional
    trail = store.read_audit("m", "t", {"w"})
    assert [e.action for e in trail.entries] == ["ingest"]   # ONE job-level entry, not one per unit
    assert not (tmp_path / "spool-m").exists()               # the owned spool is consumed on finish


def test_resume_processes_only_pending_units_and_never_duplicates(tmp_path, store) -> None:
    job_id = _job(store, tmp_path, {f"p{i}.txt": f"piece {i}".encode() for i in range(6)})
    seen: list[str] = []

    def flaky(st, job, uid, prov, *, max_bytes, now):  # noqa: ANN001, ANN202
        if len(seen) >= 2:
            raise RuntimeError("worker killed mid-job")   # a crash after two committed units
        seen.append(prov)
        _persist_unit(st, job, uid, prov, max_bytes=max_bytes, now=now)

    with pytest.raises(RuntimeError):
        _run_import(store, job_id, work=flaky, now=_NOW)     # dies after 2 units
    committed_first = set(seen)
    assert store.inventory("m", "t", {"w"}).in_corpus == 2

    # Resume: a spy asserts the work runs ONLY for the still-pending units — never the two already
    # committed (guards the resume filter itself, not merely the merge-idempotency end-state).
    resumed: list[str] = []

    def spy(st, job, uid, prov, *, max_bytes, now):  # noqa: ANN001, ANN202
        resumed.append(prov)
        _persist_unit(st, job, uid, prov, max_bytes=max_bytes, now=now)

    _run_import(store, job_id, work=spy, now=_NOW)
    assert set(resumed).isdisjoint(committed_first)         # committed units are NOT re-processed
    assert len(resumed) == 4                                # exactly the four still-pending units
    assert store.inventory("m", "t", {"w"}).in_corpus == 6  # all 6, none re-indexed as new
    assert store.import_progress(job_id).state == "done"


def test_the_attempt_counter_advances_before_the_work(tmp_path, store) -> None:
    # AD-17 (a): the counter is committed in its own transaction BEFORE the unit's work, so an OS
    # kill (here, a crash) still advances it — else resume loops onto the poison forever.
    job_id = _job(store, tmp_path, {"x.txt": b"boom"})

    def boom(st, job, uid, prov, *, max_bytes, now):  # noqa: ANN001, ANN202
        raise RuntimeError("killed mid-work, before any commit")

    with pytest.raises(RuntimeError):
        _run_import(store, job_id, work=boom, now=_NOW)
    with store._sf() as s:
        unit = s.scalars(select(ImportUnit).where(ImportUnit.job_id == job_id)).one()
    assert unit.attempts == 1 and unit.state == "pending"    # advanced despite the crash; resumable


def test_a_poison_unit_is_quarantined_and_the_job_completes(tmp_path, store) -> None:
    store.set_config("t", "admin", "import_max_attempts", 2)
    job_id = _job(store, tmp_path, {"good.txt": b"ok", "poison.txt": b"boom", "z_good.txt": b"ok2"})

    def work(st, job, uid, prov, *, max_bytes, now):  # noqa: ANN001, ANN202
        if "poison" in prov:
            raise RuntimeError("this unit keeps killing the worker")
        _persist_unit(st, job, uid, prov, max_bytes=max_bytes, now=now)

    for _ in range(10):                                      # simulate re-dispatch after each kill
        try:
            _run_import(store, job_id, work=work, now=_NOW)
        except RuntimeError:
            continue
        break
    prog = store.import_progress(job_id)
    assert prog.state == "done"                              # the job proceeded past the poison
    assert prog.committed == 2 and prog.quarantined == 1
    assert "quarantined" in _classes(store)                 # on the record (independent txn)
    assert store.inventory("m", "t", {"w"}).in_corpus == 2  # the two good units are in the corpus


def test_an_oversized_unit_is_resource_exhausted_not_an_outage(tmp_path, store) -> None:
    store.set_config("t", "admin", "import_unit_max_bytes", 10)   # a tiny per-unit ceiling
    job_id = _job(store, tmp_path, {"big.txt": b"x" * 100, "small.txt": b"ok"})
    _run_import(store, job_id, now=_NOW)
    assert "resource-exhausted" in _classes(store)          # big → a register entry, not a crash
    assert store.inventory("m", "t", {"w"}).in_corpus == 1  # small still committed; worker survived
    assert store.import_progress(job_id).state == "done"


def test_progress_is_read_from_the_ledger(tmp_path, store) -> None:
    job_id = _job(store, tmp_path, {"a.txt": b"1", "b.txt": b"2"})
    assert store.import_progress(job_id).state == "enumerating"   # provisional before the run
    _run_import(store, job_id, now=_NOW)
    p = store.import_progress(job_id)
    assert p.submitted == 2 and p.processed == 2 and p.pending == 0 and not p.provisional


def test_one_open_import_job_per_matter(tmp_path, store) -> None:
    job_id = _job(store, tmp_path, {"a.txt": b"1"})
    assert store.open_import_job("t", "m") == job_id         # open while running (FR-7)
    _run_import(store, job_id, now=_NOW)
    assert store.open_import_job("t", "m") is None            # closed once done


def test_re_dispatching_a_done_job_is_a_no_op(tmp_path, store) -> None:
    # AD-17: a re-dispatch of a completed job (its owned spool already consumed) must NOT re-derive
    # submitted to 0 nor append a second job-level audit entry — the sole authority stays correct.
    job_id = _job(store, tmp_path, {"a.txt": b"1", "b.txt": b"2"})
    _run_import(store, job_id, now=_NOW)                      # done; the owned spool is now gone
    before = store.import_progress(job_id)
    n_audit = len(store.read_audit("m", "t", {"w"}).entries)
    _run_import(store, job_id, now=_NOW)                      # a redelivery of the same job
    after = store.import_progress(job_id)
    assert after.submitted == before.submitted == 2 and after.processed == 2   # not reset to 0
    assert len(store.read_audit("m", "t", {"w"}).entries) == n_audit == 1       # no 2nd entry


def test_a_missing_owned_spool_fails_closed(tmp_path, store) -> None:
    # A spool absent at run time (a mount race) is a fault, not a legit empty 0/0 import: fail
    # closed so the queue retries, never a silent empty completion (AD-17).
    import shutil

    job_id = _job(store, tmp_path, {"a.txt": b"1"})
    shutil.rmtree(tmp_path / "spool-m")                       # the owned spool vanishes
    with pytest.raises(RuntimeError):
        _run_import(store, job_id, now=_NOW)
    assert store.import_progress(job_id).state != "done"     # never falsely completed


def test_the_db_enforces_one_open_job_per_matter(tmp_path, store) -> None:
    # FR-7 closed atomically (not just the API's read-then-create TOCTOU): a second OPEN job for
    # the same matter is rejected by the partial unique index, even under concurrency.
    from sqlalchemy.exc import IntegrityError

    _job(store, tmp_path, {"a.txt": b"1"})                   # one open job for matter "m"
    with pytest.raises(IntegrityError):
        store.create_import_job(
            job_id="job-dup", tenant="t", matter="m", scope="w", actor="Me A",
            custodian="M. Martin", case_theory=None, spool_path=str(tmp_path / "s2"), now=_NOW)


def test_worker_runs_the_job_via_the_inmemory_connector(tmp_path, monkeypatch) -> None:
    # The real enqueue→worker→ledger path over Procrastinate's in-memory connector: the task
    # builds its own store from DATABASE_URL and runs the resumable orchestration.
    url = f"sqlite:///{tmp_path / 'apx.db'}"
    Base.metadata.create_all(create_engine(url))
    monkeypatch.setenv("DATABASE_URL", url)
    fs = SqlStore(sessionmaker(bind=create_engine(url), future=True))
    job_id = _job(fs, tmp_path, {"a.txt": b"lettre", "b.txt": b"note"})

    from apx.adapters.store_postgres.queue import app as queue_app
    from apx.adapters.store_postgres.queue import run_import
    queue_app.connector.reset()
    run_import.defer(job_id=job_id)                          # enqueue (sync — no running loop here)
    queue_app.run_worker(wait=False, listen_notify=False, install_signal_handlers=False)

    assert fs.import_progress(job_id).state == "done"
    assert fs.inventory("m", "t", {"w"}).in_corpus == 2
