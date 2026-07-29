"""The embedding vector column type (story 2.8, AD-11).

``Halfvec`` is a SQLAlchemy ``TypeDecorator`` that stores a 1024-dim embedding as pgvector's
``halfvec`` on PostgreSQL — the production type HNSW indexes and queries — while degrading to a
portable ``JSON`` list of floats on any other dialect, so the in-memory SQLite tests (which run
``Base.metadata.create_all``) create and round-trip the column with no pgvector extension. The
physical type is chosen per dialect in :meth:`load_dialect_impl`; both underlying types accept and
return a ``list[float]`` of width ``dim``.

The vector holds document-derived content, so it is encrypted **at the volume**, never at the
application layer (AD-31) — a randomised AES-GCM column could never be HNSW-indexed or searched.
So this is NOT an ``EncryptedText`` column and is deliberately absent from ``ENCRYPTED_COLUMNS``.
"""

from __future__ import annotations

from sqlalchemy import JSON
from sqlalchemy.types import TypeDecorator


class Halfvec(TypeDecorator):
    """A fixed-width embedding vector. ``halfvec(dim)`` on PostgreSQL (pgvector), a ``JSON`` list of
    floats elsewhere. ``dim`` participates in the type cache key (``cache_ok``)."""

    impl = JSON
    cache_ok = True

    def __init__(self, dim: int) -> None:
        self.dim = dim
        super().__init__()

    def load_dialect_impl(self, dialect: object):  # noqa: ANN201 — SQLAlchemy dialect impl
        if getattr(dialect, "name", None) == "postgresql":
            from pgvector.sqlalchemy import HALFVEC  # PG-only; keeps SQLite free of pgvector DDL

            return dialect.type_descriptor(HALFVEC(self.dim))  # type: ignore[attr-defined]
        return dialect.type_descriptor(JSON())  # type: ignore[attr-defined]
