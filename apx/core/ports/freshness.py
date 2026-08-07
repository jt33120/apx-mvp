"""The freshness read port (Story 4.13, FR-58 / AD-23 / AD-14 / AD-13).

The surface asks two questions through **one** scoped entry point: *what stamp was this artefact
produced under* and *what is the stamp now*. Comparing them is pure Domain
(:func:`~apx.core.domain.freshness.assess_freshness`), so the port carries no notion of "stale" at
all — it only reports observables. A store that could answer "is it stale?" would be a store holding
the rule, and the rule would then be adapter-side (AD-4).

There is **no stamp-writing method here**. A stamp is written by the artefact's own owning use case
inside the same transaction as the artefact (AD-22/AD-37) — never as a second, separate act a caller
could skip. That is why the writer lives on the producing seams' own ports, not on this read port.

No method takes an identifier without a *tenant* and a ``scopes`` argument, and ``scopes`` is
carried into the query as a **pre-filter**, never a post-filter over rows already fetched (AD-13).
Out of scope and absent return the same ``None``, so a caller cannot tell one from the other
(FR-14).
"""

from __future__ import annotations

from typing import Protocol

from apx.core.domain.confidence import RecordedBound
from apx.core.domain.freshness import FreshnessStamp


class FreshnessReader(Protocol):
    def current_stamp(
        self, *, tenant: str, matter: str, scopes: set[str], version_no: int | None = None
    ) -> FreshnessStamp | None:
        """The **current** observable state of all eight enumerated inputs for a *matter*
        (FR-58/AD-23/AD-40). ``version_no`` selects which *ranking version*'s line placement the
        ``line_seq`` observable is read from — the line is version-bound, so an artefact produced
        over version 2 must be compared against version 2's line, not against the latest one.
        ``None`` when out of scope or absent (FR-14)."""
        ...

    def read_artefact_stamps(
        self, *, tenant: str, matter: str, scopes: set[str]
    ) -> tuple[tuple[str, str, int | None, bool, FreshnessStamp], ...] | None:
        """Every stamped artefact of the *matter* as ``(kind, artefact_id, own version_no,
        superseded, recorded stamp)``, oldest first. ``()`` means the *matter* is readable and has
        produced no stamped artefact yet; ``None`` means out of scope or absent — the caller must
        not render the two the same way.

        ``superseded`` is True when a newer artefact of the same kind exists. It is a fact about the
        *matter*'s state, not a verdict: the Domain decides what it means (a superseded artefact is
        not work).

        The third element is the *ranking version* the artefact **itself** belongs to, or ``None``
        when it has none (a bound is about the *matter*'s current state). It is deliberately not the
        stamp's ``ranking_version_no`` observable, which is the *matter*'s maximum: the two differ
        whenever a line was placed over a version that was not the latest."""
        ...

    def read_current_bound(
        self, *, tenant: str, matter: str, scopes: set[str]
    ) -> RecordedBound | None:
        """The *matter*'s most recent recorded *confidence bound* with the ``artefact_id`` its
        stamp is keyed by. ``None`` when out of scope, absent, or when no bound has been
        recorded."""
        ...
