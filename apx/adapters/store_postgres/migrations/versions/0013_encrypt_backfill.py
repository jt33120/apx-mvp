"""encryption at rest (story 1.7, AD-31): backfill existing plaintext rows to ciphertext.

Story 1.7 changed several content-bearing columns to the application-encrypted ``EncryptedText``
type. The physical column is unchanged (still TEXT), so there is NO DDL here — but any row
already written in the clear (a store provisioned before 1.7) now fails closed on read
(``DecryptionError``), because the type refuses a non-``apxenc:`` value by design. This
data-only migration re-encrypts those rows once, so enabling encryption on an existing store is
a supported operation, not a data-loss event.

Idempotent: a value already encrypted (``is_ciphertext``) is skipped, so a re-run is a no-op.
Key-free on an empty/already-encrypted store: the encryption key is loaded ONLY when there is a
plaintext row to encrypt — so a fresh install and the CI ``upgrade→downgrade→upgrade`` cycle run
without ``APX_ENCRYPTION_KEY`` set. Downgrade is intentionally a no-op: encryption is never
reversed (a downgrade leaves the data encrypted, which is safe), and with no DDL there is
nothing to undo.

Revision ID: 0013_encrypt_backfill
Revises: 0012_mfa_config
"""

from __future__ import annotations

from alembic import op

from apx.adapters.store_postgres.backfill import encrypt_backfill

revision = "0013_encrypt_backfill"
down_revision = "0012_mfa_config"
branch_labels = None
depends_on = None


def upgrade() -> None:
    encrypt_backfill(op.get_bind())


def downgrade() -> None:
    # Encryption is not reversed (a downgrade must not turn ciphertext back into plaintext on
    # disk), and there is no DDL to undo. Intentionally a no-op.
    pass
