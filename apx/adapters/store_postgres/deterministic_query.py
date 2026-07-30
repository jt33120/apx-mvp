"""The PostgreSQL deterministic exact-search query (Story 3.2, AD-20/AD-21).

The COMPLETE match over ``piece.full_text_normalized`` — the ``normalize()`` (``fr-fold-v1``) rule
applied to the full text at write time (``models._normalise_full_text``). The query is normalised by
the SAME ``normalize()``, so the index and the query share ONE implementation: a normalisation
divergence cannot cause a false absence (there is no second, SQL-side fold to drift from). A plain
``LIKE`` — no ``unaccent`` — so this runs on every dialect and the round-trip is CI-testable.

Scope is **joined from ``matter_scope`` as a pre-filter** (AD-13, tenant on both sides — mirror
``semantic_query.py``, including the defence-in-depth ``matter_scope.tenant`` literal), and there is
crucially **NO ``LIMIT``** — an exhaustive set is never truncated (AD-20). LIKE metacharacters in
the query are escaped, so "exact normalised containment" is exact, not a wildcard (AD-21).
"""

from __future__ import annotations

from sqlalchemy import Select, select

from apx.adapters.store_postgres.models import MatterScope, Piece


def _like_escape(term: str) -> str:
    """Escape LIKE metacharacters so a literal ``%``/``_``/``\\`` in the query is not a wildcard."""
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def exact_search_stmt(*, tenant: str, scopes: set[str], normalized_query: str) -> Select:
    """The complete scoped exact match — no ``LIMIT`` (AD-20). ``normalized_query`` is the query
    already folded by ``normalize()``; the column was folded by the same rule at write time."""
    pattern = f"%{_like_escape(normalized_query)}%"
    return (
        select(Piece.matter, Piece.id, Piece.full_text)
        .join(
            MatterScope,
            (MatterScope.matter == Piece.matter) & (MatterScope.tenant == Piece.tenant),
        )
        .where(Piece.tenant == tenant)                          # tenant first (AD-12)
        .where(MatterScope.tenant == tenant)                    # defence-in-depth (mirror 3.1)
        .where(MatterScope.scope.in_(sorted(scopes)))           # the scope PRE-filter (AD-13)
        .where(Piece.full_text_normalized.like(pattern, escape="\\"))   # normalised containment
        .order_by(Piece.matter, Piece.id)                       # deterministic; NO limit (AD-20)
    )
