"""The Embedder port — the boundary semantic search depends on (AD-4, AD-27).

Deterministic search (FR-13) finds a term; semantic search finds pieces that *speak
of* a subject, past the literal words. That needs a vector for each piece and one for
the query, from the same model. An Embedder turns text into those vectors; a
provider-agnostic API adapter (Mistral, EU-hosted) or a local model (BGE-M3, offline)
implements it, and the core imports neither. `dimensions` fixes the pgvector column
width, so the store and the embedder never disagree.
"""

from __future__ import annotations

from typing import Protocol


class EmbedderError(Exception):
    """The Embedder's failure contract (FR-9/AD-11): the embedder fails **loudly** — it raises one
    of these, it NEVER degrades to a fallback, a stub, or a hash (the v1 defect). Each subclass maps
    one-to-one to a *failure register* error class, so a halted unit is attributed, not silent."""


class EmbedderUnavailable(EmbedderError):
    """The model or service is unreachable — a connection failure, or (for the local backend) the
    model dependency is not installed. Fails loud; it never falls back to a second embedder."""


class EmbedderRateLimited(EmbedderError):
    """The provider rejected the call for rate/quota (e.g. HTTP 429) — retryable later."""


class EmbedderTimeout(EmbedderError):
    """The embedding call did not return within its bound."""


class EmbedderDimensionMismatch(EmbedderError):
    """The embedder returned a vector whose width is not ``dimensions`` — a mixed-model hazard that
    halts the unit; it never truncates or reshapes to fit (which would corrupt the index)."""


class EmbedderAuthFailed(EmbedderError):
    """The provider rejected the credential (e.g. HTTP 401/403)."""


class Embedder(Protocol):
    dimensions: int   # the vector width — must match the pgvector column
    model_id: str     # the embedder's identity, stamped on every chunk (AD-11 — detectability)
    model_version: str  # so a mixed-provenance corpus is DETECTABLE, not merely suspected

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed each text into a `dimensions`-long vector, in order. Recall-first: an
        empty input yields an empty list; the adapter never fabricates a vector."""
        ...
