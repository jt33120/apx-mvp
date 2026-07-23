"""The timed-run harness: realistic synthetic shape, correct partitioning, real speedup."""

from __future__ import annotations

from apx.timedrun.harness import StubJudge, synthetic, timed_cascade


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
