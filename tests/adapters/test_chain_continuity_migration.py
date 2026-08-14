"""The 0037 migration — the marker generalises, and an unrecorded head becomes a row (Story 5.9).

Two changes, and the assertion that matters is about the EXISTING rows: every marker written before
this migration recorded a live head that had fallen behind the journal, which is a **truncation**.
Giving them any other kind — or leaving the column nullable so a reader has to guess — would
reinterpret findings nobody re-examined. They come out ``truncated``, which is what they were.

``journal_gap`` is new: the alarm for a head the journal could not record used to be a boolean in
one process's memory, so it cleared itself on the next restart. Tested through an alembic Operations
context on SQLite, like every other migration here.
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
    Path(_store_pkg.__file__).parent / "migrations" / "versions" / "0037_chain_continuity.py")


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("apx_migration_0037", _MIGRATION)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _pre_0037(engine) -> None:  # noqa: ANN001
    """``truncation_marker`` as 0015 + 0033 left it, holding one already-detected truncation."""
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE truncation_marker (tenant TEXT PRIMARY KEY, detected_at TIMESTAMP, "
            "journal_seq INTEGER, live_seq INTEGER, chains TEXT, entries_lost INTEGER, "
            "cleared_by TEXT, reason TEXT, cleared_at TIMESTAMP)"))
        conn.execute(text(
            "INSERT INTO truncation_marker (tenant, journal_seq, live_seq, chains, entries_lost) "
            "VALUES ('cabinet', 9, 4, 'cabinet\x1faffaire-a:9->4', 5)"))


def _run(engine, mod: ModuleType, direction: str) -> None:  # noqa: ANN001
    with engine.begin() as conn:
        ctx = MigrationContext.configure(conn)
        mod.op = Operations(ctx)
        (mod.upgrade if direction == "up" else mod.downgrade)()


def test_revision_links_onto_0036() -> None:
    mod = _load()
    assert mod.revision == "0037_chain_continuity"
    assert mod.down_revision == "0036_validation_act"


def test_upgrade_adds_the_kind_and_the_forks_and_downgrade_removes_them(tmp_path) -> None:  # noqa: ANN001
    engine = create_engine(f"sqlite:///{tmp_path / 'apx.db'}", future=True)
    _pre_0037(engine)
    mod = _load()
    _run(engine, mod, "up")
    cols = {c["name"] for c in inspect(engine).get_columns("truncation_marker")}
    assert {"kind", "forks"} <= cols
    _run(engine, mod, "down")
    after = {c["name"] for c in inspect(engine).get_columns("truncation_marker")}
    assert "kind" not in after and "forks" not in after


def test_an_existing_marker_is_a_truncation_and_is_not_reinterpreted(tmp_path) -> None:  # noqa: ANN001
    """Every marker written before this migration recorded a live head BEHIND the journal. That is a
    truncation and nothing else, so it comes out labelled as one — never NULL, which would make a
    reader guess, and never ``forked``, which would be a finding nobody made."""
    engine = create_engine(f"sqlite:///{tmp_path / 'apx.db'}", future=True)
    _pre_0037(engine)
    _run(engine, _load(), "up")
    with engine.begin() as conn:
        kind, forks, lost = conn.execute(text(
            "SELECT kind, forks, entries_lost FROM truncation_marker WHERE tenant = 'cabinet'"
        )).one()
    assert kind == "truncated"
    assert forks is None, "a pre-0037 marker names no fork — none was ever detected"
    assert lost == 5, "the loss it recorded is untouched"


def test_the_journal_gap_table_is_created_and_dropped(tmp_path) -> None:  # noqa: ANN001
    engine = create_engine(f"sqlite:///{tmp_path / 'apx.db'}", future=True)
    _pre_0037(engine)
    mod = _load()
    _run(engine, mod, "up")
    assert "journal_gap" in inspect(engine).get_table_names()
    cols = {c["name"]: c for c in inspect(engine).get_columns("journal_gap")}
    assert {"id", "tenant", "scope", "seq", "chain", "at", "detail"} <= set(cols)
    # the scope is the JOURNAL identity, and it is NOT NULL: a gap that cannot name its chain is a
    # gap nothing can reconcile against later
    assert not cols["scope"]["nullable"] and not cols["seq"]["nullable"]
    _run(engine, mod, "down")
    assert "journal_gap" not in inspect(engine).get_table_names()
