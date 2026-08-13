"""The 0033 migration — chains per (tenant, matter) and a head row to allocate from (Story 5.5).

The load-bearing assertion is the one about what the migration does **not** do: it re-chains
nothing. Story 1.11's head journal holds the old chain values on a volume the dump does not cover,
so re-chaining would leave every journalled head unmatched by the live record — the exact signature
of forgery, produced by our own migration. Existing entries therefore stay on the tenant chain, at
their sequence numbers, with their chain values, and with ``content_version = 1`` so the verifier
keeps reading them under the recipe they were written with.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text

import apx.adapters.store_postgres as _store_pkg

_MIGRATION = (
    Path(_store_pkg.__file__).parent / "migrations" / "versions" / "0033_audit_chain_scope.py")


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("apx_migration_0033", _MIGRATION)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _pre_0033(engine, entries: int = 3) -> None:  # noqa: ANN001
    """``audit_record`` as 0003 left it: one chain per tenant, no scope column."""
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE audit_record (id TEXT PRIMARY KEY, tenant TEXT NOT NULL, "
            "seq INTEGER NOT NULL, matter TEXT, actor TEXT NOT NULL, action TEXT NOT NULL, "
            "detail TEXT NOT NULL, chain TEXT NOT NULL, timestamp TIMESTAMP NOT NULL, "
            "CONSTRAINT uq_audit_tenant_seq UNIQUE (tenant, seq))"))
        conn.execute(text(
            "CREATE TABLE truncation_marker (tenant TEXT PRIMARY KEY, detected_at TIMESTAMP, "
            "journal_seq INTEGER, live_seq INTEGER, cleared_by TEXT, reason TEXT, "
            "cleared_at TIMESTAMP)"))
        for i in range(1, entries + 1):
            conn.execute(text(
                "INSERT INTO audit_record VALUES (:id, 'cabinet', :seq, :matter, 'Me Dupont', "
                "'ingest', :detail, :chain, '2026-08-01 10:00:00')"),
                {"id": f"c{i}", "seq": i, "matter": "affaire-a" if i % 2 else "affaire-b",
                 "detail": f"d{i}", "chain": f"chain-{i}"})


def _run(engine, mod: ModuleType, direction: str) -> None:  # noqa: ANN001
    with engine.begin() as conn:
        ctx = MigrationContext.configure(conn)
        mod.op = Operations(ctx)
        (mod.upgrade if direction == "up" else mod.downgrade)()


def test_revision_links_onto_0032() -> None:
    mod = _load()
    assert mod.revision == "0033_audit_chain_scope"
    assert mod.down_revision == "0032_sampling_estimator"


def test_upgrade_adds_the_chain_columns_and_the_head_table() -> None:
    engine = create_engine("sqlite://")
    _pre_0033(engine)
    _run(engine, _load(), "up")
    columns = {c["name"]: c for c in inspect(engine).get_columns("audit_record")}
    assert {"chain_scope", "content_version", "app_version", "schema_version"} <= set(columns)
    assert columns["chain_scope"]["nullable"] is False
    assert columns["app_version"]["nullable"] is True
    head = {c["name"] for c in inspect(engine).get_columns("audit_chain_head")}
    assert {"tenant", "chain_scope", "seq", "chain", "anchor", "opened_at", "updated_at"} == head


def test_no_existing_entry_is_re_chained_renumbered_or_moved() -> None:
    """The head journal holds these chain values outside the database. Changing one here would
    read, from the outside, as somebody rewriting the record."""
    engine = create_engine("sqlite://")
    _pre_0033(engine)
    _run(engine, _load(), "up")
    with engine.begin() as conn:
        rows = conn.execute(text(
            "SELECT seq, matter, chain, chain_scope, content_version, app_version "
            "FROM audit_record ORDER BY seq")).all()
    assert [r[0] for r in rows] == [1, 2, 3]                       # numbers untouched
    assert [r[2] for r in rows] == ["chain-1", "chain-2", "chain-3"]  # chain values untouched
    assert [r[1] for r in rows] == ["affaire-a", "affaire-b", "affaire-a"]  # the matter is kept
    # ... and all three stay on the TENANT chain, which is in fact where they were written
    assert {r[3] for r in rows} == {""}
    # ... read under the recipe they were written with, with no invented provenance (AD-19)
    assert {r[4] for r in rows} == {1}
    assert {r[5] for r in rows} == {None}


def test_the_head_is_seeded_at_the_existing_tenant_chain_so_the_next_act_continues_it() -> None:
    """Without the seed the next act would allocate seq 1 again — colliding with the record it
    was supposed to continue."""
    engine = create_engine("sqlite://")
    _pre_0033(engine, entries=5)
    _run(engine, _load(), "up")
    with engine.begin() as conn:
        heads = conn.execute(text(
            "SELECT tenant, chain_scope, seq, chain, anchor FROM audit_chain_head")).all()
    assert heads == [("cabinet", "", 5, "chain-5", "")]


def test_a_tenant_with_an_empty_record_gets_no_head_row() -> None:
    """The chain opens on its first write, not on a migration guessing that it will."""
    engine = create_engine("sqlite://")
    _pre_0033(engine, entries=0)
    _run(engine, _load(), "up")
    with engine.begin() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM audit_chain_head")).scalar() == 0


def test_uniqueness_moves_from_the_tenant_to_the_chain() -> None:
    """Two chains of one tenant each hold a seq 1; the uniqueness that matters is per chain, and
    it is what makes a gap impossible rather than merely detectable."""
    engine = create_engine("sqlite://")
    _pre_0033(engine)
    _run(engine, _load(), "up")
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO audit_record VALUES ('n1', 'cabinet', 1, 'affaire-a', 'a', 'judge', "
            "'d', 'x', '2026-08-02 10:00:00', 'affaire-a', 2, '0.1.0', 'slice-a')"))
    with engine.begin() as conn:  # the same (tenant, chain_scope, seq) is still refused
        with pytest.raises(Exception, match="UNIQUE"):
            conn.execute(text(
                "INSERT INTO audit_record VALUES ('n2', 'cabinet', 1, 'affaire-a', 'a', 'judge', "
                "'d', 'y', '2026-08-02 10:00:00', 'affaire-a', 2, '0.1.0', 'slice-a')"))


def test_downgrade_refuses_rather_than_renumbering_a_matter_chain() -> None:
    """A downgrade that silently destroyed or renumbered evidence would be worse than one that
    fails (FR-21, AD-22). With nothing on a matter chain it is a clean reversal; with entries on
    one, it refuses and says why."""
    engine = create_engine("sqlite://")
    _pre_0033(engine)
    mod = _load()
    _run(engine, mod, "up")
    _run(engine, mod, "down")                      # nothing on a matter chain → reversible
    assert "chain_scope" not in {c["name"] for c in inspect(engine).get_columns("audit_record")}

    engine2 = create_engine("sqlite://")
    _pre_0033(engine2)
    mod2 = _load()
    _run(engine2, mod2, "up")
    with engine2.begin() as conn:
        conn.execute(text(
            "INSERT INTO audit_record VALUES ('n1', 'cabinet', 1, 'affaire-a', 'a', 'judge', "
            "'d', 'x', '2026-08-02 10:00:00', 'affaire-a', 2, '0.1.0', 'slice-a')"))
    with pytest.raises(RuntimeError, match="refusing to downgrade"):
        _run(engine2, mod2, "down")
