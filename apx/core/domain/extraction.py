"""The outcome of extracting text from one file — a domain value, store-independent."""

from __future__ import annotations

from dataclasses import dataclass

from apx.core.domain.failures import ErrorClass
from apx.core.domain.ocr_layout import OcrLayout


@dataclass(frozen=True)
class ExtractOutcome:
    """Either text was extracted (error_class is None) or it failed (text is empty). When the text
    came from OCR (Story 3.5c-1), ``layout`` carries the per-word bounding boxes so a later render
    can draw the overlay; it is ``None`` for a born-digital extraction."""

    text: str
    method: str
    version: str
    error_class: ErrorClass | None = None
    layout: OcrLayout | None = None

    @property
    def ok(self) -> bool:
        return self.error_class is None and bool(self.text)
