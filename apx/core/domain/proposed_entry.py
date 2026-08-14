"""The **proposed** *audit record* entry — the row an act will append, shown before it exists
(Story 5.7, FR-26 / FR-24 / FR-25).

FR-26 requires the *audit drawer* to show *"the proposed audit record entry in readable form"*
alongside the reversible actions. The v1 product put the model's reasoning under that label; the
UX contract corrects it, and the correction is the reason this module exists rather than a
formatting helper on a surface: what the drawer shows must be **the row**, assembled from the same
catalogue the writer uses, or it is a promise the product might not keep.

Three properties, and each is a way the surface could otherwise lie:

**It reads the catalogue, never the caller.** The chain an entry lands on is a property of the act
(:mod:`apx.core.domain.audit`), so the panel that says *"chaîne du cabinet"* and the writer that
files it there cannot disagree — an uncatalogued verb raises here exactly as it would at the write.

**It carries no timestamp.** A shown time that is not the time that will be written is a small lie
in the one place the product cannot afford one, and there is no honest value available: the entry
does not exist yet. The surface says *when you commit*, and this module refuses to hand it anything
more precise.

**It knows an override is an override.** When the act carries an FR-25 ground, the proposal says so
and states that a reason is mandatory — before the lawyer commits, which is the whole of FR-25 made
visible rather than enforced only at the boundary.

Pure core: stdlib only, no adapter import, no I/O.
"""

from __future__ import annotations

from dataclasses import dataclass

from apx.core.domain.audit import (
    ACTS,
    CHAIN_MATTER,
    TENANT_CHAIN,
    act,
    chain_label_fr,
    check_actor,
)
from apx.core.domain.override import ground_label_fr
from apx.core.domain.validation import ASSERTION_FR

#: How a catalogued verb says itself to a lawyer. A verb absent here renders as the verb — visible,
#: readable, and obviously unfinished, which is what an untranslated act should look like. Silently
#: prettifying an unknown verb would hide exactly the case worth seeing.
ACT_FR: dict[str, str] = {
    "piece_labelled": "Reclasser la pièce",
    "justification_rejected": "Écarter l'appréciation de l'outil",
    "justification_restored": "Rétablir l'appréciation de l'outil",
    "pin_override": "Épingler la pièce de l'autre côté de la ligne",
    "pin_removed": "Retirer l'épingle",
    "line_placed": "Poser la ligne",
    "line_moved": "Déplacer la ligne",
    "register_override": "Sortir l'entrée du registre",
    "truncation_override": "Acquitter une troncature du journal",
    # Story 5.8. The validation act's sentence is NOT a verb phrase like its neighbours, and that
    # is the point: FR-45 requires the control's own text to be the assertion the record will
    # attribute to her. A label reading « Valider » would let her assert it without reading it, and
    # the entry would then be a claim she never made in the words that were recorded.
    "validate_piece": ASSERTION_FR,
    "validation_withdrawn": "Retirer ma validation",
}
# Every offered act now has its sentence. ``values_accepted`` deliberately has none: it is the
# consequence the validation act writes over the values, never a gesture a lawyer proposes, and
# giving it a French label would put a second, differently-worded control in reach of the surface.


class ProposedEntryUnavailable(ValueError):
    """No honest proposal can be made for this act — an uncatalogued verb, or an act that belongs
    to a *matter* with no *matter* in hand. Refused rather than approximated: a panel that showed
    a plausible row for an act the writer would refuse is worse than a panel that shows nothing."""


@dataclass(frozen=True)
class ProposedEntry:
    """The audit row an action *will* append, as the drawer renders it (FR-26).

    Deliberately **not** an :class:`~apx.adapters.store_postgres.store.AuditEntry`: that type
    carries a sequence number, a chain value and a timestamp, none of which exist yet and none of
    which can be guessed. The shapes differ because the things differ, and a shared shape would
    invite a surface to fill the gaps."""

    action: str
    action_fr: str
    actor: str
    matter: str | None
    chain_scope: str
    chain_label_fr: str
    #: the FR-25 ground, when this act records an *override* — else ``None``
    override_ground: str | None = None
    override_ground_fr: str | None = None

    @property
    def is_override(self) -> bool:
        return self.override_ground is not None

    @property
    def reason_required(self) -> bool:
        """FR-25: an *override* cannot be committed without a reason. The panel disables its
        confirming control on this, so the cost is visible before the act rather than discovered
        as a refusal after it."""
        return self.is_override


def propose(action: str, *, actor: str, matter: str | None = None) -> ProposedEntry:
    """The entry ``action`` would append if ``actor`` committed it now.

    Raises :class:`ProposedEntryUnavailable` for an uncatalogued verb or a *matter*-level act with
    no *matter*, and the same ``UnknownActor`` the writer raises for an entry attributed to nobody
    — the proposal is refused in exactly the cases the write would be, so a panel can never offer
    an act the record would reject."""
    try:
        catalogued = act(action)
    except ValueError as exc:                      # UncataloguedAct — a verb nothing can file
        raise ProposedEntryUnavailable(str(exc)) from None
    check_actor(actor)                             # UnknownActor: an entry belongs to somebody
    if catalogued.chain == CHAIN_MATTER:
        if not matter:
            raise ProposedEntryUnavailable(
                f"{action!r} is a matter-level act and cannot be proposed without a matter")
        chain_scope = matter
    else:
        chain_scope = TENANT_CHAIN
    ground = catalogued.override
    return ProposedEntry(
        action=action,
        action_fr=ACT_FR.get(action, action),
        actor=actor,
        matter=matter,
        chain_scope=chain_scope,
        chain_label_fr=chain_label_fr(chain_scope),
        override_ground=ground,
        override_ground_fr=ground_label_fr(ground) if ground is not None else None,
    )


def untranslated_acts() -> tuple[str, ...]:
    """Every catalogued verb with no French sentence in :data:`ACT_FR`, in catalogue order.

    Not a lint: most catalogued verbs are system acts a lawyer never proposes (a login failure, a
    key rotation), and translating them would be inventing a gesture nobody offers. This exists so
    a test can pin the set that IS offered, and so adding an offered act without its sentence is a
    visible omission rather than a verb leaking onto a French panel."""
    return tuple(verb for verb in ACTS if verb not in ACT_FR)
