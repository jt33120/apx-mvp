"""The measurement record of the timed 5 000-pièce concurrent run (Story 2.13 / U2, AC2).

Per inference profile (``gpu`` = vLLM + Mistral Small 3.2 24B Q4 on 24 GB VRAM; ``cpu`` = Ollama —
AD-27, config-as-data), it holds every figure the target-hardware run must produce. Until that run
exists on the CCBE €2 000 machine, every real figure is ``None`` and ``measured`` is ``False``: the
harness records **pending**, it never invents a number (NFR-2, PRD §5/§7). The recorded state lives
in ``measurements.json`` beside this module and is what the perf-ceiling gate reads.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, fields
from pathlib import Path

PROFILES: tuple[str, ...] = ("gpu", "cpu")

# Every figure the run must produce (U2 + Open Risk 1/3). None until the hardware run — never faked.
# `index_build_within_work_mem` is a bool once known; `tesseract_vs_llm` names the bottleneck stage.
REAL_FIGURES: tuple[str, ...] = (
    "wall_clock_s",                  # 5 000-pièce concurrent wall-clock
    "extrapolated_100k_s",           # linear extrapolation to the 100 000-pièce design target
    "peak_rss_mb",                   # peak resident set size
    "peak_vram_mb",                  # peak GPU memory (gpu profile only; None on cpu)
    "chunk_yield",                   # chunks produced (extrapolated to 100 000 pièces)
    "hnsw_p95_ms",                   # HNSW p95 under a matter-scoped filter
    "index_build_within_work_mem",   # did the index build stay within maintenance_work_mem? (bool)
    "full_text_index_bytes",         # AD-21 full-text index size
    "per_piece_max",                 # worst-case per-pièce cost (chunks / chars)
    "tesseract_vs_llm",              # which stage is the bottleneck ("tesseract" | "llm")
)
# The cpu profile (Ollama) has no GPU, so it never owes a VRAM figure (peak_vram_mb stays None).
_CPU_FIGURES: tuple[str, ...] = tuple(f for f in REAL_FIGURES if f != "peak_vram_mb")

MEASUREMENTS_PATH = Path(__file__).resolve().parent / "measurements.json"


@dataclass(frozen=True)
class MeasurementRecord:
    """One inference profile's slice of the timed run. A real figure is ``None`` while pending; the
    run flips ``measured`` to ``True`` and fills every figure at once — never one without the other.
    """

    profile: str
    measured: bool = False
    wall_clock_s: float | None = None
    extrapolated_100k_s: float | None = None
    peak_rss_mb: float | None = None
    peak_vram_mb: float | None = None
    chunk_yield: float | None = None
    hnsw_p95_ms: float | None = None
    index_build_within_work_mem: bool | None = None
    full_text_index_bytes: int | None = None
    per_piece_max: float | None = None
    tesseract_vs_llm: str | None = None

    def __post_init__(self) -> None:
        if self.profile not in PROFILES:
            raise ValueError(f"unknown profile {self.profile!r}; expected one of {PROFILES}")

    def pending_figures(self) -> list[str]:
        """The real figures still unset — the work the hardware run owes. ``peak_vram_mb`` is NOT
        owed by the ``cpu`` profile (Ollama, no GPU): it is legitimately ``None`` there even after a
        real run, so it must not keep a measured cpu record forever pending."""
        owed = REAL_FIGURES if self.profile == "gpu" else _CPU_FIGURES
        return [name for name in owed if getattr(self, name) is None]

    @property
    def is_measured(self) -> bool:
        """True only when the run happened AND every real figure is populated. A ``pending`` record,
        or one where ``measured`` was flipped without the figures, can never read as measured."""
        return self.measured and not self.pending_figures()

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> MeasurementRecord:
        known = {f.name for f in fields(cls)}
        unexpected = set(data) - known
        if unexpected:
            raise ValueError(f"unexpected keys in measurement record: {sorted(unexpected)}")
        return cls(**data)


def pending(profile: str) -> MeasurementRecord:
    """An honest all-pending record for ``profile``: every figure ``None``, ``measured`` False."""
    return MeasurementRecord(profile=profile)


def load_records(path: Path = MEASUREMENTS_PATH) -> dict[str, MeasurementRecord]:
    """Load the recorded state (one record per profile) from ``measurements.json``."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    profiles = raw["profiles"]
    return {
        name: MeasurementRecord.from_dict({"profile": name, **body})
        for name, body in profiles.items()
    }


