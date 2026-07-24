"""A secret must never reach a log (story 1.8, AD-47/FR-51). The redaction filter scrubs the
configured secret values out of every record — a secret placed in a log line comes out masked,
or this test (and the build) goes red.
"""

from __future__ import annotations

import io
import logging

from apx.api.logging import SecretRedactor, _configured_secrets

_SECRET = "SavGoemmyVvu9lseGv04DjBzdXYmcvZG"  # a fake key value, never a real one


def _logged_with_redaction(secrets: list[str], message: str, *args: object) -> str:
    logger = logging.getLogger("apx.test.redaction")
    logger.handlers.clear()
    logger.setLevel(logging.INFO)
    logger.propagate = False
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.addFilter(SecretRedactor(secrets))
    logger.addHandler(handler)
    logger.info(message, *args)
    return stream.getvalue()


def test_a_secret_in_a_log_line_is_redacted() -> None:
    out = _logged_with_redaction([_SECRET], "connecting with key=%s to the model", _SECRET)
    assert _SECRET not in out
    assert "«redacted»" in out


def test_a_secret_spliced_into_the_format_string_is_redacted() -> None:
    out = _logged_with_redaction([_SECRET], f"key is {_SECRET}")  # no %-args, still scrubbed
    assert _SECRET not in out and "«redacted»" in out


def test_a_database_url_and_its_embedded_password_are_both_redacted() -> None:
    url = "postgresql+psycopg://apx:s3cr3tPassw0rd@host:5432/db"
    secrets = _configured_secrets({"DATABASE_URL": url})
    assert url in secrets and "s3cr3tPassw0rd" in secrets  # the whole URL AND its password
    whole = _logged_with_redaction(secrets, "DSN=%s", url)
    assert "s3cr3tPassw0rd" not in whole and url not in whole
    just_pw = _logged_with_redaction(secrets, "password=%s", "s3cr3tPassw0rd")
    assert "s3cr3tPassw0rd" not in just_pw  # even the bare password, logged alone


def test_configured_secrets_gathers_every_held_secret() -> None:
    env = {
        "APX_ENCRYPTION_KEY": "PRIMARYKEYVALUE0000000000000000000000000000",
        "APX_ENCRYPTION_KEYS_OLD": "OLDKEY1, OLDKEY2",
        "LLM_API_KEY": "llm-provider-key",
    }
    secrets = _configured_secrets(env)
    assert env["APX_ENCRYPTION_KEY"] in secrets
    assert "OLDKEY1" in secrets and "OLDKEY2" in secrets and "llm-provider-key" in secrets


def test_a_non_secret_line_passes_through_unchanged() -> None:
    out = _logged_with_redaction([_SECRET], "a normal log line with no secret in it")
    assert "a normal log line with no secret in it" in out and "«redacted»" not in out
