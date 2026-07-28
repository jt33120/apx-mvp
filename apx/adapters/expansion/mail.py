"""Email/mailbox expanders (stdlib — no dependency).

``EmlExpander`` surfaces a single email's ATTACHMENTS (its body is still a piece the FileExtractor
reads, so an .eml is ingested as both), bounded by the configured attachments-per-message limit
(AD-17). ``MboxExpander`` expands a ``.mbox`` mailbox export into one member .eml per message, which
the .eml path then handles — including that message's own attachments (recursion). ``.pst``/``.ost``
stores are OUT of scope: they need a different tool and a client-confirmed export format.
"""

from __future__ import annotations

import email
from email import policy
from pathlib import Path

from apx.core.domain.config import ExpansionBounds
from apx.core.ports.expansion import ContainerUnopenable


class EmlExpander:
    """Implements the Expander port for .eml files — yields their attachments (AD-17 bounded)."""

    def __init__(self, bounds: ExpansionBounds | None = None) -> None:
        self._bounds = bounds or ExpansionBounds.defaults()

    def members(self, path: Path) -> list[tuple[str, bytes]] | None:
        if path.suffix.lower() != ".eml":
            return None
        message = email.message_from_bytes(path.read_bytes(), policy=policy.default)
        parts = list(message.iter_attachments())  # cheap references; not decoded yet
        cap = self._bounds.attachments_per_message_max
        if len(parts) > cap:
            raise ContainerUnopenable(
                f"{len(parts)} attachments exceed the configured limit of {cap}")
        out: list[tuple[str, bytes]] = []
        for part in parts:
            content = part.get_content()
            data = content.encode("utf-8", "replace") if isinstance(content, str) else content
            out.append((part.get_filename() or "piece-jointe", data))
        return out


class MboxExpander:
    """Implements the Expander port for .mbox mailbox exports — one member .eml per message."""

    def __init__(self, bounds: ExpansionBounds | None = None) -> None:
        self._bounds = bounds or ExpansionBounds.defaults()

    def members(self, path: Path) -> list[tuple[str, bytes]] | None:
        if path.suffix.lower() != ".mbox":
            return None
        import mailbox

        try:
            box = mailbox.mbox(str(path))
        except Exception as exc:  # noqa: BLE001 — a mailbox we could not open: contents unknown
            raise ContainerUnopenable(
                f"could not open the mailbox ({type(exc).__name__})") from exc
        try:
            keys = list(box.keys())
            if len(keys) > self._bounds.max_members:
                raise ContainerUnopenable(
                    f"{len(keys)} messages exceed the configured limit of "
                    f"{self._bounds.max_members}")
            return [
                (f"message-{i:05d}.eml", box.get_message(key).as_bytes())
                for i, key in enumerate(keys, start=1)
            ]
        finally:
            box.close()
