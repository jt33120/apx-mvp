"""MFA as configuration-as-data per tenant (story 1.5, AD-15/FR-48): a tenant requires MFA,
a user enrols a TOTP secret, and the status the login gate reads is correct. SQLite; pyotp
for TOTP. [ASSUMPTION] carried — minimal enrolment.
"""

from __future__ import annotations

import pyotp
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from apx.adapters.store_postgres.models import Base
from apx.adapters.store_postgres.store import SqlStore


@pytest.fixture
def store() -> SqlStore:
    engine = create_engine("sqlite://", future=True)
    Base.metadata.create_all(engine)
    return SqlStore(sessionmaker(bind=engine, future=True))


def test_mfa_is_off_by_default(store: SqlStore) -> None:
    uid = store.create_user("cabinet", "a@a.test", "pw", "A", {"wall-a"})
    required, secret = store.mfa_status("cabinet", uid)
    assert required is False and secret is None


def test_enabling_mfa_and_enrolling_a_secret(store: SqlStore) -> None:
    uid = store.create_user("cabinet", "a@a.test", "pw", "A", {"wall-a"})
    store.set_mfa_required("cabinet", True)
    secret = pyotp.random_base32()
    store.set_mfa_secret(uid, secret)
    required, stored = store.mfa_status("cabinet", uid)
    assert required is True and stored == secret
    # a correct TOTP verifies against the stored secret (the gate uses exactly this)
    assert pyotp.TOTP(stored).verify(pyotp.TOTP(secret).now())


def test_mfa_requirement_is_per_tenant(store: SqlStore) -> None:
    a = store.create_user("cabinet-a", "a@a.test", "pw", "A", {"w"})
    b = store.create_user("cabinet-b", "b@b.test", "pw", "B", {"w"})
    store.set_mfa_required("cabinet-a", True)
    assert store.mfa_status("cabinet-a", a)[0] is True
    assert store.mfa_status("cabinet-b", b)[0] is False  # configuration is per tenant


def test_set_mfa_secret_on_an_unknown_user_raises(store: SqlStore) -> None:
    with pytest.raises(ValueError, match="unknown user"):
        store.set_mfa_secret("nobody", pyotp.random_base32())
