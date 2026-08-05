"""The triage-sets one-derivation gate (Story 4.7, FR-16/AD-39): a TriageSets(...) construction
outside core/domain/triage_sets.py is a second derivation of the retained/discarded view and fails
the build. Passes the real tree; fires on a fixture; fails closed."""

from __future__ import annotations

from pathlib import Path

from apx.checks.triage_sets_one_derivation import triage_sets_have_one_derivation

_CTOR = ("def bad():\n"
         "    return TriageSets(version_id='v', retained=(), discarded=(), unscored=(), "
         "pins_in_force=0, line_placed=False)\n")


def _mod(tmp_path: Path, name: str, src: str) -> Path:
    d = tmp_path / name
    d.mkdir()
    (d / f"{name}.py").write_text(src, encoding="utf-8")
    return d


def test_passes_the_real_tree() -> None:
    assert triage_sets_have_one_derivation().ok


def test_fires_on_a_construction_outside_the_owner(tmp_path: Path) -> None:
    r = triage_sets_have_one_derivation([_mod(tmp_path, "surface", _CTOR)])
    assert not r.ok and "outside triage_sets.py" in r.detail


def test_fails_closed_on_an_unparseable_file(tmp_path: Path) -> None:
    d = tmp_path / "broken"
    d.mkdir()
    (d / "broken.py").write_text("def (:\n", encoding="utf-8")
    r = triage_sets_have_one_derivation([d])
    assert not r.ok and "cannot parse" in r.detail
