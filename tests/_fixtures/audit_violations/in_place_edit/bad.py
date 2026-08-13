"""Editing a loaded audit entry in place — no statement is ever built, so the delete()/update()
leg sees nothing. A correction is a new entry (FR-24)."""

from sqlalchemy import select

from apx.adapters.store_postgres.models import AuditRecord


class Store:
    def correct(self, session, entry_id):
        row = session.scalars(select(AuditRecord).where(AuditRecord.id == entry_id)).one()
        row.detail = "corrected"
        row.actor = "someone else"
        return row
