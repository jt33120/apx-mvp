"""The confidence-one-derivation gate (Story 4.4, FR-42): the per-pièce confidence is built by one
implementation — a ``Confidence(...)`` construction outside ``core/domain/piece_confidence.py`` is a
second derivation and fails the build. Passes the real tree; fires on a fixture; fails closed."""

from __future__ import annotations

from pathlib import Path

from apx.checks.confidence_derivation import confidence_has_one_derivation


def _mod(tmp_path: Path, name: str, src: str) -> Path:
    d = tmp_path / name
    d.mkdir()
    (d / f"{name}.py").write_text(src, encoding="utf-8")
    return d


def test_passes_the_real_tree() -> None:
    assert confidence_has_one_derivation().ok


def test_fires_on_a_second_confidence_construction(tmp_path: Path) -> None:
    src = ("def sneaky():\n"
           "    return Confidence(value=0.99, signals=('made-up',))\n")
    r = confidence_has_one_derivation([_mod(tmp_path, "sneaky", src)])
    assert not r.ok and "second" in r.detail.lower()


def test_a_mere_call_to_derive_confidence_is_not_flagged(tmp_path: Path) -> None:
    # a CALLER (like ranking.rank_cascade) invokes derive_confidence — it never constructs
    # Confidence
    src = ("def caller(j, cfg):\n"
           "    return derive_confidence(j, cfg)\n")
    r = confidence_has_one_derivation([_mod(tmp_path, "caller", src)])
    assert r.ok


def test_fails_closed_on_an_unparseable_file(tmp_path: Path) -> None:
    d = tmp_path / "broken"
    d.mkdir()
    (d / "broken.py").write_text("def (:\n", encoding="utf-8")
    r = confidence_has_one_derivation([d])
    assert not r.ok and "cannot parse" in r.detail
