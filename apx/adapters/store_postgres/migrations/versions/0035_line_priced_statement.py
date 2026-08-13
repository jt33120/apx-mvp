"""the priced statement moves onto the line-placement ledger (Story 5.7, FR-24/FR-26/FR-19).

FR-24 requires the record to carry *"every position of **the line** with author and priced
statement"*, and FR-26 requires the *matter* export to carry the position history. Story 4.9 wrote
the priced statement into the ``line_moved`` **audit entry's detail** and nowhere else, which was
right for the chain and wrong for the ledger: the export would have had to recover it by parsing a
formatted string out of an encrypted detail column, matching entries to placements by a ``seq=``
substring. A record whose reading depends on parsing prose is not a record.

So the placement row carries it too. Both copies are written in the same transaction and neither is
ever rewritten (the ledger is append-only, the chain more so), so they cannot diverge — the same
argument Story 5.6 made for the register override's reason.

**Nullable, and it stays nullable.** The FIRST placement of a line is not a move and has no price:
the tool drew the cut and committed to it (Story 4.8). A NOT NULL column would force an empty
string there, and an empty priced statement is indistinguishable from a move whose price nobody
showed. NULL says "this was not a move", which is true and is different.

No backfill. Placements written before this migration keep their price on the chain only; the
export states that for those rows the statement lives in the audit entry, rather than inventing a
value it does not have (AD-19).

Revision ID: 0035_line_priced_statement
Revises: 0034_register_override
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0035_line_priced_statement"
down_revision = "0034_register_override"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # application-encrypted at rest (AD-31): a composed sentence a human was shown before
    # committing. It carries counts and a projected prevalence, not client content — but it is
    # free text authored for one matter, and the ledger's other free text (the pin reason) is
    # encrypted for the same reason.
    op.add_column(
        "line_placement", sa.Column("priced_statement", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("line_placement", "priced_statement")
