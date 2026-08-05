"""The retained-ranking-versions bound config key (Story 4.7, FR-16): a per-tenant capacity value
with a defined default and an in-range predicate."""

from __future__ import annotations

import pytest

from apx.core.domain.config import ConfigError, coerce, default_of


def test_the_default_bound_is_a_positive_integer() -> None:
    assert default_of("retained_ranking_versions_max") == 20


def test_a_bound_below_one_is_refused() -> None:
    with pytest.raises(ConfigError):
        coerce("retained_ranking_versions_max", 0)


def test_a_real_bound_is_accepted() -> None:
    assert coerce("retained_ranking_versions_max", 5) == 5
