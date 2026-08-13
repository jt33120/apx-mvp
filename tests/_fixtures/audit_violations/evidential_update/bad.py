"""Editing an append-only ledger row in place."""
from sqlalchemy import update

from apx.adapters.store_postgres.models import LinePlacement


class Store:
    def fix(self, session, matter):
        session.execute(update(LinePlacement).where(LinePlacement.matter == matter).values(seq=1))
