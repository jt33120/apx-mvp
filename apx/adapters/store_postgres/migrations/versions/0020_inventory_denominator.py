"""the inventory denominator — submitted_pieces watermark + the noise-exclusion ledger (Story 2.7).

The permanent *denominator* (AD-38) grows two durable surfaces. (1) ``matter_scope.submitted_pieces``
— the frozen, monotonic high-water mark of a matter's known pièce population, so the SM-3 invariant
``submitted_pieces == in_corpus + open_register_entries`` is a real check (not the tautology of
recomputing it as the sum); backfilled once from the current population. (2) ``noise_exclusion`` —
filesystem noise (FR-6) as its own durable, countable, listable class (path + filename encrypted,
AD-41/AD-31), keyed idempotently so a re-import never double-counts. No cascade FK (AD-7). Reversible.

Revision ID: 0020_inventory_denominator
Revises: 0019_failure_register_fields
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from apx.adapters.store_postgres.backfill import backfill_submitted_pieces

revision = "0020_inventory_denominator"
down_revision = "0019_failure_register_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # The submitted_pieces watermark. Add NOT NULL with server_default="0" (matching the model), so
    # existing rows get 0 immediately and a raw INSERT can never violate NOT NULL; then freeze each
    # matter from its current known population.
    op.add_column(
        "matter_scope",
        sa.Column("submitted_pieces", sa.Integer(), nullable=False, server_default="0"))
    backfill_submitted_pieces(op.get_bind())
    # The noise-exclusion ledger (FR-6). submitted_path/filename are EncryptedText → sa.Text().
    op.create_table(
        "noise_exclusion",
        sa.Column("id", sa.String(length=64), nullable=False),  # sha256(tenant \0 matter \0 path)
        sa.Column("tenant", sa.String(), nullable=False),
        sa.Column("matter", sa.String(), nullable=False),
        sa.Column("submitted_path", sa.Text(), nullable=False),  # EncryptedText (AD-41)
        sa.Column("filename", sa.Text(), nullable=False),        # EncryptedText (AD-41)
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("noise_exclusion")
    op.drop_column("matter_scope", "submitted_pieces")
