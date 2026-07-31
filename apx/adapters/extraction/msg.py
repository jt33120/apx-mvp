"""The ``.msg`` adapters (story 2.3, AD-28): ``MsgExtractor`` (Extractor port) and
``MsgExpander`` (Expander port), both backed by the **out-of-process, GPL-isolated**
``msg_worker``.

This module holds the ONE ``subprocess`` call site the extraction boundary allows (AD-28:
*"no subprocess call outside adapters/extraction, and no stderr=None within it"*). A crash,
a hang past the timeout, a non-zero exit, or unparseable output all become a **clean
extraction failure** here — never a raise into the worker, never an outage (AD-17) — and the
subprocess's stdout/stderr is **discarded**, so a malformed document never reaches a log or
the register (AD-28 I/O discipline).

Both classes live under ``adapters/extraction`` so the subprocess call site stays inside it;
``MsgExpander`` is composed into the expander chain by the edge builders (the composition
root imports adapters — that is not an adapter importing another adapter, AD-4).
"""

from __future__ import annotations

import base64
import json
import subprocess
import sys
from pathlib import Path

from apx.core.domain.config import ExpansionBounds
from apx.core.domain.extraction import ExtractOutcome
from apx.core.domain.failures import ErrorClass
from apx.core.ports.expansion import ContainerUnopenable

_WORKER = "apx.adapters.extraction.msg_worker"
# The subprocess's own resource bound (AD-28): a hung compound-file parse is a failure, not an
# outage. A single oversized unit is already bounded earlier by the ingestion max_bytes guard.
_TIMEOUT_S = 120
_VERSION = "extract-msg/0.56.0"
_CLASSES = {
    "extracted-empty": ErrorClass.EXTRACTED_EMPTY,
    "unreadable": ErrorClass.UNREADABLE,
    "corrupt-file": ErrorClass.CORRUPT_FILE,  # an unopenable compound file (FR-5/FR-54)
}


def _run_msg_worker(path: Path, mode: str) -> dict | None:
    """Run the GPL-isolated worker out-of-process; return its parsed JSON, or ``None`` on ANY
    failure (non-zero exit, timeout, unparseable output). ``capture_output=True`` captures
    BOTH streams — stderr is never inherited/``None`` (AD-28) — and the captured bytes are
    **discarded** here, so no document fragment leaks into a caller, a log or the register."""
    try:
        proc = subprocess.run(
            [sys.executable, "-m", _WORKER, mode, str(path)],
            capture_output=True, timeout=_TIMEOUT_S, check=False)
    except (subprocess.TimeoutExpired, OSError):
        return None
    if proc.returncode != 0:
        return None
    try:
        return json.loads(proc.stdout.decode("utf-8", "strict"))
    except (ValueError, UnicodeDecodeError):
        return None


def structured_msg(path: Path) -> dict | None:
    """The ``.msg``'s routing headers + body + attachment NAMES for the viewer render (3.5c-3), via
    the GPL-isolated worker's ``render`` mode — no attachment bytes (attachments are their own
    pièces). ``None`` on any failure (a non-``.msg``, or a crash / timeout / unreadable / empty
    ``.msg``) so the caller offers the original (FR-44). ``extract-msg`` stays worker-only; this
    wrapper touches only the worker's JSON, never the library."""
    if path.suffix.lower() != ".msg":
        return None
    result = _run_msg_worker(path, "render")
    if result is None or not result.get("ok"):
        return None
    return result


class MsgExtractor:
    """Implements the Extractor port for ``.msg`` via the out-of-process worker (AD-28)."""

    version = _VERSION

    def extract(self, path: Path) -> ExtractOutcome:
        if path.suffix.lower() != ".msg":
            return ExtractOutcome("", "none", self.version, ErrorClass.UNSUPPORTED_FORMAT)
        result = _run_msg_worker(path, "text")
        if result is None:
            return ExtractOutcome("", "extract-msg", self.version, ErrorClass.UNREADABLE)
        if not result.get("ok"):
            cls = _CLASSES.get(result.get("error_class"), ErrorClass.UNREADABLE)
            return ExtractOutcome("", "extract-msg", self.version, cls)
        # Trust boundary for the corpus and for AD-40 identity (method+version ∈ chunk_id): a
        # drifted/older worker returning ok=true with blank text or an empty method/version must
        # never seed a degenerate piece. Whitespace-only text is extracted-empty; the constants
        # stand in for empty method/version.
        text = result.get("text") or ""
        if not text.strip():
            return ExtractOutcome("", "extract-msg", self.version, ErrorClass.EXTRACTED_EMPTY)
        return ExtractOutcome(
            text, result.get("method") or "extract-msg", result.get("version") or self.version)


class MsgExpander:
    """Implements the Expander port for ``.msg`` — its top-level embedded attachments as
    member files (N attachments → N+1 *pièces* once the body is extracted too; *custodian* and
    provenance are inherited by the ingestion use case). Story 2.4 owns nested ``.msg``-in-
    ``.msg`` recursion and the depth/ratio bounds.

    A ``.msg`` with **no** attachments returns ``None`` (a plain leaf), so its body is a piece
    when present and an **empty** ``.msg`` becomes ``extracted-empty`` via the extractor path
    rather than vanishing as a transparent-but-empty container (AC5). A broken ``.msg`` also
    returns ``None`` — the extractor path then records it once as ``unreadable``; never a raise.
    An embedded ``.msg`` attachment is surfaced as a member ``.msg`` the use case recurses into
    (Story 2.4); more attachments than the configured limit is a ``ContainerUnopenable``."""

    def __init__(self, bounds: ExpansionBounds | None = None) -> None:
        self._bounds = bounds or ExpansionBounds.defaults()

    def recognises(self, path: Path) -> bool:
        return False     # a leaf-with-attachments (its body is a piece), not a pure container

    def members(self, path: Path) -> list[tuple[str, bytes]] | None:
        if path.suffix.lower() != ".msg":
            return None
        result = _run_msg_worker(path, "attachments")
        if result is None or not result.get("ok"):
            return None
        atts = result.get("attachments", [])
        cap = self._bounds.attachments_per_message_max
        if len(atts) > cap:
            raise ContainerUnopenable(
                f"{len(atts)} attachments exceed the configured limit of {cap}")
        members: list[tuple[str, bytes]] = []
        for att in atts:
            try:
                members.append((str(att["name"]), base64.b64decode(att["b64"])))
            except (KeyError, ValueError, TypeError):
                continue
        return members or None
