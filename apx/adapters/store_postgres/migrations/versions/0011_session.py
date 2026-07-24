"""owned auth (story 1.5, AD-15): the opaque server-side session table.

The cookie carries only an unguessable id; authority is this row, so sign-out, a password
change and a scope revocation take effect immediately (delete the row / re-resolve live)
rather than waiting for a token to expire — which is why AD-15 forbids a stateless JWT for
user sessions. No user data is denormalised here (actor/admin/scopes resolve live); no
cascade FK (AD-7).

Revision ID: 0011_session
Revises: 0010_tenant_qualified_identity
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0011_session"
down_revision = "0010_tenant_qualified_identity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "session",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("user_id", sa.String(length=32), nullable=False),
        sa.Column("tenant", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("absolute_expiry", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_session_user_id", "session", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_session_user_id", table_name="session")
    op.drop_table("session")
