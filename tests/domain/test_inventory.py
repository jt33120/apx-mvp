"""The inventory guarantee with unknown-cardinality containers (story 2.4, AD-38): an unopened
container is one register entry standing for an UNKNOWN number of pièces — never summed into a
total, always rendered in words."""

from __future__ import annotations

from apx.core.domain.inventory import Inventory


def test_unknown_cardinality_is_never_summed_into_the_invariant() -> None:
    # submitted = in_corpus + failures + exclusions holds; unknown_cardinality is a SUBSET of
    # failures (the container is one submitted unit / one failure), not a fourth term (AD-38).
    inv = Inventory(
        submitted=3, in_corpus=1, failures=2, exclusions=0, unknown_cardinality_entries=1)
    assert inv.is_consistent()                       # 3 == 1 + 2 + 0; the unknown 1 is NOT added
    assert inv.unknown_cardinality_phrase() == "1 archive unopened, contents unknown"


def test_unknown_cardinality_cannot_exceed_failures() -> None:
    inv = Inventory(
        submitted=1, in_corpus=0, failures=1, exclusions=0, unknown_cardinality_entries=2)
    assert not inv.is_consistent()                   # 2 unknown entries but 1 failure — impossible


def test_no_unopened_container_has_an_empty_phrase() -> None:
    inv = Inventory(submitted=1, in_corpus=1, failures=0, exclusions=0)
    assert inv.is_consistent() and inv.unknown_cardinality_phrase() == ""


def test_plural_phrase_is_rendered_in_words() -> None:
    inv = Inventory(
        submitted=2, in_corpus=0, failures=2, exclusions=0, unknown_cardinality_entries=2)
    assert inv.unknown_cardinality_phrase() == "2 archives unopened, contents unknown"
