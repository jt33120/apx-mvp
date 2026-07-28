"""piece_provenance + piece_custodian — the provenance and custodian SETS (Story 2.5, FR-4).

A *pièce*'s provenance is a set of paths (AD-8: "one *pièce* may carry several") and its
custodianship is a set (AD-9's CUSTODIAN_LINK) — **unioned, never replaced or collapsed, by every
import job** admitting the same content. This migration creates the two set tables, backfills each
existing piece's scalar ``custodian`` and ``provenance_path`` into them, then **drops the
``piece.custodian`` column** (AD-9: no custodian column may exist on ``piece``; the structural
property ``no_custodian_or_scope_column_on_piece`` enforces it). The scalar
``piece.provenance_path`` stays as the first-seen *representative* (four reads use it).

No cascade FK (AD-7): both link FKs are RESTRICT (a *pièce* is retired, never hard-deleted out
from under its sets). Dropping a *column* is not one of AD-7's forbidden tokens
(``DELETE FROM``/``TRUNCATE``/``DROP TABLE``) and is data-preserving here (backfilled first). The
backfill is key-free on an empty ``piece`` table (the CI upgrade→downgrade→upgrade cycle runs
without ``APX_ENCRYPTION_KEY``); it loads the cipher only to re-encrypt existing ciphertext under
the new column's AAD. Downgrade re-adds the column and restores a representative custodian.

Revision ID: 0018_piece_provenance_and_custodian_sets
Revises: 0017_import_job_ledger
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from apx.adapters.store_postgres.backfill import (
    migrate_piece_scalars_to_links,
    revert_piece_links_to_scalar,
)

revision = "0018_piece_provenance_and_custodian_sets"
down_revision = "0017_import_job_ledger"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "piece_provenance",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("piece_id", sa.String(length=64), nullable=False),
        sa.Column("provenance_path", sa.Text(), nullable=False),  # EncryptedText → ciphertext
        # no ondelete (AD-7): RESTRICT by default — a retired state, never a cascade
        sa.ForeignKeyConstraint(["piece_id"], ["piece.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_piece_provenance_piece_id", "piece_provenance", ["piece_id"])
    op.create_table(
        "piece_custodian",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("piece_id", sa.String(length=64), nullable=False),
        sa.Column("custodian", sa.Text(), nullable=False),  # EncryptedText → ciphertext
        sa.ForeignKeyConstraint(["piece_id"], ["piece.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_piece_custodian_piece_id", "piece_custodian", ["piece_id"])
    # backfill BEFORE the drop, so no custodian value is lost (AD-7: data-preserving)
    migrate_piece_scalars_to_links(op.get_bind())
    op.drop_column("piece", "custodian")


def downgrade() -> None:
    # Re-add the scalar nullable, restore a representative custodian per piece, then re-assert
    # NOT NULL (every piece has ≥1 custodian link, so the backfill always finds one).
    op.add_column("piece", sa.Column("custodian", sa.Text(), nullable=True))
    revert_piece_links_to_scalar(op.get_bind())
    op.alter_column("piece", "custodian", nullable=False)
    op.drop_index("ix_piece_custodian_piece_id", table_name="piece_custodian")
    op.drop_table("piece_custodian")
    op.drop_index("ix_piece_provenance_piece_id", table_name="piece_provenance")
    op.drop_table("piece_provenance")
