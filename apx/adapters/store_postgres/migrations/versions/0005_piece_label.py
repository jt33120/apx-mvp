"""slice A (triage): the piece_label table — reversible triage verdicts (judgment cascade).

Revision ID: 0005_piece_label
Revises: 0004_piece_text_key
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0005_piece_label"
down_revision = "0004_piece_text_key"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "piece_label",
        sa.Column("piece_id", sa.String(64), primary_key=True),
        sa.Column("tenant", sa.String(), nullable=False),
        sa.Column("matter", sa.String(), nullable=False),
        sa.Column("label", sa.String(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("judge", sa.String(), nullable=False),
        sa.Column("judged_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_piece_label_matter", "piece_label", ["matter"])


def downgrade() -> None:
    op.drop_index("ix_piece_label_matter", table_name="piece_label")
    op.drop_table("piece_label")
