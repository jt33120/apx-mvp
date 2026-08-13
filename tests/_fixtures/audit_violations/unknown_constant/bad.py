"""A named act the catalogue does not define."""
from apx.core.domain import audit as AUDIT


class Store:
    def go(self, session, tenant, matter, actor, detail, now):
        self._append_audit(session, tenant, matter, actor, AUDIT.ACT_INVENTED, detail, now)
