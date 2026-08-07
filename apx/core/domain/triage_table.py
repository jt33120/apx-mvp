"""The triage table as the surface reads it (Story 4.10, FR-20 / FR-16 / FR-40 / FR-42).

One coherent read of **one ranking version** (AD-23): the ranked rows, each carrying the *derived*
confidence (Story 4.4), the *editable* taxonomy label (Story 4.5) and the *derived* côté (Story
4.7), plus the line (Story 4.8) and the counts. It is a **view object** — it stores nothing, decides
nothing, and holds no membership: ``side`` is a rendering of *(the order, the line, the pins)*
recomputed at read time, never a flag anyone can set (AD-39).

Two honesty rules are carried in the types themselves, so a surface cannot quietly break them:

* ``confidence is None`` means **not derived** — never zero, never "faible" (AD-19). The band is a
  rendering of a derived number, never a model self-report (FR-42).
* ``label`` is **never empty**: a *pièce* nobody has labelled reads as the explicit ``unlabelled``
  sentinel (FR-40), and ``in_current_taxonomy`` is False for a value the taxonomy no longer holds —
  shown as such, never silently remapped.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

SIDE_RETAINED = "retained"
SIDE_DISCARDED = "discarded"
SIDE_UNSCORED = "unscored"
# The tool has not yet committed to a line, so this *pièce* is scored and ranked but on **neither**
# side of a cut that does not exist. It is a real state, not a placeholder: the contract's "line not
# yet placed" screen shows the ranked order with no cut and no retained/discarded zones. Calling
# such a row "écartée" would be the exact lie FR-16 forbids.
SIDE_UNSPLIT = "unsplit"


@dataclass(frozen=True)
class TriageRow:
    """One *pièce* as the table shows it. ``rank`` is ``None`` for the unscored tail — a *pièce* the
    cascade could not place, which is its **own** set and is never folded into the discarded one
    (AD-19/AD-36)."""

    piece_id: str
    name: str
    rank: int | None
    side: str
    confidence: float | None
    confidence_signals: tuple[str, ...]
    band: str | None
    label: str
    label_source: str | None
    label_seq: int | None
    in_current_taxonomy: bool
    pinned: bool

    @property
    def confidence_derived(self) -> bool:
        """False when the cascade derived no confidence for this *pièce* — the surface says so
        rather than showing a number nobody computed (AD-19)."""
        return self.confidence is not None


@dataclass(frozen=True)
class LineView:
    """**The line** as the table shows it: a cut named by the **identity of the last retained
    *pièce*** (FR-17), never a bare ordinal. ``placed`` False is an honest state — the tool has not
    yet committed to a position — and is rendered as such, never as a line at rank 0."""

    placed: bool
    last_retained_piece_id: str | None = None
    last_retained_rank: int | None = None
    basis: str | None = None
    seq: int | None = None
    at: datetime | None = None


@dataclass(frozen=True)
class TriageTable:
    """The whole surface, bound to ONE named ranking version (AD-23 — no unqualified reference).

    Once the line is placed, ``retained + discarded + unscored == ranked_count`` — the completeness
    the screen renders as the denominator equation under its verdict seal: the sets **partition the
    ranking** and nothing has left it (FR-16). Before it is placed there is no cut, so the ranked
    rows are **unsplit** and counted as such; the equation the screen draws then is
    ``unsplit + non-scorée = le classement``.

    **The ranking is not the dossier** (Story 4.13, FR-58). ``corpus_count`` is the number of
    *pièces* in the *matter* — what the surface labels *"pièces au dossier"* — and it is supplied,
    not inferred from the rows. *Pièces* ingested after the ranking are in **neither** set because
    they are in no set at all: they are ``unranked_count``, the third state FR-16 forbids anyone to
    invent, made visible rather than imputed (AD-19). Before this story ``corpus_count`` was
    ``len(rows)``, which silently renamed the ranking's population "the dossier" and made an import
    after the ranking invisible on the very surface that counts the sets.

    ``__post_init__`` refuses any table whose parts do not add up, so a surface can never draw a
    false equation."""

    matter: str
    version_no: int
    version_id: str
    basis: str
    case_theory_version_id: str | None
    created_at: datetime
    rows: tuple[TriageRow, ...]
    retained_count: int
    discarded_count: int
    unscored_count: int
    pins_in_force: int
    line: LineView
    taxonomy: tuple[str, ...]
    corpus_count: int  # the MATTER's pièces — never len(rows) (FR-58)

    def __post_init__(self) -> None:
        named = self.retained_count + self.discarded_count + self.unscored_count
        if named > len(self.rows):
            raise ValueError(
                f"the triage sets cannot exceed the ranking: "
                f"{self.retained_count}+{self.discarded_count}+{self.unscored_count} > "
                f"{len(self.rows)} ranked rows (FR-16)")
        if self.line.placed and named != len(self.rows):
            raise ValueError(
                f"with a line placed the sets must PARTITION the ranking: "
                f"{self.retained_count}+{self.discarded_count}+{self.unscored_count} != "
                f"{len(self.rows)} ranked rows — the surface draws this as an equation and it may "
                "never be false (FR-16)")
        if self.corpus_count < len(self.rows):
            raise ValueError(
                f"the dossier cannot be smaller than its own ranking: {self.corpus_count} pièces "
                f"< {len(self.rows)} ranked rows — a miscount is never rendered (FR-58)")

    @property
    def ranked_count(self) -> int:
        """The *pièces* the *ranking version* holds — judged, rejected and unscored alike."""
        return len(self.rows)

    @property
    def unranked_count(self) -> int:
        """*Pièces* in the *matter* that this *ranking version* never saw — ingested after it ran.
        In **neither** set, because they are in no set: stated wherever the sets are counted
        (FR-58), never folded into the discarded set and never imputed a rank (AD-19)."""
        return self.corpus_count - len(self.rows)

    @property
    def unsplit_count(self) -> int:
        """Ranked *pièces* on neither side because no line has been drawn yet — zero once it is."""
        return len(self.rows) - (
            self.retained_count + self.discarded_count + self.unscored_count)


@dataclass(frozen=True)
class ChangeLogEntry:
    """One entry of the append-only change log (FR-20/FR-40), rendered beside its row.

    ``previous`` is the value the *pièce* carried **before** this entry — the preceding entry's
    label in ``seq`` order, or the ``unlabelled`` sentinel for the first one. It is computed from
    the ledger, never stored twice: the ledger records what each act SET, and the pairing is the
    reading of it."""

    piece_id: str
    seq: int
    previous: str
    label: str
    source: str
    set_by: str
    at: datetime


def pair_change_log(
    piece_id: str, entries: tuple[tuple[int, str, str, str, datetime], ...], *, unlabelled: str
) -> tuple[ChangeLogEntry, ...]:
    """Pair a *pièce*'s ledger entries — ``(seq, label, source, set_by, at)`` ascending — into
    ``previous → new`` change-log entries (FR-20's "previous value, new value, author, timestamp").

    Pure, so the pairing is testable without a database, and shared by the per-*pièce* log and the
    matter-level one. The first entry's ``previous`` is the explicit ``unlabelled`` sentinel — never
    null, because "no label" is a value here, not an absence (FR-40)."""
    out: list[ChangeLogEntry] = []
    previous = unlabelled
    for seq, label, source, set_by, at in sorted(entries, key=lambda e: e[0]):
        out.append(ChangeLogEntry(
            piece_id=piece_id, seq=seq, previous=previous, label=label, source=source,
            set_by=set_by, at=at))
        previous = label
    return tuple(out)
