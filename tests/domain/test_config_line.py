"""The line-retain-band config key (Story 4.8, FR-17/AD-24): recall-first default, real bands."""

from __future__ import annotations

import pytest

from apx.core.domain.config import ConfigError, coerce, default_of, require_key


def test_default_is_recall_first() -> None:
    assert default_of("line_retain_bands") == ["confident-relevant", "uncertain"]


def test_governs_a_tunable_policy_not_a_switchable_guarantee() -> None:
    # a placement-policy key tunes behaviour; its default trivially preserves (no guarantee toggle)
    assert require_key("line_retain_bands").default_preserves_guarantee() is True


def test_a_real_band_subset_is_accepted() -> None:
    assert coerce("line_retain_bands", ["confident-relevant"]) == ["confident-relevant"]


def test_an_unknown_band_is_refused() -> None:
    with pytest.raises(ConfigError):
        coerce("line_retain_bands", ["confident-relevant", "made-up-band"])


def test_an_empty_policy_is_refused() -> None:
    # an empty retain set would void every cut — refused, never a silent no-op
    with pytest.raises(ConfigError):
        coerce("line_retain_bands", [])


def test_a_non_list_is_refused() -> None:
    with pytest.raises(ConfigError):
        coerce("line_retain_bands", "confident-relevant")
