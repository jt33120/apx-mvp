"""The 0031 migration — sampling_run / sampling_run_item / sampling_verdict (Story 5.1, FR-22).

Pure DDL: three new tables, no backfill and NO data migration — the legacy ``recall_review`` rows
stay exactly where they are, readable forever with their bounds (AD-7: the legacy pair is
*superseded*, never deleted). Tested via an alembic Operations context on SQLite: upgrade creates
the three tables with FR-22's freeze columns and the append-only verdict constraint, downgrade
drops them, and the revision links onto 0030.
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
    Path(_store_pkg.__file__).parent / "migrations" / "versions" / "0031_sampling_run.py")


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("apx_migration_0031", _MIGRATION)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _pre_0031(engine) -> None:  # noqa: ANN001
    """The FK target 0031 references — ``matter_scope`` — plus the legacy bound table, so the
    "nothing is migrated away" assertion below has something to be about."""
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE matter_scope (tenant TEXT, matter TEXT, scope TEXT, "
            "submitted_pieces INTEGER, case_theory TEXT, PRIMARY KEY (tenant, matter))"))
        conn.execute(text(
            "CREATE TABLE recall_review (id TEXT PRIMARY KEY, tenant TEXT, matter TEXT, "
            "population INTEGER, prevalence_upper REAL)"))
        conn.execute(text(
            "INSERT INTO recall_review VALUES ('legacy', 't', 'm', 1400, 0.014)"))


def _run(engine, mod: ModuleType, direction: str) -> None:  # noqa: ANN001
    with engine.begin() as conn:
        ctx = MigrationContext.configure(conn)
        mod.op = Operations(ctx)
        (mod.upgrade if direction == "up" else mod.downgrade)()


def test_revision_links_onto_0030() -> None:
    mod = _load()
    assert mod.revision == "0031_sampling_run"
    assert mod.down_revision == "0030_artefact_stamp"


def test_upgrade_creates_the_three_tables_and_downgrade_drops_them(tmp_path) -> None:  # noqa: ANN001
    engine = create_engine(f"sqlite:///{tmp_path / 'apx.db'}", future=True)
    _pre_0031(engine)
    mod = _load()
    _run(engine, mod, "up")
    tables = set(inspect(engine).get_table_names())
    assert {"sampling_run", "sampling_run_item", "sampling_verdict"} <= tables

    # FR-22's freeze, present as columns
    run_cols = {c["name"]: c for c in inspect(engine).get_columns("sampling_run")}
    for column in ("ranking_version_id", "ranking_version_no", "last_retained_piece_id",
                   "pin_ledger_seq", "scope"):
        assert column in run_cols, column
        assert not run_cols[column]["nullable"], f"{column} is part of the freeze (FR-22)"
    # the line is stored by pièce IDENTITY, never a bare ordinal (FR-17)
    assert not any(
        token in name for name in run_cols for token in ("position", "ordinal", "cut", "offset"))
    # nothing here is an "invalidated" flag: invalidation is a comparison (Story 4.13)
    assert not any("invalid" in name or "stale" in name for name in run_cols)

    item_cols = {c["name"] for c in inspect(engine).get_columns("sampling_run_item")}
    assert {"run_id", "draw_index", "family_id", "proxy_piece_id", "member_piece_ids"} <= item_cols

    verdict_uniques = {
        tuple(u["column_names"])
        for u in inspect(engine).get_unique_constraints("sampling_verdict")}
    assert ("run_id", "family_id", "seq") in verdict_uniques  # append-only: a correction is new

    _run(engine, mod, "down")
    assert not ({"sampling_run", "sampling_run_item", "sampling_verdict"}
                & set(inspect(engine).get_table_names()))


def test_the_legacy_bound_rows_are_not_migrated_away(tmp_path) -> None:  # noqa: ANN001
    """AD-7 / decision A1 — the legacy pair is SUPERSEDED, not deleted. A migration that dropped or
    rewrote recall_review would destroy bounds a firm may have quoted to a court."""
    engine = create_engine(f"sqlite:///{tmp_path / 'apx.db'}", future=True)
    _pre_0031(engine)
    mod = _load()
    _run(engine, mod, "up")
    with engine.begin() as conn:
        rows = conn.execute(text("SELECT id, population FROM recall_review")).fetchall()
    assert rows == [("legacy", 1400)]
    _run(engine, mod, "down")
    with engine.begin() as conn:
        assert conn.execute(text("SELECT count(*) FROM recall_review")).scalar() == 1
