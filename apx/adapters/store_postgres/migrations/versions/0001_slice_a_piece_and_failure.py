"""slice A: the piece and failure tables.

A minimal, honest down-payment on the payload schema (story 1.3). No cascade FK
(AD-7). Idempotency via a unique (matter, content_hash). The date/status invariant
enforced by a CHECK.

Revision ID: 0001_slice_a
Revises:
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001_slice_a"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "piece",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("tenant", sa.String(), nullable=False),
        sa.Column("matter", sa.String(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("provenance_path", sa.Text(), nullable=False),
        sa.Column("custodian", sa.String(), nullable=False),
        sa.Column("extraction_method", sa.String(), nullable=False),
        sa.Column("extractor_version", sa.String(), nullable=False),
        sa.Column("schema_version", sa.String(), nullable=False),
        sa.Column("ingestion_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("piece_date", sa.Date(), nullable=True),
        sa.Column("piece_date_status", sa.String(), nullable=False),
        sa.Column("full_text", sa.Text(), nullable=False),
        sa.Column("text_version", sa.String(), nullable=False),
        sa.UniqueConstraint("matter", "content_hash", name="uq_piece_matter_content"),
        sa.CheckConstraint(
            "(piece_date IS NOT NULL) = (piece_date_status = 'determined')",
            name="ck_piece_date_status",
        ),
    )
    op.create_table(
        "failure",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("tenant", sa.String(), nullable=False),
        sa.Column("matter", sa.String(), nullable=False),
        sa.Column("filename", sa.String(), nullable=False),
        sa.Column("submitted_path", sa.Text(), nullable=False),
        sa.Column("error_class", sa.String(), nullable=False),
        sa.Column("resolution_state", sa.String(), nullable=False),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("failure")
    op.drop_table("piece")
