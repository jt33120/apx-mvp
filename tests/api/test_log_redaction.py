"""A secret must never reach a log (story 1.8, AD-47/FR-51). These tests drive the REAL
installer (`install_secret_redaction`), not a hand-attached filter — including a child logger
and a `propagate=False` logger (uvicorn's shape), the paths the first cut silently missed.
"""

from __future__ import annotations

import io
import logging

import pytest

from apx.api.logging import SecretRedactor, _configured_secrets, install_secret_redaction

_SECRET = "SavGoemmyVvu9lseGv04DjBzdXYmcvZG"  # a fake key value, never a real one


@pytest.fixture(autouse=True)
def _clean_log_factory():
    """Install sets a GLOBAL record factory and is idempotent. Reset to the default BEFORE each
    test so `install_secret_redaction` actually installs THIS test's redactor (an earlier app
    test may have installed one for the conftest key), and restore AFTER so nothing leaks."""
    saved = logging.getLogRecordFactory()
    logging.setLogRecordFactory(logging.LogRecord)
    yield
    logging.setLogRecordFactory(saved)


def _capture(name: str, *, propagate: bool, message: str, args: tuple = ()) -> str:
    logger = logging.getLogger(name)
    logger.handlers.clear()
    logger.propagate = propagate
    logger.setLevel(logging.INFO)
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    logger.info(message, *args)
    return stream.getvalue()


def test_install_scrubs_a_secret_from_a_child_logger() -> None:
    install_secret_redaction({"APX_ENCRYPTION_KEY": _SECRET})
    out = _capture("apx.some.child", propagate=True, message="boot with key=%s", args=(_SECRET,))
    assert _SECRET not in out and "«redacted»" in out


def test_install_scrubs_a_propagate_false_logger() -> None:
    # uvicorn's access/error loggers set propagate=False + their own handler; a root-only filter
    # never sees them, but the global record factory does. This is the H1/H2 fix under test.
    url = f"postgresql://u:{_SECRET}@host/db"
    install_secret_redaction({"DATABASE_URL": url})
    out = _capture("apx.uvicornish", propagate=False, message="connecting to %s", args=(url,))
    assert _SECRET not in out and "«redacted»" in out


def test_install_covers_an_embedder_key_and_bootstrap_password_by_policy() -> None:
    # secrets are gathered by POLICY (name shape), so a provider/embedder key or the bootstrap
    # password is covered without editing the module (FR-51 names embedder credentials).
    install_secret_redaction(
        {"EMBEDDER_API_KEY": _SECRET, "APX_BOOTSTRAP_ADMIN_PASSWORD": "hunter2hunter2"}
    )
    out = _capture("apx.embed", propagate=True, message="key=%s pw=%s",
                   args=(_SECRET, "hunter2hunter2"))
    assert _SECRET not in out and "hunter2hunter2" not in out


def test_configured_secrets_is_policy_based() -> None:
    env = {
        "APX_ENCRYPTION_KEY": "PRIMARYKEYVALUE00000000000000000000",
        "APX_ENCRYPTION_KEYS_OLD": "OLDKEYVALUE1111111, OLDKEYVALUE2222222",
        "OPENAI_API_KEY": "openai-secret-key-value",
        "APX_COOKIE_SECURE": "1",           # a config flag, not a secret — must NOT be gathered
        "APX_DB_SSLMODE": "require",         # ditto
    }
    secrets = _configured_secrets(env)
    assert env["APX_ENCRYPTION_KEY"] in secrets
    assert "OLDKEYVALUE1111111" in secrets and "OLDKEYVALUE2222222" in secrets
    assert "openai-secret-key-value" in secrets
    assert "1" not in secrets and "require" not in secrets  # short config values are not secrets


def test_a_database_url_and_its_embedded_password_are_both_gathered() -> None:
    url = "postgresql+psycopg://apx:s3cr3tPassw0rd@host:5432/db"
    secrets = _configured_secrets({"DATABASE_URL": url})
    assert url in secrets and "s3cr3tPassw0rd" in secrets


def test_the_redactor_leaves_a_non_secret_line_unchanged() -> None:
    assert SecretRedactor([_SECRET]).redact("a normal line") == "a normal line"
