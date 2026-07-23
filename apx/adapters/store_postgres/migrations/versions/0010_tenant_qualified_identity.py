"""slice A (tenant identity, story 1.4 review): tenant-qualify the matter/piece identity.

The Chinese wall requires a *matter* to belong to exactly one *tenant* (AD-12; the spine's
`TENANT ||--o{ MATTER` ownership, AD-43 chains per (tenant, matter)). The pre-review schema
made *matter* globally unique — `matter_scope` keyed by `matter` alone and a piece unique per
`(matter, content_hash)` — so two firms that both named a matter "dupont" collided: one
firm's ingest silently overwrote the other's matter/scope and (with a shared file) its piece.

This re-keys the constraints to include *tenant*: `matter_scope` PK `(tenant, matter)`, and a
piece unique per `(tenant, matter, content_hash)`. `piece_id` itself is computed in code
(`identity.py`) and now includes tenant; this migration only re-keys the constraints — it
does not recompute existing ids (a re-ingest under the new scheme is a distinct piece, which
is correct). Safe on existing rows: `matter` was unique, so `(tenant, matter)` is too.

Revision ID: 0010_tenant_qualified_identity
Revises: 0009_chunk_payload_schema
"""

from __future__ import annotations

from alembic import op

revision = "0010_tenant_qualified_identity"
down_revision = "0009_chunk_payload_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # matter_scope: primary key (matter) -> (tenant, matter)
    op.drop_constraint("matter_scope_pkey", "matter_scope", type_="primary")
    op.create_primary_key("matter_scope_pkey", "matter_scope", ["tenant", "matter"])
    # piece: unique (matter, content_hash) -> (tenant, matter, content_hash)
    op.drop_constraint("uq_piece_matter_content", "piece", type_="unique")
    op.create_unique_constraint(
        "uq_piece_tenant_matter_content", "piece", ["tenant", "matter", "content_hash"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_piece_tenant_matter_content", "piece", type_="unique")
    op.create_unique_constraint("uq_piece_matter_content", "piece", ["matter", "content_hash"])
    op.drop_constraint("matter_scope_pkey", "matter_scope", type_="primary")
    op.create_primary_key("matter_scope_pkey", "matter_scope", ["matter"])
