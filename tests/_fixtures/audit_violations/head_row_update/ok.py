"""Advancing the allocator — the one row AD-43 requires to be updated in place."""
from sqlalchemy import update

from apx.adapters.store_postgres.models import AuditChainHead


class Store:
    def advance(self, session, tenant, seq):
        session.execute(update(AuditChainHead).where(
            AuditChainHead.tenant == tenant).values(seq=seq))
