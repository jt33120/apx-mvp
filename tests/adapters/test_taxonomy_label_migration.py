"""The 0026 migration — taxonomy_label_entry (Story 4.5, FR-40).

A pure DDL migration (creates the append-only label ledger; no backfill — a pre-4.5 pièce has no
assignment, so its current label is the `unlabelled` view default). Tested via an alembic Operations
context on SQLite: upgrade creates the table with its columns, downgrade drops it, and the revision
links onto 0025."""

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
    / "0026_taxonomy_label_entry.py")


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("apx_migration_0026", _MIGRATION)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _pre_0026(engine) -> None:  # noqa: ANN001
    """``matter_scope`` as it exists before this migration — the FK target 0026 references."""
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE matter_scope (tenant TEXT, matter TEXT, scope TEXT, "
            "submitted_pieces INTEGER, case_theory TEXT, PRIMARY KEY (tenant, matter))"))


def _run(engine, mod: ModuleType, direction: str) -> None:  # noqa: ANN001
    with engine.begin() as conn:
        ctx = MigrationContext.configure(conn)
        mod.op = Operations(ctx)
        (mod.upgrade if direction == "up" else mod.downgrade)()


def test_revision_links_onto_0025() -> None:
    mod = _load()
    assert mod.revision == "0026_taxonomy_label_entry"
    assert mod.down_revision == "0025_ranked_entry_confidence"


def test_upgrade_creates_the_table_and_downgrade_drops_it(tmp_path) -> None:  # noqa: ANN001
    engine = create_engine(f"sqlite:///{tmp_path / 'apx.db'}", future=True)
    _pre_0026(engine)
    mod = _load()
    _run(engine, mod, "up")
    assert "taxonomy_label_entry" in set(inspect(engine).get_table_names())
    cols = {c["name"] for c in inspect(engine).get_columns("taxonomy_label_entry")}
    assert {"id", "tenant", "matter", "piece_id", "seq", "label", "source", "set_by", "at"} <= cols
    _run(engine, mod, "down")
    assert "taxonomy_label_entry" not in set(inspect(engine).get_table_names())
