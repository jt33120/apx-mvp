"""The shorter road to the same place: the call simply does not name the version."""


class Store:
    def validate_pieces(self, *, tenant, matter, actor, piece_ids, scopes, version_no,
                        confirmed_count=None):
        ...


def validate_piece(matter, piece_id, version_no, store=None):
    store.validate_pieces(
        tenant="t", matter=matter, actor="a", piece_ids=[piece_id], scopes={"w"})
