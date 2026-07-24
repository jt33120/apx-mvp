"""Secret redaction for logs (story 1.8, AD-47/FR-51).

Secrets must never reach a log. The enforceable form is to scrub the configured secret *values*
out of every log record before it is emitted. This is done GLOBALLY via a `LogRecord` factory —
so it covers every logger (the app's, uvicorn's `propagate=False` access/error loggers,
sqlalchemy's), and handlers added after install — not just the root logger's handlers (a filter
there is never consulted for propagated records, and root often has no handlers under uvicorn).
A redacting formatter is also layered onto existing handlers so a secret inside a formatted
*traceback* (e.g. a DSN in a psycopg connection error) is masked too.

Secrets are gathered by POLICY, not a hand-list: any environment value whose variable name looks
like a secret (`*KEY*`, `*SECRET*`, `*TOKEN*`, `*PASSWORD*`, `*CREDENTIAL*`, `DATABASE_URL`, …)
and is long enough to be one — so a new provider/embedder key or the bootstrap password is
covered without editing this file.
"""

from __future__ import annotations

import logging
import os
import re
from collections.abc import Mapping
from urllib.parse import urlsplit

_MASK = "«redacted»"
_MIN_SECRET_LEN = 8
# Variable-name shapes that hold a secret value (case-insensitive).
_SECRET_NAME = re.compile(r"KEY|SECRET|TOKEN|PASSWORD|PASSWD|CREDENTIAL|PRIVATE|DSN|_PAT", re.I)


def _configured_secrets(env: Mapping[str, str]) -> list[str]:
    """Every concrete secret value currently configured, by policy: any env value under a
    secret-shaped name (long enough to be a real secret), plus DATABASE_URL and its embedded
    password, plus each previous encryption key listed individually. Longest first, so a value
    contained in another (a password inside its URL) is masked whole."""
    values: list[str] = []
    for name, value in env.items():
        if not value or len(value) < _MIN_SECRET_LEN:
            continue
        if name == "DATABASE_URL" or _SECRET_NAME.search(name):
            values.append(value)
            if "://" in value:
                password = urlsplit(value).password
                if password:
                    values.append(password)
    for old in env.get("APX_ENCRYPTION_KEYS_OLD", "").split(","):
        if old.strip():
            values.append(old.strip())
    return sorted({v for v in values if len(v) >= _MIN_SECRET_LEN}, key=len, reverse=True)


class SecretRedactor(logging.Filter):
    """Replaces any configured secret value with ``«redacted»``. Usable as a logging filter
    (returns True — it scrubs, never drops) and directly via :meth:`redact`."""

    def __init__(self, secrets: list[str]) -> None:
        super().__init__()
        self._secrets = [s for s in secrets if s]

    def redact(self, text: str) -> str:
        for secret in self._secrets:
            if secret in text:
                text = text.replace(secret, _MASK)
        return text

    def filter(self, record: logging.LogRecord) -> bool:
        if self._secrets:
            message = record.getMessage()
            redacted = self.redact(message)
            if redacted != message:
                record.msg = redacted
                record.args = ()
        return True


class _RedactingFormatter(logging.Formatter):
    """Wraps another formatter and scrubs its full output — including a formatted traceback."""

    def __init__(self, redactor: SecretRedactor, base: logging.Formatter) -> None:
        super().__init__()
        self._redactor = redactor
        self._base = base

    def format(self, record: logging.LogRecord) -> str:
        return self._redactor.redact(self._base.format(record))


def install_secret_redaction(env: Mapping[str, str] | None = None) -> SecretRedactor:
    """Install global log redaction (idempotent). Called at start-up and by the manage CLI."""
    source = os.environ if env is None else env
    redactor = SecretRedactor(_configured_secrets(source))
    if not redactor._secrets:
        return redactor

    # 1) Global message scrub via the record factory — covers every logger and late handlers.
    old_factory = logging.getLogRecordFactory()
    if not getattr(old_factory, "_apx_redacting", False):
        def factory(*args: object, **kwargs: object) -> logging.LogRecord:
            record = old_factory(*args, **kwargs)  # type: ignore[arg-type]
            try:
                message = record.getMessage()
            except Exception:  # noqa: BLE001 — a broken record must never crash logging
                return record
            redacted = redactor.redact(message)
            if redacted != message:
                record.msg = redacted
                record.args = ()
            return record

        factory._apx_redacting = True  # type: ignore[attr-defined]
        logging.setLogRecordFactory(factory)

    # 2) Formatter scrub on every existing handler — covers formatted tracebacks too.
    loggers: list[logging.Logger] = [logging.getLogger()]
    loggers += [logging.getLogger(n) for n in list(logging.root.manager.loggerDict)]
    for logger in loggers:
        for handler in getattr(logger, "handlers", []):
            base = handler.formatter or logging.Formatter()
            if not isinstance(base, _RedactingFormatter):
                handler.setFormatter(_RedactingFormatter(redactor, base))
    return redactor
