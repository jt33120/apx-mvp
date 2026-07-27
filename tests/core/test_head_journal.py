"""The head journal, recorded outside the restorable store (story 1.11, AD-35): record/latest/
reconcile, truncation detection, and fail-closed open. Pure core.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from apx.core.domain.head_journal import (
    HeadEntry,
    HeadJournal,
    HeadJournalUnavailable,
    open_journal,
)


def _entry(scope: str, seq: int) -> HeadEntry:
    return HeadEntry(scope, seq, f"chain{seq}", "2026-07-27T00:00:00", "0.1.0", "slice-a")


def _journal(tmp_path: Path) -> HeadJournal:
    j = HeadJournal(tmp_path / "heads.journal")
    j.ensure_writable()
    return j


def test_record_and_latest(tmp_path: Path) -> None:
    j = _journal(tmp_path)
    for seq in (1, 2, 3):
        j.record(_entry("cab", seq))
    assert j.latest("cab").seq == 3
    assert j.latest("other") is None


def test_all_latest_tracks_each_scope(tmp_path: Path) -> None:
    j = _journal(tmp_path)
    j.record(_entry("a", 5))
    j.record(_entry("b", 2))
    j.record(_entry("a", 7))
    latest = j.all_latest()
    assert latest["a"].seq == 7 and latest["b"].seq == 2


def test_reconcile_detects_a_live_head_behind_the_journal(tmp_path: Path) -> None:
    # the heart of AD-35: the journal recorded head 5; a restore left the live head at 2
    j = _journal(tmp_path)
    j.record(_entry("cab", 5))
    behind = j.reconcile("cab", live_seq=2)
    assert behind.truncated and behind.journal_seq == 5 and behind.live_seq == 2
    # a live head AT or AHEAD of the journal is normal (the journal may lag by one un-recorded head)
    assert not j.reconcile("cab", live_seq=5).truncated
    assert not j.reconcile("cab", live_seq=6).truncated
    # a scope the journal never saw cannot be truncated
    assert not j.reconcile("new", live_seq=3).truncated


def test_a_malformed_line_is_skipped_not_fatal(tmp_path: Path) -> None:
    path = tmp_path / "heads.journal"
    j = HeadJournal(path)
    j.record(_entry("cab", 1))
    path.write_text(path.read_text() + "not json\n{}\n", encoding="utf-8")  # corrupt tail
    assert j.latest("cab").seq == 1  # the valid head still reads; a truncation shows in valid data


def test_open_journal_fails_closed_when_unset() -> None:
    with pytest.raises(HeadJournalUnavailable):
        open_journal({}, required=True)          # AD-35: no journal → refuse (fail closed)
    assert open_journal({}, required=False) is None   # a stateless run tolerates absence


def test_open_journal_fails_closed_when_unwritable() -> None:
    # a path whose parent cannot be a directory (/dev/null is a device) is unwritable
    with pytest.raises(HeadJournalUnavailable):
        open_journal({"APX_HEAD_JOURNAL": "/dev/null/nope/heads.journal"}, required=True)
