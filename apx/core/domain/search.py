"""Deterministic exhaustive search — the safety net beneath triage (FR-13).

Whatever the cascade labelled, a lawyer can always find a named piece by typing a
term: a case-insensitive substring match over the stored full text — deterministic
(same query, same hits), exhaustive (every piece that contains the term), with no
model, no ranking, nothing that could silently hide a match. It is scope-constrained
like every read (the Chinese wall pre-filters search too — the query lives in the
store; this module is the pure snippet). A snippet shows where each hit matched, so
an in-word match ("bail" inside "travail") is self-evident rather than misleading.
"""

from __future__ import annotations


def snippet(text: str, term: str, *, width: int = 60) -> str:
    """A context window around the first case-insensitive occurrence of ``term`` in
    ``text``, whitespace collapsed for display and elided with … at any cut edge.
    Found in the raw text (matching the store's substring query), so if the query
    matched, the snippet shows it. An empty term or no match yields the text's head."""
    t = term.strip()
    flat_head = " ".join(text.split())[: 2 * width].strip()
    if not t:
        return flat_head
    i = text.lower().find(t.lower())
    if i < 0:
        return flat_head
    start = max(0, i - width)
    end = min(len(text), i + len(t) + width)
    window = " ".join(text[start:end].split())
    prefix = "… " if start > 0 else ""
    suffix = " …" if end < len(text) else ""
    return f"{prefix}{window}{suffix}"
