"""Container expanders: .zip archives and .eml attachments (standard library only)."""

from __future__ import annotations

import zipfile
from email.message import EmailMessage
from pathlib import Path

from apx.adapters.expansion.archives import ZipExpander
from apx.adapters.expansion.composite import CompositeExpander
from apx.adapters.expansion.mail import EmlExpander


def test_zip_expander_lists_files_not_dirs(tmp_path: Path) -> None:
    z = tmp_path / "d.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("a.txt", "alpha")
        zf.writestr("sub/b.txt", "beta")
    members = dict(ZipExpander().members(z) or [])
    assert set(members) == {"a.txt", "sub/b.txt"}
    assert members["a.txt"] == b"alpha"


def test_zip_expander_ignores_non_zip(tmp_path: Path) -> None:
    (tmp_path / "x.txt").write_text("hi", encoding="utf-8")
    assert ZipExpander().members(tmp_path / "x.txt") is None


def _write_eml(path: Path, *, attach: bool) -> None:
    msg = EmailMessage()
    msg["Subject"] = "Test"
    msg["From"] = "a@b.fr"
    msg["To"] = "c@d.fr"
    msg.set_content("Le corps du message.")
    if attach:
        msg.add_attachment(b"donnees", maintype="application", subtype="octet-stream",
                           filename="piece.bin")
    path.write_bytes(msg.as_bytes())


def test_eml_expander_returns_attachments(tmp_path: Path) -> None:
    p = tmp_path / "m.eml"
    _write_eml(p, attach=True)
    assert EmlExpander().members(p) == [("piece.bin", b"donnees")]


def test_eml_without_attachments_is_empty(tmp_path: Path) -> None:
    p = tmp_path / "m.eml"
    _write_eml(p, attach=False)
    assert EmlExpander().members(p) == []  # recognised container, no members


def test_composite_delegates_to_the_first_that_claims_it(tmp_path: Path) -> None:
    z = tmp_path / "d.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("a.txt", "x")
    (tmp_path / "n.txt").write_text("plain", encoding="utf-8")
    comp = CompositeExpander([ZipExpander(), EmlExpander()])
    assert comp.members(z) is not None                 # the zip expander claims it
    assert comp.members(tmp_path / "n.txt") is None     # a .txt is nobody's container
