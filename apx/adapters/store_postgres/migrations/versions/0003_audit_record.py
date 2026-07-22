"""slice A (audit): the append-only, chained audit_record (FR-24, FR-53).

Revision ID: 0003_audit_record
Revises: 0002_matter_scope
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003_audit_record"
down_revision = "0002_matter_scope"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audit_record",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("tenant", sa.String(), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("matter", sa.String(), nullable=True),
        sa.Column("actor", sa.String(), nullable=False),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("detail", sa.Text(), nullable=False),
        sa.Column("chain", sa.String(64), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant", "seq", name="uq_audit_tenant_seq"),
    )


def downgrade() -> None:
    op.drop_table("audit_record")
