"""The register-override port (Story 5.6, FR-25 / FR-5 / AD-37 / AD-22 / AD-4).

The one boundary the *failure register* override persists across: the store adapter implements it
(the ``open → overridden`` conditional commit, the append-only reason ledger and the atomic audit
entry), and the ``core/app`` seam depends only on this Protocol (AD-4 — the core imports no
adapter).

The store owns every guarantee, and the caller supplies only the entry, the actor and the sentence:
FR-25's mandatory reason, AD-37's conditional commit on an observed ``open`` under a row lock, and
AD-22's atomicity between the state change, the ledger row and the record.
"""

from __future__ import annotations

from typing import Protocol


class RegisterOverrider(Protocol):
    def override_register_entry(
        self, *, entry_id: str, tenant: str, actor: str, reason: str, scopes: set[str],
        is_admin: bool = False,
    ) -> str:
        """Take a *failure register* entry out of ``open`` although the document never entered the
        *corpus* — FR-5's other exit, and an *override* under FR-25.

        Requires a non-blank one-line reason (a blank one raises ``MissingOverrideReason`` and
        **nothing** is written — no state change, no ledger row, no audit entry). The commit is
        conditional on an observed ``open`` under a row lock (AD-37): an entry already ``resolved``
        or already ``overridden`` is refused rather than re-closed, so a retry that succeeded in
        between is never quietly undone. The state change, the append-only reason row and the
        ``register_override`` audit entry commit together (AD-22).

        Authorised like every other register act: the entry's *tenant* must be the caller's and its
        *matter* within the caller's scope; an entry whose *matter* is undetermined is reachable
        only by a holder of the *tenant* administrative grant (FR-49).

        Returns the resulting ``resolution_state``. Raises ``MissingOverrideReason`` on a blank
        reason, ``ScopeDenied`` out of scope **or absent** (one answer — an absent entry must not
        be tellable from one behind a wall the caller lacks), and ``ValueError`` when the entry is
        no longer ``open``."""
        ...
