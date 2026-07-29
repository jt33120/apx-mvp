"""`.msg` extraction (story 2.3, AD-28) at three honest layers, because a valid Outlook
compound file cannot be synthesised from the standard library:

1. the worker's TRANSFORM logic (`_text`) against a duck-typed fake message — headers, the
   inline reply chain, empty → `extracted-empty` — with no `extract_msg` and no real `.msg`;
2. the ADAPTER's mapping of a worker result to an `ExtractOutcome`, with the out-of-process
   call mocked, so crash/timeout/garbage → `unreadable` is decided deterministically;
3. a REAL subprocess spawn on a MALFORMED `.msg`, proving crash isolation (AC6) and that no
   document byte leaks out of the boundary (AC8) — the highest-value integration we can run
   without a valid fixture.
"""

from __future__ import annotations

import logging
from pathlib import Path
from types import SimpleNamespace

import pytest

from apx.adapters.expansion.composite import CompositeExpander
from apx.adapters.extraction import msg as msgmod
from apx.adapters.extraction.composite import CompositeExtractor
from apx.adapters.extraction.files import FileExtractor
from apx.adapters.extraction.msg import MsgExpander, MsgExtractor
from apx.adapters.extraction.msg_worker import _text
from apx.core.app.ingest import ingest_folder
from apx.core.domain.failures import ErrorClass


# ── layer 1: the worker transform, against a fake message object ──────────────────────────────
def test_worker_text_builds_routing_headers_and_keeps_the_reply_chain() -> None:
    fake = SimpleNamespace(
        sender="avocat@cabinet.fr", to="client@x.fr", cc=None, date="2021-03-03",
        subject="Sinistre du 3 mars",
        body="Bonjour Maître,\n\n> Le 2 mars, client a écrit :\n> message précédent")
    out = _text(fake)
    assert out["ok"] and out["method"] == "extract-msg" and out["version"]
    assert "From: avocat@cabinet.fr" in out["text"] and "Subject: Sinistre du 3 mars" in out["text"]
    assert "Date: 2021-03-03" in out["text"] and "Cc:" not in out["text"]   # empty header dropped
    assert "message précédent" in out["text"]        # the quoted reply chain is preserved inline


def test_worker_text_empty_message_is_extracted_empty() -> None:
    fake = SimpleNamespace(sender=None, to=None, cc=None, date=None, subject=None, body="")
    assert _text(fake) == {"ok": False, "error_class": "extracted-empty"}


# ── layer 2: the adapter maps a (mocked) worker result to an ExtractOutcome ───────────────────
def test_extractor_rejects_non_msg_as_unsupported(tmp_path: Path) -> None:
    assert MsgExtractor().extract(tmp_path / "x.pdf").error_class is ErrorClass.UNSUPPORTED_FORMAT


