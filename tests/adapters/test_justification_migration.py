"""The 0029 migration — piece_justification + justification_rejection (Story 4.6, FR-41/FR-18).

Pure DDL (creates the version-bound justification table and the version-independent rejection
ledger; no backfill). Tested via an alembic Operations context on SQLite: upgrade creates both
tables with their columns + unique constraints, downgrade drops them, and the revision links onto
0028."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text

import apx.adapters.store_postgres as _store_pkg

_MIGRATION = (
    Path(_store_pkg.__file__).parent / "migrations" / "versions" / "0029_piece_justification.py")


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("apx_migration_0029", _MIGRATION)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _pre_0029(engine) -> None:  # noqa: ANN001
    """``matter_scope`` and ``ranking_version`` as 0029 references them (its two FK targets)."""
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


def test_revision_links_onto_0028() -> None:
    mod = _load()
    assert mod.revision == "0029_piece_justification"
    assert mod.down_revision == "0028_pin_entry"


def test_upgrade_creates_both_tables_and_downgrade_drops_them(tmp_path) -> None:  # noqa: ANN001
    engine = create_engine(f"sqlite:///{tmp_path / 'apx.db'}", future=True)
    _pre_0029(engine)
    mod = _load()
    _run(engine, mod, "up")
    tables = set(inspect(engine).get_table_names())
    assert {"piece_justification", "justification_rejection"} <= tables

    pj_cols = {c["name"] for c in inspect(engine).get_columns("piece_justification")}
    assert {"id", "tenant", "matter", "ranking_version_id", "piece_id", "sentence", "basis_kind",
            "case_theory_version_id", "intrinsic_signals", "evidence_json", "source_language",
            "at"} <= pj_cols
    jr_cols = {c["name"] for c in inspect(engine).get_columns("justification_rejection")}
    assert {"id", "tenant", "matter", "piece_id", "seq", "action", "reason", "set_by",
            "at"} <= jr_cols

    pj_uniques = {tuple(u["column_names"])
                  for u in inspect(engine).get_unique_constraints("piece_justification")}
    assert ("tenant", "matter", "ranking_version_id", "piece_id") in pj_uniques
    jr_uniques = {tuple(u["column_names"])
                  for u in inspect(engine).get_unique_constraints("justification_rejection")}
    assert ("tenant", "matter", "piece_id", "seq") in jr_uniques

    _run(engine, mod, "down")
    remaining = set(inspect(engine).get_table_names())
    assert "piece_justification" not in remaining and "justification_rejection" not in remaining
