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


#: Separates the *tenant* from the *matter* in a journalled chain identity. A unit separator, not
#: a slash or a colon: those occur in identifiers, and a scope that can be spelled two ways is a
#: scope whose reconciliation can be aimed at the wrong chain.
SCOPE_SEP = "\x1f"


class AmbiguousScope(ValueError):
    """A tenant or matter containing the separator — a chain identity that cannot be parsed back."""


def journal_scope(tenant: str, chain_scope: str) -> str:
    """The journal identity of one audit chain (AD-43 chains per (tenant, matter), plus one tenant
    chain). The *tenant* chain keeps the bare tenant as its scope: that is what every head recorded
    before Story 5.5 carries, and every one of those heads was in fact a tenant-chain head — so the
    journal needs no migration and no line is reinterpreted."""
    for part in (tenant, chain_scope):
        if SCOPE_SEP in part:
            raise AmbiguousScope(f"identifier contains the scope separator: {part!r}")
    return f"{tenant}{SCOPE_SEP}{chain_scope}" if chain_scope else tenant


def tenant_of(scope: str) -> str:
    """The *tenant* a journalled scope belongs to — a truncation on any of its chains is the
    tenant's truncation."""
    return scope.split(SCOPE_SEP, 1)[0]


def chain_of(scope: str) -> str:
    """The ``chain_scope`` inside a journalled identity: the *matter*, or ``""`` for the *tenant*
    chain. The inverse of :func:`journal_scope`, so a caller comparing a journalled head against a
    live one never has to spell the chain a second way."""
    parts = scope.split(SCOPE_SEP, 1)
    return parts[1] if len(parts) == 2 else ""


@dataclass(frozen=True)
class HeadEntry:
    """One recorded chain head. ``scope`` is the chain identity from :func:`journal_scope`: the
    bare *tenant* for the *tenant* chain, or ``tenant␟matter`` for a *matter* chain."""

    scope: str
    seq: int
    chain: str
    recorded_at: str      # ISO-8601 wall-clock (UTC)
    app_version: str
    schema_version: str


@dataclass(frozen=True)
class Reconciliation:
    """The comparison of a live chain head against the journal's latest for one scope.

    ``truncated`` is True when the live head is BEHIND the journal — the record ends earlier than it
    did. ``forked`` is True when the two hold DIFFERENT VALUES at a sequence they both hold — the
    record was rewritten and re-chained, which no comparison of lengths can see. The second is the
    reason the journal has recorded a chain value on every advance since Story 1.11; until Story 5.9
    nothing read it back, and a forged restore of the same length satisfied every check the product
    ran, all of which compared one in-store value against another."""

    scope: str
    live_seq: int
    journal_seq: int
    truncated: bool
    forked: bool = False
    witnessed_seq: int = 0     # the sequence at which the two values were compared (0: nowhere)
    journal_chain: str = ""    # what the outside record holds there
    live_chain: str = ""       # what the record now carries there

    @property
    def diverged(self) -> bool:
        """Either finding. Both are a discontinuity, both are cleared only by an audited override,
        and a caller that handles one and not the other is the bug this exists to prevent."""
        return self.truncated or self.forked


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

    def entries(self) -> list[HeadEntry]:
        """Every recorded head, in append order (one file read). Callers that need several views
        (all_latest + post-clear maxima) parse ONCE via this rather than re-reading per scope."""
        if not self._path.exists():
            return []
        out: list[HeadEntry] = []
        for raw in self._path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line:
                continue
            try:
                entry = HeadEntry(**json.loads(line))
            except (ValueError, TypeError):
                continue  # a malformed line is skipped; a truncation shows in the valid heads
            # A dataclass does not check types, and this file is APPEND-ONLY: one line carrying
            # ``"seq": "9999"`` — which a restore can seed straight from an untrusted backup's head
            # tail — used to be accepted here and then raise ``TypeError`` comparing str to int in
            # every later reconciliation, forever, including the one in the boot path. A poisoned
            # line must be skippable on READ, because it can never be removed.
            if not isinstance(entry.seq, int) or isinstance(entry.seq, bool):
                continue
            if not all(isinstance(v, str) for v in (
                    entry.scope, entry.chain, entry.recorded_at,
                    entry.app_version, entry.schema_version)):
                continue
            out.append(entry)
        return out

    _entries = entries  # internal alias (kept for the methods below)

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

    def witness_upto(self, scope: str, seq: int) -> HeadEntry | None:
        """The most advanced head this journal recorded for ``scope`` **at or before** ``seq``, or
        None when it never recorded one that early.

        The journal records a head per commit, not per entry, so the two sides rarely hold the same
        sequence number; the only point at which an outside value and a live value can be compared
        at all is the highest one the outside record reached without overrunning the live one. A
        comparison taken at the journal's own latest instead would report every ordinary lagging
        journal as a disagreement."""
        best: HeadEntry | None = None
        for e in self.entries():
            # ``>=``, not ``>``: several lines can carry the same sequence — an acknowledged head is
            # written at the sequence the record already stood at — and the LAST one written is the
            # one that speaks for that point. Taking the first would let an acknowledgement be
            # answered forever by the line it was signed to settle.
            if e.scope == scope and e.seq <= seq and (best is None or e.seq >= best.seq):
                best = e
        return best

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
