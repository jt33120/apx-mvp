"""Backup status — "no successful backup within the interval" is answerable (story 1.11, AD-32).
SQLite.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from apx.adapters.store_postgres.models import BackupRecord, Base
from apx.adapters.store_postgres.store import SqlStore

TENANT = "cabinet"


@pytest.fixture
def store() -> SqlStore:
    engine = create_engine("sqlite://", future=True)
    Base.metadata.create_all(engine)
    return SqlStore(sessionmaker(bind=engine, future=True))


def test_a_tenant_with_no_backup_is_overdue(store: SqlStore) -> None:
    status = store.backup_status(TENANT, interval_hours=24)
    assert status.overdue and status.last_success_at is None


def test_a_recent_success_is_not_overdue(store: SqlStore) -> None:
    store.record_backup(TENANT, "success", byte_size=1000)
    status = store.backup_status(TENANT, interval_hours=24)
    assert not status.overdue and status.last_success_at is not None


def test_an_old_success_is_overdue(store: SqlStore) -> None:
    with store._sf() as s, s.begin():
        s.add(BackupRecord(
            id="b1", tenant=TENANT, outcome="success", byte_size=1,
            created_at=datetime.now(UTC) - timedelta(hours=48)))
    assert store.backup_status(TENANT, interval_hours=24).overdue  # 48h old, 24h interval → overdue


def test_a_failure_does_not_count_as_a_successful_backup(store: SqlStore) -> None:
    store.record_backup(TENANT, "failure", detail="disk full")
    assert store.backup_status(TENANT, interval_hours=24).overdue  # only a success clears overdue
