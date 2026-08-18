"""ranking_job — the application-owned ledger for the queued ranking act (AD-6/AD-17, story 7.6).

AD-6 names ranking by name as a queued job: the HTTP layer validates, authorises, enqueues and
returns, and the cascade — one model call per uncertain *pièce* — runs in the worker. Until this
migration the product had no ledger to enqueue against, so the act had no route at all and Epic 5's
surfaces answered *« pas de classement, pas de ligne »* over a precondition nobody could create.

Deliberately NOT a copy of ``import_job``:

* no ``spool_path`` / ``owns_spool`` / ``submitted`` / ``provisional`` — an import *is* a folder of
  units and a ranking is one monolithic pass with no checkpoint. A placeholder path would grow a
  guard that either never fires (dead code reading as a safety net) or fires on nothing real.
* a terminal ``failed`` state carrying a French reason. ``import_job``'s states are
  ``enumerating|running|done`` — it cannot express failure, and the upload route therefore answered
  503 over a permanent cause. This ledger can say what happened.
* the open-job index is the NEGATIVE form, ``state NOT IN ('done','failed')``, where
  ``uq_import_job_open`` is ``state != 'done'``. A failed job is terminal; under the
  import's form it would hold the *matter*'s re-rank shut for ever, silently.
* ``version_no`` is NULL until completion. It is minted inside ``record_ranking``'s transaction as
  ``max+1`` under a unique constraint, so a number written at enqueue would be a *prediction* — and
  two jobs would both predict n+1, leaving one permanently wrong on a row a status panel reads.

``actor`` is a person's display name → encrypted at rest (AD-31), as on ``import_job.actor``.
``detail`` is encrypted too: it is *written* as a composed French sentence, but one of its
branches interpolates an exception's own message, and an exception raised inside the cascade
can name a pièce. A column content-bearing on one branch is a content-bearing column.

Revision ID: 0038_ranking_job_ledger
Revises: 0037_chain_continuity
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0038_ranking_job_ledger"
down_revision = "0037_chain_continuity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ranking_job",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("tenant", sa.String(), nullable=False),
        sa.Column("matter", sa.String(), nullable=False),
        # the wall the ranking runs under: the worker is a different process from the request, and
        # a matter has exactly one wall (MatterScope). Persisted, never re-derived (AD-13).
        sa.Column("scope", sa.String(), nullable=False),
        sa.Column("actor", sa.String(), nullable=False),  # ciphertext (AD-31)
        sa.Column("state", sa.String(), nullable=False),  # queued|running|done|failed
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=True),
        sa.Column("detail", sa.Text(), nullable=True),  # ciphertext (AD-31)
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_ranking_job_open", "ranking_job", ["tenant", "matter"], unique=True,
        sqlite_where=sa.text("state NOT IN ('done','failed')"),
        postgresql_where=sa.text("state NOT IN ('done','failed')"))


def downgrade() -> None:
    op.drop_index("uq_ranking_job_open", table_name="ranking_job")
    op.drop_table("ranking_job")
