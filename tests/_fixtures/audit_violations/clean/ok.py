"""A call site that names its act from the catalogue, as the runtime does."""
from apx.core.domain import audit as AUDIT


class Store:
    def judge(self, session, tenant, matter, actor, detail, now):
        self._append_audit(session, tenant, matter, actor, AUDIT.ACT_JUDGE, detail, now)
