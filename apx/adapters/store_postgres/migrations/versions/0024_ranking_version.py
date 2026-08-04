"""ranking_version + ranked_entry — the ranked order and the reproducible ranking version (Story
4.3, FR-39 / AD-23).

``ranking_version`` records the complete immutable identity of what produced one ranked order (AD-23)
— all plaintext structural metadata (readable in the interface & the content-free projection,
NFR-56), no PII or content. ``ranked_entry`` holds one row per *pièce*: its rank (NULL for the
UNSCORED set — out of the order, never ranked last, AD-19), its score OR rejection class (AD-36), its
near-duplicate family + representative flag. Both tables are APPEND-ONLY and never mutated after
creation (AD-37; asserted by ``ranking_version_is_append_only``). **No retained/discarded column** —
those sets are views, never a membership (AD-39). No cascade FK (AD-7).

No backfill: ranking did not exist before this migration, so there is nothing to seed. Downgrade
drops both tables (the child ``ranked_entry`` first). No re-index / no corpus mutation (NFR-56).

Revision ID: 0024_ranking_version
Revises: 0023_case_theory_version
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0024_ranking_version"
down_revision = "0023_case_theory_version"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ranking_version",
        sa.Column("id", sa.String(length=64), nullable=False),  # = version_id (AD-23)
        sa.Column("tenant", sa.String(), nullable=False),
        sa.Column("matter", sa.String(), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("basis", sa.String(), nullable=False),
        sa.Column("identity_json", sa.Text(), nullable=False),   # plaintext structural metadata
        sa.Column("case_theory_version_id", sa.String(length=64), nullable=True),
        sa.Column("stage3_share", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        # composite FK to the matter identity (AD-12); no ondelete (AD-7 RESTRICT)
        sa.ForeignKeyConstraint(
            ["tenant", "matter"], ["matter_scope.tenant", "matter_scope.matter"]),
        sa.PrimaryKeyConstraint("id"),
        # a per-matter monotonic version_no; the index also serves (tenant, matter) lookups
        sa.UniqueConstraint("tenant", "matter", "version_no", name="uq_ranking_version"),
    )
    op.create_table(
        "ranked_entry",
        sa.Column("id", sa.String(length=64), nullable=False),  # sha256(version_id \0 piece_id)
        sa.Column("ranking_version_id", sa.String(length=64), nullable=False),
        sa.Column("tenant", sa.String(), nullable=False),
        sa.Column("matter", sa.String(), nullable=False),
        sa.Column("piece_id", sa.String(length=64), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=True),         # NULL == the unscored set (AD-19)
        sa.Column("outcome", sa.String(), nullable=False),
        sa.Column("score", sa.Float(), nullable=True),          # never imputed (AD-19)
        sa.Column("band", sa.String(), nullable=True),
        sa.Column("label", sa.String(), nullable=True),
        sa.Column("rejection_class", sa.String(), nullable=True),  # AD-36
        sa.Column("failure_reason", sa.String(), nullable=True),   # redacted diagnostic (AD-19)
        sa.Column("family_id", sa.String(length=64), nullable=False),
        sa.Column("is_representative", sa.Boolean(), nullable=False),
        sa.Column("supersedes", sa.Boolean(), nullable=False),
        # no ondelete (AD-7 RESTRICT): a version is never hard-deleted out from under its rows
        sa.ForeignKeyConstraint(["ranking_version_id"], ["ranking_version.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ranking_version_id", "piece_id", name="uq_ranked_entry"),
    )
    op.create_index("ix_ranked_entry_version_id", "ranked_entry", ["ranking_version_id"])
    op.create_index(
        "ix_ranked_entry_version_rank", "ranked_entry", ["ranking_version_id", "rank"])


def downgrade() -> None:
    op.drop_index("ix_ranked_entry_version_rank", table_name="ranked_entry")
    op.drop_index("ix_ranked_entry_version_id", table_name="ranked_entry")
    op.drop_table("ranked_entry")   # the child first (FK to ranking_version)
    op.drop_table("ranking_version")
