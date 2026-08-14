"""the validation act and the readable open ledger (Story 5.8, FR-45 / FR-44 / FR-24).

Two tables, and the first is a repair.

``piece_open`` — FR-45 turns on *whether the pièce was opened in the viewer before the act*, the
fact that distinguishes a *validation act* performed after reading from one performed from the
list. Story 3.5 has recorded every open faithfully since it shipped, as an *audit entry* whose
detail reads ``piece=<id>``. That detail is application-encrypted prose: answering *"did this lawyer
open this pièce"* would mean loading every ``retrieval``-class entry of the *matter*, decrypting
each, and string-parsing a fragment. **A record whose reading depends on parsing prose is not a
record** — the rule Story 5.7 established when the priced statement had the same shape. The audit
entry is unchanged and stays authoritative for the chain; this table is the readable half, written
in the same transaction.

**No backfill, and the reason is not laziness.** Pre-0036 opens exist only as encrypted prose. A
backfill would have to decrypt the whole *audit record* of every *matter* and re-derive a fact from
a format that was never a contract — and it would produce rows indistinguishable from ones this
ledger recorded itself. A *validation act* over a *pièce* opened before this migration therefore
records **not opened**, which is the honest answer from what is readable rather than a flattering
one reconstructed from prose. Stated here, in the store's docstring and in the story, so that
nobody later reads the gap as a bug and "fixes" it by manufacturing the record.

``validation_act`` — the ledger. Append-only, per-*pièce* monotonic ``seq``, the in-force state a
max-``seq`` view (the *pin* precedent, AD-7/AD-39): a withdrawal is an entry, never an erasure, so
both stay readable. ``opened_at`` is a **timestamp, not a boolean** — ``NULL`` is "she had not
opened it", a value is *when she did*, and a boolean would be equally true of an open six months
and three rankings before the act. ``batch_id``/``batch_size`` are FR-45's bulk markers, checked
here as a pair: a size with no identifier cannot be grouped, and an identifier with no size cannot
answer *"one gesture over how many"*.

The down-migration drops both tables. It cannot restore an acceptance it never held, and it
deliberately does not try.

Revision ID: 0036_validation_act
Revises: 0035_line_priced_statement
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0036_validation_act"
down_revision = "0035_line_priced_statement"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "piece_open",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("tenant", sa.String(), nullable=False),
        sa.Column("matter", sa.String(), nullable=False),
        sa.Column("piece_id", sa.String(length=64), nullable=False),
        # application-encrypted at rest (AD-31): the actor is PII, never a SQL predicate
        sa.Column("actor", sa.Text(), nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant", "matter"], ["matter_scope.tenant", "matter_scope.matter"]),
    )
    op.create_index(
        "ix_piece_open_piece", "piece_open", ["tenant", "matter", "piece_id", "at"])

    op.create_table(
        "validation_act",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("tenant", sa.String(), nullable=False),
        sa.Column("matter", sa.String(), nullable=False),
        sa.Column("piece_id", sa.String(length=64), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("ranking_version_id", sa.String(length=64), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("batch_id", sa.String(length=64), nullable=True),
        sa.Column("batch_size", sa.Integer(), nullable=True),
        sa.Column("accepted_side", sa.String(), nullable=True),
        sa.Column("accepted_band", sa.String(), nullable=True),
        sa.Column("accepted_confidence", sa.Float(), nullable=True),
        sa.Column("accepted_label", sa.String(), nullable=True),
        # application-encrypted at rest (AD-31): the actor is PII, never a SQL predicate
        sa.Column("actor", sa.Text(), nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant", "matter", "piece_id", "seq", name="uq_validation_act_seq"),
        sa.CheckConstraint(
            "action IN ('validated', 'withdrawn')", name="ck_validation_act_action"),
        sa.CheckConstraint(
            "(batch_id IS NULL) = (batch_size IS NULL)", name="ck_validation_act_batch_paired"),
        sa.ForeignKeyConstraint(
            ["tenant", "matter"], ["matter_scope.tenant", "matter_scope.matter"]),
    )
    op.create_index(
        "ix_validation_act_piece", "validation_act", ["tenant", "matter", "piece_id", "seq"])
    op.create_index(
        "ix_validation_act_batch", "validation_act", ["tenant", "matter", "batch_id"])


def downgrade() -> None:
    op.drop_index("ix_validation_act_batch", table_name="validation_act")
    op.drop_index("ix_validation_act_piece", table_name="validation_act")
    op.drop_table("validation_act")
    op.drop_index("ix_piece_open_piece", table_name="piece_open")
    op.drop_table("piece_open")
