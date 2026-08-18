"""The 0038 migration — the ranking-job ledger (story 7.6, AD-6/AD-17).

The assertion that carries the story is the **open-job index**. ``uq_import_job_open`` is
``state != 'done'``, and copying it here would be the plausible move: it is the neighbouring
ledger, written for the same rule (FR-7, one open job per *matter*). But this table has a terminal
``failed`` state that ``import_job`` does not, and ``failed`` is not ``done`` — so under the
import's predicate a failed job would hold the *matter*'s re-rank shut for ever, with no gesture
that could clear it. The negative form is asserted here, on the database, rather than trusted to a
comment.

Driven through an alembic Operations context on SQLite, like every other migration here.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

import apx.adapters.store_postgres as _store_pkg

_MIGRATION = (
    Path(_store_pkg.__file__).parent / "migrations" / "versions" / "0038_ranking_job_ledger.py")


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("apx_migration_0038", _MIGRATION)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _run(engine, mod: ModuleType, direction: str) -> None:  # noqa: ANN001
    with engine.begin() as conn:
        ctx = MigrationContext.configure(conn)
        mod.op = Operations(ctx)
        (mod.upgrade if direction == "up" else mod.downgrade)()


def _migrated(tmp_path: Path):  # noqa: ANN202
    engine = create_engine(f"sqlite:///{tmp_path / 'apx.db'}", future=True)
    _run(engine, _load(), "up")
    return engine


def _insert(engine, job_id: str, state: str) -> None:  # noqa: ANN001
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO ranking_job (id, tenant, matter, scope, actor, state, attempts, "
            "created_at, updated_at) VALUES (:i, 'cabinet', 'affaire-a', 'mur', 'chiffré', "
            ":s, 0, '2026-08-18', '2026-08-18')"), {"i": job_id, "s": state})


def test_revision_links_onto_0037() -> None:
    mod = _load()
    assert mod.revision == "0038_ranking_job_ledger"
    assert mod.down_revision == "0037_chain_continuity"


def test_the_table_is_created_and_dropped(tmp_path: Path) -> None:
    engine = _migrated(tmp_path)
    cols = {c["name"]: c for c in inspect(engine).get_columns("ranking_job")}
    assert {"id", "tenant", "matter", "scope", "actor", "state", "attempts", "version_no",
            "detail", "created_at", "updated_at"} == set(cols)
    # the wall must travel: the worker is a different process and may not re-derive it
    assert not cols["scope"]["nullable"]
    # the version is minted at completion, never predicted at enqueue
    assert cols["version_no"]["nullable"]
    _run(engine, _load(), "down")
    assert "ranking_job" not in inspect(engine).get_table_names()


def test_the_ledger_carries_no_spool_and_no_unit_count(tmp_path: Path) -> None:
    """Not a copy of ``import_job``. An import *is* a folder of units; a ranking is one monolithic
    pass with no checkpoint. A placeholder ``spool_path`` would grow a guard over a fabricated path
    that either never fires — dead code reading as a safety net — or fires on nothing real."""
    cols = {c["name"] for c in inspect(_migrated(tmp_path)).get_columns("ranking_job")}
    assert not cols & {"spool_path", "owns_spool", "submitted", "provisional"}


@pytest.mark.parametrize("state", ["queued", "running"])
def test_a_second_open_job_on_one_matter_is_refused_by_the_database(
    tmp_path: Path, state: str,
) -> None:
    """FR-7's shape, enforced atomically — the API's read-then-create is a TOCTOU alone."""
    engine = _migrated(tmp_path)
    _insert(engine, "job-1", state)
    with pytest.raises(IntegrityError):
        _insert(engine, "job-2", "queued")


@pytest.mark.parametrize("terminal", ["done", "failed"])
def test_a_terminal_job_never_holds_the_matter_shut(tmp_path: Path, terminal: str) -> None:
    """The whole reason the predicate is ``state NOT IN ('done','failed')`` and not the import
    ledger's ``state != 'done'``. Under the import's form the ``failed`` case here would raise —
    and a lawyer whose ranking failed once could never ask for another, in silence."""
    engine = _migrated(tmp_path)
    _insert(engine, "job-1", terminal)
    _insert(engine, "job-2", "queued")          # must not raise
    with engine.begin() as conn:
        assert conn.execute(text("SELECT count(*) FROM ranking_job")).scalar() == 2
