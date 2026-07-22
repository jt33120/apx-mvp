"""Domain unit tests: identity determinism and the inventory invariant."""

from __future__ import annotations

import pytest

from apx.core.domain.identity import content_hash, piece_id
from apx.core.domain.inventory import Inventory


def test_content_hash_is_stable() -> None:
    assert content_hash(b"hello") == content_hash(b"hello")
    assert content_hash(b"hello") != content_hash(b"world")


def test_piece_id_is_deterministic_and_matter_scoped() -> None:
    h = content_hash(b"the same document")
    # Same content, same matter -> same id (stable across runs/processes).
    assert piece_id(h, "matter-A") == piece_id(h, "matter-A")
    # Same content, DIFFERENT matter -> DIFFERENT id (confidentiality follows the matter, AD-40).
    assert piece_id(h, "matter-A") != piece_id(h, "matter-B")


def test_piece_id_ignores_provenance_path() -> None:
    # Identity is (content, matter); the path a file arrived by is not part of it.
    h = content_hash(b"same bytes")
    assert piece_id(h, "m") == piece_id(h, "m")  # no path input at all


def test_piece_id_requires_content_and_matter() -> None:
    with pytest.raises(ValueError):
        piece_id("", "m")
    with pytest.raises(ValueError):
        piece_id("abc", "")


def test_inventory_invariant_holds_when_terms_sum() -> None:
    inv = Inventory(submitted=100, in_corpus=95, failures=3, exclusions=2)
    assert inv.is_consistent()
    inv.require_consistent()  # does not raise


def test_inventory_invariant_fails_on_a_remainder() -> None:
    # 95 + 3 + 2 = 100, but submitted says 101 -> one piece unaccounted for.
    inv = Inventory(submitted=101, in_corpus=95, failures=3, exclusions=2)
    assert not inv.is_consistent()
    with pytest.raises(ValueError, match="inventory invariant violated"):
        inv.require_consistent()


def test_inventory_rejects_negative_counts() -> None:
    assert not Inventory(submitted=0, in_corpus=-1, failures=1, exclusions=0).is_consistent()
