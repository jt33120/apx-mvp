"""The evidential path's two unmeasured costs (retro action B9, AD-44).

Stories 5.8 and 5.9 each closed naming a figure nobody had:

* **the bulk *validation act*** — at the design target a select-all over ~1 700 *pièces* is
  ONE transaction holding one ``IN (…)`` predicate, 1 700 ledger rows and 3 400 audit
  entries, all allocated against **one** chain head row. Story 5.8 declined to chunk it on
  purpose (FR-45(b) makes the batch one gesture, and splitting the commit would let half of
  it land), and wrote that it was worth measuring;
* **the head journal** — parsed once per reconciliation and growing one line per commit.
  Story 1.11 deferred compaction as immaterial at the single-firm target and Story 5.9
  left the deferral standing. Immaterial is a claim about a number.

This module measures both, on demand, with the stdlib only. It is **measurement tooling,
not a product unit** — the same standing as :mod:`apx.timedrun.harness` and
:mod:`apx.fitness` — and it ships no runtime behaviour.

**What it does NOT measure, stated so the figure is not over-read.** AD-44's subject is
*contention*: many concurrent writers serialising on one chain head under
``SELECT … FOR UPDATE``. This measures a **single writer** against the suite's baseline
store. It bounds how the cost GROWS with N — which is the question Stories 5.8 and 5.9
actually left open — and says nothing about how it degrades under concurrency on
PostgreSQL. That measurement needs the real database and belongs with the 2.13
target-hardware run; nothing here licenses a claim about it.

Nothing written here touches ``measurements.json``: that record belongs to the 2.13
5 000-*pièce* run and stays honestly pending until the target hardware exists (NFR-2).
"""

from __future__ import annotations

import os
import resource
import statistics
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from apx.core.domain.head_journal import HeadEntry, HeadJournal

#: Peak RSS is bytes on Darwin and KiB on Linux. Normalising here rather than at each call
#: site keeps the two platforms' figures comparable instead of a thousandfold apart.
_RSS_DIVISOR = 1024 * 1024 if sys.platform == "darwin" else 1024


def _peak_rss_mb() -> float:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / _RSS_DIVISOR


@dataclass(frozen=True)
class BatchCost:
    """One bulk *validation act*'s measured cost. ``store`` names what it ran against, because
    a figure from SQLite and a figure from PostgreSQL are different claims."""

    pieces: int
    seconds: float
    peak_rss_mb: float
    store: str

    @property
    def per_piece_ms(self) -> float:
        return self.seconds / self.pieces * 1000 if self.pieces else 0.0


@dataclass(frozen=True)
class JournalCost:
    """The head journal at a given size: what it costs on disk, and to parse once."""

    lines: int
    scopes: int
    file_bytes: int
    parse_seconds: float
    samples: int

    @property
    def parse_us_per_line(self) -> float:
        return self.parse_seconds / self.lines * 1e6 if self.lines else 0.0

    @property
    def file_mb(self) -> float:
        return self.file_bytes / (1024 * 1024)


def measure_validation_batch(
    act: Callable[[Sequence[str]], object], piece_ids: Sequence[str], *, store: str,
) -> BatchCost:
    """Time one bulk *validation act* over ``piece_ids``.

    ``act`` is the call under measurement — the caller supplies it so this module never
    builds a store of its own and the thing timed is the product's real path
    (``SqlStore.validate_pieces``), not a re-implementation of it. The arrangement's cost
    (ingest, rank, place the line) is deliberately outside the window: what Story 5.8 left
    open is the cost of the ACT.
    """
    started = time.perf_counter()
    act(piece_ids)
    seconds = time.perf_counter() - started
    return BatchCost(pieces=len(piece_ids), seconds=seconds, peak_rss_mb=_peak_rss_mb(),
                     store=store)


def measure_journal_parse(path: Path | str, lines: int, scopes: int, *,
                          samples: int = 5) -> JournalCost:
    """Write a journal of ``lines`` heads across ``scopes`` chains, then time parsing it.

    The **median** of ``samples`` parses, not the mean and not the best: a single timing on a
    shared machine is an observation, and Story 5.3's lesson is that a number that comes back
    the same every time is not thereby a reliable estimate of anything. The written entries
    carry realistic field widths — a 64-hex chain value is what a real head holds — because a
    parse time over short synthetic lines would flatter the file size and the I/O alike.
    """
    if lines < 1 or scopes < 1:
        raise ValueError("a journal measurement needs at least one line and one scope")
    journal = HeadJournal(path)
    for i in range(lines):
        journal.record(HeadEntry(
            scope=f"cabinet␟matter-{i % scopes}", seq=(i // scopes) + 1,
            chain=f"{i:064x}", recorded_at="2026-08-15T10:00:00+00:00",
            app_version="0.1.0", schema_version="slice-a"))
    timings = []
    for _ in range(samples):
        started = time.perf_counter()
        parsed = journal.entries()
        timings.append(time.perf_counter() - started)
        if len(parsed) != lines:
            raise AssertionError(
                f"the journal parsed {len(parsed)} of {lines} lines — a measurement over a "
                "journal that does not read back is not a measurement")
    return JournalCost(lines=lines, scopes=scopes, file_bytes=os.path.getsize(journal.path),
                       parse_seconds=statistics.median(timings), samples=samples)
