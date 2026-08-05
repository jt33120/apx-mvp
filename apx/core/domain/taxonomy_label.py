"""Per-*pièce* TAXONOMY labelling — exactly one label from the *tenant*'s taxonomy, or the explicit
``unlabelled`` (Story 4.5, FR-40 / AD-19 / AD-24).

A **third** label axis, orthogonal to the two that already exist and never to be conflated with
either:

- the **relevance verdict** — ``triage.Label`` (``relevant|uncertain|discard``), the cascade's own
  judgement (FR-38), persisted in ``piece_label`` and carried as ``ranked_entry.label``;
- the **cascade band** — ``confident-relevant|uncertain|confident-discard`` (a stage-2 score band);
- **this** — a *classification* label from the *tenant*'s configured triage **taxonomy** (FR-30
  configuration-as-data), a per-*pièce* attribute that says *what kind of document* a *pièce* is.

FR-40's load-bearing promises this module and its ledger keep true: **exactly one label per pièce**
— a taxonomy member or the explicit ``unlabelled`` — with **no null and no default** (AD-19); a
label is a *label*, not a rank, so changing it **never moves a pièce or the line** (the label is not
an ordering input); a label change is an **ordinary, append-only, reversible** cell edit that
**survives re-ranking marked human-set**; and an **out-of-taxonomy label can never leak** (validated
on every write). The derivation of the *current* label from the ledger is a **pure view** — the
latest entry, or ``unlabelled`` — so the value is never a stored mutable membership (AD-39).
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import StrEnum

# The explicit enumerated absence value (spine Consistency Conventions): a *pièce* with no assigned
# category is ``unlabelled`` — NEVER null and NEVER a default category (FR-40). It joins the family
# ``custodian-undeclared`` / ``date-undetermined`` / cardinality ``unknown``.
UNLABELLED = "unlabelled"


class LabelSource(StrEnum):
    """Who set a taxonomy label — recorded so a **human-set** label is durable and survives
    re-ranking (FR-40). An append-only string value (a persisted signal must always decode, like
    ``cascade.RejectionClass``)."""

    HUMAN = "human"      # a lawyer set it via a cell edit — never overwritten by the machine
    # ── reserved: no taxonomy CLASSIFIER runs in 4.5, so the machine never assigns a label yet ──
    MACHINE = "machine"  # a future classifier's suggestion (which must never overwrite a human-set)


class OutOfTaxonomyLabel(ValueError):
    """A proposed label is neither ``unlabelled`` nor a member of the *tenant*'s configured
    taxonomy. Raised so an out-of-taxonomy label can **never leak** into the ledger (FR-40 — the
    acceptance-floor guardrail: labels are validated on every write, never coerced to a default)."""


def is_member(label: str, taxonomy: Sequence[str]) -> bool:
    """Whether ``label`` is a valid assignment target: the ``unlabelled`` sentinel (always valid),
    or a member of the *tenant*'s current taxonomy."""
    return label == UNLABELLED or label in taxonomy


def validate_label(label: str, taxonomy: Sequence[str]) -> str:
    """Return ``label`` iff it is ``unlabelled`` or a member of ``taxonomy``; else raise
    :class:`OutOfTaxonomyLabel` (AD-19 — never coerced to a default). A blank label is refused: the
    explicit absence value is ``unlabelled``, never an empty string."""
    if not label or not label.strip():
        raise OutOfTaxonomyLabel("a taxonomy label is never blank — use the explicit 'unlabelled'")
    if not is_member(label, taxonomy):
        raise OutOfTaxonomyLabel(
            f"{label!r} is not in the tenant's taxonomy nor the 'unlabelled' sentinel (FR-40)")
    return label


@dataclass(frozen=True)
class LabelEntry:
    """One change-log entry for a *pièce*'s taxonomy label (FR-40 / FR-20). **Append-only**: an
    assignment or a reversal is a NEW entry, never an overwrite (AD-7). ``seq`` is the
    server-assigned per-*pièce* monotonic order (AD-49)."""

    piece_id: str
    seq: int
    label: str
    source: LabelSource


@dataclass(frozen=True)
class LabelView:
    """A *pièce*'s **current** taxonomy label — the latest change-log entry, or ``unlabelled`` when
    the ledger holds none. ``label`` is **never null** (FR-40); ``seq``/``source`` are ``None`` only
    for the never-labelled default."""

    label: str
    source: LabelSource | None
    seq: int | None

    @property
    def is_unlabelled(self) -> bool:
        return self.label == UNLABELLED


def current_label(entries: Iterable[LabelEntry]) -> LabelView:
    """The current label = the max-``seq`` entry, or ``unlabelled`` when there is none — never null,
    never a default category (FR-40 / AD-19). A **pure view** over the append-only ledger (AD-39:
    the current value is derived, never a stored mutable column)."""
    latest: LabelEntry | None = None
    for entry in entries:
        if latest is None or entry.seq > latest.seq:
            latest = entry
    if latest is None:
        return LabelView(UNLABELLED, None, None)
    return LabelView(latest.label, latest.source, latest.seq)
