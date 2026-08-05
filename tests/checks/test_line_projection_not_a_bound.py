"""The FR-19/§0.2 gate (Story 4.9): the priced projection module never depends on the sampling
bound. Passes the real tree; fires on a fixture that imports/references it; fails closed."""

from __future__ import annotations

from pathlib import Path

from apx.checks.line_projection_not_a_bound import line_projection_is_not_a_sampling_bound


def _mod(tmp_path: Path, name: str, src: str) -> Path:
    d = tmp_path / name
    d.mkdir()
    p = d / f"{name}.py"
    p.write_text(src, encoding="utf-8")
    return p


def test_passes_the_real_tree() -> None:
    assert line_projection_is_not_a_sampling_bound().ok


def test_fires_on_an_import_of_the_bound_module(tmp_path: Path) -> None:
    src = ("from apx.core.domain.confidence import prevalence_upper_bound\n"
           "def bad(xs):\n    return prevalence_upper_bound(xs)\n")
    r = line_projection_is_not_a_sampling_bound([_mod(tmp_path, "leak", src)])
    assert not r.ok and "sampling bound" in r.detail


def test_fires_on_a_reference_without_a_direct_import(tmp_path: Path) -> None:
    src = "def bad(conf):\n    return conf.prevalence_upper_bound(0.95)\n"
    r = line_projection_is_not_a_sampling_bound([_mod(tmp_path, "ref", src)])
    assert not r.ok and "references prevalence_upper_bound" in r.detail


def test_fails_closed_on_an_unparseable_file(tmp_path: Path) -> None:
    p = _mod(tmp_path, "broken", "def (:\n")
    r = line_projection_is_not_a_sampling_bound([p])
    assert not r.ok and ("cannot parse" in r.detail or "failing closed" in r.detail)
