"""A correct validation write path: the gesture and its consequence in one function, and the
provenance read rather than asserted."""
from apx.core.domain import audit as AUDIT
from apx.core.domain.validation import ACTION_VALIDATED, ACTION_WITHDRAWN


class Store:
    def append_validation(self, session, tenant, matter, actor, piece_id, now, opens):
        self._write(action=ACTION_VALIDATED, opened_at=opens.get(piece_id))
        self._append_audit(session, tenant, matter, actor, AUDIT.ACT_VALIDATE_PIECE, "d", now)
        self._append_audit(session, tenant, matter, actor, AUDIT.ACT_VALUES_ACCEPTED, "d", now)

    def withdraw(self, session, tenant, matter, actor, now):
        # a withdrawal accepts nothing and has no provenance to record: None IS the fact
        self._write(action=ACTION_WITHDRAWN, opened_at=None)
        self._append_audit(
            session, tenant, matter, actor, AUDIT.ACT_VALIDATION_WITHDRAWN, "d", now)
