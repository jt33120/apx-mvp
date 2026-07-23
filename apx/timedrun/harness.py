"""The timed-run gate (U2): measure the judgment cascade at scale before committing to
any performance number.

The gate the architecture puts before every performance commitment. It runs the two
compute stages of the cascade over N documents — deduplication (deterministic, cheap)
then judging (the network-bound LLM band, concurrent) — and reports the envelope:
how far dedup collapses the corpus, how much the deterministic filter promotes for
free, how large the residual LLM band is, and the throughput at a given concurrency.

Offline it uses a deterministic stub (optionally with a simulated latency) so the
non-LLM envelope and the concurrency speedup are provable without spend; set a model
(MISTRAL_API_KEY / LLM_API_KEY) to time the real band. This is edge tooling, run on
demand — never in CI (a real 5,000-doc run costs money and minutes).
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass

from apx.adapters.judge.criteria import CriteriaJudge
from apx.adapters.llm_openai_compat.judge import CascadeJudge
from apx.core.app.triage import triage_pieces
from apx.core.domain.dedup import text_key
from apx.core.domain.triage import Label, Verdict
from apx.core.ports.judge import Judge


class StubJudge:
    """A deterministic fallback for offline timing: near-instant, with an optional
    latency to stand in for an LLM round-trip. Discards everything — recall is the real
    judge's concern; this exists only to measure throughput."""

    name = "stub"

    def __init__(self, latency: float = 0.0) -> None:
        self.latency = latency

    def judge(self, *, question: str, text: str) -> Verdict:
        if self.latency:
            time.sleep(self.latency)
        return Verdict(Label.DISCARD, "stub")


class _Counting:
    """Wrap a judge to count how many pieces reach it — i.e. the LLM band size."""

    def __init__(self, inner: Judge) -> None:
        self._inner = inner
        self.name = inner.name
        self.calls = 0
        self._lock = threading.Lock()

    def judge(self, *, question: str, text: str) -> Verdict:
        with self._lock:
            self.calls += 1
        return self._inner.judge(question=question, text=text)


@dataclass(frozen=True)
class Metrics:
    documents: int
    distinct: int
    promoted: int          # resolved by the deterministic filter (no LLM)
    band: int              # pieces that reached the LLM (the uncertain band)
    dedup_seconds: float
    judge_seconds: float
    workers: int

    @property
    def total_seconds(self) -> float:
        return self.dedup_seconds + self.judge_seconds

    @property
    def docs_per_second(self) -> float:
        return self.documents / self.total_seconds if self.total_seconds else 0.0

    @property
    def band_calls_per_second(self) -> float:
        return self.band / self.judge_seconds if self.judge_seconds else 0.0

    def report(self) -> str:
        collapsed = self.documents - self.distinct
        return (
            f"  documents        {self.documents}\n"
            f"  distinctes       {self.distinct}  ({collapsed} doublons effondrés par la dédup)\n"
            f"  promues (filtre) {self.promoted}   ·   band LLM {self.band}\n"
            f"  dédup            {self.dedup_seconds * 1000:.0f} ms\n"
            f"  juge (×{self.workers})       {self.judge_seconds:.2f} s   →   "
            f"{self.band_calls_per_second:.1f} appels/s\n"
            f"  débit total      {self.docs_per_second:.0f} docs/s"
        )


def synthetic(n: int, *, term: str = "pertinent") -> list[tuple[str, str]]:
    """N documents with a realistic shape (deterministic, so the gate is reproducible):
    ~30% near-duplicates the dedup collapses, ~20% matching ``term`` the filter promotes,
    the rest the residual band. No RNG — a hash of the index drives the mix."""
    pieces: list[tuple[str, str]] = []
    for i in range(n):
        bucket = (i * 2654435761) % 1000 / 1000
        if bucket < 0.30 and i > 2:
            j = i % (i // 3)  # collapse onto an earlier document's text
            text = f"document numero {j} contenu ordinaire du dossier"
        elif bucket < 0.50:
            text = f"document numero {i} mentionne {term} de maniere explicite"
        else:
            text = f"document numero {i} contenu ordinaire divers et varie"
        pieces.append((f"doc-{i:06d}", text))
    return pieces


def timed_cascade(
    raw: list[tuple[str, str]], question: str, fallback: Judge, *, workers: int
) -> Metrics:
    """Time dedup then the concurrent judge over ``raw`` (piece_id, text) pairs, with
    the deterministic filter in front of ``fallback`` (stub or real LLM)."""
    t0 = time.perf_counter()
    groups: dict[str, list[str]] = {}
    text_by_id: dict[str, str] = {}
    for pid, text in raw:
        text_by_id[pid] = text
        groups.setdefault(text_key(text), []).append(pid)
    reps = [(min(pids), text_by_id[min(pids)]) for pids in groups.values()]
    dedup_seconds = time.perf_counter() - t0

    counting = _Counting(fallback)
    cascade = CascadeJudge(CriteriaJudge(), counting)
    t1 = time.perf_counter()
    triage_pieces(reps, question, cascade, workers=workers)
    judge_seconds = time.perf_counter() - t1

    return Metrics(
        documents=len(raw), distinct=len(reps), promoted=len(reps) - counting.calls,
        band=counting.calls, dedup_seconds=dedup_seconds, judge_seconds=judge_seconds,
        workers=workers,
    )
