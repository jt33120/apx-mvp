"""PDF portfolio / embedded-files expander via pypdf (already a dependency, imported lazily).

A PDF can carry embedded files — a "portfolio"/collection or plain attachments — in
``/Names /EmbeddedFiles``. Each becomes a member *pièce* (and the PDF's own text stays a piece via
the FileExtractor — the cover sheet). A plain PDF with no embedded files yields ``None`` (a leaf,
unchanged). Bounded by the configured member limit (AD-17). The PDF file itself is already
per-unit size-bounded before expansion, so a portfolio cannot be an unbounded bomb.
"""

from __future__ import annotations

from pathlib import Path

from apx.core.domain.config import ExpansionBounds
from apx.core.ports.expansion import ContainerUnopenable


class PdfPortfolioExpander:
    """Implements the Expander port for PDFs carrying embedded files."""

    def __init__(self, bounds: ExpansionBounds | None = None) -> None:
        self._bounds = bounds or ExpansionBounds.defaults()

    def recognises(self, path: Path) -> bool:
        return False     # a PDF is a leaf (its cover text is a piece), not a pure container

    def members(self, path: Path) -> list[tuple[str, bytes]] | None:
        if path.suffix.lower() != ".pdf":
            return None
        from pypdf import PdfReader

        try:
            attachments = PdfReader(str(path)).attachments  # {name: [bytes, ...]}
        except Exception:  # noqa: BLE001 — a broken PDF is not a container we can open; let the
            # extractor path try to read it as a leaf (it will land `unreadable` there).
            return None
        if not attachments:
            return None  # a plain PDF — a leaf, its text is a piece via the FileExtractor
        members: list[tuple[str, bytes]] = []
        for name, blobs in attachments.items():
            members.extend((name, bytes(blob)) for blob in blobs)
        if len(members) > self._bounds.max_members:
            raise ContainerUnopenable(
                f"{len(members)} embedded files exceed the configured limit of "
                f"{self._bounds.max_members}")
        return members
