"""The Expander port — a container-expansion boundary the core depends on (AD-4).

A dossier arrives as containers: a .zip of the file tree, an email with attachments.
An Expander turns one such container into its member files; the ingestion use case
then ingests each member individually (recursively — a zip inside a zip works), so no
piece hides inside packaging. Adapters (zip archives, email attachments) implement
this; the core never imports them. A file that is not a container this expander
understands yields None (ingest it as an ordinary leaf).
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol


class ContainerUnopenable(Exception):  # noqa: N818 — a domain signal, not an "*Error" convention
    """Raised by an expander that RECOGNISES a container but refuses to open it — a member-count
    or expansion-ratio breach (a zip bomb), checked against the container's DECLARED sizes BEFORE
    decompressing so a bomb is never read whole. The ingestion use case records it as ONE
    `container-unopenable` register entry of cardinality `unknown` (AD-38), never an outage."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class Expander(Protocol):
    def members(self, path: Path) -> list[tuple[str, bytes]] | None:
        """The container's members as ``(relative_name, content_bytes)``, or None if
        ``path`` is not a container this expander handles. An empty list means a
        recognised-but-empty container (e.g. an email with no attachments). Raises
        ``ContainerUnopenable`` when a recognised container breaches a configured bound
        (member count / expansion ratio) — the use case turns that into a register entry."""
        ...

    def recognises(self, path: Path) -> bool:
        """True iff ``path`` is a **pure container** — all its content is members, no own leaf
        body — that this expander would expand (a cheap suffix check, NO reading). Archives and
        mailboxes are pure containers; an email/message/PDF is a leaf-with-attachments and returns
        False here (its body is still a piece). The use case uses this to refuse a pure container
        nested past the depth limit WITHOUT decompressing it, while still extracting a
        leaf-with-attachments' body at the limit."""
        ...
