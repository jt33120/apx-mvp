"""the recall guarantee: recall_review — a recorded confidence bound on a discard pile.

Revision ID: 0007_recall_review
Revises: 0006_users_and_scopes
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0007_recall_review"
down_revision = "0006_users_and_scopes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "recall_review",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("tenant", sa.String(), nullable=False),
        sa.Column("matter", sa.String(), nullable=False),
        sa.Column("population", sa.Integer(), nullable=False),
        sa.Column("sample_size", sa.Integer(), nullable=False),
        sa.Column("relevant_found", sa.Integer(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("count_upper", sa.Integer(), nullable=False),
        sa.Column("prevalence_upper", sa.Float(), nullable=False),
        sa.Column("reviewer", sa.String(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_recall_review_matter", "recall_review", ["matter"])


def downgrade() -> None:
    op.drop_index("ix_recall_review_matter", table_name="recall_review")
    op.drop_table("recall_review")
