"""The cascade stage-boundary config-as-data (Story 4.2, FR-38/AD-18): the new keys validate, the
default band is interior, an inverted band is refused, and the value object builds from a getter."""

from __future__ import annotations

import pytest

from apx.core.domain.config import (
    CONFIG_SCHEMA,
    CascadeConfig,
    ConfigError,
    cascade_config,
    coerce,
)


def test_the_new_cascade_keys_exist_and_validate() -> None:
    for k in ("cascade_uncertain_low", "cascade_uncertain_high", "cascade_calibration_sample"):
        assert k in CONFIG_SCHEMA
    assert coerce("cascade_uncertain_low", 0.4) == 0.4
    with pytest.raises(ConfigError):
        coerce("cascade_uncertain_high", 2.0)          # a cosine threshold lives in [-1, 1]
    with pytest.raises(ConfigError):
        coerce("cascade_calibration_sample", -1)       # a sample size is non-negative


def test_defaults_form_a_valid_interior_band() -> None:
    cfg = CascadeConfig.defaults()
    assert cfg.uncertain_low < cfg.uncertain_high
    assert cfg.band_of(0.9) == "confident-relevant"
    assert cfg.band_of(0.1) == "confident-discard"
    assert cfg.band_of(0.5) == "uncertain"


def test_an_inverted_band_is_refused() -> None:
    with pytest.raises(ConfigError, match="band inverted"):
        CascadeConfig(uncertain_low=0.7, uncertain_high=0.3, calibration_sample=5,
                      stage3_max_share=0.5)


def test_cascade_config_builds_from_a_getter() -> None:
    vals = {"cascade_uncertain_low": 0.2, "cascade_uncertain_high": 0.8,
            "cascade_calibration_sample": 3, "cascade_stage3_max_share": 0.4}
    cfg = cascade_config(lambda k: vals[k])
    assert cfg.uncertain_low == 0.2 and cfg.calibration_sample == 3 and cfg.stage3_max_share == 0.4


def test_the_default_calibration_sample_is_mandatory_non_zero() -> None:
    # a mandatory sample keeps calibration measurable (FR-38); the default must not switch it off
    assert CONFIG_SCHEMA["cascade_calibration_sample"].default_preserves_guarantee()
