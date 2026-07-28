"""The 0019 data backfill — failure-register cardinality (Story 2.6, AD-38).

An unopened container is `unknown` (it stands for an unknown number of pièces); everything else is
`one`. Idempotent and key-free. Tested directly (the alembic chain runs on Postgres only).
"""

from __future__ import annotations

from sqlalchemy import create_engine, text

from apx.adapters.store_postgres.backfill import backfill_failure_cardinality


def _pre_0019(engine) -> None:  # noqa: ANN001
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE failure (id TEXT PRIMARY KEY, error_class TEXT, cardinality TEXT)"))


def test_backfill_sets_unknown_only_for_containers(tmp_path) -> None:  # noqa: ANN001
    engine = create_engine(f"sqlite:///{tmp_path / 'x.db'}", future=True)
    _pre_0019(engine)
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO failure (id, error_class) VALUES "
                          "('a', 'container-unopenable'), ('b', 'extraction-error'), "
                          "('c', 'password-protected')"))
    with engine.begin() as conn:
        assert backfill_failure_cardinality(conn) == 3
    with engine.connect() as conn:
        rows = dict(conn.execute(text("SELECT id, cardinality FROM failure")).all())
    assert rows == {"a": "unknown", "b": "one", "c": "one"}


def test_backfill_is_idempotent_and_preserves_a_set_value(tmp_path) -> None:  # noqa: ANN001
    engine = create_engine(f"sqlite:///{tmp_path / 'x.db'}", future=True)
    _pre_0019(engine)
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO failure (id, error_class, cardinality) VALUES "
                          "('a', 'container-unopenable', 'unknown')"))  # already set
        backfill_failure_cardinality(conn)
        backfill_failure_cardinality(conn)  # re-run
    with engine.connect() as conn:
        card = conn.execute(text("SELECT cardinality FROM failure WHERE id='a'")).scalar()
    assert card == "unknown"
