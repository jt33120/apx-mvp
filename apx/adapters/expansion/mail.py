"""Expand an email's attachments into member files (stdlib email — no dependency).

The email BODY is still a piece in its own right (the FileExtractor reads it); this
expander only surfaces the ATTACHMENTS, so an .eml is ingested as both.
"""

from __future__ import annotations

import email
from email import policy
from pathlib import Path


class EmlExpander:
    """Implements the Expander port for .eml files — yields their attachments."""

    def members(self, path: Path) -> list[tuple[str, bytes]] | None:
        if path.suffix.lower() != ".eml":
            return None
        message = email.message_from_bytes(path.read_bytes(), policy=policy.default)
        out: list[tuple[str, bytes]] = []
        for part in message.iter_attachments():
            content = part.get_content()
            data = content.encode("utf-8", "replace") if isinstance(content, str) else content
            out.append((part.get_filename() or "piece-jointe", data))
        return out
