"""The *validation act* as pure domain (Story 5.8, FR-45/FR-44).

No clock, no store. What is asserted here is what the record cannot be talked out of: the
provenance is derived from a timestamp rather than supplied, a batch is confirmed by its own count,
the in-force view is a view, and an acceptance carries the version it accepted.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from apx.core.domain.validation import (
    ACTION_VALIDATED,
    ACTION_WITHDRAWN,
    ASSERTION_FR,
    AcceptedValues,
    BatchCountMismatch,
    BatchSplit,
    Provenance,
    UnknownValidationAction,
    ValidationCounts,
    ValidationEntry,
    check_action,
    check_confirmed_count,
    in_force,
    is_stale,
    provenance_sentence_fr,
)

_T0 = datetime(2026, 8, 13, 14, 32, tzinfo=UTC)
_VALUES = AcceptedValues(ranking_version_id="v3", side="retained", label="contrat", band="high",
                         confidence=0.91)


def _entry(seq: int, action: str = ACTION_VALIDATED, **kw) -> ValidationEntry:  # noqa: ANN003
    kw.setdefault("accepted", _VALUES if action == ACTION_VALIDATED else None)
    return ValidationEntry(
        piece_id="p", seq=seq, action=action, actor="Me Durand", at=_T0,
        ranking_version_id="v3", **kw)


# ── the assertion (FR-45) ─────────────────────────────────────────────────────────────────────

def test_the_assertion_is_the_requirement_verbatim() -> None:
    """FR-45 words the meaning and the control's own text carries it. The test pins the sentence
    because the sentence IS the mechanism: paraphrase it and the record attributes to a lawyer a
    claim she never made in those terms."""
    assert ASSERTION_FR == "J'ai lu cette pièce et j'accepte l'appréciation de l'outil."


# ── the provenance is derived, never supplied (FR-45/FR-44) ───────────────────────────────────

def test_the_provenance_has_no_constructor_taking_a_boolean() -> None:
    """The only way to obtain one is from a timestamp. This is the shape of FR-45(c)'s defect: a
    call site that could ASSERT `opened=False` over a batch is a call site that will."""
    assert Provenance.of(_T0) is Provenance.READ
    assert Provenance.of(None) is Provenance.FROM_THE_LIST
    with pytest.raises(ValueError):
        Provenance("opened")          # not a member; there are exactly two and both are derived


def test_the_entry_derives_its_own_provenance_from_the_timestamp() -> None:
    assert _entry(1, opened_at=_T0).provenance is Provenance.READ
    assert _entry(1).provenance is Provenance.FROM_THE_LIST
    assert _entry(1, opened_at=_T0).provenance.label_fr == "lue"
    assert _entry(1).provenance.label_fr == "acceptée depuis la liste"


def test_the_sentence_states_the_consequence_in_the_second_person_with_a_date() -> None:
    """« Vous », not « la pièce a été ouverte » — the fact recorded is about the acting lawyer, and
    a panel that dropped the person would let one lawyer's entry inherit another's diligence."""
    read = provenance_sentence_fr("13/08/2026 à 14 h 32")
    assert read.startswith("Vous avez ouvert cette pièce le 13/08/2026")
    assert "inscrite\ncomme lue" in read or "comme lue" in read

    from_list = provenance_sentence_fr(None)
    assert from_list.startswith("Vous n'avez pas ouvert cette pièce")
    assert "acceptée depuis la liste" in from_list
    # never a scolding: it states what the record will say, and nothing about what she should do
    assert "devez" not in from_list and "encore" not in from_list


# ── the entry's own invariants ────────────────────────────────────────────────────────────────

def test_a_validation_carries_values_and_a_withdrawal_carries_none() -> None:
    with pytest.raises(ValueError, match="accepts values"):
        ValidationEntry(piece_id="p", seq=1, action=ACTION_VALIDATED, actor="a", at=_T0,
                        ranking_version_id="v3", accepted=None)
    with pytest.raises(ValueError, match="accepts nothing"):
        ValidationEntry(piece_id="p", seq=2, action=ACTION_WITHDRAWN, actor="a", at=_T0,
                        ranking_version_id="v3", accepted=_VALUES)


def test_a_batch_is_identified_and_sized_together_or_not_at_all() -> None:
    """A size with no identifier cannot be grouped; an identifier with no size cannot answer
    §13's question 5 — *one gesture over how many*."""
    for bad in ({"batch_id": "b1"}, {"batch_size": 180}):
        with pytest.raises(ValueError, match="identified and sized together"):
            _entry(1, **bad)
    ok = _entry(1, batch_id="b1", batch_size=180)
    assert ok.in_bulk and ok.batch_size == 180


