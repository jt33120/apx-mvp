"""The 0034 migration — register_override (Story 5.6, FR-25/FR-5/AD-37).

A pure DDL migration: it creates the append-only ledger that holds the one sentence an override
costs. No backfill — every existing entry is `open` or `resolved`, and neither was ever an override.
``resolution_state`` needs no DDL to accept a third value, which is exactly why the reason needed a
table: it must not live on the mutable ``failure`` row. Tested via an alembic Operations context on
SQLite: upgrade creates the table with its columns and its lookup index, downgrade drops it, and the
revision links onto 0033.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect

import apx.adapters.store_postgres as _store_pkg

_MIGRATION = (
    Path(_store_pkg.__file__).parent / "migrations" / "versions" / "0034_register_override.py")


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("apx_migration_0034", _MIGRATION)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _run(engine, mod: ModuleType, direction: str) -> None:  # noqa: ANN001
    with engine.begin() as conn:
        ctx = MigrationContext.configure(conn)
        mod.op = Operations(ctx)
        (mod.upgrade if direction == "up" else mod.downgrade)()


def test_revision_links_onto_0033() -> None:
    mod = _load()
    assert mod.revision == "0034_register_override"
    assert mod.down_revision == "0033_audit_chain_scope"


def test_upgrade_creates_the_ledger_and_downgrade_drops_it(tmp_path) -> None:  # noqa: ANN001
    engine = create_engine(f"sqlite:///{tmp_path / 'apx.db'}", future=True)
    mod = _load()
    _run(engine, mod, "up")
    assert "register_override" in set(inspect(engine).get_table_names())
    cols = {c["name"] for c in inspect(engine).get_columns("register_override")}
    assert cols == {"id", "tenant", "entry_id", "actor", "reason", "at"}
    indexes = {i["name"] for i in inspect(engine).get_indexes("register_override")}
    assert "ix_register_override_entry" in indexes
    _run(engine, mod, "down")
    assert "register_override" not in set(inspect(engine).get_table_names())


def test_every_column_is_required(tmp_path) -> None:  # noqa: ANN001
    # a nullable reason would be an override without a sentence, arriving through the schema
    # rather than through a call site — the one route the validator cannot close
    engine = create_engine(f"sqlite:///{tmp_path / 'apx.db'}", future=True)
    _run(engine, _load(), "up")
    cols = inspect(engine).get_columns("register_override")
    nullable = {c["name"] for c in cols if c["nullable"]}
    assert nullable == set()


def test_the_model_and_the_migration_agree(tmp_path) -> None:  # noqa: ANN001
    # the ORM metadata is what the tests create_all(); the migration is what a deployment runs.
    # A drift between them is a table that exists in tests and not in production, or the reverse.
    from apx.adapters.store_postgres.models import RegisterOverride

    engine = create_engine(f"sqlite:///{tmp_path / 'apx.db'}", future=True)
    _run(engine, _load(), "up")
    migrated = {c["name"] for c in inspect(engine).get_columns("register_override")}
    assert migrated == {c.name for c in RegisterOverride.__table__.columns}
    assert RegisterOverride.__tablename__ == "register_override"
