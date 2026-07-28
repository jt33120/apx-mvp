"""The GPL isolation boundary for ``.msg`` (story 2.3, AD-28).

This is the ONLY module in the tree that imports ``extract_msg`` (**GPL-3.0-only**). It runs
as a **subprocess** — ``python -m apx.adapters.extraction.msg_worker <mode> <path>`` — so
extract-msg stays a *separate program* the proprietary product never imports (the process
boundary is the licence boundary, AD-28), and a malformed Outlook compound file that crashes
or hangs the parser dies **here**, becoming a *failure-register* entry rather than a worker
death (AD-17).

I/O discipline (AD-28): the worker writes **exactly one JSON object to stdout**; every scrap of
extract-msg chatter — warnings, object streams, filenames, document fragments emitted on
malformed input — is redirected to **stderr**, which the parent captures and **discards**. A
document fragment must never reach a log, a diagnostic, or the register. On any failure the
worker exits non-zero with nothing usable on stdout, and the parent maps that to an enumerated
error class.

Modes: ``text`` → routing headers + body (extract-msg decodes RTF-compressed bodies, TNEF and
charset internally — that is why the GPL dependency is taken rather than hand-rolling
compound-file parsing); ``attachments`` → the top-level embedded attachments as bytes. Nested
``.msg``-in-``.msg`` recursion and depth/ratio bounds are Story 2.4.
"""

from __future__ import annotations

import base64
import contextlib
import json
import sys
from typing import Any

VERSION = "extract-msg/0.56.0"
_HEADERS = ("sender", "to", "cc", "date", "subject")
_LABELS = {"sender": "From", "to": "To", "cc": "Cc", "date": "Date", "subject": "Subject"}


def _text(msg: Any) -> dict[str, Any]:
    """Routing headers a lawyer needs, then the body (which carries the quoted reply chain
    inline, as Outlook stores it). Empty headers and empty body → ``extracted-empty``."""
    lines: list[str] = []
    for attr in _HEADERS:
        value = getattr(msg, attr, None)
        if value:
            lines.append(f"{_LABELS[attr]}: {value}")
    header_text = "\n".join(lines)
    body = getattr(msg, "body", None) or ""
    text = header_text
    if body.strip():
        text = f"{header_text}\n\n{body}" if header_text else body
    if not text.strip():
        return {"ok": False, "error_class": "extracted-empty"}
    return {"ok": True, "text": text, "method": "extract-msg", "version": VERSION}


def _att_name(att: Any) -> str:
    return str(getattr(att, "longFilename", None) or getattr(att, "shortFilename", None)
               or "piece-jointe")


def _embedded_bytes(att: Any) -> bytes | None:
    """Serialise an embedded ``.msg`` attachment (``.data`` is a Message, not bytes) back to bytes
    so the ingestion use case can recurse into it (Story 2.4). extract-msg's ``save`` writes an
    embedded message as a ``.msg``; we save to a temp dir and read it back. Returns None if the
    library cannot serialise it — the caller then surfaces it as a member the ingestion records as
    a failure, never a silent drop."""
    import os
    import tempfile

    try:
        with tempfile.TemporaryDirectory() as td:
            att.save(customPath=td)
            files = [os.path.join(td, f) for f in os.listdir(td)]
            files = [f for f in files if os.path.isfile(f)]
            if not files:
                return None
            with open(files[0], "rb") as fh:  # noqa: PTH123 — a transient temp path, not a repo path
                return fh.read()
    except Exception:  # noqa: BLE001 — any serialisation failure → None; the caller never drops it
        return None


def _attachments(msg: Any) -> dict[str, Any]:
    """Top-level attachments as members. A byte attachment is its bytes; an embedded ``.msg``
    (``.data`` is a Message) is serialised back to ``.msg`` bytes so the ingestion use case
    recurses into it (Story 2.4 — its own attachments are then grandchildren, depth-bounded). An
    embedded message the library cannot serialise is surfaced with empty bytes, which ingestion
    records as a failure rather than dropping it."""
    out: list[dict[str, str]] = []
    for att in getattr(msg, "attachments", []) or []:
        data = getattr(att, "data", None)
        if isinstance(data, (bytes, bytearray)):
            out.append({"name": _att_name(att),
                        "b64": base64.b64encode(bytes(data)).decode("ascii")})
        else:
            name = _att_name(att)
            if not name.lower().endswith(".msg"):
                name = f"{name}.msg"
            raw = _embedded_bytes(att) or b""
            out.append({"name": name, "b64": base64.b64encode(raw).decode("ascii")})
    return {"ok": True, "attachments": out, "method": "extract-msg", "version": VERSION}


def run(mode: str, path: str) -> dict[str, Any]:
    """Open the .msg and dispatch on ``mode``. The ``extract_msg`` import AND all parse-time
    stdout are inside the ``redirect_stdout`` guard, so any chatter the library writes to stdout
    (even at import time) goes to stderr — stdout carries ONLY the final JSON the caller reads."""
    with contextlib.redirect_stdout(sys.stderr):
        import extract_msg

        msg = extract_msg.openMsg(path)
        try:
            if mode == "text":
                return _text(msg)
            if mode == "attachments":
                return _attachments(msg)
            return {"ok": False, "error_class": "unreadable"}
        finally:
            msg.close()


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        return 2
    mode, path = argv
    try:
        result = run(mode, path)
    except Exception:  # noqa: BLE001 — the isolation boundary: ANY parser failure exits non-zero
        # with nothing on stdout; the parent maps it to a register class and DISCARDS our
        # stderr, so no document fragment escapes (AD-28). This is deliberately broad.
        return 1
    sys.stdout.write(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
