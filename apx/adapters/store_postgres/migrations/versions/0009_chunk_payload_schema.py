"""slice A (frozen schema, story 1.3): the chunk payload table + piece.text_identity.

The ``chunk`` payload schema (AD-9) is the increment's one irreversible decision. Its
columns are exactly the enumerated set — no ``rbac_scope``/``scope`` column (scope is a
write-time check resolved from ``matter_scope`` at query time, AD-13/AD-40) and no
``custodian`` column (custodianship is a set on the *pièce*, AD-9). The piece FK carries
no ``ON DELETE`` action at all (AD-7): a *pièce* is retired, never hard-deleted out from
under its chunks. The embedding trio — the ``halfvec`` vector and its
``model_id``/``model_version`` — is added by the embedder story (2.8).

This also completes AD-10 on the *pièce*: the full extracted text gets its own identity
(``text_identity``) beside its version, backfilled for existing rows with the exact hash
the writer computes (sha256 of the UTF-8 text) so a re-write is a no-op.

NOTE (environment reconciliation): ``piece`` and ``matter_scope`` predate this migration
(the pre-BMAD ad-hoc build's 0001/0002). Story 1.3's schema work against the real tree is
therefore the ``chunk`` table plus the missing ``text_identity`` column — delivering
AC7's substance (a real migration creating the frozen chunk schema, up and down) without
re-creating tables that already exist. Recorded per the 1.1 deviation convention.

Revision ID: 0009_chunk_payload_schema
Revises: 0008_user_is_admin
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0009_chunk_payload_schema"
down_revision = "0008_user_is_admin"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # AD-10: the full text's own identity, beside its version. Add nullable, backfill
    # existing rows with the same hash the writer computes, then enforce NOT NULL.
    op.add_column("piece", sa.Column("text_identity", sa.String(length=64), nullable=True))
    op.execute(
        "UPDATE piece SET text_identity = "
        "encode(sha256(convert_to(full_text, 'UTF8')), 'hex') "
        "WHERE text_identity IS NULL"
    )
    op.alter_column("piece", "text_identity", nullable=False)

    # AD-9: the frozen chunk payload schema. Enumerated columns only; the FK to piece
    # carries no ON DELETE (AD-7); (piece_id, position, chunking_config_version) is the
    # natural key behind the deterministic chunk_id.
    op.create_table(
        "chunk",
        sa.Column("chunk_id", sa.String(length=64), primary_key=True),
        sa.Column("piece_id", sa.String(length=64), nullable=False),
        sa.Column("tenant", sa.String(), nullable=False),
        sa.Column("matter", sa.String(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("full_text_version", sa.String(), nullable=False),
        sa.Column("chunking_config_version", sa.String(), nullable=False),
        sa.Column("schema_version", sa.String(), nullable=False),
        sa.Column("external_ref", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["piece_id"], ["piece.id"], name="fk_chunk_piece"),
        sa.UniqueConstraint(
            "piece_id",
            "position",
            "chunking_config_version",
            name="uq_chunk_piece_position_cfg",
        ),
    )
    op.create_index("ix_chunk_piece_id", "chunk", ["piece_id"])


def downgrade() -> None:
    op.drop_index("ix_chunk_piece_id", table_name="chunk")
    op.drop_table("chunk")
    op.drop_column("piece", "text_identity")
