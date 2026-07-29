"""Deterministic passage chunking with provenance to the exact source span (Story 2.9, FR-11).

Provenance is **resolved, not stored**: AD-9 freezes the ``chunk`` columns with no offset column, so
a chunk carries only ``(position, full_text_version, chunking_config_version)``. The passage is
recovered by re-chunking the *pièce*'s stored full text (AD-10) under the recorded configuration and
taking ``position``. This module is that deterministic function — pure domain, no DB, no adapter
(AD-4). Because a passage is an exact slice ``full_text[start:end]``, an exact-string-containment
check (FR-11) is trivially true for a fresh passage and fails only when the source has changed.

The splitter is hand-rolled and deterministic — **no** ``langchain``/``nltk``/``spacy`` (the install
is offline and single-machine, and library tokenizers drift across versions and locales). It snaps
boundaries to sentence/paragraph ends and **never cuts inside a French legal citation or
abbreviation** (``art. L. 1235-3``, ``n° 21-12.345``, ``M.``, ``Cass. soc.``, …) — the exact forms
the v1 sentence splitter broke mid-token.
"""

from __future__ import annotations

import hashlib
import json
from bisect import bisect_right
from collections.abc import Callable, Iterable
from dataclasses import dataclass

# Abbreviations whose trailing dot is NOT a sentence end (French legal + common). Over-inclusion is
# safe (it only yields larger passages); under-inclusion breaks a citation (FR-11/AC8), so err wide.
_ABBREV: frozenset[str] = frozenset({
    "m", "mm", "mme", "mmes", "me", "mes", "mlle",           # civility
    "art", "al", "l", "r", "d", "no", "nos", "p", "pp",      # article / paragraph / page
    "cass", "soc", "civ", "com", "crim", "ch", "req", "ass", "plén", "mixte",  # jurisdictions
    "c", "cf", "ex", "etc", "op", "cit", "s", "ss", "vol", "t", "fasc", "éd", "ed", "spéc", "n",
})


@dataclass(frozen=True)
class Passage:
    """One passage of a *pièce*'s full text with the exact source span it came from. ``text`` is
    exactly ``full_text[start:end]`` — provenance to the character (FR-11)."""

    text: str
    start: int
    end: int


@dataclass(frozen=True)
class ChunkingConfig:
    """The chunking parameters as configuration-as-data. Its ``version`` is **derived from the
    content** (a short stable hash of the canonical params), so the identity stamped on a chunk can
    never diverge from the parameters that produced it (AD-40, immutable per version): a change to
    any parameter is a new version = a new generation, never a silent re-chunk of existing rows."""

    target_chars: int = 1200

    def __post_init__(self) -> None:
        if not isinstance(self.target_chars, int) or isinstance(self.target_chars, bool):
            raise ValueError("target_chars must be an integer")
        if self.target_chars < 1:
            raise ValueError("target_chars must be >= 1")

    @property
    def version(self) -> str:
        """The content-derived identity carried into every ``chunk_id`` (AD-40): stable across runs,
        processes and installations; two configs with the same params share it and any change breaks
        it. Prefixed and truncated to 16 chars — short, and under the secret-token entropy floor."""
        canonical = json.dumps({"target_chars": self.target_chars}, sort_keys=True,
                               separators=(",", ":"))
        return "c" + hashlib.sha256(canonical.encode()).hexdigest()[:15]


def chunking_config(get: Callable[[str], object]) -> ChunkingConfig:
    """Build the chunking configuration from a per-key getter (e.g. ``lambda k:
    store.get_config(tenant, k)``) — configuration-as-data (AD-24), mirroring
    ``config.expansion_bounds``. The version is derived, so it is never read from config."""
    return ChunkingConfig(target_chars=int(get("chunking_target_chars")))


def _sentence_end(text: str, i: int) -> bool:
    """Whether the terminator ``text[i]`` (one of ``. ! ?``) ends a sentence. ``!``/``?`` always do;
    a ``.`` does not when it sits inside a number (``12.345``) or closes a known abbreviation."""
    if text[i] != ".":
        return True
    if i > 0 and text[i - 1].isdigit():  # a decimal / citation number, e.g. 21-12.345
        return False
    j = i - 1
    while j >= 0 and (text[j].isalpha() or text[j] == "°"):
        j -= 1
    return text[j + 1:i].lower() not in _ABBREV


def _boundaries(text: str) -> list[int]:
    """The offsets where a passage MAY end — one past the whitespace following a real sentence
    terminator, and one past any newline. Trailing whitespace stays with the passage it follows, so
    the passages tile the text exactly. End-of-text is never a boundary; the last passage reaches
    it on its own."""
    n = len(text)
    bounds: set[int] = set()
    for i, ch in enumerate(text):
        if (ch in ".!?" and _sentence_end(text, i)) or ch == "\n":
            j = i + 1
            while j < n and text[j].isspace():
                j += 1
            if 0 < j < n:  # never end-of-text (no empty trailing passage) and never offset 0
                bounds.add(j)
    return sorted(bounds)


