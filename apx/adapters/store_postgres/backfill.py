"""Encrypt-at-rest backfill (story 1.7, AD-31).

Re-encrypt any content-bearing column value still stored in the clear — a store provisioned
before 1.7 turned these columns into ``EncryptedText``. Idempotent (an already-encrypted value
is skipped), and key-free when there is nothing to do: the cipher is loaded ONLY when a
plaintext value is found, so a fresh/already-encrypted store needs no ``APX_ENCRYPTION_KEY``.

Shared by the ``0013_encrypt_backfill`` data migration (run in the deploy's ``alembic upgrade``)
and testable directly against a connection. Without it, enabling encryption on an existing store
would make every historical row fail closed on read (the type refuses a non-ciphertext value).
"""

from __future__ import annotations

from sqlalchemy import Connection, text

from apx.core.domain.crypto import is_ciphertext

# (table, primary-key column, encrypted column, AAD context) — must match the EncryptedText
# contexts declared on the models (the 1.7 encrypted set).
ENCRYPTED_COLUMNS = [
    ("piece", "id", "provenance_path", "piece.provenance_path"),
    ("piece", "id", "custodian", "piece.custodian"),
    ("failure", "id", "filename", "failure.filename"),
    ("failure", "id", "submitted_path", "failure.submitted_path"),
    ("failure", "id", "detail", "failure.detail"),
    ("audit_record", "id", "actor", "audit_record.actor"),
    ("audit_record", "id", "detail", "audit_record.detail"),
    ("piece_label", "piece_id", "rationale", "piece_label.rationale"),
    ("user_account", "id", "mfa_secret", "user_account.mfa_secret"),
    ("recall_review", "id", "reviewer", "recall_review.reviewer"),
]


def encrypt_backfill(conn: Connection) -> int:
    """Encrypt every plaintext value in the AD-31 encrypted columns. Returns the number of
    values encrypted. Idempotent; loads the cipher only when there is plaintext to encrypt."""
    cipher = None
    encrypted = 0
    for table, pk, col, context in ENCRYPTED_COLUMNS:
        rows = conn.execute(
            text(f"SELECT {pk} AS k, {col} AS v FROM {table} WHERE {col} IS NOT NULL")  # noqa: S608
        ).all()
        plaintext = [(r.k, r.v) for r in rows if not is_ciphertext(r.v)]
        if not plaintext:
            continue
        if cipher is None:
            from apx.adapters.store_postgres.crypto_types import cipher as _cipher
            cipher = _cipher()  # raises MissingEncryptionKey if absent — fail closed
        for key, value in plaintext:
            conn.execute(
                text(f"UPDATE {table} SET {col} = :v WHERE {pk} = :k"),  # noqa: S608
                {"v": cipher.encrypt(value, aad=context), "k": key},
            )
            encrypted += 1
    return encrypted
