"""the chunk embedding trio — halfvec vector + model_id/model_version + the HNSW index (Story 2.8).

The ``chunk`` schema reserved the embedding trio for "the embedder story (2.8)"; this adds it: the
pgvector extension, ``model_id``/``model_version`` (so a mixed-provenance corpus is DETECTABLE,
AD-11), and a 1024-dim ``halfvec`` ``vector`` with an **HNSW** cosine index. All NOT NULL — a chunk
exists only once embedded (Story 2.8: embedding is a precondition of corpus admission), and the
``chunk`` table is empty before this story (the single writer was orphaned), so NOT NULL is safe.

Creating an index is not destroying one — the FR-10 "index never self-deletes" guard is about the
RUNTIME path, and alembic is exempt from it. Reversible: the downgrade drops the index + columns.

Revision ID: 0021_chunk_embedding
Revises: 0020_inventory_denominator
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import HALFVEC

revision = "0021_chunk_embedding"
down_revision = "0020_inventory_denominator"
branch_labels = None
depends_on = None

_DIM = 1024  # AD-11: the halfvec width; matches models.EMBEDDING_DIM and the Embedder port


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")  # pgvector, for the halfvec type (AD-11)
    op.add_column("chunk", sa.Column("model_id", sa.String(), nullable=False))
    op.add_column("chunk", sa.Column("model_version", sa.String(), nullable=False))
    op.add_column("chunk", sa.Column("vector", HALFVEC(_DIM), nullable=False))
    # HNSW cosine index for approximate nearest-neighbour retrieval (the searchable surface).
    op.create_index(
        "ix_chunk_vector_hnsw", "chunk", ["vector"],
        postgresql_using="hnsw", postgresql_ops={"vector": "halfvec_cosine_ops"})


def downgrade() -> None:
    op.drop_index("ix_chunk_vector_hnsw", table_name="chunk")
    op.drop_column("chunk", "vector")
    op.drop_column("chunk", "model_version")
    op.drop_column("chunk", "model_id")
