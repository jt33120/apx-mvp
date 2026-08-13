"""The register-override act (Story 5.6, FR-25 / FR-5 / AD-37) — an entry leaves ``open`` because
a person decided it should, and said why.

A thin Application-layer seam over the :class:`RegisterOverrider` port: a caller (the API, or the
register surface) depends on this **core** function, never on the store adapter (AD-4). The store
owns the guarantee — it validates the mandatory reason (FR-25), re-observes ``open`` under a row
lock (AD-37's conditional commit) and writes the state change, the append-only reason row and the
audit entry in one transaction (AD-22).

AD-37 names this use case as the **one owner** of the ``open → overridden`` transition. The other
two exits stay where they were: a successful *ingestion* retry (``open → resolved``) and a
re-import (``open → superseded-by-reimport``). A retry attempted against an entry this act has
closed is refused by that path's own conditional commit — it never silently resolves what a person
deliberately closed. Reversing an override (AD-37's *worklist* line) belongs to Story 5.7, where
the *audit drawer*'s reversible actions are the subject; it is a new entry, never an erasure.

It imports Ports only (AD-4), touches no store.
"""

from __future__ import annotations

from apx.core.ports.register_override import RegisterOverrider


def override_register_entry(
    overrider: RegisterOverrider, *, entry_id: str, tenant: str, actor: str, reason: str,
    scopes: set[str], is_admin: bool = False,
) -> str:
    """Close a *failure register* entry by *override* through the port (FR-25). Returns the
    resulting ``resolution_state``. Raises ``MissingOverrideReason`` (a blank reason — nothing
    written), ``ScopeDenied`` (out of scope, or absent — one answer, never disclosing existence),
    or ``ValueError`` when the entry is no longer ``open``."""
    return overrider.override_register_entry(
        entry_id=entry_id, tenant=tenant, actor=actor, reason=reason, scopes=scopes,
        is_admin=is_admin)
