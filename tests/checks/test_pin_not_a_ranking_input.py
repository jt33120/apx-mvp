"""The FR-43/AD-39 gate (Story 4.11): the ranked-order modules do not depend on the pin axis, so a
pin never reorders. Passes the real tree; fires on a fixture that references it; fails closed."""

from __future__ import annotations

from pathlib import Path

from apx.checks.pin_not_a_ranking_input import ranking_order_ignores_the_pin


def _mod(tmp_path: Path, name: str, src: str) -> Path:
    d = tmp_path / name
    d.mkdir()
    p = d / f"{name}.py"
    p.write_text(src, encoding="utf-8")
    return p


def test_passes_the_real_tree() -> None:
    assert ranking_order_ignores_the_pin().ok


def test_fires_on_an_import_of_the_pin_module(tmp_path: Path) -> None:
    src = "from apx.core.domain.pin import current_pins\ndef rank():\n    return current_pins([])\n"
    r = ranking_order_ignores_the_pin([_mod(tmp_path, "leak", src)])
    assert not r.ok and "pin axis" in r.detail


def test_fires_on_a_reference_to_the_pin_ledger(tmp_path: Path) -> None:
    src = "def rank(s):\n    return s.query(PinEntry).all()\n"
    r = ranking_order_ignores_the_pin([_mod(tmp_path, "ref", src)])
    assert not r.ok and "references PinEntry" in r.detail


def test_fails_closed_on_an_unparseable_file(tmp_path: Path) -> None:
    p = _mod(tmp_path, "broken", "def (:\n")
    r = ranking_order_ignores_the_pin([p])
    assert not r.ok and ("cannot parse" in r.detail or "failing closed" in r.detail)
