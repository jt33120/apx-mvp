"""The ranking-recorder port (Story 4.3, AD-37 / AD-4).

The one boundary the ranking act persists across: the store adapter implements it, the ``core/app``
orchestrator depends only on this Protocol (AD-4 — the core imports no adapter). The store mints the
per-*matter* monotonic ``version_no`` and the referenceable ``version_id`` inside its transaction
(AD-37 — one owning use case, a conditional commit), so the identity + the deterministic order are
all the caller supplies.
"""

from __future__ import annotations

from typing import Protocol

from apx.core.domain.ranking import RankedOrder, RankingIdentity, RankingVersion


class RankingRecorder(Protocol):
    def record_ranking(
        self, *, tenant: str, matter: str, actor: str, identity: RankingIdentity, order: RankedOrder
    ) -> RankingVersion:
        """Persist one ranked order against a newly-minted *ranking version*, atomically with one
        audit entry (AD-22). The implementation assigns the monotonic ``version_no``, verifies the
        recorded identity inputs are unchanged at commit time (the conditional commit, AD-23/AD-37 —
        a changed *case-theory* version fails loudly, nothing written), and never mutates a version
        after creation (append-only). Returns the minted :class:`RankingVersion`. Raises a typed
        error for an unknown *matter* or a stale identity input."""
        ...
