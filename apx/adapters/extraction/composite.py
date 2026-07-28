"""Compose extractors: the first that recognises the format wins (mirrors expansion/composite).

A format-specific extractor (the out-of-process ``.msg`` one) sits ahead of the general
``FileExtractor``; each declines a format it does not handle with ``unsupported-format``, so
the chain routes ``.msg`` to the ``.msg`` extractor and everything else onward, and a format
no extractor handles still ends as ``unsupported-format`` (counted, never vanished — FR-3/AC4).
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from apx.core.domain.extraction import ExtractOutcome
from apx.core.domain.failures import ErrorClass
from apx.core.ports.extraction import Extractor


class CompositeExtractor:
    """Implements the Extractor port by delegating to a chain; the first extractor whose
    outcome is not ``unsupported-format`` wins."""

    def __init__(self, extractors: Iterable[Extractor]) -> None:
        self._extractors = tuple(extractors)

    def extract(self, path: Path) -> ExtractOutcome:
        outcome = ExtractOutcome("", "none", "composite/1", ErrorClass.UNSUPPORTED_FORMAT)
        for extractor in self._extractors:
            outcome = extractor.extract(path)
            if outcome.error_class is not ErrorClass.UNSUPPORTED_FORMAT:
                return outcome
        return outcome  # every extractor declined → the last unsupported-format outcome
