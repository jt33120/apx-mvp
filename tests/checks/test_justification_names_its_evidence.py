"""The FR-41 gate (Story 4.6): the Justification value object is built only in justification.py, so
its named-evidence invariant cannot be bypassed. Passes the real tree; fires on a construction
elsewhere; fails closed on an unparseable file."""

from __future__ import annotations

from pathlib import Path

from apx.checks.justification_names_its_evidence import justification_names_its_evidence


def _mod(tmp_path: Path, name: str, src: str) -> Path:
    d = tmp_path / name
    d.mkdir()
    p = d / f"{name}.py"
    p.write_text(src, encoding="utf-8")
    return p


def test_passes_the_real_tree() -> None:
    assert justification_names_its_evidence().ok


def test_fires_on_a_construction_outside_the_owning_module(tmp_path: Path) -> None:
    src = "def sneaky():\n    return Justification(piece_id='p', sentence='fluent', evidence=())\n"
    r = justification_names_its_evidence([_mod(tmp_path, "leak", src)])
    assert not r.ok and "outside justification.py" in r.detail


def test_fails_closed_on_an_unparseable_file(tmp_path: Path) -> None:
    r = justification_names_its_evidence([_mod(tmp_path, "broken", "def (:\n")])
    assert not r.ok and ("cannot parse" in r.detail or "failing closed" in r.detail)


# ── the SECOND leg (the review's confirmed finding): the write seam re-runs the invariant ─────────
def _store(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "store.py"
    p.write_text(
        "class SqlStore:\n"
        "    def record_justification(self, *, tenant, sentence, basis, evidence, scopes):\n"
        f"{body}",
        encoding="utf-8")
    return p


def test_fires_when_the_write_seam_does_not_validate(tmp_path: Path) -> None:
    # a write that persists without re-running the invariant can commit a row the READ path cannot
    # rebuild — unreadable forever (write-once, AD-7 forbids a delete).
    body = "        session.add(PieceJustification(sentence=sentence))\n"
    r = justification_names_its_evidence(None, _store(tmp_path, body))
    assert not r.ok and "validate_named_evidence" in r.detail


def test_passes_when_the_write_seam_validates(tmp_path: Path) -> None:
    body = ("        validate_named_evidence(sentence, basis, evidence)\n"
            "        session.add(PieceJustification(sentence=sentence))\n")
    assert justification_names_its_evidence(None, _store(tmp_path, body)).ok


def test_fires_when_the_write_seam_is_missing(tmp_path: Path) -> None:
    p = tmp_path / "store.py"
    p.write_text("class SqlStore:\n    pass\n", encoding="utf-8")
    r = justification_names_its_evidence(None, p)
    assert not r.ok and "record_justification" in r.detail
