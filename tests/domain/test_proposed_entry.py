"""The proposed *audit record* entry — the row before it is a row (Story 5.7, FR-26/FR-24/FR-25).

Pure: no clock, no store. What is asserted here is what the drawer promises: the chain comes from
the catalogue and not from the caller, no timestamp is invented, an override announces itself and
its mandatory reason, and an act the writer would refuse cannot be proposed.
"""

from __future__ import annotations

import dataclasses

import pytest

from apx.core.domain import audit
from apx.core.domain.audit import UnknownActor
from apx.core.domain.override import GROUND_CONTRADICTS_MACHINE, GROUND_GUARD_BYPASS
from apx.core.domain.proposed_entry import (
    ACT_FR,
    ProposedEntry,
    ProposedEntryUnavailable,
    propose,
    untranslated_acts,
)
from apx.core.domain.validation import ASSERTION_FR


def test_the_chain_comes_from_the_catalogue_never_from_the_caller() -> None:
    # a matter-level act files on the matter's chain even with a tenant in hand, and a tenant-level
    # act files on the tenant chain even with a matter in hand — the panel and the writer cannot
    # disagree about where the entry will land
    on_matter = propose(audit.ACT_PIN_OVERRIDE, actor="claire", matter="Vinci / Sogea")
    assert on_matter.chain_scope == "Vinci / Sogea"
    assert on_matter.chain_label_fr == "affaire « Vinci / Sogea »"

    on_tenant = propose(audit.ACT_REGISTER_OVERRIDE, actor="claire", matter="Vinci / Sogea")
    assert on_tenant.chain_scope == audit.TENANT_CHAIN
    assert on_tenant.chain_label_fr == "chaîne du cabinet"
    assert on_tenant.matter == "Vinci / Sogea"      # what the act is ABOUT, still carried


def test_no_timestamp_is_invented() -> None:
    # a shown time that is not the time that will be written is a small lie in the one place the
    # product cannot afford one — and there is no honest value: the entry does not exist yet
    fields = {f.name for f in dataclasses.fields(ProposedEntry)}
    assert not any("time" in f or "stamp" in f or f == "at" for f in fields), fields


def test_no_sequence_or_chain_value_is_invented_either() -> None:
    fields = {f.name for f in dataclasses.fields(ProposedEntry)}
    assert "seq" not in fields and "chain" not in fields


def test_an_override_announces_itself_and_its_mandatory_reason() -> None:
    p = propose(audit.ACT_PIN_OVERRIDE, actor="claire", matter="m")
    assert p.is_override and p.override_ground == GROUND_CONTRADICTS_MACHINE
    assert p.override_ground_fr and p.override_ground_fr != p.override_ground
    assert p.reason_required                        # FR-25, visible BEFORE the act


def test_the_guard_bypass_ground_reaches_the_panel_too() -> None:
    p = propose(audit.ACT_TRUNCATION_OVERRIDE, actor="patron")
    assert p.override_ground == GROUND_GUARD_BYPASS and p.reason_required


def test_an_ordinary_act_owes_no_reason() -> None:
    p = propose(audit.ACT_PIN_REMOVED, actor="claire", matter="m")
    assert not p.is_override and p.override_ground is None and not p.reason_required


def test_an_uncatalogued_verb_cannot_be_proposed() -> None:
    # the panel must never offer an act the writer would refuse — a plausible row for an impossible
    # act is worse than no row
    with pytest.raises(ProposedEntryUnavailable):
        propose("piece_labeled", actor="claire", matter="m")     # a typo of piece_labelled


def test_a_matter_level_act_without_a_matter_is_refused() -> None:
    with pytest.raises(ProposedEntryUnavailable, match="matter"):
        propose(audit.ACT_PIN_OVERRIDE, actor="claire")


def test_an_entry_attributed_to_nobody_is_refused_here_as_at_the_write() -> None:
    for nobody in ("", "   ", "unknown", "system"):
        with pytest.raises(UnknownActor):
            propose(audit.ACT_PIN_REMOVED, actor=nobody, matter="m")


def test_the_validation_act_is_proposable_now_and_carries_its_own_sentence() -> None:
    """Story 5.8 catalogued the verb, so the drawer's control is offered rather than disabled.

    Its ``action_fr`` is the **assertion itself**, not a verb phrase like every other offered act.
    That difference is the requirement: FR-45 makes the control's own text the claim the record
    will attribute to her, and a label reading « Valider » would let her assert it unread."""
    proposed = propose(audit.ACT_VALIDATE_PIECE, actor="claire", matter="m")
    assert proposed.action_fr == ASSERTION_FR
    assert proposed.chain_scope == "m"          # the matter's own chain (AD-43)
    assert not proposed.reason_required         # a validation is not an FR-25 override


def test_the_class_name_is_not_a_verb_and_still_cannot_be_proposed() -> None:
    """``validation_act`` is an FR-24 **class**, and no verb is spelled that way. Proposing it must
    still fail: the surface names acts, and a class that happened to be proposable would file
    entries nothing counts."""
    with pytest.raises(ProposedEntryUnavailable):
        propose("validation_act", actor="claire", matter="m")


def test_the_acceptance_is_never_offered_as_a_gesture() -> None:
    """``values_accepted`` is the consequence the validation act writes over the values, never
    something a lawyer proposes. It is deliberately absent from ACT_FR, so a surface that tried to
    offer it would render the bare verb — visible, and obviously wrong."""
    assert audit.ACT_VALUES_ACCEPTED in audit.ACTS
    assert audit.ACT_VALUES_ACCEPTED in untranslated_acts()


def test_every_act_the_drawer_offers_says_itself_in_french() -> None:
    # the acts the UX contract puts in band 4 (the validation act is 5.8's and is not offerable)
    offered = (
        audit.ACT_PIECE_LABELLED, audit.ACT_JUSTIFICATION_REJECTED,
        audit.ACT_JUSTIFICATION_RESTORED, audit.ACT_PIN_OVERRIDE, audit.ACT_PIN_REMOVED,
    )
    for verb in offered:
        assert verb in ACT_FR, verb
        assert propose(verb, actor="claire", matter="m").action_fr != verb


def test_an_untranslated_verb_renders_as_itself_rather_than_prettified() -> None:
    # visible and obviously unfinished beats a silently invented sentence
    untranslated = untranslated_acts()
    assert audit.ACT_LOGIN_FAILED in untranslated       # a system act nobody proposes
    p = propose(audit.ACT_SEARCH, actor="claire")
    assert p.action_fr == audit.ACT_SEARCH


def test_the_french_table_names_only_catalogued_verbs() -> None:
    # a sentence for a verb that does not exist is a sentence nothing can ever show
    assert set(ACT_FR) <= set(audit.ACTS)
