"""backup, restore & DR (story 1.11, AD-32/AD-35): backup_record + truncation_marker.

``backup_record`` answers "no successful backup within the interval" (AD-32); ``truncation_marker``
persists a detected restore-truncation — the live chain head fell behind the head journal (AD-35),
never repaired, cleared only by an audited override. The head journal itself lives OUTSIDE the
restorable database (a file on a volume the dump does not cover), so it is not a table.

Revision ID: 0015_backup_and_truncation
Revises: 0014_tenant_setting
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0015_backup_and_truncation"
down_revision = "0014_tenant_setting"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "backup_record",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("tenant", sa.String(), nullable=False),
        sa.Column("outcome", sa.String(), nullable=False),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("byte_size", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_backup_record_tenant", "backup_record", ["tenant"])
    op.create_table(
        "truncation_marker",
        sa.Column("tenant", sa.String(), primary_key=True),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("journal_seq", sa.Integer(), nullable=False),
        sa.Column("live_seq", sa.Integer(), nullable=False),
        sa.Column("cleared_by", sa.Text(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("cleared_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("truncation_marker")
    op.drop_index("ix_backup_record_tenant", table_name="backup_record")
    op.drop_table("backup_record")
