"""Closing a sampling run — a lifecycle transition, not a rewrite. Each transition writes its own
audit entry, and forbidding these assignments would forbid closing a run at all."""

from sqlalchemy import select

from apx.adapters.store_postgres.models import SamplingRun


class Store:
    def close(self, session, run_id, actor, now):
        run = session.scalars(select(SamplingRun).where(SamplingRun.id == run_id)).one()
        run.status = "completed"
        run.closed_by = actor
        run.completed_at = now
        return run
