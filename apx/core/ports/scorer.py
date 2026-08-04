"""The SemanticScorer port — the cascade's stage-2 boundary (Story 4.2, FR-38 / AD-18 / AD-4).

Stage 2 scores each representative pièce cheaply against a query (the case theory), over the FR-9
embeddings already produced — the difference between the €2 000 box and the €20 000 one is spending
the LLM (stage 3) only on what this cheap tier could not separate. The core depends on this port and
imports no adapter (AD-4); a Postgres adapter runs the halfvec cosine over the corpus, and a fake
stands in for tests (the scorer is Postgres-only, so its behavioural run is pg-gated).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Protocol


class SemanticScorer(Protocol):
    def score(
        self, *, tenant: str, matter: str, scopes: set[str], query_text: str,
        piece_ids: Sequence[str],
    ) -> Mapping[str, float]:
        """A cheap relevance score in ``[-1, 1]`` for each of ``piece_ids`` — the maximum cosine of
        the pièce's chunks to the embedded ``query_text`` — over the corpus embeddings, **scope
        pre-filtered** (AD-13). A pièce with no scorable chunk is **absent** from the returned
        mapping (the caller reads absence as no-signal, never as a zero — AD-19). Never proves
        absence."""
        ...
