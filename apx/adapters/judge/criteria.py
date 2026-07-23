"""The deterministic filter tier of the cascade — a transparent judge, no model.

A piece is RELEVANT if it contains one of the matter's declared terms (the lawyer's
own triage query, comma-separated); otherwise UNCERTAIN. It never DISCARDs: the
absence of a declared term is not evidence of irrelevance (recall over precision), so
what this tier does not promote falls to the uncertain band the LLM tier then judges.

This is not a fixture and not a stand-in for a model (FR-33): it is a real,
defensible rule over real text, and it names the term it matched so the verdict can
be shown. Terms and text are normalised the same way the near-duplicate key is
(``dedup.normalize_text``), and matched on word boundaries so "bail" does not match
inside "travail".
"""

from __future__ import annotations

from apx.core.domain.dedup import normalize_text
from apx.core.domain.triage import Label, Verdict


def _terms(question: str) -> list[str]:
    """The declared terms: comma-separated, each normalised (internal spaces kept, so
    a multi-word term like "contrat de bail" stays one term)."""
    return [t for t in (normalize_text(part) for part in question.split(",")) if t]


class CriteriaJudge:
    """Recall-first deterministic judge: promote on a declared-term match, else defer."""

    name = "criteria"

    def judge(self, *, question: str, text: str) -> Verdict:
        terms = _terms(question)
        if not terms:
            return Verdict(Label.UNCERTAIN, "aucun critère fourni — à juger")
        hay = f" {normalize_text(text)} "
        hits = sorted({t for t in terms if f" {t} " in hay})
        if hits:
            return Verdict(Label.RELEVANT, f"correspond à : {', '.join(hits)}")
        return Verdict(Label.UNCERTAIN, "aucun terme déclaré présent — à juger")
