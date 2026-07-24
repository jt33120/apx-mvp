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
def cipher() -> Cipher:
    """The process-wide cipher, from ``APX_ENCRYPTION_KEY``. Cached after first use;
    fails closed if the key is absent or unusable (MissingEncryptionKey). Public so the store
    can decrypt raw-read columns defensively (the audit trail's graceful-degrade path)."""
    return Cipher.from_env()


class EncryptedText(TypeDecorator):
    """Application-layer AES-256-GCM at rest. ``None`` round-trips as ``None`` (a nullable
    column stays nullable); every non-null value is stored encrypted and returned decrypted.
    A stored value that is not ciphertext fails closed on read (crypto.DecryptionError).

    Each column passes its identity (``"table.column"``) as the cipher's associated data, so a
    ciphertext is bound to its column: a stolen-disk / DB-write attacker cannot relocate one
    column's ciphertext into another column or table and have it decrypt (AAD mismatch → fail
    closed). (Cross-row relocation within the SAME column is not closed by a column-level AAD —
    that needs row-bound AAD in the store layer; recorded as a residual.)"""

    impl = Text
    cache_ok = True

    def __init__(self, context: str) -> None:
        # `context` is the AAD — the column's logical identity, e.g. "piece.provenance_path".
        # Stored as an attribute so it participates in SQLAlchemy's type cache key (cache_ok).
        self.context = context
        super().__init__()

    def process_bind_param(self, value: str | None, dialect: object) -> str | None:
        if value is None:
            return None
        return cipher().encrypt(value, aad=self.context)

    def process_result_value(self, value: str | None, dialect: object) -> str | None:
        if value is None:
            return None
        return cipher().decrypt(value, aad=self.context)