def test_an_uncatalogued_action_is_refused() -> None:
    with pytest.raises(UnknownValidationAction):
        check_action("deleted")
    assert check_action(ACTION_VALIDATED) == ACTION_VALIDATED


# ── the in-force view (AD-7/AD-39) ────────────────────────────────────────────────────────────

def test_the_in_force_validation_is_a_view_and_a_withdrawal_lifts_it() -> None:
    """The pin precedent: never a stored membership. And *never validated* and *validated then
    withdrawn* stay different facts — the entries are all still there."""
    assert in_force(()) is None
    validated = _entry(1)
    assert in_force((validated,)) is validated
    withdrawn = _entry(2, ACTION_WITHDRAWN)
    assert in_force((validated, withdrawn)) is None
    again = _entry(3)
    assert in_force((validated, withdrawn, again)) is again


def test_the_view_reads_the_max_seq_not_the_last_element() -> None:
    """Order of the tuple must not decide the answer: a store read that came back sorted by piece
    then seq, or by nothing at all, has to give the same in-force validation."""
    entries = (_entry(3), _entry(1), _entry(2, ACTION_WITHDRAWN))
    assert in_force(entries) is not None
    assert in_force(entries).seq == 3


# ── staleness names what was accepted (AD-23) ─────────────────────────────────────────────────

def test_staleness_is_a_statement_about_the_referent_never_an_invalidation() -> None:
    entry = _entry(1)
    assert not is_stale(entry, "v3")
    assert is_stale(entry, "v4")
    # with no current version there is nothing to compare against, and inventing a verdict would be
    # the nearly-right referent this project keeps finding
    assert not is_stale(entry, None)


# ── the bulk gesture (FR-45) ──────────────────────────────────────────────────────────────────

def test_the_confirmation_names_the_count_it_is_about_to_act_on() -> None:
    assert check_confirmed_count(180, 180) == 180
    with pytest.raises(BatchCountMismatch, match="confirms a different act"):
        check_confirmed_count(181, 180)          # the selection changed under the dialog


def test_the_split_is_the_information_not_the_total() -> None:
    """A confirmation naming only the total obtains consent while telling her nothing she did not
    already know. Each of the three sentences says what the RECORD will carry."""
    mixed = BatchSplit(total=180, opened=12)
    assert mixed.not_opened == 168
    assert "12" in mixed.sentence_fr() and "168" in mixed.sentence_fr()
    assert "jamais comme lues" in mixed.sentence_fr()

    none_opened = BatchSplit(total=168, opened=0)
    assert "aucune" in none_opened.sentence_fr()
    assert "168" in none_opened.sentence_fr()

    all_opened = BatchSplit(total=12, opened=12)
    assert "toutes" in all_opened.sentence_fr()
    assert "depuis la liste" not in all_opened.sentence_fr()


# ── the counts the export prints (FR-45(d)) ───────────────────────────────────────────────────

def test_the_two_registers_are_counted_apart_and_never_pooled() -> None:
    counts = ValidationCounts(read=12, from_the_list=168, in_bulk=168, batches=1, withdrawn=1,
                              never_validated=0)
    assert counts.in_force == 180
    assert counts.individually == 12
    # the whole point: a reader can tell 12 judgements from one gesture over 168
    assert counts.read != counts.in_force


def test_an_untouched_matter_reports_zero_rather_than_nothing() -> None:
    """As of this story a 0 in §7 means *nobody validated anything*, which is a finding about the
    firm. Before it, the section said the act did not exist — a finding about the build."""
    counts = ValidationCounts(never_validated=40)
    assert counts.in_force == 0 and counts.individually == 0


def test_an_opened_at_six_months_before_the_act_is_still_read_but_says_when() -> None:
    """The timestamp is kept precisely because the flag is lossy: this entry is honestly *lue*, and
    the reader is the one who decides what an open from February is worth against an act in
    August."""
    long_ago = _T0 - timedelta(days=180)
    entry = _entry(1, opened_at=long_ago)
    assert entry.provenance is Provenance.READ
    assert entry.opened_at == long_ago
