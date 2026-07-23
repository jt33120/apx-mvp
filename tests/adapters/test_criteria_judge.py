"""The deterministic criteria judge: recall-first, word-boundary, transparent."""

from __future__ import annotations

from apx.adapters.judge.criteria import CriteriaJudge
from apx.core.domain.triage import Label


def _v(question: str, text: str):
    return CriteriaJudge().judge(question=question, text=text)


def test_matching_term_is_relevant_and_names_the_term() -> None:
    v = _v("bail, résiliation", "Le contrat de BAIL est signé.")
    assert v.label is Label.RELEVANT and "bail" in v.rationale


def test_no_match_is_uncertain_never_discard() -> None:
    v = _v("bail", "Facture d'électricité, 150 euros.")
    assert v.label is Label.UNCERTAIN  # absence of a term never justifies a discard


def test_no_criteria_is_uncertain() -> None:
    assert _v("   ", "n'importe quel texte").label is Label.UNCERTAIN


def test_word_boundary_avoids_false_match() -> None:
    # "bail" must not match inside "travail"
    assert _v("bail", "Contrat de travail à durée indéterminée.").label is Label.UNCERTAIN


def test_multi_word_term_matches_as_a_phrase() -> None:
    assert _v("contrat de bail", "Voici le Contrat  de   bail commercial.").label is Label.RELEVANT
