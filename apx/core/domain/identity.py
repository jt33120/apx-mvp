"""Deterministic piece identity (AD-40).

A piece's identity is a function of (content, matter) — never of its provenance
path. The same file imported into two matters is two pieces; confidentiality
follows the matter. Identity is stable across runs, processes and installations,
and is never allocated from a restarting counter (the v1 defect).
"""

from __future__ import annotations

import hashlib


def content_hash(data: bytes) -> str:
    """A stable content hash of a piece's raw bytes."""
    return hashlib.sha256(data).hexdigest()


def piece_id(content_hash_hex: str, matter: str) -> str:
    """Deterministic piece id from (content, matter). Path is NOT part of identity."""
    if not content_hash_hex:
        raise ValueError("content_hash_hex is required")
    if not matter:
        raise ValueError("matter is required")
    return hashlib.sha256(f"{matter}\x00{content_hash_hex}".encode()).hexdigest()
