"""ranked_entry.confidence + confidence_signals — the derived per-pièce confidence (Story 4.4,
FR-42 / AD-19).

Two nullable columns on ``ranked_entry``: ``confidence`` (a derived certainty in [0,1]) and
``confidence_signals`` (the comma-joined observable signals it came from). **NULL == not derived**
(AD-19 — never a zero or a default): an UNSCORED pièce, a REJECTED near-duplicate member, or an
intrinsic pièce with no observable has no confidence. Plaintext structural metadata (a float + a
categorical signal list), no content. NO backfill: a pre-4.4 ranking had no derivation, so its
confidence is genuinely unknown = NULL (honest, AD-19). Downgrade drops both columns.

Revision ID: 0025_ranked_entry_confidence
Revises: 0024_ranking_version
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0025_ranked_entry_confidence"
down_revision = "0024_ranking_version"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("ranked_entry", sa.Column("confidence", sa.Float(), nullable=True))
    op.add_column("ranked_entry", sa.Column("confidence_signals", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("ranked_entry", "confidence_signals")
    op.drop_column("ranked_entry", "confidence")
