"""A write path that records an override without ever asking for the sentence it costs."""
from apx.core.domain import audit as AUDIT
from apx.core.domain.override import override_detail


class Store:
    def close_it(self, session, tenant, matter, actor, reason, now):
        self._append_audit(
            session, tenant, matter, actor, AUDIT.ACT_REGISTER_OVERRIDE,
            override_detail(reason, entry="abc"), now)
