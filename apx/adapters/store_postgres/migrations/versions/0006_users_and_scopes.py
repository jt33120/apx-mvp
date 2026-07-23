"""owned auth: user_account + user_scope — identity and authoritative scope grants (AD-15/AD-13).

Revision ID: 0006_users_and_scopes
Revises: 0005_piece_label
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0006_users_and_scopes"
down_revision = "0005_piece_label"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_account",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("tenant", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.Column("display_name", sa.String(), nullable=False),
        sa.UniqueConstraint("tenant", "email", name="uq_user_tenant_email"),
    )
    op.create_table(
        "user_scope",
        sa.Column("user_id", sa.String(32), primary_key=True),
        sa.Column("scope", sa.String(), primary_key=True),
    )


def downgrade() -> None:
    op.drop_table("user_scope")
    op.drop_table("user_account")
