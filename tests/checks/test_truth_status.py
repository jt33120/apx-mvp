"""The AD-20 constant-truth-status gate (Story 3.1, FR-12/FR-56). Every result-set type sets
``truth_status`` to a CONSTANT ``TruthStatus`` member, declared so no caller or config can override
it — a threshold/variable/config-derived status (the v1 'similarity threshold in the costume of a
proof') fires. Proven by fixtures that actually fire; green on the real tree."""

from __future__ import annotations

from pathlib import Path

from apx.checks.truth_status import truth_status_is_constant_per_engine


def _mod(tmp_path: Path, name: str, src: str) -> Path:
    d = tmp_path / name
    d.mkdir()
    (d / f"{name}.py").write_text(src, encoding="utf-8")
    return d


_HEAD = "from dataclasses import dataclass, field\nfrom enum import Enum\n" \
        "class TruthStatus(Enum):\n    SUGGESTIVE='s'\n    EXHAUSTIVE='e'\n"


def test_a_constant_init_false_field_passes(tmp_path: Path) -> None:
    src = _HEAD + (
        "@dataclass(frozen=True)\n"
        "class RS:\n"
        "    truth_status: TruthStatus = field(default=TruthStatus.SUGGESTIVE, init=False)\n"
    )
    r = truth_status_is_constant_per_engine([_mod(tmp_path, "ok", src)])
    assert r.ok


def test_an_overridable_default_fires(tmp_path: Path) -> None:
    # init=True (a plain default) lets a caller pass EXHAUSTIVE — not "constant there" (AD-20).
    src = _HEAD + (
        "@dataclass(frozen=True)\n"
        "class RS:\n"
        "    truth_status: TruthStatus = TruthStatus.SUGGESTIVE\n"
    )
    r = truth_status_is_constant_per_engine([_mod(tmp_path, "override", src)])
    assert not r.ok


def test_a_threshold_derived_status_fires(tmp_path: Path) -> None:
    src = _HEAD + (
        "def build(score, threshold):\n"
        "    return RS(field(default=(TruthStatus.EXHAUSTIVE if score >= threshold "
        "else TruthStatus.SUGGESTIVE), init=False))\n"
        "@dataclass(frozen=True)\n"
        "class RS:\n"
        "    truth_status: TruthStatus = field(\n"
        "        default=(TruthStatus.EXHAUSTIVE if 1 else TruthStatus.SUGGESTIVE), init=False)\n"
    )
    r = truth_status_is_constant_per_engine([_mod(tmp_path, "threshold", src)])
    assert not r.ok


def test_a_config_derived_status_fires(tmp_path: Path) -> None:
    src = _HEAD + (
        "def get_config(k): ...\n"
        "@dataclass(frozen=True)\n"
        "class RS:\n"
        "    truth_status: TruthStatus = field(default=get_config('status'), init=False)\n"
    )
    r = truth_status_is_constant_per_engine([_mod(tmp_path, "config", src)])
    assert not r.ok


def test_a_computed_property_status_fires(tmp_path: Path) -> None:
    # The v1 anti-pattern reincarnated as a @property that DERIVES the label from a threshold — the
    # gate must anchor on the TruthStatus TYPE, not the field name, and must NOT report "vacuous".
    src = _HEAD + (
        "@dataclass(frozen=True)\n"
        "class RS:\n"
        "    t: float = 0.9\n"
        "    @property\n"
        "    def truth_status(self):\n"
        "        return TruthStatus.EXHAUSTIVE if self.t >= 0.9 else TruthStatus.SUGGESTIVE\n"
    )
    r = truth_status_is_constant_per_engine([_mod(tmp_path, "prop", src)])
    assert not r.ok and "vacuous" not in r.detail


def test_a_status_under_another_field_name_fires(tmp_path: Path) -> None:
    src = _HEAD + (
        "@dataclass(frozen=True)\n"
        "class RS:\n"
        "    completeness: TruthStatus = TruthStatus.EXHAUSTIVE\n"   # init-able, another name
    )
    r = truth_status_is_constant_per_engine([_mod(tmp_path, "altname", src)])
    assert not r.ok and "vacuous" not in r.detail


def test_a_plain_assign_conditional_status_fires(tmp_path: Path) -> None:
    src = _HEAD + (
        "FLAG = True\n"
        "@dataclass(frozen=True)\n"
        "class RS:\n"
        "    truth_status = TruthStatus.EXHAUSTIVE if FLAG else TruthStatus.SUGGESTIVE\n"
    )
    r = truth_status_is_constant_per_engine([_mod(tmp_path, "plainif", src)])
    assert not r.ok


def test_a_setattr_relabel_fires(tmp_path: Path) -> None:
    src = _HEAD + (
        "@dataclass(frozen=True)\n"
        "class RS:\n"
        "    truth_status: TruthStatus = field(default=TruthStatus.SUGGESTIVE, init=False)\n"
        "    def __post_init__(self):\n"
        "        object.__setattr__(self, 'truth_status', TruthStatus.EXHAUSTIVE)\n"
    )
    r = truth_status_is_constant_per_engine([_mod(tmp_path, "setattr", src)])
    assert not r.ok


def test_a_suggestive_type_carrying_a_denominator_field_fires(tmp_path: Path) -> None:
    # A suggestive set can never express completeness (AD-20) — a denominator-shaped field on a
    # SUGGESTIVE type fires, even under a compound name a plain denylist would miss.
    src = _HEAD + (
        "@dataclass(frozen=True)\n"
        "class RS:\n"
        "    total_in_corpus: int = 0\n"
        "    truth_status: TruthStatus = field(default=TruthStatus.SUGGESTIVE, init=False)\n"
    )
    r = truth_status_is_constant_per_engine([_mod(tmp_path, "denom", src)])
    assert not r.ok


def test_an_aliased_truthstatus_constant_passes(tmp_path: Path) -> None:
    # An aliased import must not false-positive (LOW-4) — reading a member is always safe.
    src = (
        "from dataclasses import dataclass, field\n"
        "from enum import Enum\n"
        "class TruthStatus(Enum):\n    SUGGESTIVE='s'\n    EXHAUSTIVE='e'\n"
        "TS = TruthStatus\n"
        "@dataclass(frozen=True)\n"
        "class RS:\n"
        "    truth_status: TruthStatus = field(default=TS.SUGGESTIVE, init=False)\n"
    )
    r = truth_status_is_constant_per_engine([_mod(tmp_path, "alias", src)])
    assert r.ok


def test_it_is_vacuous_when_no_result_set_type_exists(tmp_path: Path) -> None:
    r = truth_status_is_constant_per_engine([_mod(tmp_path, "plain", "X = 1\n")])
    assert r.ok and "vacuous" in r.detail


def test_the_real_tree_passes_suggestive_is_a_constant_site() -> None:
    r = truth_status_is_constant_per_engine()
    assert r.ok


def test_it_fails_closed_on_an_unparseable_file(tmp_path: Path) -> None:
    r = truth_status_is_constant_per_engine([_mod(tmp_path, "broken", "def (:\n")])
    assert not r.ok
