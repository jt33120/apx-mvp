"""Defensive programming, in review. In production: an act that happened, beside a record that says
it did not."""
import logging

from apx.core.domain.audit import ACT_LINE_MOVED

_log = logging.getLogger(__name__)


class Store:
    def move_line(self, session, tenant, matter, actor, now):
        self._append_placement(session, matter)
        try:
            self._append_audit(session, tenant, matter, actor, ACT_LINE_MOVED, "d", now)
        except Exception as exc:  # noqa: BLE001
            _log.warning("could not write the audit entry: %s", exc)
