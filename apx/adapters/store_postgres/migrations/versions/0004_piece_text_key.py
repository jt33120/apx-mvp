"""slice A (triage): the near-duplicate key on piece (the judgment cascade's deterministic tier).

Revision ID: 0004_piece_text_key
Revises: 0003_audit_record
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004_piece_text_key"
down_revision = "0003_audit_record"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # NOT NULL with an empty server_default so the add is safe on any existing rows;
    # the app always computes a real key (dedup.text_key), so the default is never
    # relied on in practice. Indexed — deduplication groups by this key.
    op.add_column(
        "piece",
        sa.Column("text_key", sa.String(64), nullable=False, server_default=""),
    )
    op.create_index("ix_piece_text_key", "piece", ["text_key"])


def downgrade() -> None:
    op.drop_index("ix_piece_text_key", table_name="piece")
    op.drop_column("piece", "text_key")
