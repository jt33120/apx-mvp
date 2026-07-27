"""Two concrete Embedder implementations — a FALLBACK, the FR-9/AD-11 violation. AST-scanned."""

from __future__ import annotations


class PrimaryEmbedder:
    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] for _ in texts]


class FallbackEmbedder:  # the forbidden second implementation — there is no fallback embedder
    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] for _ in texts]
