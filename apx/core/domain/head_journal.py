"""The chain head, recorded OUTSIDE the restorable store (story 1.11, AD-35).

A dump restore (AD-46) is the one blessed operation that can hard-delete the evidential record,
and a truncation to an earlier *consistent* point is **undetectable from inside the database** —
every chain link still verifies; AD-43 finds a hole in the middle, not a record that now ends
earlier than it did. Nothing inside the restorable database records where the head *was*.

The head journal is that outside record: an append-only file on a volume the dump does not cover
(``APX_HEAD_JOURNAL``), copied onto every backup. On every advance of a *tenant* chain the head —
scope, sequence, chain value, wall-clock, application & schema versions — is appended. On start-up
and on restore the live head is **reconciled** against the journal's latest: a live head **behind**
the journal is a **truncation** — the record now ends earlier than it did. A missing or unwritable
journal **fails start-up** (the same gate as the encryption key). Pure core: stdlib only.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


class HeadJournalUnavailable(RuntimeError):
    """The head journal is absent or unwritable — start-up must fail closed (AD-35), on the same
    gate as the encryption key: without it, a restore-truncation is undetectable."""


@dataclass(frozen=True)
class HeadEntry:
    """One recorded chain head. ``scope`` is the *tenant* (AD-43 chains per tenant)."""

    scope: str
    seq: int
    chain: str
    recorded_at: str      # ISO-8601 wall-clock (UTC)
    app_version: str
    schema_version: str


@dataclass(frozen=True)
class Reconciliation:
    """The comparison of a live chain head against the journal's latest for one scope. ``truncated``
    is True when the live head is BEHIND the journal — the record ends earlier than it did."""

    scope: str
    live_seq: int
    journal_seq: int
    truncated: bool


class HeadJournal:
    """An append-only journal of chain heads at ``path`` — a volume the dump does not cover."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    @property
    def path(self) -> Path:
        return self._path

    def ensure_writable(self) -> None:
        """Raise ``HeadJournalUnavailable`` unless the journal can be appended to (creating it if
        absent). Called by ``open_journal`` so a missing/unwritable journal fails start-up."""
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._path.open("a", encoding="utf-8"):
                pass
        except OSError as exc:
            raise HeadJournalUnavailable(
                f"head journal at {self._path} is not writable: {exc}") from exc

    def record(self, entry: HeadEntry) -> None:
        """Append one head. Append-only: a head is never rewritten or removed. Raises ``OSError``
        on a write failure (a full disk) — the caller surfaces it (AC5), never swallows it."""
        line = json.dumps(asdict(entry), ensure_ascii=False, sort_keys=True)
        with self._path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")

    def _entries(self) -> list[HeadEntry]:
        if not self._path.exists():
            return []
        out: list[HeadEntry] = []
        for line in self._path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                out.append(HeadEntry(**json.loads(line)))
            except (ValueError, TypeError):
                continue  # a malformed line is skipped; a truncation shows in the valid heads
        return out

    def latest(self, scope: str) -> HeadEntry | None:
        """The most recently recorded head for a scope (the highest seq), or None if never seen."""
        seen = [e for e in self._entries() if e.scope == scope]
        return max(seen, key=lambda e: e.seq) if seen else None

    def all_latest(self) -> dict[str, HeadEntry]:
        latest: dict[str, HeadEntry] = {}
        for e in self._entries():
            if e.scope not in latest or e.seq > latest[e.scope].seq:
                latest[e.scope] = e
        return latest

    def reconcile(self, scope: str, live_seq: int) -> Reconciliation:
        """Compare a live chain head against the journal's latest. A live seq BELOW the journal's
        is a truncation — the record now ends earlier than it did (AD-35). A live head AT or AHEAD
        of the journal is normal (the journal may lag by the last un-recorded append)."""
        recorded = self.latest(scope)
        journal_seq = recorded.seq if recorded is not None else 0
        return Reconciliation(scope, live_seq, journal_seq, truncated=live_seq < journal_seq)


def open_journal(env: dict[str, str], *, required: bool = True) -> HeadJournal | None:
    """Open the head journal from ``APX_HEAD_JOURNAL``. When ``required`` (the start-up gate), a
    missing or unwritable journal raises ``HeadJournalUnavailable`` — fail closed (AD-35). When not
    required (a context with no journal configured, e.g. a stateless run), returns None."""
    path = env.get("APX_HEAD_JOURNAL", "").strip()
    if not path:
        if required:
            raise HeadJournalUnavailable(
                "APX_HEAD_JOURNAL is not set — the chain head cannot be recorded outside the "
                "restorable store, so a restore-truncation would be undetectable (AD-35)")
        return None
    journal = HeadJournal(path)
    journal.ensure_writable()
    return journal
