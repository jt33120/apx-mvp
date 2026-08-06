"""pin_entry — the pin, moving a single pièce across the line (Story 4.11, FR-43/FR-25).

A NEW append-only, version-independent ledger: one row per pin or unpin of a pièce, keyed by
(tenant, matter, piece_id) with a per-pièce monotonic ``seq`` (AD-49). The CURRENT pin is a VIEW over
it (the max-seq row, in force only when its action is retain/discard). Version-independent, so a pin
survives re-ranking (FR-43). NO backfill: a pre-4.11 pièce has no pin. No re-index, no corpus mutation
(NFR-56). Downgrade drops the table.

Revision ID: 0028_pin_entry
Revises: 0027_line_placement
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0028_pin_entry"
down_revision = "0027_line_placement"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pin_entry",
        sa.Column("id", sa.String(length=64), nullable=False),   # sha256(tenant\0matter\0pid\0seq)
        sa.Column("tenant", sa.String(), nullable=False),
        sa.Column("matter", sa.String(), nullable=False),
        sa.Column("piece_id", sa.String(length=64), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),          # per-pièce monotonic (AD-49)
        sa.Column("action", sa.String(), nullable=False),        # retain | discard | removed
        sa.Column("reason", sa.Text(), nullable=False),          # EncryptedText → Text at rest
        sa.Column("set_by", sa.Text(), nullable=False),          # EncryptedText → Text at rest
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        # composite FK to the matter identity (AD-12); no ondelete (AD-7 RESTRICT)
        sa.ForeignKeyConstraint(
            ["tenant", "matter"], ["matter_scope.tenant", "matter_scope.matter"]),
        sa.PrimaryKeyConstraint("id"),
        # a per-pièce monotonic seq; a concurrent double-write collides here, never overwrites
        sa.UniqueConstraint("tenant", "matter", "piece_id", "seq", name="uq_pin_entry_seq"),
    )
    op.create_index("ix_pin_entry_piece", "pin_entry", ["tenant", "matter", "piece_id"])


def downgrade() -> None:
    op.drop_index("ix_pin_entry_piece", table_name="pin_entry")
    op.drop_table("pin_entry")
