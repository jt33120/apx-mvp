"""The timed-run harness: realistic synthetic shape, correct partitioning, real speedup, and the
full-pipeline machine envelope (Story 2.13, U2 / Open Risk 3)."""

from __future__ import annotations

import threading
import time

from apx.timedrun.harness import (
    Envelope,
    StubJudge,
    stub_stages,
    synthetic,
    timed_cascade,
    timed_pipeline,
)


def test_timed_pipeline_runs_four_stages_concurrently_and_captures_the_envelope() -> None:
    units = [(f"u{i:04d}", f"document numero {i}") for i in range(20)]
    calls = {"extract": 0, "embed": 0, "judge": 0}
    lock = threading.Lock()

    def _c(kind: str, value: object) -> object:
        with lock:
            calls[kind] += 1
        return value

    env = timed_pipeline(
        units,
        extract=lambda u: _c("extract", u[1]),
        ocr=lambda u: "",
        embed=lambda t: _c("embed", [0.0]),
        judge=lambda t: _c("judge", None),
        workers=8,
    )
    assert isinstance(env, Envelope)
    assert env.documents == 20
    assert calls == {"extract": 20, "embed": 20, "judge": 20}  # every unit through every stage
    assert env.wall_clock_s >= 0.0 and env.peak_rss_mb > 0.0
    assert env.peak_vram_mb is None or env.peak_vram_mb >= 0.0   # None in CI (no GPU)
    assert env.extrapolated_100k_s >= 0.0


def test_the_pipeline_overlaps_stages_so_concurrency_hides_a_latent_stage() -> None:
    units = [(f"u{i:04d}", f"t{i}") for i in range(24)]
    stages = stub_stages()
    stages["judge"] = lambda t: time.sleep(0.02)  # a latent (network-bound) judge, as in production
    slow = timed_pipeline(units, workers=1, **stages)
    fast = timed_pipeline(units, workers=12, **stages)
    assert fast.wall_clock_s < slow.wall_clock_s   # concurrency hides the latent stage (Risk 3)


def test_stub_stages_populate_the_envelope_over_the_synthetic_corpus_without_a_real_model() -> None:
    env = timed_pipeline(synthetic(40), workers=8, **stub_stages())
    assert env.documents == 40 and env.peak_rss_mb > 0.0
    assert env.peak_vram_mb is None                # no GPU in CI — recorded unavailable, not faked
    assert env.docs_per_second > 0.0


def test_sample_vram_survives_garbage_or_non_utf8_nvidia_smi_output(monkeypatch) -> None:
    # nvidia-smi can print a driver/NVML error to stdout with exit code 0, or non-UTF8 bytes; the
    # probe must resolve those to None (as its docstring promises), never crash the sampler thread.
    import apx.timedrun.harness as harness

    class _Proc:
        def __init__(self, out: bytes) -> None:
            self.stdout = out
            self.returncode = 0

    def _run_returning(out: bytes):
        return lambda *a, **k: _Proc(out)

    for stdout in (b"Failed to initialize NVML: Driver/library mismatch\n", b"\xff\xfe", b""):
        monkeypatch.setattr(harness.subprocess, "run", _run_returning(stdout))
        assert harness.sample_vram_mb() is None       # no numeric reading → None, no exception

    # a valid reading survives noise on other lines, and the max across GPUs is taken
    monkeypatch.setattr(harness.subprocess, "run", _run_returning(b"512\nERR\n2048\n"))
    assert harness.sample_vram_mb() == 2048.0


def test_synthetic_has_duplicates_and_matches() -> None:
    raw = synthetic(300, term="pertinent")
    texts = [t for _, t in raw]
    assert len(raw) == 300
    assert any("pertinent" in t for t in texts)  # some the filter will promote
    assert len(set(texts)) < 300                 # some the dedup will collapse


def test_timed_cascade_partitions_the_corpus() -> None:
    m = timed_cascade(synthetic(300, term="pertinent"), "pertinent", StubJudge(), workers=8)
    assert m.documents == 300
    assert m.distinct < 300                    # duplicates collapsed
    assert m.promoted + m.band == m.distinct   # each distinct piece: promoted or judged
    assert m.promoted > 0 and m.band > 0
    assert m.docs_per_second > 0


def test_concurrency_speeds_up_a_latent_band() -> None:
    raw = synthetic(40, term="alpha")
    slow = timed_cascade(raw, "beta-unmatched", StubJudge(latency=0.02), workers=1)
    fast = timed_cascade(raw, "beta-unmatched", StubJudge(latency=0.02), workers=12)
    assert slow.promoted == 0 and slow.band == slow.distinct  # nothing matched -> all judged
    assert fast.judge_seconds < slow.judge_seconds            # concurrency helped
