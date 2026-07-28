"""The inventory guarantee (FR-6), as a domain invariant.

Every submitted piece is in exactly one of three named, countable places:
    submitted = in corpus + open failures + declared exclusions
with no fourth bucket and no unnamed remainder. This is the honest core of the
triage product — "nothing relevant was lost silently" becomes a number a lawyer
can state — and it is checked here, in the domain, independent of any store.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Inventory:
    submitted: int
    in_corpus: int
    failures: int
    exclusions: int
    # Story 2.4 (AD-38): the count of open `container-unopenable` entries — each standing for an
    # UNKNOWN number of pièces. It is a SUBSET annotation of `failures` (the container is itself one
    # submitted unit / one failure), so it is **never** summed into any total; it is rendered in
    # words. The permanent six-field denominator record + the no-int structural property are 2.7.
    unknown_cardinality_entries: int = 0

    def is_consistent(self) -> bool:
        """The invariant: the three named terms account for every submitted piece. Note
        `unknown_cardinality_entries` is NOT a term here — it annotates a subset of `failures`
        (AD-38: an unknown cardinality is never summed into a total)."""
        return (
            self.submitted == self.in_corpus + self.failures + self.exclusions
            and min(self.in_corpus, self.failures, self.exclusions, self.submitted) >= 0
            and 0 <= self.unknown_cardinality_entries <= self.failures
        )

    def unknown_cardinality_phrase(self) -> str:
        """The words an absence claim / denominator must show for open unopened containers — never
        a number folded into a total (AD-38: *"N archive(s) unopened, contents unknown"*, never
        "· N not indexed"). Empty when there are none."""
        n = self.unknown_cardinality_entries
        if n <= 0:
            return ""
        return f"{n} archive unopened, contents unknown" if n == 1 else (
            f"{n} archives unopened, contents unknown")

    def require_consistent(self) -> None:
        """Raise if the invariant does not hold — a violation is a hard failure (SM-3)."""
        if not self.is_consistent():
            raise ValueError(
                "inventory invariant violated: "
                f"submitted={self.submitted} != in_corpus={self.in_corpus} "
                f"+ failures={self.failures} + exclusions={self.exclusions}"
            )
