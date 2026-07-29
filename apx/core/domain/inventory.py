"""The inventory guarantee (FR-6) and the *denominator* record (AD-38), as a domain invariant.

The *denominator* is **one record of six disjoint named counts, never a bare integer** (AD-38):
``submitted_pieces``, ``in_corpus``, ``open_register_entries``, ``excluded_as_noise``, ``retired``
and ``unknown_cardinality_entries``. The identity SM-3 asserts, over **known** *pièces* after
container expansion, is

    submitted_pieces == in_corpus + open_register_entries      # exactly, always

— ``excluded_as_noise`` (filesystem noise, FR-6) and ``retired`` (AD-7) sit **outside** the
identity as their own named lines; ``unknown_cardinality_entries`` is a **subset** of
``open_register_entries`` (an unopened *container* is one open entry standing for an UNKNOWN number
of *pièces*) and is **never summed into any total** — it is rendered in words (AD-38). This is the
honest core of the triage product: *"nothing relevant was lost silently"* becomes a number a lawyer
can state, checked here, in the domain, independent of any store.

*(Corrected in Story 2.7 from the Story 2.4/2.6 stopgap ``submitted == in_corpus + failures +
exclusions`` — the epics' loose three-term phrasing. AD-38 and the spine's inventory state-machine
note govern: noise is a separate named line, not a summed term, because a ``.DS_Store`` was never a
pièce. The full accounting still has no unnamed remainder — every enumerated object is a pièce
→ ``submitted_pieces`` → ``in_corpus`` xor ``open_register_entries``, or is ``excluded_as_noise`` —
but the SM-3 identity is the two-term core. The count that makes the identity a real check, not a
tautology, is ``submitted_pieces`` read from the frozen application-owned ledger — Story 2.7.)*
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Inventory:
    """The *denominator* — AD-38's one record with exactly these six disjoint named counts. There is
    deliberately **no `int` representation** of the whole (a structural property forbids collapsing
    it to one number, and ``unknown_cardinality_entries`` is never summed into a total)."""

    submitted_pieces: int
    in_corpus: int
    open_register_entries: int
    # ── outside the SM-3 identity, each its own named line ──
    excluded_as_noise: int = 0     # filesystem noise (FR-6): declared, configured, never a pièce
    retired: int = 0               # AD-7: retired by state, never hard-deleted (reserved; 0 today)
    # ── a SUBSET annotation of `open_register_entries`, NEVER summed into a total (AD-38) ──
    unknown_cardinality_entries: int = 0   # open `container-unopenable` entries — rendered in words

    def is_consistent(self) -> bool:
        """The SM-3 invariant: over **known** *pièces*, ``submitted_pieces == in_corpus +
        open_register_entries``. ``excluded_as_noise`` and ``retired`` sit **outside** the identity
        (their own named lines); ``unknown_cardinality_entries`` is a subset of
        ``open_register_entries`` and is never a term here (AD-38 — an unknown cardinality is never
        summed into a total)."""
        return (
            self.submitted_pieces == self.in_corpus + self.open_register_entries
            and min(
                self.submitted_pieces, self.in_corpus, self.open_register_entries,
                self.excluded_as_noise, self.retired) >= 0
            and 0 <= self.unknown_cardinality_entries <= self.open_register_entries
        )

    def unknown_cardinality_phrase(self) -> str:
        """The words an absence claim / *denominator* must show for open unopened containers — never
        a number folded into a total (AD-38: *"N archive(s) unopened, contents unknown"*, never
        "· N not indexed"). Empty when there are none."""
        n = self.unknown_cardinality_entries
        if n <= 0:
            return ""
        return f"{n} archive unopened, contents unknown" if n == 1 else (
            f"{n} archives unopened, contents unknown")

    def require_consistent(self) -> None:
        """Raise if the invariant does not hold — a violation is a hard failure (SM-3, a release
        blocker: a single violation is not a bug)."""
        if not self.is_consistent():
            raise ValueError(
                "inventory invariant violated: "
                f"submitted_pieces={self.submitted_pieces} != in_corpus={self.in_corpus} "
                f"+ open_register_entries={self.open_register_entries} "
                f"(excluded_as_noise={self.excluded_as_noise}, retired={self.retired}, "
                f"unknown_cardinality_entries={self.unknown_cardinality_entries} — outside the "
                "identity / never summed)"
            )
