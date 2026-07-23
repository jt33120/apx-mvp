"""The triage use case — judge the uncertain band, carry every verdict's rationale.

Pure orchestration in the Application layer: it depends on the Domain and the
``Judge`` port, never on an adapter (AD-4), and the core imports no LLM SDK (AD-27).
The band it judges is the distinct set left after deduplication; a representative's
label stands for its whole near-duplicate cluster. Recall over precision lives in the
judge, not here — this use case just applies it and preserves the explanation, so no
label (least of all a discard) is ever silent.
"""

from __future__ import annotations

from apx.core.domain.triage import PieceLabel, TriageOutcome
from apx.core.ports.judge import Judge


def triage_pieces(pieces: list[tuple[str, str]], question: str, judge: Judge) -> TriageOutcome:
    """Judge each ``(piece_id, text)`` against the triage ``question``."""
    labels = []
    for piece_id, text in pieces:
        verdict = judge.judge(question=question, text=text)
        labels.append(PieceLabel(piece_id, verdict.label, verdict.rationale))
    return TriageOutcome(tuple(labels))
