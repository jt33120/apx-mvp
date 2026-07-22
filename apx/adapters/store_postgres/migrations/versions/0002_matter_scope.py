"""slice A (RBAC): the matter_scope table — the authoritative scope, pre-filtered
at query time (AD-13). Never denormalised onto piece/chunk rows.

Revision ID: 0002_matter_scope
Revises: 0001_slice_a
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002_matter_scope"
down_revision = "0001_slice_a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "matter_scope",
        sa.Column("matter", sa.String(), primary_key=True),
        sa.Column("tenant", sa.String(), nullable=False),
        sa.Column("scope", sa.String(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("matter_scope")
