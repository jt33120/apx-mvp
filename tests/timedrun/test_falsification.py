"""The falsification criteria as code (Story 2.13, AC3): from a MeasurementRecord, decide whether
the run falsifies the €2 000-machine sizing. A breach is a recorded finding — never smoothed over —
and a pending record is neither passing nor falsified (it is unmeasured)."""

from __future__ import annotations

from apx.timedrun.record import (
    MAINTENANCE_WORK_MEM_GB,
    MAX_CHUNKS,
    MAX_HNSW_P95_MS,
    WEEKEND_SECONDS,
    MeasurementRecord,
    falsifies,
    is_clean,
    pending,
)


def _measured(**over: object) -> MeasurementRecord:
    """A fully-measured, within-envelope record; override one figure to breach one threshold."""
    base = dict(
        profile="gpu", measured=True, wall_clock_s=8_000.0, extrapolated_100k_s=160_000.0,
        peak_rss_mb=12_000.0, peak_vram_mb=22_000.0, chunk_yield=5_000_000.0, hnsw_p95_ms=500.0,
        index_build_within_work_mem=True, full_text_index_bytes=2_000_000_000, per_piece_max=180.0,
        tesseract_vs_llm="llm",
    )
    base.update(over)
    return MeasurementRecord(**base)


def test_a_clean_measured_record_falsifies_nothing() -> None:
    assert falsifies(_measured()) == []
    assert is_clean(_measured())


def test_each_threshold_breach_is_a_specific_finding() -> None:
    assert any("chunk" in f for f in falsifies(_measured(chunk_yield=MAX_CHUNKS + 1)))
    assert any("p95" in f for f in falsifies(_measured(hnsw_p95_ms=MAX_HNSW_P95_MS + 1)))
    past_weekend = _measured(extrapolated_100k_s=WEEKEND_SECONDS + 1)
    assert any("weekend" in f.lower() for f in falsifies(past_weekend))
    assert any("tesseract" in f.lower() for f in falsifies(_measured(tesseract_vs_llm="tesseract")))
    over_mem = _measured(index_build_within_work_mem=False)
    assert any("work_mem" in f.lower() for f in falsifies(over_mem))


def test_the_thresholds_are_named_constants_not_magic_numbers() -> None:
    assert MAX_CHUNKS >= 8_000_000
    assert MAX_HNSW_P95_MS == 2_000
    assert WEEKEND_SECONDS == 2 * 24 * 3_600
    assert MAINTENANCE_WORK_MEM_GB == 64


def test_a_pending_record_is_neither_passing_nor_falsified() -> None:
    rec = pending("gpu")
    assert falsifies(rec) == []       # nothing was measured, so nothing can be falsified
    assert not is_clean(rec)          # but it is NOT passing either — it is unmeasured
    assert not rec.is_measured
