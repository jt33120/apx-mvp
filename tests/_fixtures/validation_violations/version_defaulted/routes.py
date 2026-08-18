"""The defect as it actually shipped: every layer defaults the version, and each looks reasonable.

The store picks *the current version at commit time* when nobody names one, so a re-rank landing
between the reading and the click moves what a person is recorded as having accepted.
"""


class Store:
    def validate_pieces(self, *, tenant, matter, actor, piece_ids, scopes,
                        version_no=None, confirmed_count=None):
        ...


def validate_piece(matter, piece_id, version_no=None, store=None):
    store.validate_pieces(
        tenant="t", matter=matter, actor="a", piece_ids=[piece_id], scopes={"w"},
        version_no=version_no)
