"""The 0024 migration — ranking_version + ranked_entry (Story 4.3, FR-39/AD-23).

A pure DDL migration (no backfill — ranking did not exist before it). Tested by running upgrade →
downgrade directly against SQLite through an alembic Operations context: upgrade creates both
tables,
downgrade drops them, and the revision links onto 0023 as the new head."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text

import apx.adapters.store_postgres as _store_pkg

_MIGRATION = (
    Path(_store_pkg.__file__).parent / "migrations" / "versions" / "0024_ranking_version.py")


def _load() -> ModuleType:
    """Load the 0024 migration by path — its filename starts with a digit, so it cannot be imported
    by dotted name (this is how alembic itself loads revision scripts)."""
    spec = importlib.util.spec_from_file_location("apx_migration_0024", _MIGRATION)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _pre_0024(engine) -> None:  # noqa: ANN001
    """``matter_scope`` as it exists before this migration — the FK target 0024 references."""
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE matter_scope (tenant TEXT, matter TEXT, scope TEXT, "
            "submitted_pieces INTEGER, case_theory TEXT, PRIMARY KEY (tenant, matter))"))


def _run(engine, mod: ModuleType, direction: str) -> None:  # noqa: ANN001
    with engine.begin() as conn:
        ctx = MigrationContext.configure(conn)
        mod.op = Operations(ctx)  # bind the module's op proxy to this connection
        (mod.upgrade if direction == "up" else mod.downgrade)()


def test_revision_links_onto_0023_as_the_head() -> None:
    mod = _load()
    assert mod.revision == "0024_ranking_version"
    assert mod.down_revision == "0023_case_theory_version"


def test_upgrade_creates_both_tables_and_downgrade_drops_them(tmp_path) -> None:  # noqa: ANN001
    engine = create_engine(f"sqlite:///{tmp_path / 'apx.db'}", future=True)
    _pre_0024(engine)
    mod = _load()
    _run(engine, mod, "up")
    tables = set(inspect(engine).get_table_names())
    assert {"ranking_version", "ranked_entry"} <= tables
    cols = {c["name"] for c in inspect(engine).get_columns("ranked_entry")}
    assert {"rank", "outcome", "score", "rejection_class", "family_id", "is_representative"} <= cols
    # no retained/discarded set membership column (AD-39)
    assert not any("retained" in c or "discarded" in c for c in cols)
    _run(engine, mod, "down")
    remaining = set(inspect(engine).get_table_names())
    assert "ranking_version" not in remaining and "ranked_entry" not in remaining
