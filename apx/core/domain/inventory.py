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

    def is_consistent(self) -> bool:
        """The invariant: the three named terms account for every submitted piece."""
        return (
            self.submitted == self.in_corpus + self.failures + self.exclusions
            and min(self.in_corpus, self.failures, self.exclusions, self.submitted) >= 0
        )

    def require_consistent(self) -> None:
        """Raise if the invariant does not hold — a violation is a hard failure (SM-3)."""
        if not self.is_consistent():
            raise ValueError(
                "inventory invariant violated: "
                f"submitted={self.submitted} != in_corpus={self.in_corpus} "
                f"+ failures={self.failures} + exclusions={self.exclusions}"
            )
