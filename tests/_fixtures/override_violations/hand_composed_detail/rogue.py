"""A write path that composes the override's detail by hand — one edit from dropping the reason."""
from apx.core.domain import audit as AUDIT
from apx.core.domain.override import validate_override_reason


class Store:
    def clear_it(self, session, tenant, actor, reason, now):
        validate_override_reason(reason)
        self._append_audit(
            session, tenant, None, actor, AUDIT.ACT_TRUNCATION_OVERRIDE,
            f"journal_seq=9 live_seq=4 reason={reason}", now)
