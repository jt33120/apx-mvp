"""sampling_run — the estimator's frozen inputs and its recorded method (Story 5.2, OQ-4).

Two NULLABLE columns on the existing ``sampling_run`` table. Pure DDL: no backfill, no data
migration, no re-index, no corpus mutation (NFR-56).

``population_family_sizes`` is the size of every family in the frozen population, sorted descending
and comma-joined — including the families nobody drew. OQ-4's first hard input needs it: a bound
over near-duplicate FAMILIES converts to a *pièce* figure only as a worst case (if at most D
families are relevant, at most the D LARGEST are), and that worst case must be computed over the
population as it was **at draw time**, not as the matter looks now.

``estimator_method`` names the statistic that produced the recorded numbers (FR-23: changing the
method produces a *new* bound rather than silently restating the old one).

**Both are nullable, and deliberately not back-filled.** A Story-5.1 run genuinely has no frozen
size list and was closed before the method was recorded. Filling them with today's values would
give those rows a provenance they do not have — the same failure as a stale artefact reading fresh,
which is the defect this build keeps meeting (AD-19, AD-23). A run without a size list reports its
*pièce* worst case as **not computable**.

Revision ID: 0032_sampling_estimator
Revises: 0031_sampling_run
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0032_sampling_estimator"
down_revision = "0031_sampling_run"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sampling_run", sa.Column("population_family_sizes", sa.Text(), nullable=True))
    op.add_column(
        "sampling_run", sa.Column("estimator_method", sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column("sampling_run", "estimator_method")
    op.drop_column("sampling_run", "population_family_sizes")
