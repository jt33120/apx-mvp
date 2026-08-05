"""The ranked-order-ignores-the-label gate (Story 4.5, FR-40/FR-43/AD-39): the modules that compute
the ranked order must not import or reference the taxonomy-label axis — a label can never be an
ordering input, so it never moves a pièce or the line. Passes the real tree; fires on a fixture that
wires the label into the order; fails closed."""

from __future__ import annotations

from pathlib import Path

from apx.checks.label_not_a_ranking_input import ranking_order_ignores_the_taxonomy_label


def _file(tmp_path: Path, name: str, src: str) -> Path:
    p = tmp_path / name
    p.write_text(src, encoding="utf-8")
    return p


def test_passes_the_real_ranking_modules() -> None:
    assert ranking_order_ignores_the_taxonomy_label().ok


def test_a_clean_module_passes(tmp_path: Path) -> None:
    src = "def rank(rows):\n    return sorted(rows)\n"
    assert ranking_order_ignores_the_taxonomy_label([_file(tmp_path, "clean.py", src)]).ok


def test_fires_on_an_import_of_the_label_module(tmp_path: Path) -> None:
    src = ("from apx.core.domain.taxonomy_label import current_label\n"
           "def rank(rows):\n    return sorted(rows, key=current_label)\n")
    r = ranking_order_ignores_the_taxonomy_label([_file(tmp_path, "bad.py", src)])
    assert not r.ok and "taxonomy_label" in r.detail


def test_fires_on_a_reference_to_the_label_table(tmp_path: Path) -> None:
    src = "def rank(s):\n    return s.query(TaxonomyLabelEntry).all()\n"
    r = ranking_order_ignores_the_taxonomy_label([_file(tmp_path, "bad2.py", src)])
    assert not r.ok and "TaxonomyLabelEntry" in r.detail


def test_fails_closed_on_an_unparseable_file(tmp_path: Path) -> None:
    r = ranking_order_ignores_the_taxonomy_label([_file(tmp_path, "broken.py", "def (:\n")])
    assert not r.ok and "cannot parse" in r.detail
