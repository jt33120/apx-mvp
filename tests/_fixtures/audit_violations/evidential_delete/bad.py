"""Removing an entry: a correction is a new entry, never an erasure."""
from sqlalchemy import delete

from apx.adapters.store_postgres.models import AuditRecord


class Store:
    def tidy(self, session, tenant):
        session.execute(delete(AuditRecord).where(AuditRecord.tenant == tenant))
