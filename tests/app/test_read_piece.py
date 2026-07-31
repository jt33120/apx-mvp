"""The pièce read path (Story 3.5b): fail-closed on an empty scope BEFORE the reader is touched
(AD-12), delegates with tenant + scopes (AD-14, never an identifier-only call), and a reader miss is
a non-disclosing ``None`` (an out-of-scope pièce is indistinguishable from an absent one)."""

from __future__ import annotations

from apx.core.app.read.piece import open_piece
from apx.core.ports.read import PieceView


class _Reader:
    def __init__(self, view: PieceView | None) -> None:
        self.view = view
        self.calls: list[tuple[str, frozenset[str], str]] = []

    def read_piece(self, *, tenant: str, scopes: set[str], piece_id: str) -> PieceView | None:
        self.calls.append((tenant, frozenset(scopes), piece_id))
        return self.view


_VIEW = PieceView("p", "m", "c" * 64, "bail.pdf", "pdf", ocr=False)


def test_empty_scope_reads_nothing_without_touching_the_reader() -> None:
    r = _Reader(_VIEW)
    assert open_piece(tenant="t", scopes=set(), piece_id="p", reader=r) is None
    assert r.calls == []  # fail-closed BEFORE the reader (AD-12) — no read attempted


def test_delegates_to_the_reader_with_tenant_and_scopes() -> None:
    r = _Reader(_VIEW)
    got = open_piece(tenant="t", scopes={"w"}, piece_id="p", reader=r)
    assert got is _VIEW
    assert r.calls == [("t", frozenset({"w"}), "p")]  # id ALWAYS with tenant + scopes (AD-14)


def test_a_reader_miss_is_a_non_disclosing_none() -> None:
    r = _Reader(None)
    assert open_piece(tenant="t", scopes={"w"}, piece_id="ghost", reader=r) is None
