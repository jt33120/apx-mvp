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


def chunk_id(piece_id_hex: str, position: int, chunking_config_version: str) -> str:
    """Deterministic chunk id from (piece, position, chunking-config version) — AD-9,
    AD-40. Never a restarting counter (the v1 defect): the same passage under the same
    chunking configuration has the same id across runs, processes and installations, so
    a re-ingest does not duplicate and a re-chunk under a new configuration is a
    distinct, detectable generation."""
    if not piece_id_hex:
        raise ValueError("piece_id_hex is required")
    if not isinstance(position, int) or isinstance(position, bool) or position < 0:
        raise ValueError("position must be a non-negative integer")
    if not chunking_config_version:
        raise ValueError("chunking_config_version is required")
    key = f"{piece_id_hex}\x00{position}\x00{chunking_config_version}"
    return hashlib.sha256(key.encode()).hexdigest()
