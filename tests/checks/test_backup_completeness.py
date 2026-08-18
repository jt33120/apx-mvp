"""The build-time half of C2: a backup's coverage is total over the model (Story 7.2, AD-32/AD-33).

The runtime property is proven in ``tests/adapters/test_backup_captures_every_table.py``. This is
the guard that makes the *next* table's absence a red build instead of a discovery made by the
person who needed the *pièce* — the failure mode the hand-written tuple had for eleven stories.
"""

from __future__ import annotations

import pytest
from sqlalchemy import Column, ForeignKey, MetaData, String, Table

from apx.adapters.store_postgres import backup_plan as plan_module
from apx.adapters.store_postgres.backup_plan import IncompleteBackupPlan, backup_plan
from apx.checks.backup_completeness import the_backup_plan_is_total


def _model(*, orphan: bool = False) -> MetaData:
    md = MetaData()
    Table("piece", md, Column("id", String, primary_key=True), Column("tenant", String))
    Table("piece_custodian", md, Column("id", String, primary_key=True),
          Column("piece_id", String, ForeignKey("piece.id")))
    if orphan:
        Table("shiny_new_ledger", md, Column("id", String, primary_key=True))
    return md


def test_it_is_green_on_the_live_model() -> None:
    from apx.adapters.store_postgres.models import Base

    total = len(Base.metadata.tables)
    result = the_backup_plan_is_total()
    assert result.ok, result.detail
    assert f"{total} of {total}" in result.detail


def test_a_table_reached_by_no_rule_fails_the_build() -> None:
    """The C2 shape exactly: somebody adds a ledger, nobody thinks about the backup, and the loss
    has no error message anywhere until a restore."""
    result = the_backup_plan_is_total(_model(orphan=True))
    assert not result.ok
    assert "shiny_new_ledger" in result.detail


def test_a_child_reached_through_its_declared_foreign_key_is_enough() -> None:
    """A table with no ``tenant`` column is not a problem — a table with no *route* is. The three
    that went missing this way (``import_unit``, ``sampling_run_item``, ``sampling_verdict``) each
    declare the key that reaches their tenant, and the plan follows it."""
    result = the_backup_plan_is_total(_model())
    assert result.ok, result.detail
    assert [cap.table for cap in backup_plan(_model())] == ["piece", "piece_custodian"]


def test_an_exclusion_with_no_reason_is_not_an_exclusion(monkeypatch) -> None:  # noqa: ANN001
    """The escape hatch, guarded. A written exclusion is how a table legitimately leaves a backup,
    and an unguarded one is how it leaves quietly — one blank string at a time."""
    monkeypatch.setitem(plan_module._EXCLUDED, "piece_custodian", "   ")
    result = the_backup_plan_is_total(_model())
    assert not result.ok
    assert "piece_custodian" in result.detail and "no reason" in result.detail


def test_an_exclusion_naming_a_table_the_model_no_longer_has_fails(monkeypatch) -> None:  # noqa: ANN001
    """A stale exclusion is a decision about something that is not there — and it hides the day a
    table comes back under that name, which is the moment it would silently stay out."""
    monkeypatch.setitem(plan_module._EXCLUDED, "gone_in_a_migration", "dropped in 0021")
    result = the_backup_plan_is_total(_model())
    assert not result.ok
    assert "gone_in_a_migration" in result.detail


def test_an_exclusion_with_a_reason_is_accepted_and_counted(monkeypatch) -> None:  # noqa: ANN001
    """And the legitimate case works, with the reason recorded where the operator reads it."""
    monkeypatch.setitem(
        plan_module._EXCLUDED, "piece_custodian", "hypothetical: not a tenant's data")
    result = the_backup_plan_is_total(_model())
    assert result.ok
    assert "1 excluded with a written reason" in result.detail


def test_the_plan_itself_raises_rather_than_returning_a_subset() -> None:
    """The check is the belt. The braces is that ``backup_plan`` refuses at RUNTIME too, so a build
    that skipped the check still cannot take a backup that quietly omits a table."""
    with pytest.raises(IncompleteBackupPlan, match="shiny_new_ledger"):
        backup_plan(_model(orphan=True))
