"""Deterministic piece identity (AD-40, AD-12).

A piece's identity is a function of (tenant, matter, content) — never of its
provenance path. A *matter* belongs to exactly one *tenant* (the spine's
`TENANT ||--o{ MATTER` ownership; audit chains are per `(tenant, matter)`, AD-43),
and matter names are tenant-local free strings — so *tenant* is inside the identity:
two firms that both name a matter "dupont" and hold the same file are two distinct
pieces, never a silent collision that would let one firm's ingest seize or overwrite
the other's (AD-12, tenant-first, fail-closed). Identity is stable across runs,
processes and installations, and is never allocated from a restarting counter.
"""

from __future__ import annotations

import hashlib


def content_hash(data: bytes) -> str:
    """A stable content hash of a piece's raw bytes."""
    return hashlib.sha256(data).hexdigest()


def piece_id(tenant: str, content_hash_hex: str, matter: str) -> str:
    """Deterministic piece id from (tenant, content, matter). Path is NOT part of
    identity; tenant IS (AD-12) — a matter is tenant-local, so the same file under the
    same matter name in two tenants is two distinct pieces."""
    if not tenant:
        raise ValueError("tenant is required")
    if not content_hash_hex:
        raise ValueError("content_hash_hex is required")
    if not matter:
        raise ValueError("matter is required")
    return hashlib.sha256(f"{tenant}\x00{matter}\x00{content_hash_hex}".encode()).hexdigest()


def chunk_id(
    piece_id_hex: str,
    full_text_version: str,
    position: int,
    chunking_config_version: str,
) -> str:
    """Deterministic chunk id from (piece, full-text version, position, chunking-config
    version) — AD-40. The **extractor is inside the identity of what it produced**:
    ``full_text_version`` is AD-10's version identity of the stored full text (it carries
    the extraction method and extractor version, AD-28), so a **re-extraction produces new
    chunks with new ids** — the old ones are retired by state, never overwritten in place
    (AD-7), and every artefact citing them is marked stale (AD-23). Never a restarting
    counter (the v1 defect): stable across runs, processes and installations, so a
    re-ingest under the same versions does not duplicate, and a re-extraction or re-chunk
    is a distinct, detectable generation."""
    if not piece_id_hex:
        raise ValueError("piece_id_hex is required")
    if not full_text_version:
        raise ValueError("full_text_version is required")
    if not isinstance(position, int) or isinstance(position, bool) or position < 0:
        raise ValueError("position must be a non-negative integer")
    if not chunking_config_version:
        raise ValueError("chunking_config_version is required")
    key = f"{piece_id_hex}\x00{full_text_version}\x00{position}\x00{chunking_config_version}"
    return hashlib.sha256(key.encode()).hexdigest()
