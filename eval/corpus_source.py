"""Access to the lifted evaluation corpus (Story 2.12, FR-54) — a CONFIGURED DATA SOURCE, never a
fixture (FR-33). The corpus lives under ``eval/corpus/`` (a top-level tree, outside ``apx/`` and
``tests/``) and is ingested through the real ingestion path, exactly as client material is.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

_EVAL_ROOT = Path(__file__).resolve().parent
CORPUS_ROOT = _EVAL_ROOT / "corpus"
MANIFEST = CORPUS_ROOT / "manifest.json"
PROVENANCE = _EVAL_ROOT / "provenance.json"


def load_manifest() -> dict[str, Any]:
    """The gold manifest — ``{use_case, specialite, periode, avocats, dossiers, items}``. Each item
    is ``{id, rel, kind, date, gold_dossier, gold_pertinence}`` (``gold_dossier`` may be null)."""
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def load_provenance() -> dict[str, Any]:
    """The recorded licence/provenance verification for the specific distribution (FR-54)."""
    return json.loads(PROVENANCE.read_text(encoding="utf-8"))


def resolve(rel: str) -> Path:
    """The real file for a manifest item's ``rel``. The v1 ``raw/`` prefix is stripped — the corpus
    was lifted from ``data/mock/raw/`` into ``eval/corpus/``."""
    return CORPUS_ROOT / rel.removeprefix("raw/")


def corpus_digest() -> str:
    """A deterministic digest of the specific distribution (FR-54's recorded licence-verification
    step): sha256 over ``manifest.json`` and each of the manifest's item files, keyed by posix
    relpath (sorted) and concatenated with the bytes. It certifies THE EVAL SET (the manifest + its
    139 items), so a drift in the corpus is a detectable, reviewable event — while a stray OS file
    (a ``.DS_Store``) cannot spuriously invalidate it, because only the enumerated set is hashed.
    Stable across machines given a byte-preserving checkout (see the corpus ``.gitattributes``)."""
    rels = sorted({"manifest.json",
                   *(item["rel"].removeprefix("raw/") for item in load_manifest()["items"])})
    digest = hashlib.sha256()
    for rel in rels:
        digest.update(rel.encode())
        digest.update((CORPUS_ROOT / rel).read_bytes())
    return digest.hexdigest()
