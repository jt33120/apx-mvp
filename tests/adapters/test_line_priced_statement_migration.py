"""The 0035 migration — the priced statement moves onto the line-placement ledger (Story 5.7).

A pure DDL migration: one nullable column, no backfill. FR-24 records every position of the line
*with its priced statement*, and Story 4.9 wrote that statement only into the `line_moved` audit
entry's detail — so the export would have had to recover it by parsing prose out of an encrypted
column. Tested via an alembic Operations context on SQLite: upgrade adds the column **nullable**,
downgrade drops it, and the revision links onto 0034.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text

import apx.adapters.store_postgres as _store_pkg

_MIGRATION = (
    Path(_store_pkg.__file__).parent / "migrations" / "versions"
    / "0035_line_priced_statement.py")


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("apx_migration_0035", _MIGRATION)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _pre_0035(engine) -> None:  # noqa: ANN001
    """The table 0035 alters, in its pre-0035 shape."""
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE line_placement (id TEXT PRIMARY KEY, tenant TEXT, matter TEXT, "
            "ranking_version_id TEXT, seq INTEGER, last_retained_piece_id TEXT, basis TEXT, "
            "placed_by TEXT, at TIMESTAMP)"))


def _run(engine, mod: ModuleType, direction: str) -> None:  # noqa: ANN001
    with engine.begin() as conn:
        ctx = MigrationContext.configure(conn)
        mod.op = Operations(ctx)
        (mod.upgrade if direction == "up" else mod.downgrade)()


def test_revision_links_onto_0034() -> None:
    mod = _load()
    assert mod.revision == "0035_line_priced_statement"
    assert mod.down_revision == "0034_register_override"


def test_upgrade_adds_the_column_and_downgrade_drops_it(tmp_path) -> None:  # noqa: ANN001
    engine = create_engine(f"sqlite:///{tmp_path / 'apx.db'}", future=True)
    _pre_0035(engine)
    mod = _load()
    _run(engine, mod, "up")
    cols = {c["name"] for c in inspect(engine).get_columns("line_placement")}
    assert "priced_statement" in cols
    _run(engine, mod, "down")
    assert "priced_statement" not in {
        c["name"] for c in inspect(engine).get_columns("line_placement")}


def test_the_column_is_nullable_and_stays_so(tmp_path) -> None:  # noqa: ANN001
    # NULL is the FIRST placement — the tool drew the cut and committed to it, so there was no
    # price to show. NOT NULL would force an empty string there, and an empty priced statement is
    # indistinguishable from a move whose price nobody showed.
    engine = create_engine(f"sqlite:///{tmp_path / 'apx.db'}", future=True)
    _pre_0035(engine)
    _run(engine, _load(), "up")
    col = next(c for c in inspect(engine).get_columns("line_placement")
               if c["name"] == "priced_statement")
    assert col["nullable"]


def test_existing_rows_are_not_backfilled(tmp_path) -> None:  # noqa: ANN001
    # a placement written before this migration keeps its price on the chain only; inventing a
    # value it does not have would be exactly the imputation AD-19 forbids
    engine = create_engine(f"sqlite:///{tmp_path / 'apx.db'}", future=True)
    _pre_0035(engine)
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO line_placement (id, tenant, matter, ranking_version_id, seq, "
            "last_retained_piece_id, basis, placed_by, at) "
            "VALUES ('x', 't', 'm', 'v', 1, 'p', 'intrinsic', 'enc', '2026-08-01')"))
    _run(engine, _load(), "up")
    with engine.begin() as conn:
        assert conn.execute(text("SELECT priced_statement FROM line_placement")).scalar() is None


def test_the_model_and_the_migration_agree(tmp_path) -> None:  # noqa: ANN001
    from apx.adapters.store_postgres.models import LinePlacement

    engine = create_engine(f"sqlite:///{tmp_path / 'apx.db'}", future=True)
    _pre_0035(engine)
    _run(engine, _load(), "up")
    migrated = {c["name"] for c in inspect(engine).get_columns("line_placement")}
    assert migrated == {c.name for c in LinePlacement.__table__.columns}
