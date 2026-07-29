"""The one *chunk* writer (story 1.3; AD-9, AD-40, AD-13). The single place a ``Chunk``
row is ever constructed — a static check asserts it stays the only one (Task 5).

The write is the increment's irreversible seam, so it is guarded on three sides and
defaults nothing:

1. **Completeness.** The ``PayloadRecord`` is validated at the boundary; an incomplete
   or inconsistent payload is rejected with a typed error, never written with a default
   (FR-8). A later story wires the rejection into the *failure register* (2.6).
2. **Scope.** ``rbac_scope`` is a **required argument with no default** and is *checked*,
   never stored: it must equal the *matter*'s authoritative scope in ``matter_scope``
   (AD-13), under the same *tenant* (AD-12, tenant-first, fail-closed). Because scope is
   not a column, a re-scope takes effect at the next read with nothing to propagate.
3. **Version.** The writer is stamped at construction with the *import job*'s schema and
   chunking versions; a payload under different versions halts rather than mixing two
   generations of *chunks* inside one *matter* (AD-40).
"""

from __future__ import annotations

from sqlalchemy.orm import Session, sessionmaker

from apx.adapters.store_postgres.models import EMBEDDING_DIM, Chunk, MatterScope
from apx.core.domain.identity import chunk_id, piece_id
from apx.core.domain.payload import PayloadRecord


class UnauthorizedScope(Exception):
    """The caller's RBAC scope is not the *matter*'s authoritative scope, or is empty
    (AD-12/AD-13). Fail closed: a *chunk* is never written under an unauthorised scope."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class VersionMismatch(Exception):
    """The payload's schema/chunking version differs from the one the *import job*
    started under (AD-40). The write halts rather than mixing generations in one matter."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class PieceIdentityMismatch(Exception):
    """The payload's ``source_piece_id`` is not ``piece_id(content_hash, matter)`` — the
    chunk would reference a *pièce* that does not match its own provenance. Because
    ``piece_id`` encodes the *matter* (AD-40), this is a cross-matter hazard, so the single
    write seam rejects it fail-closed (AD-12)."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class ChunkStore:
    """The single implementation of the ``ChunkWriter`` port. Stamped at construction
    with the active *schema* and *chunking* versions — the *import job*'s generation."""

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        *,
        schema_version: str,
        chunking_config_version: str,
    ) -> None:
        self._sf = session_factory
        self._schema_version = schema_version
        self._chunking_config_version = chunking_config_version

    def write_chunk(
        self, payload: PayloadRecord, *, rbac_scope: str,
        vector: list[float], model_id: str, model_version: str,
    ) -> str:
        """Write one embedded *chunk* (story 2.8). The embedding trio (``vector`` +
        ``model_id``/``model_version``, AD-11) is a write-time argument, NOT part of the frozen
        ``PayloadRecord`` (1.3's non-embedding provenance). A vector whose width ≠ the column
        dimension **halts** and writes nothing (AC4 — a dimension mismatch never self-deletes)."""
        # 1. Completeness — reject at the boundary (raises IncompletePayload).
        payload.validate()
        # 1a. Dimension guard (AD-11/FR-10): a wrong-width vector halts here, before any write —
        #     it never truncates or recreates the index (the v1 self-wipe defect).
        if len(vector) != EMBEDDING_DIM or not model_id.strip() or not model_version.strip():
            raise VersionMismatch(
                f"embedding is {len(vector)}-dim (expected {EMBEDDING_DIM}) or its model identity "
                "is blank — the unit halts, the corpus is untouched")

        # 1b. The referenced pièce must be the one this payload describes. piece_id encodes
        #     (content, matter) (AD-40), so a mismatch means the chunk would point at another
        #     matter's pièce — a Chinese-wall hazard the single seam refuses (AD-12).
        expected_piece = piece_id(payload.tenant, payload.content_hash, payload.matter)
        if payload.source_piece_id != expected_piece:
            raise PieceIdentityMismatch(
                f"source_piece_id {payload.source_piece_id!r} != "
                f"piece_id(tenant, content_hash, matter) {expected_piece!r}"
            )

        # 3. Version guard — refuse a chunk from a different generation (AD-40). Checked
        #    before any write so a mismatch touches nothing.
        if payload.schema_version != self._schema_version:
            raise VersionMismatch(
                f"payload schema_version {payload.schema_version!r} != import job "
                f"{self._schema_version!r} — one matter never holds two generations"
            )
        if payload.chunking_config_version != self._chunking_config_version:
            raise VersionMismatch(
                f"payload chunking_config_version {payload.chunking_config_version!r} != "
                f"import job {self._chunking_config_version!r}"
            )

        # 2a. An empty scope is never authorised — reject before touching the store.
        if not rbac_scope or not rbac_scope.strip():
            raise UnauthorizedScope("an empty RBAC scope is never authorised (fail closed)")

        cid = chunk_id(
            payload.source_piece_id,
            payload.text_version,
            payload.position,
            payload.chunking_config_version,
        )
        with self._sf() as session, session.begin():
            # 2b. Scope is checked against the matter's authoritative row, never persisted.
            # keyed by the composite (tenant, matter) PK — a matter is tenant-local (AD-12)
            authorised = session.get(
                MatterScope, {"tenant": payload.tenant, "matter": payload.matter}
            )
            if (
                authorised is None
                or authorised.scope != rbac_scope
                or authorised.tenant != payload.tenant
            ):
                raise UnauthorizedScope(
                    f"scope {rbac_scope!r} is not authorised for matter "
                    f"{payload.matter!r} (tenant {payload.tenant!r})"
                )
            # The one Chunk construction site. `merge` makes a re-write idempotent
            # (deterministic id → same row), never a duplicate (AD-17).
            session.merge(
                Chunk(
                    chunk_id=cid,
                    piece_id=payload.source_piece_id,
                    tenant=payload.tenant,
                    matter=payload.matter,
                    position=payload.position,
                    full_text_version=payload.text_version,
                    chunking_config_version=payload.chunking_config_version,
                    schema_version=payload.schema_version,
                    external_ref=None,
                    model_id=model_id,
                    model_version=model_version,
                    vector=vector,
                )
            )
        return cid
