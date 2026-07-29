"""The 0020 data backfill — the submitted_pieces watermark (Story 2.7, AD-38).

Each existing matter's ``submitted_pieces`` is frozen from its current known population
(``in_corpus + open_register_entries``); a resolved failure is not counted, an empty matter is 0.
Tested directly (the alembic chain runs on Postgres only).
"""

from __future__ import annotations

from sqlalchemy import create_engine, text

from apx.adapters.store_postgres.backfill import backfill_submitted_pieces


def _pre_0020(engine) -> None:  # noqa: ANN001
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE matter_scope (tenant TEXT, matter TEXT, scope TEXT, "
            "submitted_pieces INTEGER, PRIMARY KEY (tenant, matter))"))
        conn.execute(text("CREATE TABLE piece (id TEXT PRIMARY KEY, tenant TEXT, matter TEXT)"))
        conn.execute(text(
            "CREATE TABLE failure (id TEXT PRIMARY KEY, tenant TEXT, matter TEXT, "
            "resolution_state TEXT)"))


def test_backfill_freezes_submitted_pieces_from_the_population(tmp_path) -> None:  # noqa: ANN001
    engine = create_engine(f"sqlite:///{tmp_path / 'x.db'}", future=True)
    _pre_0020(engine)
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO matter_scope (tenant, matter, scope) VALUES "
                          "('t', 'm', 'w'), ('t', 'empty', 'w')"))
        conn.execute(text("INSERT INTO piece (id, tenant, matter) VALUES "
                          "('p1', 't', 'm'), ('p2', 't', 'm')"))
        conn.execute(text("INSERT INTO failure (id, tenant, matter, resolution_state) VALUES "
                          "('f1', 't', 'm', 'open'), ('f2', 't', 'm', 'resolved')"))
    with engine.begin() as conn:
        assert backfill_submitted_pieces(conn) == 2  # both matter rows set
    with engine.connect() as conn:
        rows = dict(conn.execute(text("SELECT matter, submitted_pieces FROM matter_scope")).all())
    # m: 2 pieces + 1 OPEN failure (the resolved one is not counted); the empty matter: 0.
    assert rows == {"m": 3, "empty": 0}


def test_backfill_is_a_pure_recompute_and_idempotent(tmp_path) -> None:  # noqa: ANN001
    engine = create_engine(f"sqlite:///{tmp_path / 'x.db'}", future=True)
    _pre_0020(engine)
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO matter_scope (tenant, matter, scope) VALUES ('t', 'm', 'w')"))
        conn.execute(text("INSERT INTO piece (id, tenant, matter) VALUES ('p1', 't', 'm')"))
        backfill_submitted_pieces(conn)
        backfill_submitted_pieces(conn)  # re-run — a pure recompute from the population
    with engine.connect() as conn:
        got = conn.execute(text("SELECT submitted_pieces FROM matter_scope WHERE matter='m'"))
    assert got.scalar() == 1
