"""The OCR layout domain value (Story 3.5c-1): a stable JSON round-trip so the boxes stored at
ingestion deserialise back exactly for the viewer's overlay; unicode-safe and compact."""

from __future__ import annotations

import pytest

from apx.core.domain.ocr_layout import OcrLayout, OcrPage, OcrWord


def _layout() -> OcrLayout:
    return OcrLayout(
        pages=(
            OcrPage(width=1200, height=1600, words=(
                OcrWord("Contrat", 100, 200, 80, 20, 96.5),
                OcrWord("de", 190, 200, 20, 20, 91.0),
                OcrWord("bail", 230, 200, 40, 20, 88.0),
            )),
            OcrPage(width=1200, height=1600, words=()),   # a blank page keeps its dimensions
        ),
        dpi=200,
    )


def test_round_trips_exactly() -> None:
    lay = _layout()
    assert OcrLayout.from_json(lay.to_json()) == lay      # frozen dataclasses → value equality


def test_encoding_is_unicode_safe_and_compact() -> None:
    lay = OcrLayout(pages=(OcrPage(800, 1000, (OcrWord("créance", 1, 2, 3, 4, 88.0),)),), dpi=150)
    raw = lay.to_json()
    assert "créance" in raw                               # ensure_ascii=False — accents survive
    assert ", " not in raw                                # compact separators
    assert OcrLayout.from_json(raw) == lay


def test_empty_layout_round_trips() -> None:
    lay = OcrLayout(pages=(), dpi=200)
    assert OcrLayout.from_json(lay.to_json()) == lay


def test_from_json_fails_closed_on_a_malformed_shape() -> None:
    # a half/partial layout would make the viewer draw a wrong overlay — from_json must RAISE,
    # never return a truncated layout (AC4). Covers non-JSON, missing keys, and bad types.
    for bad in (
        "not json at all",                                    # not JSON → JSONDecodeError
        '{"dpi": 200}',                                       # missing "pages" → KeyError
        '{"pages": []}',                                      # missing "dpi" → KeyError
        '{"dpi": 200, "pages": [{"width": 1}]}',              # a page missing "height"/"words"
        '{"dpi": "x", "pages": []}',                          # non-numeric dpi → ValueError
    ):
        with pytest.raises((ValueError, KeyError, TypeError)):
            OcrLayout.from_json(bad)
