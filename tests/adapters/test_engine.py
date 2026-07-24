"""DATABASE_URL normalisation: managed hosts hand out driverless URLs; bind psycopg. Plus
TLS in transit (story 1.7, AD-31): the app↔store connection requires SSL by default."""

from __future__ import annotations

import pytest

from apx.adapters.store_postgres.engine import _normalise, _with_sslmode


def test_managed_postgres_urls_get_the_psycopg_driver() -> None:
    assert _normalise("postgres://u:p@h:5432/db") == "postgresql+psycopg://u:p@h:5432/db"
    assert _normalise("postgresql://u:p@h:5432/db") == "postgresql+psycopg://u:p@h:5432/db"


def test_explicit_driver_and_sqlite_pass_through() -> None:
    assert _normalise("postgresql+psycopg://u@h/db") == "postgresql+psycopg://u@h/db"
    assert _normalise("sqlite:////tmp/x.db") == "sqlite:////tmp/x.db"


def test_a_postgres_url_requires_tls_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("APX_DB_SSLMODE", raising=False)  # no override → the secure default
    assert _with_sslmode("postgresql+psycopg://u:p@h:5432/db") == (
        "postgresql+psycopg://u:p@h:5432/db?sslmode=require"
    )


def test_a_same_machine_loopback_may_opt_out(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APX_DB_SSLMODE", "disable")  # the documented same-host exemption
    assert _with_sslmode("postgresql+psycopg://u@h/db") == "postgresql+psycopg://u@h/db?sslmode=disable"


def test_an_explicit_sslmode_in_the_url_is_left_untouched(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APX_DB_SSLMODE", "require")
    url = "postgresql+psycopg://u@h/db?sslmode=verify-full"
    assert _with_sslmode(url) == url  # never doubled, never downgraded


def test_sslmode_joins_an_existing_query_with_ampersand(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("APX_DB_SSLMODE", raising=False)
    url = "postgresql+psycopg://u@h/db?connect_timeout=5"
    assert _with_sslmode(url) == url + "&sslmode=require"


def test_sqlite_is_never_given_an_sslmode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APX_DB_SSLMODE", "require")
    assert _with_sslmode("sqlite:////tmp/x.db") == "sqlite:////tmp/x.db"


def test_sslmode_in_the_password_is_not_a_false_positive(monkeypatch: pytest.MonkeyPatch) -> None:
    # the guard parses the query string, not the whole URL — a password containing "sslmode="
    # must not be read as an already-set sslmode and silently skip TLS.
    monkeypatch.delenv("APX_DB_SSLMODE", raising=False)
    url = "postgresql+psycopg://u:p-sslmode=x@h:5432/db"
    assert _with_sslmode(url) == url + "?sslmode=require"
