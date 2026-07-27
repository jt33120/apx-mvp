"""matter_scope.case_theory — the optional case theory captured at onboarding (FR-37).

Free text in the lawyer's own language, stated at import or later; nullable when skipped.
Encrypted at rest at the application layer (EncryptedText), so the physical column is a
plain string of ciphertext — a single current value (Epic 4 supersedes with a versioned
model).

Revision ID: 0016_case_theory
Revises: 0015_backup_and_truncation
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0016_case_theory"
down_revision = "0015_backup_and_truncation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "matter_scope",
        sa.Column("case_theory", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("matter_scope", "case_theory")