def any_measured(records: dict[str, MeasurementRecord] | None = None) -> bool:
    """True once ANY profile has a complete measured record — the fact the perf-ceiling gate keys on
    (a declared ceiling is permitted once a figure it could rest on exists; until then, none may be
    invented, NFR-2). Reads ``measurements.json`` by default."""
    records = load_records() if records is None else records
    return any(record.is_measured for record in records.values())


# --------------------------------------------------------------------------------------------------
# The falsification criteria (Story 2.13, AC3 / Open Risk 1 & 3). Named constants, not magic values.
# A breach revises the hardware ask or the cascade aggressiveness — a recorded finding, never
# smoothed over. All figures are extrapolated to the 100 000-pièce design target.
# --------------------------------------------------------------------------------------------------

MAX_CHUNKS = 8_000_000             # chunk yield > ~8 M ⇒ the pgvector-only single store is wrong
MAX_HNSW_P95_MS = 2_000            # HNSW p95 > ~2 s under a matter-scoped filter ⇒ wrong
WEEKEND_SECONDS = 2 * 24 * 3_600   # 48 h; wall-clock past one weekend ⇒ UJ-1 invalid, sizing wrong
MAINTENANCE_WORK_MEM_GB = 64       # the reference machine; the index build must fit work_mem


def falsifies(record: MeasurementRecord) -> list[str]:
    """The breached thresholds, as recorded findings. Each check runs only on a figure that was
    actually measured — a ``None`` (pending) figure cannot falsify anything (you cannot refute an
    unmeasured claim). So a fully-pending record returns ``[]``; that is *unmeasured*, not *passing*
    (see :func:`is_clean`)."""
    findings: list[str] = []
    if record.chunk_yield is not None and record.chunk_yield > MAX_CHUNKS:
        findings.append(
            f"chunk yield {record.chunk_yield:,.0f} > {MAX_CHUNKS:,} (100k target) — "
            "the pgvector-only single store is wrong (Open Risk 1)"
        )
    if record.hnsw_p95_ms is not None and record.hnsw_p95_ms > MAX_HNSW_P95_MS:
        findings.append(
            f"HNSW p95 {record.hnsw_p95_ms:.0f} ms > {MAX_HNSW_P95_MS} ms under a matter-scoped "
            "filter — retrieval sizing is wrong (Open Risk 1)"
        )
    if record.extrapolated_100k_s is not None and record.extrapolated_100k_s > WEEKEND_SECONDS:
        findings.append(
            f"wall-clock extrapolates to {record.extrapolated_100k_s / 3_600:.1f} h for 100k "
            "pièces — past one weekend: UJ-1 invalid, the €2 000 sizing is wrong (Open Risk 3)"
        )
    if record.tesseract_vs_llm == "tesseract":
        findings.append(
            "Tesseract overtook the LLM as the bottleneck — the hardware recommendation is wrong "
            "(Open Risk 3)"
        )
    if record.index_build_within_work_mem is False:
        findings.append(
            f"index build exceeded maintenance_work_mem ({MAINTENANCE_WORK_MEM_GB} GB machine) "
            "— sizing is wrong (Open Risk 1)"
        )
    return findings


def is_falsified(record: MeasurementRecord) -> bool:
    """The run breached at least one threshold."""
    return bool(falsifies(record))


def is_clean(record: MeasurementRecord) -> bool:
    """A *measured* record that breaches nothing. A pending record is neither clean nor falsified —
    it is unmeasured, and must never read as passing."""
    return record.is_measured and not falsifies(record)
