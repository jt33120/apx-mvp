"""Fake ``Embedder`` implementations for tests — substituted at the port boundary INSIDE the test
process (AD-11), never in the runtime tree, so the ``embedder_has_one_implementation`` structural
property is unaffected (it scans ``apx/`` only). These stand in for the real BGE-M3 model so the
suite never loads it."""

from __future__ import annotations

from collections.abc import Callable

from apx.adapters.store_postgres.models import EMBEDDING_DIM
from apx.core.ports.embedding import EmbedderError


class FakeEmbedder:
    """A deterministic 1024-dim embedder — every text embeds to the same valid vector."""

    dimensions = EMBEDDING_DIM
    model_id = "fake-embedder"
    model_version = "fake-v1"

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.1] * EMBEDDING_DIM for _ in texts]


class FailingEmbedder:
    """Raises a given ``EmbedderError`` for any text matching ``fails_on`` (default: all), and
    embeds the rest normally — for the transient-failure job tests (AC5)."""

    dimensions = EMBEDDING_DIM
    model_id = "fake-embedder"
    model_version = "fake-v1"

    def __init__(
        self, error: EmbedderError, *, fails_on: Callable[[str], bool] = lambda _t: True,
    ) -> None:
        self._error = error
        self._fails_on = fails_on

    def embed(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for text in texts:
            if self._fails_on(text):
                raise self._error
            out.append([0.1] * EMBEDDING_DIM)
        return out
