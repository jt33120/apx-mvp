"""Suite-wide provisioning for encryption at rest (story 1.7, AD-31).

Tests SHOULD run with encryption on — it is the real posture, and it makes the encrypted
columns and the start-up gate exercised by the whole suite rather than a corner of it. This
autouse, session-scoped fixture sets a throwaway application key and attests the (test) data
volume, so:

  * every ``EncryptedText`` column round-trips through a real AES-256-GCM cipher, and
  * ``with TestClient(app)`` passes the fail-closed start-up gate.

The gate's own fail-closed branches are driven in ``tests/api/test_startup_gate.py`` with an
explicit ``env`` dict, and the cipher's key handling in ``tests/domain/test_crypto.py`` with
its own keys — neither disturbs this global, so the process-wide cipher cache stays valid.
"""

from __future__ import annotations

import os

import pytest

from apx.core.domain.crypto import generate_key


@pytest.fixture(scope="session", autouse=True)
def _encryption_provisioned() -> None:
    # A fresh key per test run — never a committed constant (the static check forbids that).
    os.environ.setdefault("APX_ENCRYPTION_KEY", generate_key())
    os.environ.setdefault("APX_VOLUME_ENCRYPTED", "1")
