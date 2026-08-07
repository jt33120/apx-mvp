"""sampling_run — the frozen random draw from the discarded set (Story 5.1, FR-22).

Three NEW tables. ``sampling_run`` holds the freeze: the *ranking version*, the position of **the
line** by the identity of the last retained *pièce*, the pin-ledger position, the *RBAC scope* at
draw time. ``sampling_run_item`` holds the explicit identifier list — FR-22's *"a seed alone is
insufficient"* made structural. ``sampling_verdict`` is the append-only verdict ledger (a
correction is a new row).

The population these tables are drawn over is the Epic-4 **derived** discarded set, not the
Story-2.x label pile (planning decision A1). Nothing here stores an ``invalidated`` flag:
invalidation is the comparison of the run's ``artefact_stamp`` (kind ``sampling_run``) against the
current observables — Story 4.13's machinery.

NO backfill and NO data migration: the legacy ``recall_review`` rows stay exactly where they are,
readable forever with their bounds (AD-7 — the legacy pair is *superseded*, never deleted). No
re-index, no corpus mutation (NFR-56). Downgrade drops the three tables.

Revision ID: 0031_sampling_run
Revises: 0030_artefact_stamp
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0031_sampling_run"
down_revision = "0030_artefact_stamp"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sampling_run",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("tenant", sa.String(), nullable=False),
        sa.Column("matter", sa.String(), nullable=False),
        # ── the freeze (FR-22) — every one NOT NULL, asserted by sampling-run-freezes-identifiers
        sa.Column("ranking_version_id", sa.String(length=64), nullable=False),
        sa.Column("ranking_version_no", sa.Integer(), nullable=False),
        # the position of THE LINE, by the identity of the last retained pièce (FR-17) — never a
        # bare integer, so an import that adds pièces cannot silently move what the run recorded.
        sa.Column("last_retained_piece_id", sa.String(length=64), nullable=False),
        sa.Column("pin_ledger_seq", sa.Integer(), nullable=False),
        # a scope NAME (a Chinese-wall label), also a SQL predicate elsewhere → plaintext (NFR-56)
        sa.Column("scope", sa.String(), nullable=False),
        sa.Column("seed", sa.Integer(), nullable=False),
        # ── the draw ────────────────────────────────────────────────────────────────────────────
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("population_families", sa.Integer(), nullable=False),
        sa.Column("population_pieces", sa.Integer(), nullable=False),
        sa.Column("sample_size", sa.Integer(), nullable=False),
        sa.Column("is_census", sa.Boolean(), nullable=False),
        # ── lifecycle ───────────────────────────────────────────────────────────────────────────
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("started_by", sa.Text(), nullable=False),      # PII → application-encrypted
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_by", sa.Text(), nullable=True),        # PII → application-encrypted
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        # ── the result, written only at completion ──────────────────────────────────────────────
        sa.Column("relevant_found", sa.Integer(), nullable=True),
        sa.Column("count_upper", sa.Integer(), nullable=True),
        sa.Column("prevalence_upper", sa.Float(), nullable=True),
        # composite FK to the matter identity (AD-12); no ondelete (AD-7 RESTRICT)
        sa.ForeignKeyConstraint(
            ["tenant", "matter"], ["matter_scope.tenant", "matter_scope.matter"]),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "status in ('open', 'completed', 'abandoned')", name="ck_sampling_run_status"),
    )
    op.create_index(
        "ix_sampling_run_matter", "sampling_run", ["tenant", "matter", "started_at"])

    op.create_table(
        "sampling_run_item",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("run_id", sa.String(length=32), nullable=False),
        sa.Column("draw_index", sa.Integer(), nullable=False),
        sa.Column("family_id", sa.String(length=64), nullable=False),
        sa.Column("proxy_piece_id", sa.String(length=64), nullable=False),
        # newline-joined pièce ids — FR-22's explicit identifier list. Identity hashes, so
        # plaintext: no content, no PII (NFR-56).
        sa.Column("member_piece_ids", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["sampling_run.id"]),  # no ondelete (AD-7)
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "family_id", name="uq_sampling_run_item"),
    )
    op.create_index(
        "ix_sampling_run_item_run", "sampling_run_item", ["run_id", "draw_index"])

    op.create_table(
        "sampling_verdict",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("run_id", sa.String(length=32), nullable=False),
        sa.Column("family_id", sa.String(length=64), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),  # monotonic per (run, family)
        sa.Column("relevant", sa.Boolean(), nullable=False),
        sa.Column("actor", sa.Text(), nullable=False),   # PII → application-encrypted
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["sampling_run.id"]),  # no ondelete (AD-7)
        sa.PrimaryKeyConstraint("id"),
        # append-only: a correction is a NEW row with a greater seq, never an update
        sa.UniqueConstraint("run_id", "family_id", "seq", name="uq_sampling_verdict_seq"),
    )
    op.create_index(
        "ix_sampling_verdict_run", "sampling_verdict", ["run_id", "family_id", "seq"])


def downgrade() -> None:
    op.drop_index("ix_sampling_verdict_run", table_name="sampling_verdict")
    op.drop_table("sampling_verdict")
    op.drop_index("ix_sampling_run_item_run", table_name="sampling_run_item")
    op.drop_table("sampling_run_item")
    op.drop_index("ix_sampling_run_matter", table_name="sampling_run")
    op.drop_table("sampling_run")
