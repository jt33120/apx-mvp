"""The 0028 migration — pin_entry (Story 4.11, FR-43).

A pure DDL migration (creates the append-only, version-independent pin ledger; no backfill).
Tested via an alembic Operations context on SQLite: upgrade creates the table with its columns +
the per-pièce unique constraint, downgrade drops it, and the revision links onto 0027."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text

import apx.adapters.store_postgres as _store_pkg

_MIGRATION = (
    Path(_store_pkg.__file__).parent / "migrations" / "versions" / "0028_pin_entry.py")


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("apx_migration_0028", _MIGRATION)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _pre_0028(engine) -> None:  # noqa: ANN001
    """``matter_scope`` as it exists before this migration — the FK target 0028 references."""
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE matter_scope (tenant TEXT, matter TEXT, scope TEXT, "
            "submitted_pieces INTEGER, case_theory TEXT, PRIMARY KEY (tenant, matter))"))


def _run(engine, mod: ModuleType, direction: str) -> None:  # noqa: ANN001
    with engine.begin() as conn:
        ctx = MigrationContext.configure(conn)
        mod.op = Operations(ctx)
        (mod.upgrade if direction == "up" else mod.downgrade)()


def test_revision_links_onto_0027() -> None:
    mod = _load()
    assert mod.revision == "0028_pin_entry"
    assert mod.down_revision == "0027_line_placement"


def test_upgrade_creates_the_table_and_downgrade_drops_it(tmp_path) -> None:  # noqa: ANN001
    engine = create_engine(f"sqlite:///{tmp_path / 'apx.db'}", future=True)
    _pre_0028(engine)
    mod = _load()
    _run(engine, mod, "up")
    assert "pin_entry" in set(inspect(engine).get_table_names())
    cols = {c["name"] for c in inspect(engine).get_columns("pin_entry")}
    assert {"id", "tenant", "matter", "piece_id", "seq", "action", "reason", "set_by", "at"} <= cols
    uniques = {tuple(u["column_names"]) for u in inspect(engine).get_unique_constraints(
        "pin_entry")}
    assert ("tenant", "matter", "piece_id", "seq") in uniques
    _run(engine, mod, "down")
    assert "pin_entry" not in set(inspect(engine).get_table_names())
