"""case_theory_version — the versioned, audited case theory (Story 4.1, FR-37).

The append-only version table that SUPERSEDES the single ``matter_scope.case_theory`` column (kept
as a denormalised current-value cache). Each rewrite is a new version; a *withdrawal* is a
NULL-text version; a prior version is never updated or deleted (AD-7). ``id`` is the deterministic
sha256 identity a future *ranking version* names (AD-23). The confidential columns (``text``, the
legal strategy; ``actor``, a display name) store ciphertext as ``Text`` — the app layer AES-GCM
encrypts them (AD-31). No cascade FK (AD-7): the composite FK to ``matter_scope`` is RESTRICT.

The backfill seeds version 1 from any existing ``matter_scope.case_theory`` value (re-encrypted
under the new column's AAD), and is key-free on an empty store — so the CI
upgrade→downgrade→upgrade cycle runs without ``APX_ENCRYPTION_KEY``. Downgrade drops the table; the
retained ``matter_scope.case_theory`` column is untouched (data-preserving).

Revision ID: 0023_case_theory_version
Revises: 0022_deterministic_index
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from apx.adapters.store_postgres.backfill import backfill_case_theory_versions

revision = "0023_case_theory_version"
down_revision = "0022_deterministic_index"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "case_theory_version",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("tenant", sa.String(), nullable=False),
        sa.Column("matter", sa.String(), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=True),    # EncryptedText → ciphertext; NULL = withdrawal
        sa.Column("actor", sa.Text(), nullable=False),  # EncryptedText → ciphertext
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        # composite FK to the matter identity (AD-12); no ondelete (AD-7 RESTRICT)
        sa.ForeignKeyConstraint(
            ["tenant", "matter"], ["matter_scope.tenant", "matter_scope.matter"]),
        sa.PrimaryKeyConstraint("id"),
        # a per-matter monotonic version_no; the index also serves (tenant, matter) lookups
        sa.UniqueConstraint("tenant", "matter", "version_no", name="uq_case_theory_version"),
    )
    # seed version 1 from the existing single-value column (no-op + key-free on an empty store)
    backfill_case_theory_versions(op.get_bind())


def downgrade() -> None:
    op.drop_table("case_theory_version")
