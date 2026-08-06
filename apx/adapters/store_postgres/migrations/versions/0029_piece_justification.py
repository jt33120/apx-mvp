"""piece_justification + justification_rejection — the named-evidence justification (Story 4.6,
FR-41/FR-18/FR-11).

Two NEW tables:

- ``piece_justification`` — the justification is the output of ONE ranking version's judgement, so
  it is **version-bound** (keyed by ``ranking_version_id`` + ``piece_id``). It carries the one-line
  ``sentence`` (a model summary, encrypted), the stated ``basis`` (named, plaintext), the named
  ``evidence`` extracts as an encrypted JSON blob (chunk id + quoted passage — the containment
  target), and an optional ``source_language``. No re-index, no corpus mutation (NFR-56).
- ``justification_rejection`` — rejecting the tool's assessment for a *pièce* is a HUMAN act,
  **version-INDEPENDENT** (keyed by the *pièce*), APPEND-ONLY with a per-*pièce* monotonic ``seq``
  (AD-49): reject / restore are new rows, never an overwrite (AD-7), so a rejection survives
  re-ranking and a restore reverses it without a delete.

NO backfill: a pre-4.6 *pièce* has no justification and no rejection. Downgrade drops both tables.

Revision ID: 0029_piece_justification
Revises: 0028_pin_entry
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0029_piece_justification"
down_revision = "0028_pin_entry"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "piece_justification",
        sa.Column("id", sa.String(length=64), nullable=False),  # sha256(version_id \0 piece_id)
        sa.Column("tenant", sa.String(), nullable=False),
        sa.Column("matter", sa.String(), nullable=False),
        sa.Column("ranking_version_id", sa.String(length=64), nullable=False),  # version-bound
        sa.Column("piece_id", sa.String(length=64), nullable=False),
        sa.Column("sentence", sa.Text(), nullable=False),        # EncryptedText → Text at rest
        sa.Column("basis_kind", sa.String(), nullable=False),    # case-theory | intrinsic
        sa.Column("case_theory_version_id", sa.String(length=64), nullable=True),  # ct path
        sa.Column("intrinsic_signals", sa.String(), nullable=False),  # comma-joined, "" otherwise
        sa.Column("evidence_json", sa.Text(), nullable=False),   # EncryptedText → Text at rest
        sa.Column("source_language", sa.String(), nullable=True),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        # the version this justification was derived against; no ondelete (AD-7 RESTRICT)
        sa.ForeignKeyConstraint(["ranking_version_id"], ["ranking_version.id"]),
        # composite FK to the matter identity (AD-12); no ondelete (AD-7 RESTRICT)
        sa.ForeignKeyConstraint(
            ["tenant", "matter"], ["matter_scope.tenant", "matter_scope.matter"]),
        sa.PrimaryKeyConstraint("id"),
        # one justification per pièce per version; a concurrent double-write collides here
        sa.UniqueConstraint(
            "tenant", "matter", "ranking_version_id", "piece_id", name="uq_piece_justification"),
    )
    op.create_index(
        "ix_piece_justification_version", "piece_justification",
        ["tenant", "matter", "ranking_version_id"])

    op.create_table(
        "justification_rejection",
        sa.Column("id", sa.String(length=64), nullable=False),   # sha256(tenant\0matter\0pid\0seq)
        sa.Column("tenant", sa.String(), nullable=False),
        sa.Column("matter", sa.String(), nullable=False),
        sa.Column("piece_id", sa.String(length=64), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),          # per-pièce monotonic (AD-49)
        sa.Column("action", sa.String(), nullable=False),        # rejected | restored
        sa.Column("reason", sa.Text(), nullable=True),           # EncryptedText → Text; optional
        sa.Column("set_by", sa.Text(), nullable=False),          # EncryptedText → Text at rest
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        # composite FK to the matter identity (AD-12); no ondelete (AD-7 RESTRICT)
        sa.ForeignKeyConstraint(
            ["tenant", "matter"], ["matter_scope.tenant", "matter_scope.matter"]),
        sa.PrimaryKeyConstraint("id"),
        # a per-pièce monotonic seq; a concurrent double-write collides here, never overwrites
        sa.UniqueConstraint(
            "tenant", "matter", "piece_id", "seq", name="uq_justification_rejection_seq"),
    )
    op.create_index(
        "ix_justification_rejection_piece", "justification_rejection",
        ["tenant", "matter", "piece_id"])


def downgrade() -> None:
    op.drop_index("ix_justification_rejection_piece", table_name="justification_rejection")
    op.drop_table("justification_rejection")
    op.drop_index("ix_piece_justification_version", table_name="piece_justification")
    op.drop_table("piece_justification")
