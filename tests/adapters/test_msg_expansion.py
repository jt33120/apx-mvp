"""`.msg` attachment expansion (stories 2.3/2.4, AD-28/AC2/FR-57): the worker's `_attachments`
transform against a fake message, the `MsgExpander` mapping with the out-of-process call mocked, the
N+1 / custodian / provenance guarantee through the real ingestion use case, and — Story 2.4 —
nested `.msg`-in-`.msg`: an embedded message is serialised back to `.msg` bytes and recursed into
(its own attachments become grandchildren), never skipped, never silently dropped.
"""

from __future__ import annotations

import base64
from pathlib import Path
from types import SimpleNamespace

import pytest

from apx.adapters.expansion.composite import CompositeExpander
from apx.adapters.extraction import msg as msgmod
from apx.adapters.extraction.composite import CompositeExtractor
from apx.adapters.extraction.files import FileExtractor
from apx.adapters.extraction.msg import MsgExpander, MsgExtractor
from apx.adapters.extraction.msg_worker import _attachments
from apx.core.app.ingest import ingest_folder


# ── layer 1: the worker _attachments transform, against fake attachments ──────────────────────
def test_worker_attachments_returns_byte_payloads_with_names() -> None:
    att1 = SimpleNamespace(data=b"PDF bytes", longFilename="rapport.pdf", shortFilename=None)
    att2 = SimpleNamespace(data=b"note bytes", longFilename=None, shortFilename="note.txt")
    out = _attachments(SimpleNamespace(attachments=[att1, att2]))
    assert out["ok"] and [a["name"] for a in out["attachments"]] == ["rapport.pdf", "note.txt"]
    assert base64.b64decode(out["attachments"][0]["b64"]) == b"PDF bytes"


def test_worker_attachments_surfaces_an_embedded_message_as_a_msg_member(tmp_path: Path) -> None:
    # Story 2.4 un-defers nested .msg: an embedded message (data is a Message, not bytes) is
    # serialised back to .msg bytes via extract-msg's save() so ingestion recurses into it. The fake
    # models the REAL contract: extract-msg's save writes a top-level .msg ONLY with
    # extractEmbedded=True (else a text-export subfolder) — so the assert locks that kwarg in.
    def _save(customPath: str | None = None, extractEmbedded: bool = False, **kw: object) -> None:
        assert extractEmbedded is True, "the worker must pass extractEmbedded=True"
        (Path(customPath) / "inner.msg").write_bytes(b"EMBEDDED-MSG-BYTES")

    embedded = SimpleNamespace(data=SimpleNamespace(subject="nested"), longFilename="courrier",
                               shortFilename=None, save=_save)
    real = SimpleNamespace(data=b"x", longFilename="a.txt", shortFilename=None)
    out = _attachments(SimpleNamespace(attachments=[embedded, real]))
    assert [a["name"] for a in out["attachments"]] == ["courrier.msg", "a.txt"]  # .msg member added
    assert base64.b64decode(out["attachments"][0]["b64"]) == b"EMBEDDED-MSG-BYTES"


def test_worker_never_silently_drops_an_unserialisable_embedded_message() -> None:
    # If extract-msg cannot serialise the embedded message (no save path here), it is surfaced with
    # empty bytes — ingestion records that member as a failure, never a silent drop.
    embedded = SimpleNamespace(
        data=SimpleNamespace(subject="x"), longFilename="inner.msg", shortFilename=None)
    out = _attachments(SimpleNamespace(attachments=[embedded]))
    assert out["attachments"][0]["name"] == "inner.msg" and out["attachments"][0]["b64"] == ""


# ── layer 2: MsgExpander maps a (mocked) worker result ────────────────────────────────────────
def test_expander_ignores_non_msg(tmp_path: Path) -> None:
    assert MsgExpander().members(tmp_path / "archive.zip") is None


