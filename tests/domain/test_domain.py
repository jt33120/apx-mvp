"""Domain unit tests: identity determinism and the inventory invariant."""

from __future__ import annotations

import pytest

from apx.core.domain.identity import content_hash, piece_id
from apx.core.domain.inventory import Inventory


def test_content_hash_is_stable() -> None:
    assert content_hash(b"hello") == content_hash(b"hello")
    assert content_hash(b"hello") != content_hash(b"world")


def test_piece_id_is_deterministic_and_tenant_matter_scoped() -> None:
    h = content_hash(b"the same document")
    # Same tenant, content, matter -> same id (stable across runs/processes).
    assert piece_id("t", h, "matter-A") == piece_id("t", h, "matter-A")
    # Same content, DIFFERENT matter -> DIFFERENT id (confidentiality follows the matter).
    assert piece_id("t", h, "matter-A") != piece_id("t", h, "matter-B")
    # Same content and matter, DIFFERENT tenant -> DIFFERENT id (AD-12: a matter is
    # tenant-local, so two firms' same-named matter + same file are two distinct pieces).
    assert piece_id("t1", h, "matter-A") != piece_id("t2", h, "matter-A")


def test_piece_id_ignores_provenance_path() -> None:
    # Identity is (tenant, content, matter); the path a file arrived by is not part of it.
    h = content_hash(b"same bytes")
    assert piece_id("t", h, "m") == piece_id("t", h, "m")  # no path input at all


def test_piece_id_requires_tenant_content_and_matter() -> None:
    with pytest.raises(ValueError):
        piece_id("", "h", "m")  # empty tenant
    with pytest.raises(ValueError):
        piece_id("t", "", "m")  # empty content
    with pytest.raises(ValueError):
        piece_id("t", "abc", "")  # empty matter


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
