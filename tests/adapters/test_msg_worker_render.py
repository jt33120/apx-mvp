"""The `.msg` worker's `render` transform (Story 3.5c-3): structured routing headers + body + the
attachment NAMES from a duck-typed fake message — no `extract_msg`, no real `.msg` — and an empty
message → `extracted-empty`. Attachment bytes NEVER cross into the render result (AC2)."""

from __future__ import annotations

import sys
import types
from types import SimpleNamespace

import pytest

from apx.adapters.extraction.msg_worker import _render, run


def test_render_returns_structured_headers_body_and_attachment_names() -> None:
    fake = SimpleNamespace(
        sender="avocat@cabinet.fr", to="client@x.fr", cc=None, date="2021-03-03",
        subject="Sinistre du 3 mars",
        body="Bonjour Maître,\n\n> Le 2 mars, client a écrit :\n> message précédent",
        attachments=[SimpleNamespace(longFilename="rapport.pdf", shortFilename=None),
                     SimpleNamespace(longFilename=None, shortFilename="annexe.xlsx")])
    out = _render(fake)
    assert out["ok"] and out["method"] == "extract-msg" and out["version"]
    assert out["from"] == "avocat@cabinet.fr" and out["subject"] == "Sinistre du 3 mars"
    assert out["date"] == "2021-03-03" and "cc" not in out          # an empty header is dropped
    assert "message précédent" in out["body"]                        # the reply chain stays inline
    assert out["attachments"] == ["rapport.pdf", "annexe.xlsx"]      # NAMES only


def test_render_empty_message_is_extracted_empty() -> None:
    fake = SimpleNamespace(sender=None, to=None, cc=None, date=None, subject=None,
                           body="", attachments=[])
    assert _render(fake) == {"ok": False, "error_class": "extracted-empty"}


def test_render_carries_no_attachment_bytes() -> None:
    # a .msg render lists attachment NAMES, never their bytes — attachments are their own pièces
    fake = SimpleNamespace(
        sender="a@b.fr", to=None, cc=None, date=None, subject="S", body="corps",
        attachments=[SimpleNamespace(longFilename="secret.pdf", shortFilename=None,
                                     data=b"CONFIDENTIAL BYTES")])
    out = _render(fake)
    assert out["attachments"] == ["secret.pdf"]
    assert "CONFIDENTIAL BYTES" not in str(out)   # attachment bytes never enter the render process


def test_run_dispatches_the_render_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    # `run("render", path)` dispatches to _render — inject a fake extract_msg (a valid .msg cannot
    # be synthesised from stdlib), so the new dispatch line runs — not just the _render transform.
    fake_msg = SimpleNamespace(sender="a@b.fr", to=None, cc=None, date=None, subject="Objet",
                               body="corps", attachments=[], close=lambda: None)
    exceptions = types.SimpleNamespace(InvalidFileFormatError=type("IFFE", (Exception,), {}))
    fake = types.SimpleNamespace(openMsg=lambda p: fake_msg, exceptions=exceptions)
    monkeypatch.setitem(sys.modules, "extract_msg", fake)
    monkeypatch.setitem(sys.modules, "extract_msg.exceptions", exceptions)
    out = run("render", "whatever.msg")
    assert out["ok"] and out["from"] == "a@b.fr" and out["subject"] == "Objet"


def test_run_unknown_mode_is_unreadable(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_msg = SimpleNamespace(close=lambda: None)
    exceptions = types.SimpleNamespace(InvalidFileFormatError=type("IFFE", (Exception,), {}))
    fake = types.SimpleNamespace(openMsg=lambda p: fake_msg, exceptions=exceptions)
    monkeypatch.setitem(sys.modules, "extract_msg", fake)
    monkeypatch.setitem(sys.modules, "extract_msg.exceptions", exceptions)
    assert run("bogus", "x.msg") == {"ok": False, "error_class": "unreadable"}
