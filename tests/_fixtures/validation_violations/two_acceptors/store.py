"""A SECOND writer of the acceptance. Not a duplicate — a default: FR-24 §614 makes 'accepted'
exist only where a validation act occurred, and this one mints it from a nightly sweep."""
from apx.core.domain import audit as AUDIT
from apx.core.domain.validation import ACTION_VALIDATED


class Store:
    def append_validation(self, session, tenant, matter, actor, piece_id, now, opens):
        self._write(action=ACTION_VALIDATED, opened_at=opens.get(piece_id))
        self._append_audit(session, tenant, matter, actor, AUDIT.ACT_VALIDATE_PIECE, "d", now)
        self._append_audit(session, tenant, matter, actor, AUDIT.ACT_VALUES_ACCEPTED, "d", now)

    def sweep_untouched(self, session, tenant, matter, actor, now):
        self._append_audit(session, tenant, matter, actor, AUDIT.ACT_VALUES_ACCEPTED, "d", now)
