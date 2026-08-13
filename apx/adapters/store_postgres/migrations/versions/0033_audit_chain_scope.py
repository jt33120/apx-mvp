"""audit chains per (tenant, matter) plus one tenant chain, with a locked head row (Story 5.5).

AD-43 decided both halves of this before any of it was built, and neither was implemented: the
chain's **scope**, and the **authority** the sequence number comes from.

**The scope.** FR-53 requires a gap, a reordering or a truncation to be detectable by a reader
holding *only the export*, and an export is per *matter* (FR-26). Under one chain per *tenant* the
export of a *matter* has a hole wherever a sibling *matter* wrote an entry in between, and its
links cannot be recomputed at all — each runs through an entry the reader is not entitled to see.
The *bâtonnier* would find tampering on an untampered record, every time.

**The authority.** ``audit_chain_head`` is the row the next number is allocated from, under
``SELECT … FOR UPDATE`` inside the acting transaction. AD-43 forbids a sequence generator: a burned
``nextval`` after an ordinary worker crash manufactures a permanent gap that reports as tampering
forever and that AD-22 forbids anyone to repair.

**Nothing already written is re-chained, and the head journal of Story 1.11 is why.** It holds the
old chain values on a volume the dump does not cover; re-chaining would leave every journalled head
unmatched by the live record — the exact signature of forgery, produced by our own migration. So
the existing entries stay where they are, at their sequence numbers, with their chain values, on
the *tenant* chain (``chain_scope = ''``) whatever *matter* they name. They keep
``content_version = 1`` and no versions: they were written before either was recorded, and filling
them in with today's values would give them a provenance they do not have (AD-19). Each *matter*
chain therefore starts empty and is anchored, at its first entry, to the *tenant* chain's head at
that moment.

Revision ID: 0033_audit_chain_scope
Revises: 0032_sampling_estimator
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0033_audit_chain_scope"
down_revision = "0032_sampling_estimator"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. the chain each entry belongs to. Existing entries default to '' — the tenant chain —
    #    which is where they were in fact written, one chain for the whole tenant.
    op.add_column(
        "audit_record",
        sa.Column("chain_scope", sa.String(), nullable=False, server_default=""))
    # 2. the recipe the chain value was taken over, and the two versions FR-24 wants recorded.
    op.add_column(
        "audit_record",
        sa.Column("content_version", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("audit_record", sa.Column("app_version", sa.String(length=32), nullable=True))
    op.add_column("audit_record", sa.Column("schema_version", sa.String(length=32), nullable=True))

    # 3. (tenant, seq) is no longer unique — two chains of one tenant each hold a seq 1. The
    #    uniqueness that matters is per chain, and it is what makes a gap impossible.
    with op.batch_alter_table("audit_record") as batch:
        batch.drop_constraint("uq_audit_tenant_seq", type_="unique")
        batch.create_unique_constraint(
            "uq_audit_chain_seq", ["tenant", "chain_scope", "seq"])

    # 4. the sequence authority.
    op.create_table(
        "audit_chain_head",
        sa.Column("tenant", sa.String(), primary_key=True),
        sa.Column("chain_scope", sa.String(), primary_key=True),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("chain", sa.String(length=64), nullable=False),
        sa.Column("anchor", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    # 4b. the truncation marker now describes EVERY chain a restore rolled back, and the TOTAL
    #     number of entries lost. With several chains per tenant, one (journal_seq, live_seq) pair
    #     can only describe one of them, and a reader shown the smallest loss is being flattered.
    op.add_column("truncation_marker", sa.Column("chains", sa.Text(), nullable=True))
    op.add_column(
        "truncation_marker",
        sa.Column("entries_lost", sa.Integer(), nullable=False, server_default="0"))

    # 5. seed one head per tenant at the tenant chain's CURRENT head, so the first entry written
    #    after this migration continues the existing chain rather than restarting at 1 and
    #    colliding. The anchor is '' — the tenant chain is the root, and that is where every
    #    pre-5.5 record in fact started. A tenant whose record is empty gets no row; the chain
    #    opens on first write.
    op.execute(sa.text(
        "INSERT INTO audit_chain_head "
        "(tenant, chain_scope, seq, chain, anchor, opened_at, updated_at) "
        "SELECT a.tenant, '', a.seq, a.chain, '', a.timestamp, a.timestamp FROM audit_record a "
        "WHERE a.chain_scope = '' AND a.seq = ("
        "  SELECT MAX(b.seq) FROM audit_record b "
        "  WHERE b.tenant = a.tenant AND b.chain_scope = '')"
    ))


def downgrade() -> None:
    # Reversible as DDL. It does NOT put the record back: entries written on a matter chain would
    # collide on (tenant, seq) with the tenant chain's own, so the downgrade refuses rather than
    # dropping or renumbering anything — a downgrade that silently destroys evidence is worse than
    # one that fails (FR-21, AD-22).
    conn = op.get_bind()
    matter_chained = conn.execute(sa.text(
        "SELECT COUNT(*) FROM audit_record WHERE chain_scope <> ''")).scalar() or 0
    if matter_chained:
        raise RuntimeError(
            f"refusing to downgrade: {matter_chained} audit entries live on a matter chain and "
            "would collide on (tenant, seq); their sequence numbers cannot be undone without "
            "rewriting the record (AD-22)")
    op.drop_column("truncation_marker", "entries_lost")
    op.drop_column("truncation_marker", "chains")
    op.drop_table("audit_chain_head")
    with op.batch_alter_table("audit_record") as batch:
        batch.drop_constraint("uq_audit_chain_seq", type_="unique")
        batch.create_unique_constraint("uq_audit_tenant_seq", ["tenant", "seq"])
    op.drop_column("audit_record", "schema_version")
    op.drop_column("audit_record", "app_version")
    op.drop_column("audit_record", "content_version")
    op.drop_column("audit_record", "chain_scope")
