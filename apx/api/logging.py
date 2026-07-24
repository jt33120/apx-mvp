"""Secret redaction for logs (story 1.8, AD-47/FR-51).

Secrets must never reach a log. The enforceable form of that is a logging filter that scrubs
the known secret *values* (the configured keys and credentials, read from the environment) out
of every log record before it is emitted — so even a careless ``logger.info(f"...{url}...")``
that includes a `DATABASE_URL` or an API key comes out masked. A structural "no secret at a log
call site" check is not decidable generically; this filter plus a seeded-secret test (a secret
in a log line must come out redacted, or the build is red) is the enforceable guarantee.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Mapping
from urllib.parse import urlsplit

_MASK = "«redacted»"

# The environment variables that hold a secret value. Their VALUES (not their names) are what
# must never appear in a log line.
_SECRET_ENV_VARS = (
    "APX_ENCRYPTION_KEY",
    "APX_SECRET_KEY",
    "LLM_API_KEY",
    "MISTRAL_API_KEY",
)


def _configured_secrets(env: Mapping[str, str]) -> list[str]:
    """Every concrete secret value currently configured — the primary and previous encryption
    keys, the session secret, the model-provider keys, and the ``DATABASE_URL`` (whole, and its
    embedded password, which may be logged on its own by a driver)."""
    values: list[str] = []
    for name in _SECRET_ENV_VARS:
        value = env.get(name)
        if value:
            values.append(value)
    for old in env.get("APX_ENCRYPTION_KEYS_OLD", "").split(","):
        if old.strip():
            values.append(old.strip())
    db_url = env.get("DATABASE_URL")
    if db_url:
        values.append(db_url)
        password = urlsplit(db_url).password
        if password:
            values.append(password)
    # longest first, so a value contained in another (a password inside its URL) is masked whole
    return sorted(set(values), key=len, reverse=True)


class SecretRedactor(logging.Filter):
    """A logging filter that replaces any configured secret value with ``«redacted»`` in the
    formatted record. Returns True always (it never drops a record — it scrubs it)."""

    def __init__(self, secrets: list[str]) -> None:
        super().__init__()
        self._secrets = [s for s in secrets if s]

    def filter(self, record: logging.LogRecord) -> bool:
        if not self._secrets:
            return True
        message = record.getMessage()
        redacted = message
        for secret in self._secrets:
            if secret in redacted:
                redacted = redacted.replace(secret, _MASK)
        if redacted != message:
            record.msg = redacted
            record.args = ()  # already interpolated into the redacted message
        return True


def install_secret_redaction(env: Mapping[str, str] | None = None) -> SecretRedactor:
    """Attach the redactor to the root logger AND to every existing handler (a filter on a
    logger only sees records emitted directly to it; handlers see propagated records too), so
    output from any logger — including uvicorn's — is scrubbed. Idempotent. Called at start-up."""
    source = os.environ if env is None else env
    redactor = SecretRedactor(_configured_secrets(source))
    root = logging.getLogger()
    if not any(isinstance(f, SecretRedactor) for f in root.filters):
        root.addFilter(redactor)
    for handler in root.handlers:
        if not any(isinstance(f, SecretRedactor) for f in handler.filters):
            handler.addFilter(redactor)
    return redactor
