"""File-based text extraction (a slice of story 2.3).

Covers plain text (.txt/.md/.log/.csv), born-digital PDF (pypdf), Word (.docx) and
email (.eml) — the formats a real dossier is actually made of. Word and email are
read with the standard library only (a .docx is a zip of XML; email has a parser in
the stdlib), so no dependency and nothing for the egress guard to forbid. Everything
else is `unsupported-format`; an extraction that yields no text is `extracted-empty`
(NOT counted in the corpus — otherwise an absence claim would assert it was searched).
Scanned-PDF OCR and .msg are later (they pull a dependency / touch the timed run).
Runs inside the tenant boundary (no hosted service).
"""

from __future__ import annotations

import email
import zipfile
from email import policy
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree as ET

from apx.core.domain.extraction import ExtractOutcome
from apx.core.domain.failures import ErrorClass

_TEXT_SUFFIXES = {".txt", ".md", ".log", ".csv"}
_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"  # WordprocessingML ns


class _HtmlText(HTMLParser):
    """Collect visible text, dropping tags and the contents of script/style."""

    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []
        self._skip = False

    def handle_starttag(self, tag: str, attrs: object) -> None:
        if tag in ("script", "style"):
            self._skip = True

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style"):
            self._skip = False

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self._parts.append(data)

    def text(self) -> str:
        return " ".join("".join(self._parts).split())


class FileExtractor:
    """Implements the Extractor port for files on disk."""

    version = "files/2"

    def extract(self, path: Path) -> ExtractOutcome:
        suffix = path.suffix.lower()
        if suffix in _TEXT_SUFFIXES:
            return self._text(path)
        if suffix == ".pdf":
            return self._pdf(path)
        if suffix == ".docx":
            return self._docx(path)
        if suffix == ".eml":
            return self._eml(path)
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

    def _docx(self, path: Path) -> ExtractOutcome:
        """A .docx is a zip; the body text lives in word/document.xml as <w:t> runs,
        grouped into <w:p> paragraphs (table cells carry paragraphs too, so iterating
        every paragraph captures table text as well)."""
        try:
            with zipfile.ZipFile(path) as archive:
                document = archive.read("word/document.xml")
            root = ET.fromstring(document)
        except (zipfile.BadZipFile, KeyError, OSError, ET.ParseError):
            return ExtractOutcome("", "docx", self.version, ErrorClass.UNREADABLE)
        paragraphs = [
            "".join(node.text or "" for node in para.iter(f"{_W}t"))
            for para in root.iter(f"{_W}p")
        ]
        text = "\n".join(paragraphs)
        if not text.strip():
            return ExtractOutcome("", "docx", self.version, ErrorClass.EXTRACTED_EMPTY)
        return ExtractOutcome(text, "docx", self.version)

    def _eml(self, path: Path) -> ExtractOutcome:
        """An email as searchable text: the routing headers a lawyer needs (from, to,
        date, subject) followed by the body — the text/plain part, or the text/html
        part with its tags stripped."""
        try:
            msg = email.message_from_bytes(path.read_bytes(), policy=policy.default)
        except (OSError, ValueError):
            return ExtractOutcome("", "eml", self.version, ErrorClass.UNREADABLE)
        headers = [f"{h}: {msg[h]}" for h in ("From", "To", "Cc", "Date", "Subject") if msg[h]]
        body = ""
        try:
            part = msg.get_body(preferencelist=("plain", "html"))
            if part is not None:
                content = part.get_content()
                if part.get_content_subtype() == "html":
                    parser = _HtmlText()
                    parser.feed(content)
                    content = parser.text()
                body = content
        except (LookupError, ValueError, KeyError):
            body = ""
        text = "\n".join(headers)
        if body.strip():
            text = f"{text}\n\n{body}" if text else body
        if not text.strip():
            return ExtractOutcome("", "eml", self.version, ErrorClass.EXTRACTED_EMPTY)
        return ExtractOutcome(text, "eml", self.version)
