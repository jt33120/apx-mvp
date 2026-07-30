"""The semantic search engine (Story 3.1, AD-16/AD-20) — the first reader through the one read entry
point (AD-14). It embeds the query with the same model that embedded the *chunks*, runs a scoped
nearest-neighbour search, and constructs a **suggestive** result set — the constant truth status is
a property of ``SuggestiveResultSet`` (AD-20), set nowhere here by a threshold or a config.

Scope is a query **pre-filter** (AD-13): ``scopes`` is passed into the search, never applied to a
fetched result set. A caller with no scope reads nothing (fail-closed, AD-12) — the engine
short-circuits before it even embeds the query.
"""

from __future__ import annotations

from collections.abc import Callable

from apx.core.domain.config import coerce
from apx.core.domain.retrieval import SuggestiveResultSet
from apx.core.ports.embedding import Embedder, EmbedderError
from apx.core.ports.read import SemanticReader


def search_semantic(
    *,
    tenant: str,
    scopes: set[str],
    query: str,
    embedder: Embedder,
    reader: SemanticReader,
    k: int,
    config_get: Callable[[str], object],
) -> SuggestiveResultSet:
    """Embed ``query``, run the scoped top-``k`` nearest-neighbour search over the *chunk* index,
    and return a ``SuggestiveResultSet`` — ranked, ≤ ``k``, each result openable via ``chunk_id``. A
    caller with an empty scope set gets an empty set without a query being run (fail-closed, AD-12).

    The similarity floor is **configuration-as-data** (AD-24): the engine resolves it from
    ``config_get`` (e.g. ``lambda k: store.get_config(tenant, k)``), so the value that runs — and
    that the result records — is the tenant's configured one, never a caller-supplied override.
    ``k`` is a result-shape bound (a page of results), not a latency target (NFR-2)."""
    # coerce (not bare float): validates type + the cosine range, so a stray bool/str/out-of-range
    # config value fails loud rather than silently disabling retrieval (True → 1.0 admits nothing).
    similarity_threshold = float(coerce("similarity_threshold", config_get("similarity_threshold")))
    if not scopes:
        return SuggestiveResultSet(results=(), k=k, similarity_threshold=similarity_threshold)
    vectors = embedder.embed([query])
    if not vectors:  # the port yields one vector per non-empty input; empty is a contract breach
        raise EmbedderError("the embedder returned no vector for the query")
    query_vector = vectors[0]
    results = reader.search_semantic(
        tenant=tenant,
        scopes=scopes,
        query_vector=query_vector,
        k=k,
        min_similarity=similarity_threshold,
    )
    return SuggestiveResultSet(
        results=tuple(results), k=k, similarity_threshold=similarity_threshold
    )
