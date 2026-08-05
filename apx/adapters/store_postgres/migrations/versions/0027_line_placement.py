"""line_placement — the tool draws the line and commits (Story 4.8, FR-17).

A NEW append-only, version-bound ledger: one row per line placement (a system recommendation, later
a human move or reversal), keyed by ``ranking_version_id`` with a per-version monotonic ``seq``
(AD-49). The CURRENT line is a VIEW over it (the max-seq row, or none when unplaced). The line is
stored by the IDENTITY of the last retained pièce (``last_retained_piece_id``), never a bare integer
position — so an import that adds pièces cannot silently move it (FR-17). NO backfill: a pre-4.8
ranking has no line until one is placed — honest (AD-19). No re-index, no corpus mutation (NFR-56).
Downgrade drops the table.

Revision ID: 0027_line_placement
Revises: 0026_taxonomy_label_entry
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0027_line_placement"
down_revision = "0026_taxonomy_label_entry"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "line_placement",
        sa.Column("id", sa.String(length=64), nullable=False),      # sha256(version_id\0seq)
        sa.Column("tenant", sa.String(), nullable=False),
        sa.Column("matter", sa.String(), nullable=False),
        sa.Column("ranking_version_id", sa.String(length=64), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),             # per-version monotonic (AD-49)
        # THE LINE'S IDENTITY — the last retained pièce, never a bare integer position (FR-17)
        sa.Column("last_retained_piece_id", sa.String(length=64), nullable=False),
        sa.Column("basis", sa.String(), nullable=False),            # case-theory:<id> | intrinsic:..
        sa.Column("placed_by", sa.Text(), nullable=False),          # EncryptedText → Text at rest
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        # no ondelete on the ranking-version FK (AD-7 RESTRICT): a version is retired, never deleted
        sa.ForeignKeyConstraint(["ranking_version_id"], ["ranking_version.id"]),
        # composite FK to the matter identity (AD-12); no ondelete (AD-7 RESTRICT)
        sa.ForeignKeyConstraint(
            ["tenant", "matter"], ["matter_scope.tenant", "matter_scope.matter"]),
        sa.PrimaryKeyConstraint("id"),
        # a per-version monotonic seq; a concurrent double-write collides here, never overwrites
        sa.UniqueConstraint("ranking_version_id", "seq", name="uq_line_placement_seq"),
    )
    op.create_index(
        "ix_line_placement_version", "line_placement", ["tenant", "matter", "ranking_version_id"])


def downgrade() -> None:
    op.drop_index("ix_line_placement_version", table_name="line_placement")
    op.drop_table("line_placement")
