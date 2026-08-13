"""the failure-register override ledger (Story 5.6, FR-25 / FR-5 / AD-37).

AD-37's ownership table has always named a ``failure register entry: open → overridden``
transition owned by "the *override* use case". There was no override use case, and
``resolution_state`` was documented as ``open|resolved``. FR-5 is explicit that an entry leaves
``open`` **only** by successful *ingestion* or by "an explicit user action recorded in the *audit
record* with a reason (an *override* per FR-25)" — so until now the only exit required the document
to become readable, and an entry for a document that never will be stayed ``open`` forever,
permanently inflating the "not indexed" count the home screen shows.

This adds the ledger, not the state: ``resolution_state`` is a plain string column and needs no
DDL to accept a third value. What needs a table is the **reason**, and it does not go on
``failure``. That row is mutable — every retry refreshes its ``error_class``, ``cardinality`` and
``detail`` — so a reason parked there could be edited afterwards while the copy chained into the
*audit record* stayed as written. Here nothing is updated. The row is the act.

No backfill: every existing entry is ``open`` or ``resolved``, and neither was ever an override.
The down-migration drops the table and nothing else; it cannot restore an overridden entry to
``open``, and it deliberately does not try — inventing a state transition inside a schema rollback
is exactly the silent repair AD-35 and FR-53 forbid.

Revision ID: 0034_register_override
Revises: 0033_audit_chain_scope
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0034_register_override"
down_revision = "0033_audit_chain_scope"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "register_override",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("tenant", sa.String(), nullable=False),
        sa.Column("entry_id", sa.String(length=64), nullable=False),
        # application-encrypted at rest (AD-31): the actor is PII, the reason is content
        sa.Column("actor", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_register_override_entry", "register_override", ["tenant", "entry_id"])


def downgrade() -> None:
    op.drop_index("ix_register_override_entry", table_name="register_override")
    op.drop_table("register_override")
