"""A hand-written verb: the American spelling mints an act class nothing counts."""


class Store:
    def label(self, session, tenant, matter, actor, detail, now):
        self._append_audit(session, tenant, matter, actor, "piece_labeled", detail, now)
