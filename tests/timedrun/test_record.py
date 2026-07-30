"""The per-profile measurement record (Story 2.13, AC2): every figure the target-hardware run must
produce, honestly `pending` until it happens — never a fabricated number (NFR-2)."""

from __future__ import annotations

from dataclasses import replace

from apx.timedrun.record import PROFILES, REAL_FIGURES, MeasurementRecord, load_records, pending


def test_the_schema_covers_every_research_figure() -> None:
    # U2 + Open Risk 1/3: wall-clock (+ its 100k extrapolation), peak RSS, peak VRAM, chunk yield,
    # HNSW p95, index-build-within-work_mem, full-text index size, per-pièce max, Tesseract-vs-LLM.
    rec = pending("gpu")
    for figure in REAL_FIGURES:
        assert hasattr(rec, figure), f"the record is missing the research figure {figure!r}"


def test_a_pending_record_has_every_real_figure_unset_and_is_not_measured() -> None:
    rec = pending("gpu")
    assert rec.profile == "gpu"
    assert rec.measured is False
    for figure in REAL_FIGURES:
        assert getattr(rec, figure) is None, f"{figure} should be pending, not a fabricated number"
    assert not rec.is_measured
    assert set(rec.pending_figures()) == set(REAL_FIGURES)


def test_a_pending_record_can_never_be_read_as_a_measured_one() -> None:
    # `is_measured` is true only when the run happened AND every figure is set — so a `pending`
    # record, or one with `measured` never flipped, can never masquerade as a measured one.
    rec = pending("gpu")
    assert not rec.is_measured
    stray = replace(rec, wall_clock_s=123.0)          # a stray figure without flipping `measured`
    assert not stray.is_measured
    lying = replace(rec, measured=True)               # `measured=True` but every figure still None
    assert not lying.is_measured


def test_a_fully_measured_cpu_record_is_measured_even_though_it_has_no_vram() -> None:
    # The cpu profile (Ollama) has no GPU, so peak_vram_mb is legitimately None even after a real
    # run — it must NOT keep the record forever "unmeasured" (else the gate never clears for cpu).
    figures = {f: 1.0 for f in REAL_FIGURES if f not in ("tesseract_vs_llm", "peak_vram_mb")}
    cpu = MeasurementRecord(
        profile="cpu", measured=True, tesseract_vs_llm="llm", peak_vram_mb=None, **figures
    )
    assert cpu.is_measured                            # measured despite no VRAM figure
    assert "peak_vram_mb" not in cpu.pending_figures()
    # the gpu profile, by contrast, DOES owe a VRAM figure — None there means still pending
    gpu = replace(cpu, profile="gpu")
    assert not gpu.is_measured
    assert "peak_vram_mb" in gpu.pending_figures()


def test_the_recorded_state_is_honestly_pending_for_both_profiles_today() -> None:
    records = load_records()
    assert set(records) == set(PROFILES)              # gpu + cpu, config-as-data (AD-27)
    for profile, rec in records.items():
        assert rec.measured is False, f"{profile} claims measured — no hardware run has happened"
        assert not rec.is_measured
        assert rec.pending_figures(), f"{profile} should still have pending figures"
