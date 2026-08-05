"""The 0025 migration — ranked_entry.confidence + confidence_signals (Story 4.4, FR-42).

A pure DDL migration (adds two nullable columns; no backfill — a pre-4.4 ranking had no derivation,
so its confidence is genuinely NULL). Tested via an alembic Operations context on SQLite: upgrade
adds
both columns, downgrade drops them, and the revision links onto 0024."""

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
    / "0025_ranked_entry_confidence.py")


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("apx_migration_0025", _MIGRATION)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _pre_0025(engine) -> None:  # noqa: ANN001
    """``ranked_entry`` as 0024 leaves it — enough columns for the ALTER to attach to."""
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE ranked_entry (id TEXT PRIMARY KEY, ranking_version_id TEXT, "
            "piece_id TEXT, rank INTEGER, outcome TEXT, family_id TEXT, "
            "is_representative BOOLEAN)"))


def _run(engine, mod: ModuleType, direction: str) -> None:  # noqa: ANN001
    with engine.begin() as conn:
        ctx = MigrationContext.configure(conn)
        mod.op = Operations(ctx)
        (mod.upgrade if direction == "up" else mod.downgrade)()


def test_revision_links_onto_0024() -> None:
    mod = _load()
    assert mod.revision == "0025_ranked_entry_confidence"
    assert mod.down_revision == "0024_ranking_version"


def test_upgrade_adds_both_columns_and_downgrade_drops_them(tmp_path) -> None:  # noqa: ANN001
    engine = create_engine(f"sqlite:///{tmp_path / 'apx.db'}", future=True)
    _pre_0025(engine)
    mod = _load()
    _run(engine, mod, "up")
    cols = {c["name"] for c in inspect(engine).get_columns("ranked_entry")}
    assert {"confidence", "confidence_signals"} <= cols
    _run(engine, mod, "down")
    cols_after = {c["name"] for c in inspect(engine).get_columns("ranked_entry")}
    assert "confidence" not in cols_after and "confidence_signals" not in cols_after
