"""File-based text extraction (a minimal slice of story 2.3).

Covers plain text (.txt/.md/.log) and born-digital PDF (pypdf). Everything else
is `unsupported-format`; an extraction that yields no text is `extracted-empty`
(NOT counted in the corpus — otherwise an absence claim would assert it was
searched). Runs inside the tenant boundary (no hosted service).
"""

from __future__ import annotations

from pathlib import Path

from apx.core.domain.extraction import ExtractOutcome
from apx.core.domain.failures import ErrorClass

_TEXT_SUFFIXES = {".txt", ".md", ".log", ".csv"}


class FileExtractor:
    """Implements the Extractor port for files on disk."""

    version = "files/1"

    def extract(self, path: Path) -> ExtractOutcome:
        suffix = path.suffix.lower()
        if suffix in _TEXT_SUFFIXES:
            return self._text(path)
        if suffix == ".pdf":
            return self._pdf(path)
        return ExtractOutcome("", "none", self.version, ErrorClass.UNSUPPORTED_FORMAT)

    def _text(self, path: Path) -> ExtractOutcome:
        try:
            text = path.read_text(encoding="utf-8", errors="strict")
        except (UnicodeDecodeError, OSError):
            return ExtractOutcome("", "text", self.version, ErrorClass.UNREADABLE)
        if not text.strip():
            return ExtractOutcome("", "text", self.version, ErrorClass.EXTRACTED_EMPTY)
        return ExtractOutcome(text, "text", self.version)

    def _pdf(self, path: Path) -> ExtractOutcome:
        from pypdf import PdfReader
        from pypdf.errors import PdfError

        try:
            reader = PdfReader(str(path))
            text = "\n".join((page.extract_text() or "") for page in reader.pages)
        except (PdfError, OSError, ValueError):
            return ExtractOutcome("", "pypdf", self.version, ErrorClass.UNREADABLE)
        if not text.strip():
            # A born-digital PDF with no text layer (e.g. a scan) — OCR is story 2.3.
            return ExtractOutcome("", "pypdf", self.version, ErrorClass.EXTRACTED_EMPTY)
        return ExtractOutcome(text, "pypdf", self.version)
