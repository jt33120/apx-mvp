"""the discontinuity marker generalises, and an unrecorded head stops being a memory (Story 5.9,
FR-53 / FR-52 / AD-35).

Two changes, and both exist because a condition that must survive was being held somewhere it
could not.

``truncation_marker.kind`` / ``.forks`` — the marker was built for one finding: the live head fell
BEHIND the outside witness, so the record ends earlier than it did. Story 5.9 adds the second, which
no comparison of lengths can see: the two hold **different values at a sequence they both hold**, so
the record was rewritten and re-chained. That is a **fork**, not a truncation, and a *bâtonnier* told
one when it was the other is being told the wrong thing. It gets its own kind rather than its own
table, because AD-35 gives a discontinuity exactly one way out — an audited *override* with a reason
— and two tables would be two ways out, one of which somebody would eventually forget to name on the
export. Existing rows are ``truncated``: every marker written before this migration was one.

``journal_gap`` — a head the journal could not record means a later truncation to that point is
undetectable. That alarm lived in ``SqlStore.journal_degraded``, an in-memory flag on one process:
it cleared on the next deploy, could never be raised by the import worker (which had no journal at
all), and was therefore a **silent repair of exactly the condition AD-35 forbids repairing**. Here it
is a row: which chain, how far it had run, the value it carried, and when the write failed — the
material a later reconciliation needs, not merely a boolean saying something once went wrong.

The down-migration drops both. It cannot un-know a fork and does not pretend to.

Revision ID: 0037_chain_continuity
Revises: 0036_validation_act
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0037_chain_continuity"
down_revision = "0036_validation_act"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "truncation_marker",
        sa.Column("kind", sa.String(), nullable=False, server_default="truncated"))
    op.add_column("truncation_marker", sa.Column("forks", sa.Text(), nullable=True))

    op.create_table(
        "journal_gap",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("tenant", sa.String(), nullable=False),
        # the JOURNAL scope (the bare tenant for the tenant chain, tenant␟matter for a matter
        # chain) — the same key the journal itself uses, so the two can be compared without a
        # translation step that could aim a reconciliation at the wrong chain
        sa.Column("scope", sa.String(), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("chain", sa.String(length=64), nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        # the write failure, verbatim: an operator alarm, never client content
        sa.Column("detail", sa.Text(), nullable=True),
    )
    op.create_index("ix_journal_gap_tenant", "journal_gap", ["tenant", "at"])


def downgrade() -> None:
    op.drop_index("ix_journal_gap_tenant", table_name="journal_gap")
    op.drop_table("journal_gap")
    op.drop_column("truncation_marker", "forks")
    op.drop_column("truncation_marker", "kind")
