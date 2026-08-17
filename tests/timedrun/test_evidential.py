"""The evidential path's two measurements (retro action B9, AD-44).

The measurement itself is on-demand tooling and its real figures come from a run at the design
target. What these tests hold is that the instrument is honest: it times the product's own call
rather than a re-implementation, it refuses a journal that does not read back, and neither figure
can be obtained without the work actually happening.
"""

from __future__ import annotations

import pytest

from apx.timedrun.evidential import (
    BatchCost,
    JournalCost,
    measure_journal_parse,
    measure_validation_batch,
)


def test_the_batch_measurement_times_the_call_it_is_given() -> None:
    # The act is injected, so what is timed is `SqlStore.validate_pieces` at a real call site —
    # never a second implementation that could drift from the path a lawyer's click takes.
    seen: list[int] = []
    cost = measure_validation_batch(
        lambda ids: seen.append(len(ids)), [f"p{i}" for i in range(7)], store="sqlite")
    assert seen == [7], "the measurement must actually perform the act"
    assert cost.pieces == 7
    assert cost.seconds >= 0.0
    assert cost.store == "sqlite"


def test_the_batch_cost_names_the_store_it_was_measured_against() -> None:
    # A figure from SQLite and a figure from PostgreSQL are different claims, and a reader who
    # cannot tell which one they hold will quote the flattering one.
    cost = BatchCost(pieces=1700, seconds=2.0, peak_rss_mb=132.0, store="sqlite-in-memory")
    assert "sqlite" in cost.store
    assert cost.per_piece_ms == pytest.approx(2.0 / 1700 * 1000)


def test_an_empty_batch_reports_no_per_piece_cost_rather_than_dividing_by_zero() -> None:
    assert BatchCost(pieces=0, seconds=0.5, peak_rss_mb=1.0, store="none").per_piece_ms == 0.0


def test_the_journal_measurement_writes_reads_back_and_reports_the_file(tmp_path) -> None:  # noqa: ANN001
    cost = measure_journal_parse(tmp_path / "heads.journal", lines=40, scopes=4, samples=2)
    assert cost.lines == 40
    assert cost.scopes == 4
    assert cost.samples == 2
    assert cost.file_bytes > 0, "a journal of forty heads is not an empty file"
    assert cost.parse_seconds >= 0.0
    assert cost.parse_us_per_line > 0.0


def test_the_journal_measurement_refuses_a_degenerate_size(tmp_path) -> None:  # noqa: ANN001
    with pytest.raises(ValueError):
        measure_journal_parse(tmp_path / "a.journal", lines=0, scopes=1)
    with pytest.raises(ValueError):
        measure_journal_parse(tmp_path / "b.journal", lines=5, scopes=0)


def test_the_journal_cost_reports_its_file_size_in_the_unit_it_names() -> None:
    cost = JournalCost(lines=1000, scopes=20, file_bytes=2 * 1024 * 1024,
                       parse_seconds=0.01, samples=5)
    assert cost.file_mb == pytest.approx(2.0)
    assert cost.parse_us_per_line == pytest.approx(10.0)
