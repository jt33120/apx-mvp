"""AD-38 (Story 2.7): the two inventory-record structural properties — green on the shipped tree,
firing on a wrong field set and on a forbidden sum, and failing closed on an unparseable file."""

from __future__ import annotations

from pathlib import Path

from apx.checks.inventory_record import (
    inventory_record_fields_enumerated,
    unknown_cardinality_never_summed,
)

_FX = Path(__file__).resolve().parents[1] / "_fixtures" / "structural_violations"


# ── (A) the six-field record shape ──────────────────────────────────────────────────────────────

def test_field_check_is_green_on_the_real_tree() -> None:
    assert inventory_record_fields_enumerated().ok


def test_field_check_fires_on_a_wrong_field_set() -> None:
    result = inventory_record_fields_enumerated(
        _FX / "inventory_record_fields" / "wrong_inventory.py")
    assert not result.ok and "retired" in result.detail  # the missing field is named


def test_field_check_fails_closed_on_an_unparseable_file(tmp_path: Path) -> None:
    bad = tmp_path / "broken.py"
    bad.write_text("class Inventory(  # unclosed\n", encoding="utf-8")
    result = inventory_record_fields_enumerated(bad)
    assert not result.ok and "parse" in result.detail


# ── (B) the unknown cardinality (and the other outside-the-identity counts) is never summed ──────

def test_sum_check_is_green_on_the_real_tree() -> None:
    assert unknown_cardinality_never_summed().ok


def test_sum_check_fires_on_a_forbidden_sum() -> None:
    result = unknown_cardinality_never_summed([_FX / "unknown_summed"])
    assert not result.ok and "summed" in result.detail


def test_sum_check_fires_on_a_builtin_sum_call() -> None:
    # AD-38 forbids `sum([... unknown ...])` (the builtin-total idiom) as much as `+`.
    result = unknown_cardinality_never_summed([_FX / "unknown_summed_builtin"])
    assert not result.ok and "summed" in result.detail


def test_sum_check_does_not_flag_a_bare_retired_local() -> None:
    # `retired` is a common word — a bare `active + retired` local must NOT false-positive; only an
    # attribute `x.retired` (or the two distinctive names as bare names) is flagged.
    import tempfile
    from pathlib import Path as _Path
    with tempfile.TemporaryDirectory() as d:
        (_Path(d) / "unrelated.py").write_text(
            "def f(active, retired):\n    return active + retired\n", encoding="utf-8")
        assert unknown_cardinality_never_summed([_Path(d)]).ok


def test_sum_check_fails_closed_on_an_unparseable_file(tmp_path: Path) -> None:
    (tmp_path / "broken.py").write_text("def f(:\n    pass\n", encoding="utf-8")
    result = unknown_cardinality_never_summed([tmp_path])
    assert not result.ok and "parse" in result.detail
