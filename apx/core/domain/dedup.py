"""The deterministic tier of the judgment cascade: near-duplicate detection.

Before any LLM touches a piece, we collapse the corpus by content. Two pieces
carrying the SAME text modulo formatting — a re-save, different line endings, an
encoding round-trip, whitespace or case — are the same document to a reader, so
they form one cluster and are judged once. This is the cheapest, largest and most
certain reduction of the corpus; the LLM band and the confidence bound only ever
face the distinct set. Per-piece judgment on 100,000 documents is the system's
biggest cost and its biggest data egress, so what the deterministic tier collapses
here is never spent downstream.

Recall over precision (a non-negotiable): the normalisation is CONSERVATIVE. It
removes only what provably does not change meaning — Unicode form, case, and
whitespace — never punctuation, digits or words. Two genuinely different documents
will not share a key; when in doubt pieces stay separate and fall to the uncertain
band, where each is judged on its own. A false merge would hide a piece behind
another's verdict, so we never risk one. Collapsing is reversible: every member is
kept and linked to its representative, nothing is deleted (triage is labelling).

Fuzzy near-duplicate (edit-distance / shingling) and rule filters are the next
tiers of the cascade; this module is the exact-modulo-formatting core.
"""

from __future__ import annotations

import hashlib
import unicodedata
from dataclasses import dataclass


def normalize_text(text: str) -> str:
    """A conservative canonical form: NFC Unicode, lower-cased, runs of whitespace
    collapsed to a single space, trimmed. Removes formatting noise ONLY — never
    punctuation, digits or words — so the key stays faithful to meaning."""
    return " ".join(unicodedata.normalize("NFC", text).lower().split())


def text_key(text: str) -> str:
    """The near-duplicate key: sha256 of the normalised text. Same key <=> same text
    modulo formatting. Deterministic and stable across runs and machines."""
    return hashlib.sha256(normalize_text(text).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class DuplicateCluster:
    key: str
    representative: str        # the piece_id judged on behalf of the cluster
    members: tuple[str, ...]   # every piece_id in the cluster, representative included

    @property
    def size(self) -> int:
        return len(self.members)

    @property
    def duplicates(self) -> int:
        return len(self.members) - 1  # collapsed away — kept, not deleted (reversible)


@dataclass(frozen=True)
class DedupReport:
    submitted: int          # corpus pieces considered
    distinct: int           # clusters, singletons included — what remains to examine
    duplicates: int         # pieces collapsed into a representative
    clusters: tuple[DuplicateCluster, ...]  # multi-member clusters only (singletons omitted)

    def is_consistent(self) -> bool:
        # Nothing lost: every piece is either its cluster's sole member or a duplicate.
        return self.distinct + self.duplicates == self.submitted

    def require_consistent(self) -> DedupReport:
        if not self.is_consistent():
            raise ValueError(
                f"dedup inventory inconsistent: distinct {self.distinct} + "
                f"duplicates {self.duplicates} != submitted {self.submitted}"
            )
        return self


def cluster(items: list[tuple[str, str]]) -> DedupReport:
    """Cluster ``(piece_id, text_key)`` pairs into duplicate classes, deterministically.

    The representative of a class is the lexicographically smallest piece_id (stable
    regardless of input order). The report lists only multi-member clusters — a
    singleton is its own distinct piece and needs no explanation — but ``distinct``
    counts singletons too. The invariant ``distinct + duplicates == submitted`` holds
    by construction and is asserted before returning (nothing lost)."""
    groups: dict[str, list[str]] = {}
    for pid, key in items:
        groups.setdefault(key, []).append(pid)
    clusters: list[DuplicateCluster] = []
    duplicates = 0
    for key, pids in groups.items():
        members = tuple(sorted(pids))
        if len(members) > 1:
            clusters.append(DuplicateCluster(key, members[0], members))
            duplicates += len(members) - 1
    report = DedupReport(
        submitted=len(items),
        distinct=len(groups),
        duplicates=duplicates,
        clusters=tuple(sorted(clusters, key=lambda c: (-c.size, c.representative))),
    )
    return report.require_consistent()
