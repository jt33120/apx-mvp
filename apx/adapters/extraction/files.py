"""File-based text extraction (a slice of story 2.3).

Covers plain text (.txt/.md/.log/.csv), born-digital PDF (pypdf), Word (.docx),
spreadsheets (.xlsx via openpyxl — AD-28's named Office tool) and email (.eml). Text,
Word and email are read with the standard library only (a .docx is a zip of XML; email
has a parser in the stdlib), so no dependency and nothing for the egress guard to forbid;
.xlsx uses openpyxl (MIT, in-process, imported lazily). Everything else is
`unsupported-format`; an extraction that yields no text is `extracted-empty` (NOT counted
in the corpus — otherwise an absence claim would assert it was searched). .msg is handled
out-of-process by the GPL-isolated MsgExtractor (AD-28), not here. Scanned-PDF OCR is the
Tesseract adapter. Runs inside the tenant boundary (no hosted service).
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
        if suffix == ".xlsx":
            return self._xlsx(path)
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
        from pypdf.errors import (
            PyPdfError,  # the base pypdf error; `PdfError` does not exist (6.14)
        )

        try:
            reader = PdfReader(str(path))
            text = "\n".join((page.extract_text() or "") for page in reader.pages)
        except (PyPdfError, OSError, ValueError):
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

    def _xlsx(self, path: Path) -> ExtractOutcome:
        """A .xlsx read across every sheet. ``data_only`` reads a formula's **cached value**,
        never its ``=A1+A2`` text — so a normal Excel/LibreOffice workbook contributes its
        computed values with no formula noise. But a workbook whose writer cached **no** values
        (a purely programmatic export) would read empty under ``data_only``; rather than a false
        *not in corpus* (an absence claim would then wrongly assert it was searched), fall back to
        reading the formulas/literals so the sheet is still searchable — recall over precision.
        ``read_only`` streams so a large sheet need not load whole (AD-17)."""
        text = self._xlsx_read(path, data_only=True)
        if text is None:
            return ExtractOutcome("", "xlsx", self.version, ErrorClass.UNREADABLE)
        if not text.strip():
            fallback = self._xlsx_read(path, data_only=False)
            if fallback is None:
                return ExtractOutcome("", "xlsx", self.version, ErrorClass.UNREADABLE)
            text = fallback
        if not text.strip():
            return ExtractOutcome("", "xlsx", self.version, ErrorClass.EXTRACTED_EMPTY)
        return ExtractOutcome(text, "xlsx", self.version)

    def _xlsx_read(self, path: Path, *, data_only: bool) -> str | None:
        """Join every sheet's non-blank cell values into text, or ``None`` on ANY read failure
        (→ ``unreadable``). openpyxl's failure surface on the malformed input AD-28 calls the
        *normal* case is broad — bad zip, malformed sheet XML (``ET.ParseError``), encrypted,
        truncated — so a broad catch maps them ALL to a clean outcome and, crucially, never lets
        a parser message escape into ``str(exc)`` and the register (AD-28 I/O discipline). openpyxl
        is imported lazily so the app still imports where it is absent."""
        import openpyxl

        workbook = None
        try:
            workbook = openpyxl.load_workbook(path, read_only=True, data_only=data_only)
            lines: list[str] = []
            for sheet in workbook.worksheets:
                for row in sheet.iter_rows(values_only=True):
                    cells = [str(v) for v in row if v is not None and str(v).strip()]
                    if cells:
                        lines.append(" ".join(cells))
            return "\n".join(lines)
        except Exception:  # noqa: BLE001 — malformed is the normal case (AD-28); never leak str(exc)
            return None
        finally:
            if workbook is not None:
                workbook.close()

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
