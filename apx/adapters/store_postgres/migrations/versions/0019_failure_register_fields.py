"""failure register fields — custodian, cardinality, undetermined matter (Story 2.6, FR-5).

The failure register grows the FR-5 fields it was missing: `custodian` (PII, encrypted, where
known) and `cardinality` (`one` | `unknown` — AD-38: an unopened container stands for an unknown
number of pièces and is never summed). `matter` becomes nullable so an entry that could not be
attributed to a matter (undetermined) can exist and be shown only to the tenant-wide admin (FR-49);
a NULL matter has no `matter_scope` row, so the scope pre-filter excludes it from every ordinary
read by construction. No cascade FK (AD-7). Reversible.

Revision ID: 0019_failure_register_fields
Revises: 0018_piece_provenance_and_custodian_sets
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from apx.adapters.store_postgres.backfill import backfill_failure_cardinality

revision = "0019_failure_register_fields"
down_revision = "0018_piece_provenance_and_custodian_sets"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("failure", sa.Column("custodian", sa.Text(), nullable=True))  # EncryptedText
    # add cardinality nullable, backfill (AD-38), then assert NOT NULL — matches the model (no
    # server_default). The backfill is a tested helper (backfill.backfill_failure_cardinality).
    op.add_column("failure", sa.Column("cardinality", sa.String(), nullable=True))
    backfill_failure_cardinality(op.get_bind())
    op.alter_column("failure", "cardinality", nullable=False)
    # an entry may now be unattributed to a matter (undetermined) — admin-only visibility (FR-49)
    op.alter_column("failure", "matter", existing_type=sa.String(), nullable=True)


def downgrade() -> None:
    # NULL (undetermined) matters cannot go back to NOT NULL as-is; a downgrade past 2.6 with
    # undetermined entries would need to re-home them first. Vacuous on an empty/attributed store.
    op.alter_column("failure", "matter", existing_type=sa.String(), nullable=False)
    op.drop_column("failure", "cardinality")
    op.drop_column("failure", "custodian")
