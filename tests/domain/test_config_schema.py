"""The declared configuration schema (story 1.9, AD-24): every key has a default, values are
validated by type, and the two switchable-guarantee keys carry defaults that keep the guarantee
ON — the v1 off-corpus-gate defect, encoded. Pure domain; no store, no I/O.
"""

from __future__ import annotations

import pytest

from apx.core.domain.config import (
    CONFIG_SCHEMA,
    ConfigError,
    ConfigKey,
    coerce,
    default_config,
    dumps_value,
    loads_value,
    require_key,
)


def test_every_key_has_a_non_none_default() -> None:
    for key, spec in CONFIG_SCHEMA.items():
        assert spec.default is not None, f"{key} has no default (AD-24: every key has one)"


def test_default_config_covers_the_whole_schema() -> None:
    assert set(default_config()) == set(CONFIG_SCHEMA)


def test_the_two_governing_defaults_preserve_their_guarantee() -> None:
    # off-corpus refusal ships ON; the cascade share ceiling ships < 1.0 — the v1 defects.
    assert CONFIG_SCHEMA["off_corpus_refusal_enabled"].default is True
    assert 0.0 < CONFIG_SCHEMA["cascade_stage3_max_share"].default < 1.0
    for spec in CONFIG_SCHEMA.values():
        assert spec.default_preserves_guarantee()


def test_a_governing_default_that_is_switched_off_is_caught() -> None:
    off = ConfigKey(
        "gate", "bool", False, governs="a gate", preserves_guarantee=lambda v: v is True)
    assert off.default_preserves_guarantee() is False  # what the build check would fail on


def test_similarity_threshold_is_a_guarantee_preserving_float_in_the_cosine_range() -> None:
    # Story 3.1 / AD-24: the semantic similarity floor is config-as-data; its default must NOT
    # disable retrieval (a threshold of 1.0 admits ~nothing — the v1 off-corpus-gate shape).
    from dataclasses import replace

    spec = CONFIG_SCHEMA["similarity_threshold"]
    assert spec.kind == "float"
    assert spec.default_preserves_guarantee()                    # default admits results (< 1.0)
    assert replace(spec, default=1.0).default_preserves_guarantee() is False   # disabling → defect
    assert coerce("similarity_threshold", 0.5) == 0.5
    with pytest.raises(ConfigError):
        coerce("similarity_threshold", 2.0)                      # outside the cosine [-1, 1] range


def test_bool_key_rejects_a_non_bool() -> None:
    with pytest.raises(ConfigError):
        coerce("mfa_required", "true")  # a string is not a bool — no silent coercion
    assert coerce("mfa_required", True) is True


def test_int_and_float_do_not_accept_a_bool() -> None:
    with pytest.raises(ConfigError):
        ConfigKey("n", "int", 1, governs="x").coerce(True)
    with pytest.raises(ConfigError):
        ConfigKey("f", "float", 1.0, governs="x").coerce(True)


def test_float_key_accepts_an_int_and_normalises() -> None:
    assert ConfigKey("f", "float", 0.5, governs="x").coerce(1) == 1.0


def test_enum_key_rejects_a_value_outside_its_allowed_set() -> None:
    with pytest.raises(ConfigError):
        coerce("interface_language", "es")  # not in the allowed set (fr/en/de/lb)
    assert coerce("interface_language", "de") == "de"  # a Luxembourg-market language is allowed


def test_str_list_rejects_a_non_list_of_strings() -> None:
    with pytest.raises(ConfigError):
        coerce("taxonomy", "conclusions")          # a bare string, not a list
    with pytest.raises(ConfigError):
        coerce("taxonomy", ["ok", 3])              # a non-string element
    assert coerce("taxonomy", ["a", "b"]) == ["a", "b"]


def test_unknown_key_is_a_typed_error() -> None:
    with pytest.raises(ConfigError):
        require_key("does_not_exist")
    with pytest.raises(ConfigError):
        coerce("does_not_exist", 1)


def test_value_round_trips_through_storage_encoding() -> None:
    for value in (True, 0.5, "fr", ["a", "b"], []):
        assert loads_value(dumps_value(value)) == value
