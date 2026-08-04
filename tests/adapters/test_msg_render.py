"""The `.msg` renderer (Story 3.5c-3): headers + body + attachment names → SANITISED inline HTML via
the GPL-isolated worker (mocked at `_run_msg_worker`). Adversarial fields are neutralised; a
non-.msg name or any worker failure offers the original (`None`), never a raise."""

from __future__ import annotations

import pytest

from apx.adapters.extraction import msg as msgmod
from apx.adapters.render_html.msg import MsgRenderer


def _worker(monkeypatch: pytest.MonkeyPatch, result: object) -> None:
    monkeypatch.setattr(msgmod, "_run_msg_worker", lambda p, m: result)


def test_renders_headers_body_and_attachment_names(monkeypatch: pytest.MonkeyPatch) -> None:
    _worker(monkeypatch, {"ok": True, "from": "a@b.fr", "to": "c@d.fr", "date": "2021-03-03",
                          "subject": "Sinistre", "body": "Bonjour Maître,\nvoir pièce jointe.",
                          "attachments": ["rapport.pdf"]})
    doc = MsgRenderer().render(filename="mail.msg", data=b"...")
    assert doc is not None and doc.format == "html" and doc.title == "Sinistre"  # subject = title
    assert "a@b.fr" in doc.html and "Sinistre" in doc.html and "Bonjour Maître" in doc.html
    assert "<br>" in doc.html                          # a body newline is preserved
    assert "rapport.pdf" in doc.html                   # the attachment NAME is listed
    assert "<script" not in doc.html.lower()


def test_adversarial_headers_and_body_are_neutralised(monkeypatch: pytest.MonkeyPatch) -> None:
    _worker(monkeypatch, {"ok": True, "from": "<script>alert(1)</script>@x",
                          "subject": "<img src=x onerror=y()>",
                          "body": "<iframe src=//evil></iframe> corps",
                          "attachments": ["<b onclick=z>a.pdf</b>"]})
    doc = MsgRenderer().render(filename="evil.msg", data=b"...")
    assert doc is not None
    low = doc.html.lower()
    # no LIVE tag from any field (escaped inert text may still carry the word "onerror"/"onclick")
    for live in ("<script", "<img", "<iframe"):
        assert live not in low
    assert "&lt;script&gt;" in low                      # the field was escaped to inert text


def test_a_non_msg_offers_the_original() -> None:
    assert MsgRenderer().render(filename="x.docx", data=b"...") is None   # not this format


def test_a_worker_failure_offers_the_original(monkeypatch: pytest.MonkeyPatch) -> None:
    _worker(monkeypatch, None)                          # crash / timeout / unreadable
    assert MsgRenderer().render(filename="m.msg", data=b"...") is None


def test_an_empty_msg_offers_the_original(monkeypatch: pytest.MonkeyPatch) -> None:
    _worker(monkeypatch, {"ok": False, "error_class": "extracted-empty"})
    assert MsgRenderer().render(filename="m.msg", data=b"...") is None


def test_a_long_body_is_truncated_not_dropped(monkeypatch: pytest.MonkeyPatch) -> None:
    _worker(monkeypatch, {"ok": True, "subject": "S", "body": "x" * 100, "attachments": []})
    doc = MsgRenderer(max_body_chars=10).render(filename="m.msg", data=b"...")
    assert doc is not None and doc.truncated is True    # honest, never a silent drop


def test_fails_closed_to_none_when_the_sanitiser_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    # a missing/erroring nh3 must fail CLOSED to None (offer the original), never a raise/500 — the
    # renderer-level guard mirrors _docx/_xlsx (review: it previously caught only OSError).
    _worker(monkeypatch, {"ok": True, "subject": "S", "body": "corps", "attachments": []})
    import nh3

    def _boom(*args: object, **kwargs: object) -> None:
        raise RuntimeError("nh3 down")

    monkeypatch.setattr(nh3, "clean", _boom)
    assert MsgRenderer().render(filename="m.msg", data=b"...") is None


def test_structured_msg_wrapper(monkeypatch: pytest.MonkeyPatch, tmp_path: object) -> None:
    from pathlib import Path

    from apx.adapters.extraction.msg import structured_msg
    assert structured_msg(Path("x.pdf")) is None                          # the non-.msg guard
    monkeypatch.setattr(msgmod, "_run_msg_worker", lambda p, m: {"ok": True, "from": "a@b.fr"})
    assert structured_msg(Path("m.msg")) == {"ok": True, "from": "a@b.fr"}   # ok → the dict
    monkeypatch.setattr(msgmod, "_run_msg_worker", lambda p, m: {"ok": False, "error_class": "x"})
    assert structured_msg(Path("m.msg")) is None                          # not-ok → None
    monkeypatch.setattr(msgmod, "_run_msg_worker", lambda p, m: None)
    assert structured_msg(Path("m.msg")) is None                          # worker failure → None


def test_spool_dir_prefers_the_encrypted_data_volume(
        monkeypatch: pytest.MonkeyPatch, tmp_path: object) -> None:
    import tempfile

    from apx.adapters.spool import spool_dir
    monkeypatch.setenv("APX_DATA_PATH", str(tmp_path))
    assert spool_dir() == str(tmp_path)                   # decrypted plaintext stays on the volume
    monkeypatch.delenv("APX_DATA_PATH", raising=False)
    assert spool_dir() == tempfile.gettempdir()           # dev/test fallback only
