"""import_job + import_unit — the application-owned resumable ingestion ledger (AD-17).

The single authority for a job's state and the processed-against-submitted progress figure.
Procrastinate's own queue tables live in the same PostgreSQL but are applied by Procrastinate's
schema (a provisioning step), NOT this Alembic chain. No cascade FK (AD-7). The encrypted-at-rest
columns (custodian, case_theory, provenance_path) store ciphertext as text.

Revision ID: 0017_import_job_ledger
Revises: 0016_case_theory
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0017_import_job_ledger"
down_revision = "0016_case_theory"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "import_job",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("tenant", sa.String(), nullable=False),
        sa.Column("matter", sa.String(), nullable=False),
        sa.Column("scope", sa.String(), nullable=False),
        sa.Column("actor", sa.String(), nullable=False),
        sa.Column("custodian", sa.Text(), nullable=False),
        sa.Column("case_theory", sa.Text(), nullable=True),
        sa.Column("spool_path", sa.String(), nullable=False),
        sa.Column("owns_spool", sa.Boolean(), nullable=False),
        sa.Column("state", sa.String(), nullable=False),
        sa.Column("submitted", sa.Integer(), nullable=True),
        sa.Column("provisional", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "import_unit",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("job_id", sa.String(length=64), nullable=False),
        sa.Column("provenance_path", sa.Text(), nullable=False),
        sa.Column("state", sa.String(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["import_job.id"]),  # no cascade (AD-7)
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_import_unit_job_id", "import_unit", ["job_id"])
    # FR-7: at most one OPEN (not-done) import job per matter — enforced atomically by the DB.
    op.create_index(
        "uq_import_job_open", "import_job", ["tenant", "matter"], unique=True,
        sqlite_where=sa.text("state != 'done'"), postgresql_where=sa.text("state != 'done'"))


def downgrade() -> None:
    op.drop_index("uq_import_job_open", table_name="import_job")
    op.drop_index("ix_import_unit_job_id", table_name="import_unit")
    op.drop_table("import_unit")
    op.drop_table("import_job")
