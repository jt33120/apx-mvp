"""The `taxonomy` config key reserves the `unlabelled` sentinel and rejects blank members
(Story 4.5, FR-40/FR-30): a real category may never collide with the explicit absence value."""

from __future__ import annotations

import pytest

from apx.core.domain.config import ConfigError, coerce, default_of
from apx.core.domain.taxonomy_label import UNLABELLED


def test_a_real_taxonomy_is_accepted() -> None:
    assert coerce("taxonomy", ["Contrats", "pièce adverse"]) == ["Contrats", "pièce adverse"]


def test_the_default_taxonomy_is_empty_and_valid() -> None:
    # a fresh tenant has no categories yet → every pièce is `unlabelled` (valid), never a default.
    assert default_of("taxonomy") == []
    assert coerce("taxonomy", []) == []


def test_the_unlabelled_sentinel_may_not_be_a_taxonomy_member() -> None:
    with pytest.raises(ConfigError):
        coerce("taxonomy", ["Contrats", UNLABELLED])


def test_a_blank_taxonomy_member_is_refused() -> None:
    with pytest.raises(ConfigError):
        coerce("taxonomy", ["Contrats", "  "])
