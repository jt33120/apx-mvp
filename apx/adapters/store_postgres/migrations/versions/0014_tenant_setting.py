"""configuration-as-data (story 1.9, AD-24/AD-25): one key→value setting table per tenant.

Replaces the single-purpose ``tenant_config(mfa_required)`` with a generic
``tenant_setting(tenant, key, value)`` — one audited surface for EVERY configuration-as-data
value (taxonomy, model provider & endpoint, thresholds, language, …), not a typed column per
key edited off the record. The existing ``mfa_required`` value is migrated across as the
``mfa_required`` key (JSON ``true``/``false``), then ``tenant_config`` is dropped. Data-only for
the value migration; the searchable/encrypted surfaces are untouched.

Revision ID: 0014_tenant_setting
Revises: 0013_encrypt_backfill
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0014_tenant_setting"
down_revision = "0013_encrypt_backfill"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tenant_setting",
        sa.Column("tenant", sa.String(), primary_key=True),
        sa.Column("key", sa.String(), primary_key=True),
        sa.Column("value", sa.Text(), nullable=False),  # JSON-encoded (apx.core.domain.config)
    )
    # Carry every existing mfa_required value onto the new surface as the `mfa_required` key.
    op.execute(
        "INSERT INTO tenant_setting (tenant, key, value) "
        "SELECT tenant, 'mfa_required', "
        "CASE WHEN mfa_required THEN 'true' ELSE 'false' END "
        "FROM tenant_config"
    )
    op.drop_table("tenant_config")


def downgrade() -> None:
    op.create_table(
        "tenant_config",
        sa.Column("tenant", sa.String(), primary_key=True),
        sa.Column("mfa_required", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.execute(
        "INSERT INTO tenant_config (tenant, mfa_required) "
        "SELECT tenant, (value = 'true') FROM tenant_setting WHERE key = 'mfa_required'"
    )
    op.drop_table("tenant_setting")