def test_expander_returns_decoded_members(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(msgmod, "_run_msg_worker", lambda p, m: {"ok": True, "attachments": [
        {"name": "a.txt", "b64": base64.b64encode(b"lettre").decode("ascii")}]})
    assert MsgExpander().members(tmp_path / "m.msg") == [("a.txt", b"lettre")]


def test_expander_with_no_attachments_returns_none(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # zero attachments → None so the .msg is a leaf: its body is a piece, or an empty .msg is
    # extracted-empty via the extractor — never a vanished transparent-empty container (AC5).
    monkeypatch.setattr(msgmod, "_run_msg_worker", lambda p, m: {"ok": True, "attachments": []})
    assert MsgExpander().members(tmp_path / "m.msg") is None


def test_expander_on_a_broken_msg_returns_none(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(msgmod, "_run_msg_worker", lambda p, m: None)
    assert MsgExpander().members(tmp_path / "m.msg") is None


# ── layer 3: N+1, custodian inherited, provenance to parent — through real ingestion ──────────
def test_msg_with_two_attachments_yields_three_pieces_custodian_inherited(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def fake_worker(path: Path, mode: str) -> dict:
        if mode == "attachments":
            return {"ok": True, "attachments": [
                {"name": "rapport.txt", "b64": base64.b64encode(b"rapport d'expertise").decode()},
                {"name": "annexe.txt", "b64": base64.b64encode(b"annexe jointe").decode()}]}
        return {"ok": True, "text": "From: a@x.fr\nSubject: dossier\n\ncorps du courriel",
                "method": "extract-msg", "version": "extract-msg/0.56.0"}

    monkeypatch.setattr(msgmod, "_run_msg_worker", fake_worker)
    (tmp_path / "courriel.msg").write_bytes(b"placeholder; the worker is mocked")

    extractor = CompositeExtractor([MsgExtractor(), FileExtractor()])
    expander = CompositeExpander([MsgExpander()])
    result = ingest_folder(tmp_path, matter="m", tenant="t", extractor=extractor,
                           custodian="M. Dupont", expander=expander)

    assert result.inventory.in_corpus == 3                 # 2 attachments + the body = N+1
    provs = sorted(pc.provenance_path for pc in result.pieces)
    assert provs == ["courriel.msg", "courriel.msg/annexe.txt", "courriel.msg/rapport.txt"]
    assert all(pc.custodian == "M. Dupont" for pc in result.pieces)   # inherited on every piece
    assert result.inventory.is_consistent()


def test_nested_msg_in_msg_recurses_end_to_end(monkeypatch: pytest.MonkeyPatch,
                                               tmp_path: Path) -> None:
    # Story 2.4 (FR-57): an embedded .msg becomes a member and is recursed into — its own
    # attachment is a grandchild pièce, provenance carried through both message layers. The worker
    # is mocked (no real .msg fixture); it keys off a sentinel in the member bytes to distinguish
    # the inner message from the outer.
    def b64(data: bytes) -> str:
        return base64.b64encode(data).decode("ascii")

    def fake_worker(path: Path, mode: str) -> dict:
        data = Path(path).read_bytes() if Path(path).exists() else b""
        inner = b"INNER-MSG-SENTINEL" in data
        if mode == "attachments":
            if inner:
                return {"ok": True, "attachments": [
                    {"name": "grandchild.txt", "b64": b64(b"contenu du petit-enfant")}]}
            return {"ok": True, "attachments": [
                {"name": "inner.msg", "b64": b64(b"INNER-MSG-SENTINEL")}]}
        text = "corps du message interne" if inner else "corps du message externe"
        return {"ok": True, "text": text, "method": "extract-msg", "version": "extract-msg/0.56.0"}

    monkeypatch.setattr(msgmod, "_run_msg_worker", fake_worker)
    (tmp_path / "externe.msg").write_bytes(b"placeholder; the worker is mocked")

    extractor = CompositeExtractor([MsgExtractor(), FileExtractor()])
    expander = CompositeExpander([MsgExpander()])
    result = ingest_folder(tmp_path, matter="m", tenant="t", extractor=extractor,
                           custodian="M. Durand", expander=expander)

    provs = {pc.provenance_path for pc in result.pieces}
    assert "externe.msg" in provs                                   # outer body
    assert "externe.msg/inner.msg" in provs                         # inner body — recursed into
    assert "externe.msg/inner.msg/grandchild.txt" in provs          # grandchild — through 2 layers
    assert all(pc.custodian == "M. Durand" for pc in result.pieces)  # inherited all the way down
    assert result.inventory.is_consistent()
