"""The Store write contract — the boundary the frozen payload schema is written across
(story 1.3, AD-9). Ports are protocols only; the core imports no adapter (AD-4).

``ChunkWriter`` is where "one writer, scope required" is *expressed*: a single method,
taking the complete ``PayloadRecord`` and the caller's *RBAC scope* as a **required
argument with no default**. Scope is an argument and never a field (AD-9/AD-13/AD-40) —
the writer checks it against the *matter*'s authoritative scope at write time and does
not persist it, so a re-scope takes effect at the next read with nothing to propagate.
The adapter (``store_postgres``) provides the one implementation; a static check asserts
there is exactly one (story 1.3, Task 5).
"""

from __future__ import annotations

from typing import Protocol

from apx.core.domain.payload import PayloadRecord


class ChunkWriter(Protocol):
    def write_chunk(self, payload: PayloadRecord, *, rbac_scope: str) -> str:
        """Write one *chunk* and its *pièce* provenance under an authorised scope, and
        return the deterministic ``chunk_id``.

        ``rbac_scope`` is required and has no default: a *chunk* is never written under
        an unstated or empty scope. The implementation rejects — with a typed error,
        never a silent default — an incomplete payload, a scope not authorised for the
        payload's *matter*, or a *schema/chunking* version that differs from the one the
        in-flight *import job* started under (AD-9, AD-40; FR-8)."""
        ...
