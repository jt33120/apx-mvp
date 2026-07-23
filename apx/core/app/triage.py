"""The triage use case — judge the uncertain band, carry every verdict's rationale.

Pure orchestration in the Application layer: it depends on the Domain and the
``Judge`` port, never on an adapter (AD-4), and the core imports no LLM SDK (AD-27).
The band it judges is the distinct set left after deduplication; a representative's
label stands for its whole near-duplicate cluster. Recall over precision lives in the
judge, not here — this use case just applies it and preserves the explanation, so no
label (least of all a discard) is ever silent.

Per-piece judgment is the system's dominant cost, and the LLM tier's cost is network
latency, not CPU. So judging is dispatched over a bounded thread pool: the calls
overlap (I/O-bound work releases the GIL), which is what makes 5,000 documents
tractable. Results are gathered in input order, so labels stay aligned to their pieces.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from apx.core.domain.triage import PieceLabel, TriageOutcome
from apx.core.ports.judge import Judge


def triage_pieces(
    pieces: list[tuple[str, str]], question: str, judge: Judge, *, workers: int = 1
) -> TriageOutcome:
    """Judge each ``(piece_id, text)`` against the triage ``question``. With
    ``workers`` > 1 the judgments run concurrently over a thread pool (bounded), which
    matters for the network-bound LLM tier; order is preserved."""

    def label_one(item: tuple[str, str]) -> PieceLabel:
        piece_id, text = item
        verdict = judge.judge(question=question, text=text)
        return PieceLabel(piece_id, verdict.label, verdict.rationale)

    if workers <= 1 or len(pieces) <= 1:
        labels = [label_one(item) for item in pieces]
    else:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            labels = list(pool.map(label_one, pieces))  # map preserves input order
    return TriageOutcome(tuple(labels))
