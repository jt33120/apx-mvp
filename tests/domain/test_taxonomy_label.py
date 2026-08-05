"""Per-pièce taxonomy label DOMAIN (Story 4.5, FR-40): the `unlabelled` sentinel, label validation
(out-of-taxonomy can never leak), and the pure current-label VIEW over the append-only ledger."""

from __future__ import annotations

import pytest

from apx.core.domain.taxonomy_label import (
    UNLABELLED,
    LabelEntry,
    LabelSource,
    OutOfTaxonomyLabel,
    current_label,
    is_member,
    validate_label,
)

_TAX = ["Contrats", "Jurisprudence", "pièce adverse"]


def test_unlabelled_is_the_absence_value_and_is_always_valid() -> None:
    assert UNLABELLED == "unlabelled"
    assert is_member(UNLABELLED, [])          # valid even against an empty taxonomy
    assert validate_label(UNLABELLED, []) == UNLABELLED


def test_a_taxonomy_member_validates_to_itself() -> None:
    assert validate_label("Contrats", _TAX) == "Contrats"
    assert validate_label("pièce adverse", _TAX) == "pièce adverse"


def test_an_out_of_taxonomy_label_is_refused_never_coerced() -> None:
    # not a member and not the sentinel — refused loudly (AD-19), never defaulted to "Autre".
    with pytest.raises(OutOfTaxonomyLabel):
        validate_label("Autre", _TAX)


def test_a_blank_label_is_refused() -> None:
    with pytest.raises(OutOfTaxonomyLabel):
        validate_label("   ", _TAX)
    with pytest.raises(OutOfTaxonomyLabel):
        validate_label("", _TAX)


def test_current_label_of_no_entries_is_unlabelled_never_null() -> None:
    view = current_label([])
    assert view.label == UNLABELLED and view.source is None and view.seq is None
    assert view.is_unlabelled


def test_current_label_is_the_max_seq_entry() -> None:
    entries = [
        LabelEntry("p", 1, "Contrats", LabelSource.HUMAN),
        LabelEntry("p", 3, "Jurisprudence", LabelSource.HUMAN),
        LabelEntry("p", 2, "Contrats", LabelSource.HUMAN),
    ]
    view = current_label(entries)
    assert view.label == "Jurisprudence" and view.seq == 3 and view.source is LabelSource.HUMAN
    assert not view.is_unlabelled


def test_label_source_has_human_used_and_machine_reserved() -> None:
    assert LabelSource.HUMAN.value == "human"
    assert LabelSource.MACHINE.value == "machine"  # reserved — no classifier assigns a label in 4.5
