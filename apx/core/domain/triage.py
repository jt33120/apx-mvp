"""Triage labels — the reversible verdicts of the judgment cascade.

Every judged piece gets exactly one label. Triage is reversible labelling, never
deletion: a DISCARD sets a piece aside, it does not remove it, and a re-judge simply
overwrites the label. Recall over precision: a judge that is unsure returns UNCERTAIN
(for a closer look — the LLM tier, then a human), never DISCARD. A DISCARD must be
defensible, so every verdict carries a non-empty rationale — nothing is set aside
silently.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Label(StrEnum):
    RELEVANT = "relevant"      # responsive — kept in the set
    UNCERTAIN = "uncertain"    # not resolved — the band a closer judge (LLM, then human) takes
    DISCARD = "discard"        # not responsive — set aside, reversibly, and only when defensible


@dataclass(frozen=True)
class Verdict:
    label: Label
    rationale: str   # why — never empty; a keep or a discard must be explainable


@dataclass(frozen=True)
class PieceLabel:
    piece_id: str
    label: Label
    rationale: str


@dataclass(frozen=True)
class TriageOutcome:
    labels: tuple[PieceLabel, ...]

    @property
    def judged(self) -> int:
        return len(self.labels)

    @property
    def relevant(self) -> int:
        return sum(1 for x in self.labels if x.label is Label.RELEVANT)

    @property
    def uncertain(self) -> int:
        return sum(1 for x in self.labels if x.label is Label.UNCERTAIN)

    @property
    def discarded(self) -> int:
        return sum(1 for x in self.labels if x.label is Label.DISCARD)

    def is_consistent(self) -> bool:
        # every piece carries exactly one of the three labels — nothing uncounted
        return self.relevant + self.uncertain + self.discarded == self.judged
