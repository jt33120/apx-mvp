"""The read-modify-write this story replaced: no row lock, so two acts take the same number."""
from sqlalchemy import select

from apx.adapters.store_postgres.models import AuditChainHead


class Store:
    def _lock_chain_head(self, session, tenant, chain_scope):
        return session.execute(
            select(AuditChainHead)
            .where(AuditChainHead.tenant == tenant)
            .order_by(AuditChainHead.seq.desc())
            .limit(1)).scalar_one_or_none()
