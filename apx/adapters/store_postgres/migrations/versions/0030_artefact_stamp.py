"""artefact_stamp — the freshness stamp of every derived artefact (Story 4.13, FR-58/AD-23/AD-40).

A NEW append-only ledger: one row per produced derived artefact (a ranking version, a line
placement, a recorded confidence bound), holding the observable state of the eight enumerated
staleness inputs at the moment it was produced. Staleness is then a COMPARISON against the current
observables, never a stored flag anyone has to remember to set.

Written inside the producing artefact's own transaction (AD-22) by its one owning use case (AD-37).
NO backfill: an artefact produced before this story has no stamp, and the surface says its inputs
cannot be verified — never that they are unchanged (an absence of evidence is not evidence of
freshness). No re-index, no corpus mutation (NFR-56). Downgrade drops the table.

Revision ID: 0030_artefact_stamp
Revises: 0029_piece_justification
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0030_artefact_stamp"
down_revision = "0029_piece_justification"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "artefact_stamp",
        sa.Column("id", sa.String(length=64), nullable=False),   # sha256(tenant\0matter\0kind\0aid)
        sa.Column("tenant", sa.String(), nullable=False),
        sa.Column("matter", sa.String(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),          # ranking | line | bound
        sa.Column("artefact_id", sa.String(length=64), nullable=False),
        # the canonical JSON of the eight observables — PLAINTEXT structural metadata (NFR-56),
        # like ranking_version.identity_json: counts, seqs, a scope name and two hashes. No PII,
        # no content.
        sa.Column("stamp_json", sa.Text(), nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        # composite FK to the matter identity (AD-12); no ondelete (AD-7 RESTRICT)
        sa.ForeignKeyConstraint(
            ["tenant", "matter"], ["matter_scope.tenant", "matter_scope.matter"]),
        sa.PrimaryKeyConstraint("id"),
        # one stamp per artefact; a concurrent double-write collides here and fails loudly
        # (AD-37 conditional commit), never a silent overwrite of the recorded inputs.
        sa.UniqueConstraint("tenant", "matter", "kind", "artefact_id", name="uq_artefact_stamp"),
    )
    op.create_index("ix_artefact_stamp_matter", "artefact_stamp", ["tenant", "matter"])


def downgrade() -> None:
    op.drop_index("ix_artefact_stamp_matter", table_name="artefact_stamp")
    op.drop_table("artefact_stamp")
