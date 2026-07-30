"""the deterministic search index — piece.full_text_normalized (Story 3.2, AD-21).

The deterministic exhaustive search runs a plain ``LIKE`` over ``full_text_normalized``: the
``normalize()`` (fr-fold-v1) rule applied to the full text at write time, so the corpus is folded the
SAME way the query is (one implementation — a divergence cannot cause a false absence). This adds the
column and backfills it from the stored ``full_text`` using that rule, then makes it NOT NULL.

Reversible: the downgrade drops the column. Postgres-only, like every migration in this tree. Same
AD-31 exemption as ``full_text`` — a searchable index cannot be application-encrypted.

Revision ID: 0022_deterministic_index
Revises: 0021_chunk_embedding
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from apx.core.domain.normalization import normalize

revision = "0022_deterministic_index"
down_revision = "0021_chunk_embedding"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("piece", sa.Column("full_text_normalized", sa.Text(), nullable=True))
    bind = op.get_bind()
    piece = sa.table("piece", sa.column("id", sa.String), sa.column("full_text", sa.Text),
                     sa.column("full_text_normalized", sa.Text))
    for row in bind.execute(sa.select(piece.c.id, piece.c.full_text)):
        bind.execute(
            piece.update().where(piece.c.id == row.id).values(full_text_normalized=normalize(row.full_text))
        )
    op.alter_column("piece", "full_text_normalized", nullable=False)


def downgrade() -> None:
    op.drop_column("piece", "full_text_normalized")
