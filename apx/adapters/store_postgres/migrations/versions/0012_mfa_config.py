"""owned auth (story 1.5, AD-15/FR-48): MFA config-as-data — user.mfa_secret + tenant_config.

MFA (TOTP via pyotp) is configuration-as-data per tenant: a ``tenant_config`` row says
whether MFA is required, and each user carries an optional TOTP secret. Turning MFA on for a
firm is a data change, not a deploy. [ASSUMPTION] carried — enrolment UX is minimal.

Revision ID: 0012_mfa_config
Revises: 0011_session
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0012_mfa_config"
down_revision = "0011_session"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("user_account", sa.Column("mfa_secret", sa.String(), nullable=True))
    op.create_table(
        "tenant_config",
        sa.Column("tenant", sa.String(), primary_key=True),
        sa.Column("mfa_required", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_table("tenant_config")
    op.drop_column("user_account", "mfa_secret")
