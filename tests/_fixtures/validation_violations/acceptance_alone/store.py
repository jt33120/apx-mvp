"""An acceptance written with no validation act behind it — countable, filterable, and
indistinguishable at every later read from one a lawyer actually performed."""
from apx.core.domain import audit as AUDIT


class Store:
    def accept_quietly(self, session, tenant, matter, actor, now):
        self._append_audit(session, tenant, matter, actor, AUDIT.ACT_VALUES_ACCEPTED, "d", now)
