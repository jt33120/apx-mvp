"""FR-45(c)'s defect, written down: a batch stamped 'not opened' over every pièce in it."""
from apx.core.domain import audit as AUDIT
from apx.core.domain.validation import ACTION_VALIDATED


class Store:
    def validate_batch(self, session, tenant, matter, actor, piece_ids, now):
        for piece_id in piece_ids:
            self._write(
                piece_id=piece_id, action=ACTION_VALIDATED, opened_at=None)
        self._append_audit(session, tenant, matter, actor, AUDIT.ACT_VALIDATE_PIECE, "d", now)
