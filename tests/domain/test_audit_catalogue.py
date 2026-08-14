"""The audit catalogue is the mechanism FR-24's enumeration was not (Story 5.5).

FR-24 lists thirteen classes of act that must be recorded. A list in a requirements document is
discharged by reading it; these tests make it discharged by the build. They also freeze the two
things a later story would otherwise break by tidying: the historical verbs (renaming one orphans
every entry already written under it) and the v1 chain recipe (changing it turns a correct record
unverifiable in one deploy).
"""

from __future__ import annotations

import pytest

from apx.core.domain import audit

# ── the chain identity (AD-43) ────────────────────────────────────────────────────────────────

def test_the_tenant_chain_is_named_not_inferred_from_a_missing_matter() -> None:
    assert audit.chain_scope_of("dupont-2026") == "dupont-2026"
    assert audit.chain_scope_of(None) == audit.TENANT_CHAIN
    assert audit.chain_scope_of("") == audit.TENANT_CHAIN
    # the empty string, not None — the column is NOT NULL and the head row's key needs no COALESCE
    assert audit.TENANT_CHAIN == ""


def test_a_chain_says_which_one_it_is_in_the_lawyers_language() -> None:
    assert "dupont" in audit.chain_label_fr("dupont-2026")
    assert audit.chain_label_fr(audit.TENANT_CHAIN) == "chaîne du cabinet"


# ── the catalogue ─────────────────────────────────────────────────────────────────────────────

def test_every_fr24_class_is_either_covered_or_declared_pending_with_its_story() -> None:
    covered = audit.covered_classes()
    for cls in audit.FR24_CLASSES:
        if cls in covered:
            assert cls not in audit.PENDING_CLASSES, (
                f"{cls} is written by {audit.verbs_for(cls)} and cannot also be pending")
        else:
            assert cls in audit.PENDING_CLASSES, f"FR-24 class {cls} has no writer and no owner"
            assert audit.PENDING_CLASSES[cls], f"{cls} is pending with no story number"


def test_a_pending_class_names_a_real_story_number() -> None:
    for cls, story in audit.PENDING_CLASSES.items():
        assert cls in audit.FR24_CLASSES, f"{cls} is not an FR-24 class"
        major, _, minor = story.partition(".")
        assert major.isdigit() and minor.isdigit(), f"{cls} names {story!r}, not a story number"


def test_modified_and_accepted_are_two_classes_never_one() -> None:
    """FR-24 §614 makes them asymmetric: 'accepted' exists ONLY where a validation act occurred —
    not by default, not by elapsed time, not by having been on screen. Folded into one class,
    'accepted' silently acquires every value the user merely left alone.

    Both are covered as of Story 5.8, and the asymmetry is now enforced rather than deferred: the
    accepted class has exactly ONE verb, which is what makes "only where a validation act occurred"
    a property of the catalogue instead of a promise about call sites."""
    assert audit.CLASS_VALUE_MODIFIED in audit.covered_classes()
    assert audit.CLASS_VALUE_ACCEPTED in audit.covered_classes()
    assert audit.PENDING_CLASSES == {}, "Story 5.8 was the last pending class"
    assert list(audit.verbs_for(audit.CLASS_VALUE_ACCEPTED)) == [audit.ACT_VALUES_ACCEPTED]
    assert len(audit.verbs_for(audit.CLASS_VALUE_MODIFIED)) > 1, (
        "a modification has many shapes; an acceptance has exactly one, and that asymmetry is "
        "the requirement rather than an accident of the catalogue")


def test_every_catalogued_verb_has_a_class_a_chain_and_is_uniquely_keyed() -> None:
    verbs = [a.verb for a in audit.ACTS.values()]
    assert len(verbs) == len(set(verbs)), "a duplicated verb would shadow a catalogue row"
    known = set(audit.FR24_CLASSES) | {audit.CLASS_CHAIN_LIFECYCLE, audit.CLASS_SECURITY_EVENT}
    for a in audit.ACTS.values():
        assert a.act_class in known, f"{a.verb} carries an unknown class {a.act_class}"
        assert a.chain in (audit.CHAIN_MATTER, audit.CHAIN_TENANT)


def test_an_uncatalogued_verb_is_refused_rather_than_recorded() -> None:
    with pytest.raises(audit.UncataloguedAct):
        audit.act("piece_labeled")  # the American spelling: a typo, not an act class
    assert audit.act(audit.ACT_PIECE_LABELLED).act_class == audit.CLASS_VALUE_MODIFIED


