"""The 0032 migration — the estimator's frozen inputs and its method (Story 5.2, OQ-4).

Pure DDL: two NULLABLE columns on ``sampling_run``, no backfill. The absence of a backfill is the
point and is asserted: a Story-5.1 run genuinely has no frozen family-size list and was closed
before the method was recorded, and filling those in with today's values would give the row a
provenance it does not have (AD-19). Tested via an alembic Operations context on SQLite.
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
    Path(_store_pkg.__file__).parent / "migrations" / "versions" / "0032_sampling_estimator.py")


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("apx_migration_0032", _MIGRATION)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _pre_0032(engine) -> None:  # noqa: ANN001
    """``sampling_run`` as 0031 left it, holding one completed Story-5.1 run."""
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE sampling_run (id TEXT PRIMARY KEY, tenant TEXT, matter TEXT, "
            "population_families INTEGER, population_pieces INTEGER, sample_size INTEGER, "
            "status TEXT, count_upper INTEGER, prevalence_upper REAL)"))
        conn.execute(text(
            "INSERT INTO sampling_run VALUES "
            "('older', 't', 'm', 120, 1400, 30, 'completed', 6, 0.05)"))


def _run(engine, mod: ModuleType, direction: str) -> None:  # noqa: ANN001
    with engine.begin() as conn:
        ctx = MigrationContext.configure(conn)
        mod.op = Operations(ctx)
        (mod.upgrade if direction == "up" else mod.downgrade)()


def test_revision_links_onto_0031() -> None:
    mod = _load()
    assert mod.revision == "0032_sampling_estimator"
    assert mod.down_revision == "0031_sampling_run"


def test_upgrade_adds_the_two_columns_and_downgrade_removes_them() -> None:
    engine = create_engine("sqlite://")
    mod = _load()
    _pre_0032(engine)
    _run(engine, mod, "up")
    columns = {c["name"]: c for c in inspect(engine).get_columns("sampling_run")}
    assert "population_family_sizes" in columns and "estimator_method" in columns
    assert columns["population_family_sizes"]["nullable"] is True
    assert columns["estimator_method"]["nullable"] is True
    _run(engine, mod, "down")
    after = {c["name"] for c in inspect(engine).get_columns("sampling_run")}
    assert "population_family_sizes" not in after and "estimator_method" not in after


def test_an_existing_run_is_not_back_filled_and_keeps_its_numbers() -> None:
    """AD-19. The older run's bound is untouched, and its two new columns are NULL — *not
    computable*, which is a true statement about it, rather than today's method and a fabricated
    size list, which would be a false one."""
    engine = create_engine("sqlite://")
    mod = _load()
    _pre_0032(engine)
    _run(engine, mod, "up")
    with engine.begin() as conn:
        row = conn.execute(text(
            "SELECT count_upper, prevalence_upper, population_family_sizes, estimator_method "
            "FROM sampling_run WHERE id = 'older'")).one()
    assert row[0] == 6 and abs(row[1] - 0.05) < 1e-9
    assert row[2] is None and row[3] is None
