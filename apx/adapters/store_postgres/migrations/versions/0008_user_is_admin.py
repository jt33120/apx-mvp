"""cockpit: user_account.is_admin — who may administer users and scope grants.

Revision ID: 0008_user_is_admin
Revises: 0007_recall_review
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0008_user_is_admin"
down_revision = "0007_recall_review"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_account",
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("user_account", "is_admin")
