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

import resource
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
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


# --------------------------------------------------------------------------------------------------
# The machine envelope (Story 2.13 / U2, Open Risk 3): OCR + embedding + LLM judgement summed while
# CONTENDING for one machine. The number nobody had. Real figures need the CCBE target hardware; the
# framework here is provable in CI with stubs and NEVER fabricates a figure (NFR-2).
# --------------------------------------------------------------------------------------------------


def sample_vram_mb() -> float | None:
    """Current GPU memory in use (MiB) via ``nvidia-smi`` — no new dependency, stdlib subprocess.

    Returns ``None`` when there is no GPU / no ``nvidia-smi`` (the CPU profile and all of CI): VRAM
    is a GPU-profile figure, recorded ``unavailable`` rather than invented. Output is captured, not
    inherited; a missing binary, a timeout, or a non-zero exit all resolve to ``None``.
    """
    try:
        proc = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            capture_output=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    # nvidia-smi can print a driver/NVML error to stdout with exit code 0 (or non-UTF8 bytes); any
    # unparseable line resolves to no reading rather than crashing the sampler thread.
    values: list[float] = []
    for line in proc.stdout.decode("utf-8", "replace").splitlines():
        try:
            values.append(float(line.strip()))
        except ValueError:
            continue
    return max(values) if values else None


def _peak_rss_mb() -> float:
    """Peak resident set size of this process (MiB). ``ru_maxrss`` is KiB on Linux (the target
    hardware) and bytes on macOS (dev) — normalise by platform so the figure is MiB on both."""
    ru = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    divisor = 1024 * 1024 if sys.platform == "darwin" else 1024
    return ru / divisor


class _VramPeak:
    """Poll VRAM in the background during a run and keep the peak. ``peak`` stays ``None`` the whole
    run when there is no GPU (the sampler observes nothing to record) — never faked to zero."""

    def __init__(self, interval: float = 0.1) -> None:
        self._interval = interval
        self.peak: float | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def _poll(self) -> None:
        while not self._stop.is_set():
            sample = sample_vram_mb()
            if sample is not None:
                self.peak = sample if self.peak is None else max(self.peak, sample)
            self._stop.wait(self._interval)

    def __enter__(self) -> _VramPeak:
        self._thread = threading.Thread(target=self._poll, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)


@dataclass(frozen=True)
class Envelope:
    """The machine envelope of one concurrent run: what the four stages cost together on one box."""

    documents: int
    wall_clock_s: float
    peak_rss_mb: float
    peak_vram_mb: float | None      # None on the CPU profile / in CI — never invented (NFR-2)
    workers: int

    @property
    def docs_per_second(self) -> float:
        return self.documents / self.wall_clock_s if self.wall_clock_s else 0.0

    @property
    def extrapolated_100k_s(self) -> float:
        """Linear extrapolation to the 100 000-piece design target. A projection, not a measurement
        — honest only alongside the real per-document cost it is scaled from."""
        return self.wall_clock_s / self.documents * 100_000 if self.documents else 0.0

    def report(self) -> str:
        if self.peak_vram_mb is None:
            vram = "indisponible (pas de GPU)"
        else:
            vram = f"{self.peak_vram_mb:.0f} MiB"
        return (
            f"  documents        {self.documents}  (×{self.workers} en concurrence)\n"
            f"  horloge          {self.wall_clock_s:.2f} s  →  {self.docs_per_second:.0f} docs/s\n"
            f"  RSS crête        {self.peak_rss_mb:.0f} MiB\n"
            f"  VRAM crête       {vram}\n"
            f"  extrapolé 100k   {self.extrapolated_100k_s / 3600:.1f} h"
        )


def timed_pipeline(
    units: list[tuple[str, str]],
    *,
    extract,
    ocr,
    embed,
    judge,
    workers: int,
) -> Envelope:
    """Run the four ingestion stages — extraction, OCR (for scans), embedding, LLM judgement —
    CONCURRENTLY over ``units``, so up to ``workers`` pieces are in flight at once and the stages
    overlap and contend for the machine (Open Risk 3: nobody summed the machine). Captures the
    machine envelope: wall-clock, peak RSS, peak VRAM.

    The four stages are injected callables — near-instant stubs and a fake embedder in CI (no real
    model, no GPU), the real components (Tesseract, BGE-M3, the LLM band) on the target hardware.
    A piece whose extraction returns empty (a scan) falls back to OCR, exactly as production does.
    """
    with _VramPeak() as vram:
        t0 = time.perf_counter()

        def _process(unit: tuple[str, str]) -> None:
            text = extract(unit) or ocr(unit)
            embed(text)
            judge(text)

        with ThreadPoolExecutor(max_workers=workers) as pool:
            for _ in pool.map(_process, units):
                pass
        wall_clock_s = time.perf_counter() - t0

    return Envelope(
        documents=len(units),
        wall_clock_s=wall_clock_s,
        peak_rss_mb=_peak_rss_mb(),
        peak_vram_mb=vram.peak,
        workers=workers,
    )


def stub_stages() -> dict:
    """The four CI-default stages as injectable callables: near-instant stand-ins so the concurrent
    orchestration and the envelope capture are provable without the real Tesseract, BGE-M3 or LLM —
    none is loaded (AD-11: the embedder is faked at the port boundary). Extraction is a passthrough
    over the already-extracted synthetic text; on the target hardware the real components are
    swapped in stage by stage. Pass to ``timed_pipeline(units, **stub_stages())``."""
    stub = StubJudge()
    return {
        "extract": lambda unit: unit[1],
        "ocr": lambda unit: "",
        "embed": lambda text: [0.0] * 8,   # a fake vector — the real BGE-M3 is never loaded
        "judge": lambda text: stub.judge(question="pertinent", text=text),
    }
