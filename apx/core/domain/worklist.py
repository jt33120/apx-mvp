"""The *worklist* — derived from staleness, never stored (Story 4.13, FR-58).

FR-58 requires that ingestion into a ranked *matter* *"generates a worklist line offering a
re-rank"*. A worklist line here is a **view over the freshness assessments**, computed at read time
by :func:`worklist_lines`. Nothing is persisted, so there is no queue row to drift from the
staleness it reports, nothing to garbage-collect when the artefact is recomputed, and no
invalidation rule to get wrong — a stored worklist would need exactly the freshness comparison this
module already is.

A line **offers**; it never acts. FR-58: *"staleness is resolved only by explicit user-initiated
recomputation"* — the surface renders the offer, the user decides, and the recomputation produces a
**new** artefact.

Pure: no clock, no I/O, Domain imports only (AD-4).
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from apx.core.domain.freshness import (
    KIND_BOUND,
    KIND_LINE,
    KIND_RANKING,
    KIND_SAMPLING_RUN,
    Freshness,
)

# What a line offers. An offer is a named act the user may start — never something the system does
# on its own, and never a promise that the recomputation has been queued.
OFFER_RERANK = "re-rank"        # produce a NEW ranking version over the current corpus
OFFER_REPLACE_LINE = "re-line"  # place the line again over the current order
OFFER_RESAMPLE = "re-sample"    # draw and review a new sample, producing a NEW bound
# FR-23's own remedy, and deliberately NOT ``OFFER_RERANK``: a re-rank offered because the corpus
# moved re-runs the same case theory over new material, which is exactly the act that cannot help
# here. The finding is that the theory is not separating this matter, so the offer names the
# revision (FR-37). Two offers, because they are two different acts with two different reasons.
OFFER_RERANK_REVISED_THEORY = "re-rank-revised-theory"

_OFFER_BY_KIND = {
    KIND_RANKING: OFFER_RERANK,
    KIND_LINE: OFFER_REPLACE_LINE,
    KIND_BOUND: OFFER_RESAMPLE,
    # A *sampling run* (Story 5.1) offers the same act whether it is an OPEN run whose population
    # moved under it (FR-22's "invalidated in flight") or a COMPLETED one whose bound has gone
    # stale: draw again. One offer, because "abandon and redraw" and "re-sample" are the same
    # gesture to the lawyer — and because two offers for one kind would let a surface pick the
    # wrong one. The run's own reading carries ``invalidated_in_flight`` for the immediate telling.
    KIND_SAMPLING_RUN: OFFER_RESAMPLE,
}

# The French sentence each offer says on the surface. Verb-first, the lawyer's voice (DESIGN.md).
_OFFER_FR = {
    OFFER_RERANK: "Re-classer produira une nouvelle version ; vos valeurs saisies seront "
                  "conservées.",
    OFFER_REPLACE_LINE: "Replacer la ligne produira une nouvelle position ; l'ordre ne bouge pas.",
    OFFER_RESAMPLE: "Ré-échantillonner produira une nouvelle borne ; l'ancienne reste consultable.",
    OFFER_RERANK_REVISED_THEORY: (
        "Reclasser avec une théorie du cas révisée produira une nouvelle version ; déplacer la "
        "ligne ne corrigerait rien."),
}

# The *ranking version* itself is the work, not one of its stamped artefacts (FR-23, Story 5.4).
KIND_RANKING_UNFIT = "ranking_unfit"


@dataclass(frozen=True)
class WorklistLine:
    """One line: a stale artefact, the inputs that moved, and what is offered.

    ``changed_fr`` carries the French phrases so the surface never has to re-derive them from the
    keys, and ``offer_fr`` is the sentence beside the button. ``artefact_id`` names the artefact the
    offer would supersede — never the artefact it would produce, which does not exist yet.
    """

    kind: str
    artefact_id: str
    changed: tuple[str, ...]
    changed_fr: tuple[str, ...]
    offer: str
    offer_fr: str


def worklist_line(assessment: Freshness) -> WorklistLine | None:
    """One line for one assessment, or ``None`` when the artefact is not work.

    Two artefacts are not work: a **fresh** one (nothing moved) and a **superseded** one (the
    recomputation this line would offer has already been performed, and produced the artefact that
    replaced it). Superseded artefacts keep their verdict on the freshness surface — they are still
    readable and the verdict is still true of them (AD-7) — but they must not generate an offer, or
    the offer never discharges: the user accepts the re-rank and the banner still demands one,
    growing by one paragraph per act until nobody reads it."""
    if assessment.fresh or assessment.superseded:
        return None
    offer = _OFFER_BY_KIND[assessment.kind]
    return WorklistLine(
        kind=assessment.kind, artefact_id=assessment.artefact_id, changed=assessment.changed,
        changed_fr=assessment.changed_fr, offer=offer, offer_fr=_OFFER_FR[offer])


def unfitness_line(*, version_id: str, said_fr: str) -> WorklistLine:
    """FR-23's third clause, which had no code anywhere until the Story 5.4 review said so.

    The requirement has **four** parts: declare the *ranking version* unfit, say so in words,
    *"produce a worklist line offering a re-rank with a revised or newly written case theory
    (FR-37)"*, and not offer a line move. Three were built and this one was not — a requirement
    two-thirds implemented reads, from the outside, exactly like one that is finished.

    Unlike every other line here it is **not** derived from a freshness assessment: nothing is
    stale. The ranking is fresh, current, and not ranking anything — which is why the offer is the
    revised theory rather than the plain re-rank a staleness line would give.

    ``changed`` carries the finding itself in ``changed_fr``, so the surface can state *why* this
    line exists without re-deriving the threshold: a line that said only "re-rank" would be an
    instruction with no argument behind it.
    """
    return WorklistLine(
        kind=KIND_RANKING_UNFIT, artefact_id=version_id, changed=(KIND_RANKING_UNFIT,),
        changed_fr=(said_fr,), offer=OFFER_RERANK_REVISED_THEORY,
        offer_fr=_OFFER_FR[OFFER_RERANK_REVISED_THEORY])


def worklist_lines(assessments: Iterable[Freshness]) -> tuple[WorklistLine, ...]:
    """The *matter*'s worklist. ``()`` when nothing is stale — an empty worklist that was **read**,
    which the surface must not render the same way it renders a worklist it **could not** read
    (the Story 4.10 lesson: a failed read is not a verified absence)."""
    lines: list[WorklistLine] = []
    for assessment in assessments:
        line = worklist_line(assessment)
        if line is not None:
            lines.append(line)
    return tuple(lines)


def offers(lines: Sequence[WorklistLine]) -> tuple[str, ...]:
    """The distinct offers present, in first-seen order — what the surface can propose right now."""
    seen: list[str] = []
    for line in lines:
        if line.offer not in seen:
            seen.append(line.offer)
    return tuple(seen)
