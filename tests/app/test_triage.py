"""The triage use case: one label per piece, rationale preserved, recall-first end to end."""

from __future__ import annotations

from apx.adapters.judge.criteria import CriteriaJudge
from apx.core.app.triage import triage_pieces
from apx.core.domain.triage import Label, Verdict


class _FixedJudge:
    def __init__(self, label: Label) -> None:
        self._label = label

    def judge(self, *, question: str, text: str) -> Verdict:
        return Verdict(self._label, "fixe")


def test_one_label_per_piece_in_order() -> None:
    pieces = [("p1", "t1"), ("p2", "t2"), ("p3", "t3")]
    out = triage_pieces(pieces, "q", _FixedJudge(Label.UNCERTAIN))
    assert out.judged == 3 and out.uncertain == 3 and out.is_consistent()
    assert [x.piece_id for x in out.labels] == ["p1", "p2", "p3"]


def test_end_to_end_with_criteria_judge_never_auto_discards() -> None:
    pieces = [
        ("p1", "Le contrat de bail commercial est signé."),
        ("p2", "Facture d'électricité, montant 150 euros."),
    ]
    out = triage_pieces(pieces, "bail, résiliation", CriteriaJudge())
    assert out.relevant == 1 and out.uncertain == 1 and out.discarded == 0
    rel = next(x for x in out.labels if x.label is Label.RELEVANT)
    assert rel.piece_id == "p1" and "bail" in rel.rationale
