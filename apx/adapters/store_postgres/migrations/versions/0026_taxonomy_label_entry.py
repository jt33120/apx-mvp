"""taxonomy_label_entry — per-pièce TAXONOMY labelling (Story 4.5, FR-40).

A NEW append-only, version-independent ledger: one row per label assignment or reversal, keyed by
(tenant, matter, piece_id) with a per-pièce monotonic ``seq`` (AD-49). The CURRENT label is a VIEW
over it (the max-seq row, or ``unlabelled``). NO backfill: a pre-4.5 pièce has no assignment, so its
current label is the ``unlabelled`` view default — honest (AD-19), never a guessed category. No
re-index, no corpus mutation (NFR-56). Downgrade drops the table.

Revision ID: 0026_taxonomy_label_entry
Revises: 0025_ranked_entry_confidence
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0026_taxonomy_label_entry"
down_revision = "0025_ranked_entry_confidence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "taxonomy_label_entry",
        sa.Column("id", sa.String(length=64), nullable=False),  # sha256(tenant\0matter\0pid\0seq)
        sa.Column("tenant", sa.String(), nullable=False),
        sa.Column("matter", sa.String(), nullable=False),
        sa.Column("piece_id", sa.String(length=64), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),          # per-pièce monotonic (AD-49)
        sa.Column("label", sa.String(), nullable=False),         # taxonomy member OR 'unlabelled'
        sa.Column("source", sa.String(), nullable=False),        # human | machine (reserved)
        sa.Column("set_by", sa.Text(), nullable=False),          # EncryptedText → Text at rest
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        # composite FK to the matter identity (AD-12); no ondelete (AD-7 RESTRICT)
        sa.ForeignKeyConstraint(
            ["tenant", "matter"], ["matter_scope.tenant", "matter_scope.matter"]),
        sa.PrimaryKeyConstraint("id"),
        # a per-pièce monotonic seq; a concurrent double-write collides here, never overwrites
        sa.UniqueConstraint("tenant", "matter", "piece_id", "seq", name="uq_taxonomy_label_seq"),
    )
    op.create_index(
        "ix_taxonomy_label_piece", "taxonomy_label_entry", ["tenant", "matter", "piece_id"])


def downgrade() -> None:
    op.drop_index("ix_taxonomy_label_piece", table_name="taxonomy_label_entry")
    op.drop_table("taxonomy_label_entry")
