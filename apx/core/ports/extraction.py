"""The Extractor port — a text-extraction boundary the core depends on (AD-4).

Adapters (pypdf, extract-msg, Tesseract OCR, …) implement this; the core never
imports them directly. This slice ships a file-based implementation covering .txt
and PDF; the full format surface is story 2.3.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from apx.core.domain.extraction import ExtractOutcome


class Extractor(Protocol):
    def extract(self, path: Path) -> ExtractOutcome: ...
