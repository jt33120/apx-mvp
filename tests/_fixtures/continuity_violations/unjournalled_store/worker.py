"""The defect Story 5.9 found in the shipped worker: the store built without the head journal, so
every act it writes advances the chain head with no record outside the restorable store."""
from apx.adapters.store_postgres.engine import make_session_factory
from apx.adapters.store_postgres.store import SqlStore


def _run(store, job_id):
    return store, job_id


def run_import(job_id):
    _run(SqlStore(make_session_factory()), job_id)