def test_extractor_maps_a_successful_parse(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(msgmod, "_run_msg_worker", lambda p, m: {
        "ok": True, "text": "corps du message", "method": "extract-msg",
        "version": "extract-msg/0.56.0"})
    out = MsgExtractor().extract(tmp_path / "m.msg")
    assert out.ok and out.text == "corps du message" and out.method == "extract-msg"
    assert out.version == "extract-msg/0.56.0"       # extractor version recorded (AC3)


def test_extractor_maps_extracted_empty(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(msgmod, "_run_msg_worker",
                        lambda p, m: {"ok": False, "error_class": "extracted-empty"})
    out = MsgExtractor().extract(tmp_path / "m.msg")
    assert not out.ok and out.error_class is ErrorClass.EXTRACTED_EMPTY   # not in corpus (AC5)


def test_extractor_worker_failure_is_unreadable(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # A crash, a timeout, or unparseable output all surface from _run_msg_worker as None.
    monkeypatch.setattr(msgmod, "_run_msg_worker", lambda p, m: None)
    out = MsgExtractor().extract(tmp_path / "m.msg")
    assert not out.ok and out.error_class is ErrorClass.UNREADABLE


def test_a_missing_msg_is_unreadable_not_corrupt_file(tmp_path: Path) -> None:
    pytest.importorskip("extract_msg")
    # a .msg that vanished between enumeration and processing (FileNotFoundError in the worker) is
    # `unreadable`, NOT `corrupt-file` — a missing file is not a damaged one (review MED); only an
    # invalid compound file (InvalidFileFormatError) is corrupt-file.
    out = MsgExtractor().extract(tmp_path / "gone.msg")
    assert not out.ok and out.error_class is ErrorClass.UNREADABLE


# ── layer 3: a REAL subprocess on a malformed .msg — crash isolation + no leak ────────────────
def test_a_malformed_msg_is_a_failure_not_a_worker_death(tmp_path: Path) -> None:
    pytest.importorskip("extract_msg")               # the parser-failure path needs the parser
    p = tmp_path / "casse.msg"
    p.write_bytes(b"this is not an OLE compound file at all")
    out = MsgExtractor().extract(p)                  # spawns the real out-of-process worker
    # a file that is not a valid compound file at all is `corrupt-file`, not merely `unreadable`
    # (Story 2.12/FR-54 sharpened the class); still mapped cleanly out-of-process, never a raise
    assert not out.ok and out.error_class is ErrorClass.CORRUPT_FILE


def test_a_malformed_msg_never_leaks_its_bytes_out_of_the_boundary(tmp_path: Path) -> None:
    # AD-28 I/O discipline: the parser emits document fragments on stderr for malformed input;
    # the adapter discards them. A seeded token in the file must not surface in the outcome.
    pytest.importorskip("extract_msg")
    seed = "SEEDED-TOKEN-b7f3c9e1"
    p = tmp_path / "fuite.msg"
    p.write_bytes(f"garbage {seed} garbage".encode())
    out = MsgExtractor().extract(p)
    assert not out.ok and seed not in (out.text or "")   # no document byte reaches the outcome


def test_a_malformed_msg_leaks_no_seeded_token_into_the_register_or_a_log(
        tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    # AC8 end-to-end: ingest a seeded, malformed .msg; the failure it produces carries no document
    # text in its register detail, and nothing is logged carrying the token (AD-28 I/O discipline).
    pytest.importorskip("extract_msg")
    seed = "SEEDED-TOKEN-9f2a51"
    (tmp_path / "fuite.msg").write_bytes(f"garbage {seed} garbage".encode())
    extractor = CompositeExtractor([MsgExtractor(), FileExtractor()])
    expander = CompositeExpander([MsgExpander()])
    with caplog.at_level(logging.DEBUG):
        result = ingest_folder(tmp_path, matter="m", tenant="t", extractor=extractor,
                               expander=expander)
    assert result.inventory.open_register_entries == 1 and result.inventory.in_corpus == 0  # kept
    failure = result.failures[0]
    assert failure.error_class is ErrorClass.CORRUPT_FILE   # an unopenable compound file (2.12)
    assert seed not in (failure.detail or "")            # no document byte in the register detail
    assert seed not in caplog.text                       # nor in any emitted log


def test_the_child_subprocess_stderr_never_reaches_the_parent_fd(
        tmp_path: Path, capfd: pytest.CaptureFixture[str]) -> None:
    # AC8 lock at the file-descriptor level: capfd captures the CHILD's fd1/fd2. With
    # capture_output=True the child's streams are PIPEs, never the parent's fds, so a seeded token
    # in a malformed .msg reaches neither. A mutation that inherited stderr would put the parser's
    # document fragments on the parent fd2 and fail this — which .detail/caplog tests cannot see.
    pytest.importorskip("extract_msg")
    seed = "SEEDED-FD-LEAK-4c8e17"
    p = tmp_path / "fuite.msg"
    p.write_bytes(f"garbage {seed} garbage".encode())
    MsgExtractor().extract(p)
    captured = capfd.readouterr()
    assert seed not in captured.err and seed not in captured.out


def test_a_worker_that_exceeds_the_timeout_is_unreadable_not_an_outage(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # AC6's "worker that exceeds the timeout" half (the malformed-.msg half is the real-subprocess
    # test above): a genuine subprocess.TimeoutExpired must map to unreadable, never raise.
    import subprocess

    def _raise_timeout(*args: object, **kwargs: object) -> None:
        raise subprocess.TimeoutExpired(cmd="msg_worker", timeout=0.01)

    monkeypatch.setattr(msgmod.subprocess, "run", _raise_timeout)
    p = tmp_path / "lent.msg"
    p.write_bytes(b"placeholder; subprocess.run is patched to time out")
    out = MsgExtractor().extract(p)
    assert not out.ok and out.error_class is ErrorClass.UNREADABLE