def test_the_historical_verbs_can_never_leave_the_catalogue() -> None:
    """Every verb eleven prior stories wrote into the record. A verb removed here does not tidy
    the code — it orphans entries already written under it, which FR-24 requires to stay countable
    and filterable. Both spellings (kebab and snake) are frozen for the same reason."""
    historical = {
        "bulk-retry", "config_changed", "create_user", "export-bound", "export-register",
        "grant_scope", "ingest", "judge", "justification_recorded", "key_rotated", "line_moved",
        "line_placed", "open-piece", "piece_labelled", "ranking_recorded", "rescope_matter",
        "retry", "revoke_scope", "sampling-run-abandon", "sampling-run-complete",
        "sampling-run-start", "sampling-verdict", "tenant_provisioned", "truncation_override",
        "pin_override", "pin_removed", "justification_rejected", "justification_restored",
        "search", "export-search", "grant_admin", "revoke_admin", "case_theory_written",
        "case_theory_withdrawn", "login_failed", "login_locked_out", "login_mfa_unenrolled",
        "login_mfa_failed",
    }
    assert historical <= set(audit.ACTS), sorted(historical - set(audit.ACTS))


def test_a_tenant_level_act_never_claims_a_matter_chain() -> None:
    for verb in ("grant_scope", "revoke_scope", "config_changed", "tenant_provisioned",
                 "login_failed", "chain_opened"):
        assert audit.act(verb).chain == audit.CHAIN_TENANT, verb
    # a re-scope names a matter and is a tenant-authority act: the matter is its subject
    assert audit.act("rescope_matter").chain == audit.CHAIN_MATTER


# ── the actor (FR-24) ─────────────────────────────────────────────────────────────────────────

def test_no_entry_is_ever_attributed_to_nobody() -> None:
    for nobody in ("unknown", "UNKNOWN", " unknown ", "", "system", "anonymous"):
        with pytest.raises(audit.UnknownActor):
            audit.check_actor(nobody)


def test_a_system_actor_names_a_catalogued_component() -> None:
    assert audit.system_actor("auth") == "system:auth"
    assert audit.is_system_actor("system:auth")
    assert not audit.is_system_actor("Maître Dupont")
    with pytest.raises(audit.UnknownActor):
        audit.system_actor("telemetry")
    with pytest.raises(audit.UnknownActor):
        audit.check_actor("system:telemetry")


def test_a_persons_display_name_passes_through_unchanged() -> None:
    assert audit.check_actor("Maître Dupont") == "Maître Dupont"


# ── the chained content (FR-53) ───────────────────────────────────────────────────────────────

def _content(version: int, **over: object) -> str:
    kwargs: dict[str, object] = dict(
        version=version, seq=7, tenant="cabinet", chain_scope="dupont-2026",
        matter="dupont-2026", actor="Maître Dupont", action="line_moved", detail="d",
        timestamp="2026-08-12T09:00:00.000000", app_version="0.1.0", schema_version="1",
    )
    kwargs.update(over)
    return audit.chained_content(**kwargs)  # type: ignore[arg-type]


def test_the_v1_recipe_is_frozen_byte_for_byte() -> None:
    """Every entry written before Story 5.5 chained over this exact string. Changing it does not
    migrate anything — it reports tampering on a record nobody touched."""
    assert _content(audit.CONTENT_V1) == (
        "7|cabinet|dupont-2026|Maître Dupont|line_moved|d|2026-08-12T09:00:00.000000")


def test_the_v1_recipe_renders_a_matterless_entry_as_the_empty_string() -> None:
    assert _content(audit.CONTENT_V1, matter=None).startswith("7|cabinet||")


def test_the_v2_recipe_names_the_chain_and_carries_both_versions() -> None:
    content = _content(audit.CONTENT_V2)
    assert content.startswith("v2|")
    assert "|dupont-2026|dupont-2026|" in content   # chain scope, then the matter
    assert content.endswith("|0.1.0|1")


def test_the_two_recipes_can_never_collide() -> None:
    """A v1 content string can never be produced by the v2 recipe, whatever the field values —
    so an entry can never be replayed under the other reading to forge a matching chain value."""
    assert not _content(audit.CONTENT_V1).startswith("v2|")
    assert _content(audit.CONTENT_V2) != _content(audit.CONTENT_V1)


def test_an_unknown_content_version_is_refused_never_guessed() -> None:
    with pytest.raises(audit.UnknownContentVersion):
        _content(3)


def test_the_chain_value_depends_on_the_predecessor_and_the_content() -> None:
    content = _content(audit.CONTENT_V2)
    first = audit.chain_value("", content)
    assert audit.chain_value("abc", content) != first
    assert audit.chain_value("", content + " ") != first
    assert len(first) == 64
