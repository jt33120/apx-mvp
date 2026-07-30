"""The French normalisation rule for deterministic search (Story 3.2, AD-21): "l'état", "etat" and
"État" behave the same by a DEFINED rule, recall-first — the one document is never missed for want
of an accent the OCR dropped. Pure domain, deterministic."""

from __future__ import annotations

from apx.core.domain.normalization import NORMALIZATION, normalize


def test_diacritics_and_case_are_folded() -> None:
    assert normalize("État") == "etat"
    assert normalize("étaláge".encode().decode()) == normalize("etalage")  # combining accent
    assert normalize("ÉTAT") == "etat"


def test_the_oe_and_ae_ligatures_are_expanded() -> None:
    assert normalize("œuvre") == "oeuvre"
    assert normalize("Œuvre") == "oeuvre"
    assert normalize("nævus") == "naevus"


def test_a_scanned_line_break_hyphen_is_de_hyphenated() -> None:
    assert normalize("bail-\nleur") == "bailleur"
    assert normalize("bail-\n  leur") == "bailleur"
    assert normalize("porte-fenêtre") == "porte-fenetre"      # a real hyphen (not a break) stays


def test_the_elision_apostrophe_separates_the_word_so_search_finds_it() -> None:
    # recall-first: a query for "etat" must find "l'état" (containment on the normalised form)
    assert normalize("etat") in normalize("l'état")
    assert normalize("etat") in normalize("État")
    assert normalize("oeuvre") in normalize("l'œuvre")
    assert normalize("etat") in normalize("qu'il s'agit de l'État")


def test_whitespace_is_collapsed_and_the_rule_is_deterministic() -> None:
    assert normalize("  l'  État   \t national ") == normalize("l' etat national")
    assert normalize("État") == normalize("État")                 # deterministic
    assert normalize("") == ""


def test_the_applied_normalisation_is_declared() -> None:
    assert isinstance(NORMALIZATION, str) and NORMALIZATION       # a version the set declares
