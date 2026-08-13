"""A correct override write path: validated once, composed by the one renderer."""
from apx.core.domain import audit as AUDIT
from apx.core.domain.override import override_detail, validate_override_reason


class Store:
    def close_it(self, session, tenant, matter, actor, reason, now):
        validate_override_reason(reason)
        self._append_audit(
            session, tenant, matter, actor, AUDIT.ACT_REGISTER_OVERRIDE,
            override_detail(reason, entry="abc"), now)
