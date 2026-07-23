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


class Expander(Protocol):
    def members(self, path: Path) -> list[tuple[str, bytes]] | None:
        """The container's members as ``(relative_name, content_bytes)``, or None if
        ``path`` is not a container this expander handles. An empty list means a
        recognised-but-empty container (e.g. an email with no attachments)."""
        ...
