"""The FR-11/FR-41 gate (Story 4.6): the justification read seam containment-verifies every extract
at show time — read_justification references both resolve_chunk and verify_justification. Passes the
real store; fires on a read seam that skips either; fails closed on a missing/unparseable file."""

from __future__ import annotations

from pathlib import Path

from apx.checks.justification_verified_at_show_time import justification_verified_at_show_time


def _store(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "store.py"
    p.write_text(
        "class SqlStore:\n"
        "    def read_justification(self, *, tenant, matter, scopes, piece_id):\n"
        f"{body}",
        encoding="utf-8")
    return p


def test_passes_the_real_store() -> None:
    assert justification_verified_at_show_time().ok


def test_fires_when_the_read_skips_the_resolver(tmp_path: Path) -> None:
    # a read that returns evidence WITHOUT resolve_chunk could show an unresolved extract as normal
    body = "        return verify_justification(j, lambda c, q: None)\n"
    r = justification_verified_at_show_time(_store(tmp_path, body))
    assert not r.ok and "resolve_chunk" in r.detail


def test_fires_when_the_read_skips_the_verifier(tmp_path: Path) -> None:
    body = "        return self.resolve_chunk(piece_id, tenant, scopes)\n"
    r = justification_verified_at_show_time(_store(tmp_path, body))
    assert not r.ok and "verify_justification" in r.detail


def test_fires_when_there_is_no_read_seam(tmp_path: Path) -> None:
    p = tmp_path / "store.py"
    p.write_text("class SqlStore:\n    pass\n", encoding="utf-8")
    r = justification_verified_at_show_time(p)
    assert not r.ok and "read_justification" in r.detail


def test_fails_closed_on_a_missing_file(tmp_path: Path) -> None:
    r = justification_verified_at_show_time(tmp_path / "nope.py")
    assert not r.ok
