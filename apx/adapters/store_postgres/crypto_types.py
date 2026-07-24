"""The encrypted column type (story 1.7, AD-31).

``EncryptedText`` is a SQLAlchemy ``TypeDecorator`` that encrypts on write and decrypts
on read, transparently — the store code assigns and reads plaintext, the database holds
only ``apxenc:`` ciphertext. Its physical type is ``Text``, so the base64 token fits in the
same unbounded column with no DDL change (Alembic migrations are hand-written; the ORM type
governs bind/result processing, not the schema).

The cipher is resolved lazily from the environment (:func:`apx.core.domain.crypto.Cipher.from_env`)
and cached — so importing the models needs no key, but the first read or write of an
encrypted column does. Absence fails closed there, and the start-up gate (AD-31) turns the
same absence into a refusal to boot, so it never gets that far in a real deployment.

Because AES-GCM ciphertext is randomised (a fresh nonce per write), an ``EncryptedText``
column can never be matched, ordered or grouped in SQL — it holds document *content*, never
a query key. Keys, ids, hashes and categorical metadata stay plaintext by design.
"""

from __future__ import annotations

from functools import lru_cache

from sqlalchemy import Text
from sqlalchemy.types import TypeDecorator

from apx.core.domain.crypto import Cipher


@lru_cache(maxsize=1)
def _cipher() -> Cipher:
    """The process-wide cipher, from ``APX_ENCRYPTION_KEY``. Cached after first use;
    fails closed if the key is absent or unusable (MissingEncryptionKey)."""
    return Cipher.from_env()


class EncryptedText(TypeDecorator):
    """Application-layer AES-256-GCM at rest. ``None`` round-trips as ``None`` (a nullable
    column stays nullable); every non-null value is stored encrypted and returned decrypted.
    A stored value that is not ciphertext fails closed on read (crypto.DecryptionError)."""

    impl = Text
    cache_ok = True

    def process_bind_param(self, value: str | None, dialect: object) -> str | None:
        if value is None:
            return None
        return _cipher().encrypt(value)

    def process_result_value(self, value: str | None, dialect: object) -> str | None:
        if value is None:
            return None
        return _cipher().decrypt(value)
