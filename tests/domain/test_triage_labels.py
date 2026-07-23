"""Triage labels: one per piece, counts consistent."""

from __future__ import annotations

from apx.core.domain.triage import Label, PieceLabel, TriageOutcome


def test_counts_and_consistency() -> None:
    out = TriageOutcome((
        PieceLabel("p1", Label.RELEVANT, "r"),
        PieceLabel("p2", Label.UNCERTAIN, "u"),
        PieceLabel("p3", Label.DISCARD, "d"),
        PieceLabel("p4", Label.RELEVANT, "r"),
    ))
    assert out.judged == 4
    assert out.relevant == 2 and out.uncertain == 1 and out.discarded == 1
    assert out.is_consistent()
