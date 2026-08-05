"""The 0027 migration — line_placement (Story 4.8, FR-17).

A pure DDL migration (creates the append-only, version-bound line-placement ledger; no backfill — a
pre-4.8 ranking has no line until one is placed). Tested via an alembic Operations context on
SQLite: upgrade creates the table with its columns + the per-version unique constraint, downgrade
drops it, and the revision links onto 0026."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text

import apx.adapters.store_postgres as _store_pkg

_MIGRATION = (
    Path(_store_pkg.__file__).parent / "migrations" / "versions" / "0027_line_placement.py")


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("apx_migration_0027", _MIGRATION)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _pre_0027(engine) -> None:  # noqa: ANN001
    """The FK targets 0027 references — ``matter_scope`` and ``ranking_version``."""
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE matter_scope (tenant TEXT, matter TEXT, scope TEXT, "
            "submitted_pieces INTEGER, case_theory TEXT, PRIMARY KEY (tenant, matter))"))
        conn.execute(text("CREATE TABLE ranking_version (id TEXT PRIMARY KEY)"))


def _run(engine, mod: ModuleType, direction: str) -> None:  # noqa: ANN001
    with engine.begin() as conn:
        ctx = MigrationContext.configure(conn)
        mod.op = Operations(ctx)
        (mod.upgrade if direction == "up" else mod.downgrade)()


def test_revision_links_onto_0026() -> None:
    mod = _load()
    assert mod.revision == "0027_line_placement"
    assert mod.down_revision == "0026_taxonomy_label_entry"


def test_upgrade_creates_the_table_and_downgrade_drops_it(tmp_path) -> None:  # noqa: ANN001
    engine = create_engine(f"sqlite:///{tmp_path / 'apx.db'}", future=True)
    _pre_0027(engine)
    mod = _load()
    _run(engine, mod, "up")
    assert "line_placement" in set(inspect(engine).get_table_names())
    cols = {c["name"] for c in inspect(engine).get_columns("line_placement")}
    assert {"id", "tenant", "matter", "ranking_version_id", "seq", "last_retained_piece_id",
            "basis", "placed_by", "at"} <= cols
    # FR-17: the line's identity is the pièce, and there is NO bare-integer ordinal position column
    assert not any(tok in c for c in cols for tok in ("position", "ordinal", "cut", "offset"))
    uniques = {tuple(u["column_names"]) for u in inspect(engine).get_unique_constraints(
        "line_placement")}
    assert ("ranking_version_id", "seq") in uniques  # per-version monotonic seq
    _run(engine, mod, "down")
    assert "line_placement" not in set(inspect(engine).get_table_names())
