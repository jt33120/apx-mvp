"""The outcome of extracting text from one file — a domain value, store-independent."""

from __future__ import annotations

from dataclasses import dataclass

from apx.core.domain.failures import ErrorClass


@dataclass(frozen=True)
class ExtractOutcome:
    """Either text was extracted (error_class is None) or it failed (text is empty)."""

    text: str
    method: str
    version: str
    error_class: ErrorClass | None = None

    @property
    def ok(self) -> bool:
        return self.error_class is None and bool(self.text)
