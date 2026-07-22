"""Ingestion error classes (a subset of FR-5's enumerated, stable set).

A piece that does not enter the corpus is enumerated here, never dropped. This
slice covers the classes its minimal extraction can produce; the full set and the
failure-register table land in story 2.6.
"""

from __future__ import annotations

from enum import StrEnum


class ErrorClass(StrEnum):
    UNREADABLE = "unreadable"
    UNSUPPORTED_FORMAT = "unsupported-format"
    EXTRACTED_EMPTY = "extracted-empty"
    EXTRACTION_ERROR = "extraction-error"
    UNKNOWN = "unknown"
