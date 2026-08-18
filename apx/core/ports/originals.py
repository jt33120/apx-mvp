"""The OriginalStore port — the retained-original boundary the core depends on (AD-4, Story 3.5a).

The pièce viewer must **render** documents, not only their extracted text, so the ORIGINAL bytes
of every ingested pièce are retained at rest — content-addressed by ``content_hash`` (AD-40),
partitioned by ``tenant``, encrypted at rest (AD-31), inside the tenant boundary. Adapters (a
filesystem store on the data volume) implement this; the ingest use case depends only on the port.

``put`` is called at pièce-creation, streaming each blob as it is produced (never accumulating a
whole import in memory), and is idempotent — the same content within a tenant is stored once.
``open`` (the read side) exists for the read path (Story 3.5b/c); this increment wires only ``put``.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Protocol


class OriginalStore(Protocol):
    def put(self, tenant: str, content_hash: str, data: bytes, kind: str = "original") -> None:
        """Retain ``data`` for ``(tenant, content_hash, kind)``, encrypted at rest. ``kind`` selects
        the artifact — ``original`` (the file bytes) or a derived kind like ``ocr-layout`` (Story
        3.5c-1) — bound into the AAD, so one kind can never be read as another. Idempotent: a blob
        already present for that identity is not rewritten. Raises ``OSError`` on a disk failure —
        the caller records it as that pièce's failure, never an escape."""
        ...

    def open(self, tenant: str, content_hash: str, kind: str = "original") -> bytes:
        """The retained bytes for ``(tenant, content_hash, kind)``, decrypted. Fails closed — raises
        when the blob is absent, tampered, or unauthenticated (never returns garbage)."""
        ...

    def size(self, tenant: str, content_hash: str, kind: str = "original") -> int | None:
        """The retained blob's PLAINTEXT byte size, or ``None`` when absent — the viewer's
        render-bound decision (Story 3.5b/c), computed WITHOUT decrypting the blob."""
        ...

    # ── the sealed face: backup and restore (Story 7.2, AD-32) ──────────────────────────────
    #
    # AD-32's Rule names the *originals* first among the things a complete backup carries, and
    # nothing copied them. They move as the ciphertext they already are, because a backup that
    # decrypted a firm's corpus in order to copy it would put the whole corpus in memory in the
    # clear and would make the operator taking the backup hold the key. Neither is necessary: the
    # blob is already sealed, and its AAD binds it to (tenant, content_hash, kind), so a blob
    # restored under a different identity fails authentication instead of being served.

    def sealed_blobs(self, tenant: str) -> Iterator[tuple[str, str]]:
        """Every retained ``(content_hash, kind)`` for ``tenant``, from the store itself rather
        than from a table that lists what *should* be there — so a derived kind nobody wrote down
        travels too. Fails closed on an unrecognised blob name."""
        ...

    def read_sealed(self, tenant: str, content_hash: str, kind: str = "original") -> bytes:
        """The blob exactly as stored — still ciphertext. No key required, and none used."""
        ...

    def put_sealed(
        self, tenant: str, content_hash: str, kind: str, sealed: bytes
    ) -> None:
        """Put back bytes taken by :meth:`read_sealed`, unchanged. The AAD is inside them, so a
        blob written under a tenant/hash/kind that is not its own is unreadable rather than
        wrong — a mis-restored bundle cannot serve one firm's document as another's."""
        ...
