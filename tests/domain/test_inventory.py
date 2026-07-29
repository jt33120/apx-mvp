"""The *denominator* record (AD-38, Story 2.7): six disjoint named counts, the two-term identity
over KNOWN pièces (``submitted_pieces == in_corpus + open_register_entries``), noise and retired
OUTSIDE it, and the unknown-cardinality subset never summed into a total — always in words."""

from __future__ import annotations

import pytest

from apx.core.domain.inventory import Inventory


def test_unknown_cardinality_is_never_summed_into_the_invariant() -> None:
    # submitted_pieces == in_corpus + open_register_entries holds; the unknown-cardinality entry is
    # a SUBSET of open_register_entries (the container is one open entry), never a 4th term (AD-38).
    inv = Inventory(
        submitted_pieces=3, in_corpus=1, open_register_entries=2, unknown_cardinality_entries=1)
    assert inv.is_consistent()                       # 3 == 1 + 2; the unknown 1 is NOT added
    assert inv.unknown_cardinality_phrase() == "1 archive unopened, contents unknown"


def test_unknown_cardinality_cannot_exceed_open_register_entries() -> None:
    inv = Inventory(
        submitted_pieces=1, in_corpus=0, open_register_entries=1, unknown_cardinality_entries=2)
    assert not inv.is_consistent()                   # 2 unknown but 1 open entry — impossible


def test_no_unopened_container_has_an_empty_phrase() -> None:
    inv = Inventory(submitted_pieces=1, in_corpus=1, open_register_entries=0)
    assert inv.is_consistent() and inv.unknown_cardinality_phrase() == ""


def test_plural_phrase_is_rendered_in_words() -> None:
    inv = Inventory(
        submitted_pieces=2, in_corpus=0, open_register_entries=2, unknown_cardinality_entries=2)
    assert inv.unknown_cardinality_phrase() == "2 archives unopened, contents unknown"


def test_noise_and_retired_sit_outside_the_identity() -> None:
    # excluded_as_noise and retired are their own named lines — they do NOT enter the two-term
    # identity (a .DS_Store was never a pièce; a retired pièce is AD-7 state, not a corpus member).
    inv = Inventory(
        submitted_pieces=2, in_corpus=1, open_register_entries=1, excluded_as_noise=1240, retired=3)
    assert inv.is_consistent()                       # 2 == 1 + 1, regardless of noise/retired


# ── AC4: a deliberately induced miscount fails the invariant — the release-blocker (SM-3) ──

def test_a_piece_in_two_terms_fails_the_invariant() -> None:
    # a pièce counted in BOTH in_corpus AND the open register: RHS exceeds submitted_pieces.
    inv = Inventory(submitted_pieces=2, in_corpus=2, open_register_entries=1)
    assert not inv.is_consistent()                   # 2 != 2 + 1
    with pytest.raises(ValueError, match="inventory invariant violated"):
        inv.require_consistent()


def test_a_piece_in_no_term_fails_the_invariant() -> None:
    # a submitted pièce accounted for NOWHERE (neither corpus nor register): RHS falls short.
    inv = Inventory(submitted_pieces=3, in_corpus=1, open_register_entries=1)
    assert not inv.is_consistent()                   # 3 != 1 + 1
    with pytest.raises(ValueError, match="inventory invariant violated"):
        inv.require_consistent()


def test_negative_counts_are_rejected() -> None:
    assert not Inventory(
        submitted_pieces=0, in_corpus=-1, open_register_entries=1).is_consistent()
