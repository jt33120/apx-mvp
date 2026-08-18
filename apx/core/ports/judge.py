"""The Judge port — the boundary the judgment cascade decides across (AD-4, AD-27).

A deterministic filter (declared criteria) and, later, a provider-agnostic LLM
implement this; the core imports neither an LLM SDK nor any adapter. The contract is
recall-first: return UNCERTAIN when not sure, and never DISCARD what cannot be
defended — so a piece is set aside only on a judgment that can be shown, never by
the absence of a signal.
"""

from __future__ import annotations

from typing import Protocol

from apx.core.domain.ranking import JudgeIdentity
from apx.core.domain.triage import Verdict


class Judge(Protocol):
    name: str  # self-identifying, recorded on every label for transparency (FR-33)

    #: what this judge IS — provider, endpoint, model, temperature and sampling, reported by the
    #: judge rather than read from configuration, so a *ranking version* names the decider that
    #: actually ran (Story 7.3, AD-23). ``name`` is for a label; this is for the immutable
    #: fingerprint, and the two must not be confused.
    identity: JudgeIdentity

    def judge(self, *, question: str, text: str) -> Verdict:
        """Decide whether a piece's ``text`` is responsive to the matter's triage
        ``question``. Recall over precision: prefer UNCERTAIN to a wrong DISCARD."""
        ...