def chunk(full_text: str, config: ChunkingConfig) -> list[Passage]:
    """Split ``full_text`` into contiguous passages under ``config`` — deterministic (AC1), each an
    exact slice with its ``(start, end)`` provenance (AC3), snapped to sentence/paragraph boundaries
    so no French legal citation is cut (AC8). Greedy: take the furthest boundary within
    ``target_chars`` of the current start; if none, take the next boundary rather than cut a
    sentence; if there is none at all, the passage runs to the end."""
    n = len(full_text)
    if n == 0:
        return []
    bounds = _boundaries(full_text)
    passages: list[Passage] = []
    start = 0
    while start < n:
        limit = start + config.target_chars
        if limit >= n:
            end = n
        else:
            lo = bisect_right(bounds, start)  # first boundary strictly after start
            hi = bisect_right(bounds, limit)  # first boundary strictly after the limit
            if hi > lo:                        # a boundary in (start, limit] → take the furthest
                end = bounds[hi - 1]
            elif hi < len(bounds):             # none within the budget → the next one (don't cut)
                end = bounds[hi]
            else:                              # no boundary left at all → run to the end
                end = n
        passages.append(Passage(text=full_text[start:end], start=start, end=end))
        start = end
    return passages


# ── Resolution: recovering a chunk's exact passage from the stored full text (Story 2.9, FR-11) ──

# The enumerated resolution-failure causes — a closed set, surfaced verbatim wherever an extract
# appears; a failed resolution is NEVER shown as though it resolved (AD-10).
PIECE_GONE = "piece-gone"
TEXT_CHANGED = "text-changed"
CONFIG_SUPERSEDED = "config-superseded"
POSITION_OUT_OF_RANGE = "position-out-of-range"
CONTAINMENT_FAILED = "containment-failed"


@dataclass(frozen=True)
class ResolvedPassage:
    """A chunk resolved to its exact source span — provenance to the character (FR-11). ``text`` is
    exactly ``full_text[start:end]``."""

    text: str
    start: int
    end: int


@dataclass(frozen=True)
class FailedResolution:
    """A chunk that could not be resolved at read time (FR-11). ``cause`` is one of the enumerated
    constants above; its containing export/citation is marked degraded (AD-10) and the extract is
    never displayed as though it resolved."""

    cause: str


def resolve_passage(
    *, full_text: str, piece_text_version: str, piece_text_identity: str,
    chunk_full_text_version: str, chunk_position: int, chunk_config_version: str,
    config: ChunkingConfig, expected_text: str | None = None,
) -> ResolvedPassage | FailedResolution:
    """Resolve a chunk to its exact source passage by re-chunking the pièce's stored full text and
    taking ``chunk_position`` (provenance by resolution, AD-9/AD-10). Returns a ``FailedResolution``
    (never a passage) when the text changed under re-extraction, the config was superseded (AD-40),
    the position is gone, or a supplied ``expected_text`` is no longer in the resolved passage. A
    missing pièce (``piece-gone``) is the caller's to detect.

    The primary text-changed guard is the version: a re-extraction bumps ``full_text_version``
    (AD-40/AD-28), so old chunks become TEXT_CHANGED. The sha256 check is a secondary torn-row
    backstop; it fires only if the stored full text is out of sync with its recorded
    ``text_identity`` (corruption / partial write / migration bug), never on the normal path. AD-9
    stores no per-chunk text identity, so the version is the binding."""
    if chunk_full_text_version != piece_text_version:
        return FailedResolution(TEXT_CHANGED)  # a re-extraction produced a new full-text version
    if hashlib.sha256(full_text.encode()).hexdigest() != piece_text_identity:
        return FailedResolution(TEXT_CHANGED)  # torn row: full text desynced from its identity
    if config.version != chunk_config_version:
        return FailedResolution(CONFIG_SUPERSEDED)  # a superseded chunking generation (AD-40)
    passages = chunk(full_text, config)
    if not 0 <= chunk_position < len(passages):
        return FailedResolution(POSITION_OUT_OF_RANGE)
    passage = passages[chunk_position]
    if expected_text is not None and expected_text not in passage.text:
        return FailedResolution(CONTAINMENT_FAILED)  # a stored extract no longer in THIS passage
    return ResolvedPassage(text=passage.text, start=passage.start, end=passage.end)


def is_degraded(resolutions: Iterable[ResolvedPassage | FailedResolution]) -> bool:
    """An export/citation is DEGRADED if any extract it carries failed to resolve (AD-10): the
    container states it on its face and a failed extract is never presented as current."""
    return any(isinstance(r, FailedResolution) for r in resolutions)
