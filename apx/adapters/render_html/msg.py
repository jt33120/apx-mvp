"""Server-side ``.msg`` (Outlook email) rendering for the pièce viewer (Story 3.5c-3, AD-14/AD-28).

Renders an email — its routing headers, its body (with the inline quoted reply chain, as Outlook
stores it), and its attachment **names** — to **sanitised** inline HTML, inside the tenant boundary.
The structured extraction runs in the **GPL-isolated out-of-process worker** (`extract-msg` is never
imported here — that stays in ``adapters/extraction/msg_worker``); this adapter only escapes the
worker's fields, assembles HTML, and routes it through the SAME ``_rendered`` choke point as the
office renderers, so a `.msg` render is sanitised by the one nh3 allow-list and constructs no
``RenderedDocument`` of its own (the ``rendered_html_is_sanitized`` gate covers this file too).

Attachments are their own pièces (expanded at ingestion, Story 2.4) — this render lists their names
so the reader opens each as its own audited pièce; it never embeds attachment bytes. A non-`.msg`
name, or any worker failure (crash / timeout / unreadable / empty), yields ``None`` — the edge then
offers the original (FR-44), never a raise, never a 500.
"""

from __future__ import annotations

import contextlib
import html
import os
import tempfile
from pathlib import Path

from apx.adapters.render_html.renderer import _rendered
from apx.core.ports.render import RenderedDocument

# Lawyer-language header labels (FR); the worker returns the raw values, escaped + sanitised here.
_HEADER_LABELS = (("from", "De"), ("to", "À"), ("cc", "Cc"), ("date", "Date"), ("subject", "Objet"))


def _spool_dir() -> str:
    """Decrypted ``.msg`` plaintext must transit the ENCRYPTED data volume (AD-31), not the system
    temp (a possibly-unencrypted mount) — matching ``FilesystemOriginalStore``'s on-volume temp.
    Falls back to the system temp only when ``APX_DATA_PATH`` is unset (dev/test). Read per render,
    so the cached renderer honours the current environment."""
    return os.environ.get("APX_DATA_PATH", "").strip() or tempfile.gettempdir()


class MsgRenderer:
    """Implements the ``PieceRenderer`` port for ``.msg`` via the GPL-isolated worker (Story
    3.5c-3). Any other format → ``None`` (the edge offers the original)."""

    def __init__(self, max_body_chars: int = 200_000) -> None:
        # A body cap protects the reader's machine on a pathological email; a cap hit sets truncated
        # (never a silent drop). The gross original byte bound (3.5b/3.5c-2) is the first guard.
        self._max_body_chars = max_body_chars

    def render(self, *, filename: str, data: bytes) -> RenderedDocument | None:
        if not filename.lower().endswith(".msg"):
            return None
        from apx.adapters.extraction.msg import structured_msg

        # The worker reads a PATH; spool the decrypted bytes to a transient temp file ON THE
        # ENCRYPTED DATA VOLUME (not the system temp — AD-31), removed in `finally` so the plaintext
        # never persists. Everything is INSIDE the guard, so ANY failure (spool, worker, sanitise, a
        # missing nh3) fails CLOSED to None (offer the original — mirrors _docx/_xlsx), never an
        # unguarded raise/500, never unsanitised HTML.
        tmp: str | None = None
        try:
            fd, tmp = tempfile.mkstemp(suffix=".msg", dir=_spool_dir())
            with os.fdopen(fd, "wb") as fh:
                fh.write(data)
            struct = structured_msg(Path(tmp))
            if struct is None:
                return None
            body_html, truncated = self._body_html(struct)
            return _rendered(_title(struct, filename), _headers_html(struct) + body_html, truncated)
        except Exception:  # noqa: BLE001 — any failure → None (offer the original), never a 500
            return None
        finally:
            if tmp is not None:
                with contextlib.suppress(OSError):
                    os.unlink(tmp)

    def _body_html(self, struct: dict) -> tuple[str, bool]:
        body = str(struct.get("body") or "")
        truncated = len(body) > self._max_body_chars
        if truncated:
            body = body[: self._max_body_chars]
        atts = struct.get("attachments") or []
        att_html = ""
        if atts:
            items = "".join(f"<li>{html.escape(str(a))}</li>" for a in atts)
            att_html = f"<p>Pièces jointes :</p><ul>{items}</ul>"
        # escape THEN newline→<br>: after escape there is no raw '<' from the body, so the only
        # markup is our own <br>/<hr>/<div>; nh3 (via _rendered) is the belt over the braces. Emit
        # the body section only when there IS a body (a headers-only email leaves no empty <div>).
        body_div = ""
        if body.strip():
            body_div = f"<hr><div>{html.escape(body).replace(chr(10), '<br>')}</div>"
        return body_div + att_html, truncated


def _title(struct: dict, filename: str) -> str:
    return str(struct.get("subject") or "").strip() or filename


def _headers_html(struct: dict) -> str:
    esc = html.escape
    rows = "".join(
        f'<tr><th scope="row">{esc(label)}</th><td>{esc(str(struct[key]))}</td></tr>'
        for key, label in _HEADER_LABELS if struct.get(key))
    return f"<table><tbody>{rows}</tbody></table>" if rows else ""
