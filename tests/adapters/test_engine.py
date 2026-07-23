"""DATABASE_URL normalisation: managed hosts hand out driverless URLs; bind psycopg."""

from __future__ import annotations

from apx.adapters.store_postgres.engine import _normalise


def test_managed_postgres_urls_get_the_psycopg_driver() -> None:
    assert _normalise("postgres://u:p@h:5432/db") == "postgresql+psycopg://u:p@h:5432/db"
    assert _normalise("postgresql://u:p@h:5432/db") == "postgresql+psycopg://u:p@h:5432/db"


def test_explicit_driver_and_sqlite_pass_through() -> None:
    assert _normalise("postgresql+psycopg://u@h/db") == "postgresql+psycopg://u@h/db"
    assert _normalise("sqlite:////tmp/x.db") == "sqlite:////tmp/x.db"
