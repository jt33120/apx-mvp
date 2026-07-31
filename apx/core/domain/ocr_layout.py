"""The OCR layout of a scanned pièce — where each recognised word sits on the page image (Story
3.5c-1). A pure domain value, store-independent: the Tesseract extractor produces it at ingestion,
the ingest use case stores it (encrypted, content-addressed), and a later render (3.5c-2) draws the
text overlay and highlights a passage from these boxes — without re-running OCR at view time.

Coordinates are in the page IMAGE's pixel space at the recorded ``dpi``, so a renderer that
rasterises the same page at the same dpi can place each box exactly. Serialised to a stable JSON
shape for the blob.
"""

from __future__ import annotations

import json
from dataclasses import dataclass


@dataclass(frozen=True)
class OcrWord:
    """One recognised word: its bounding box (page-image pixels) + Tesseract confidence (0–100)."""

    text: str
    left: int
    top: int
    width: int
    height: int
    confidence: float


@dataclass(frozen=True)
class OcrPage:
    """One page: the page-image dimensions (pixels) and its recognised words, in reading order."""

    width: int
    height: int
    words: tuple[OcrWord, ...]


@dataclass(frozen=True)
class OcrLayout:
    """A scanned pièce's OCR layout — its pages, and the rasterisation ``dpi`` the boxes are in."""

    pages: tuple[OcrPage, ...]
    dpi: int

    def to_json(self) -> str:
        """A stable, compact JSON encoding for the at-rest blob."""
        return json.dumps(
            {
                "dpi": self.dpi,
                "pages": [
                    {
                        "width": p.width,
                        "height": p.height,
                        "words": [
                            {"t": w.text, "l": w.left, "o": w.top, "w": w.width,
                             "h": w.height, "c": w.confidence}
                            for w in p.words
                        ],
                    }
                    for p in self.pages
                ],
            },
            ensure_ascii=False, separators=(",", ":"),
        )

    @classmethod
    def from_json(cls, raw: str) -> OcrLayout:
        """Parse a :meth:`to_json` blob back to an ``OcrLayout`` (fail-closed on a malformed shape:
        a ``KeyError``/``TypeError``/``ValueError`` propagates, never a half layout)."""
        doc = json.loads(raw)
        pages = tuple(
            OcrPage(
                width=int(p["width"]),
                height=int(p["height"]),
                words=tuple(
                    OcrWord(text=str(w["t"]), left=int(w["l"]), top=int(w["o"]),
                            width=int(w["w"]), height=int(w["h"]), confidence=float(w["c"]))
                    for w in p["words"]
                ),
            )
            for p in doc["pages"]
        )
        return cls(pages=pages, dpi=int(doc["dpi"]))
