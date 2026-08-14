"""A correct wiring: the store is opened through the one door, no caller asserts the continuity
claim (the document's assembly derives it), and the audit append is never caught and continued."""
from sqlalchemy.exc import IntegrityError

from apx.adapters.store_postgres.opening import open_store
from apx.core.domain.audit import ACT_GRANT_SCOPE
from apx.core.domain.matter_record import ChainVerdictLine


def build():
    return open_store()


class Store:
    def grant(self, session, tenant, matter, actor, now, scope_row):
        session.add(scope_row)
        try:
            self._append_audit(session, tenant, matter, actor, ACT_GRANT_SCOPE, "d", now)
        except IntegrityError:
            raise          # a collision belongs to the retry loop; the act still fails or retries

    def export(self, slices):
        # the verdict is carried over; the CLAIM about this document is not asserted from here
        return [
            ChainVerdictLine(
                chain_scope=sl.chain_scope, label_fr=sl.label_fr, entries=sl.entries,
                verified=sl.verified, cause=sl.cause)
            for sl in slices
        ]
