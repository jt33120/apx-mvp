"""The sentence is reconstructible from the record, with no model call (Story 5.4, FR-23 / FR-55).

FR-23: *"Every number in the sentence is reconstructible from the audit record alone. **Asserted by
test: recompute from the exported audit record and compare.**"* FR-55: *"the confidence bound
sentence is regenerable from the audit record **without** a model call — a statistical statement
must never depend on a network call."*

**This is the positive proof, and it is the point of the file.** The structural check
``statement-composed-offline`` asserts an ABSENCE: that the composer's import closure reaches no
network. An absence-check passes on an empty file and on a module that composes nothing. What
follows regenerates the sentence from the exported payload and **nothing else**, and compares it
character for character against the one the product shipped — with every outbound socket refused.

The *audit record* proper is Story 5.5. Until it lands, the record this round trip reads is the
**exported run payload** — the run as it leaves the product over the wire, which is the artefact a
*bâtonnier* would be handed. When 5.5 ships, the source moves and the assertion tightens; its shape
does not change.
"""

from __future__ import annotations

import socket
from pathlib import Path

import pytest

from apx.core.domain.statement import StatementInputs, statement_fr
from tests.api.test_ingest_api import _login, _prepare, _reset_state  # noqa: F401 — autouse
from tests.api.test_sampling_api import (
    MATTER,
    _complete,
    _judge_all,
    _matter,
    _start,
)

# What a *sampling run* counts (FR-38) — the same label the read seam puts on the wire. Named here
# rather than read from the payload on purpose: the regeneration must be able to state the unit
# from the record, and a unit smuggled in from the live object would make the round trip circular.
RUN_UNIT_FR = "familles de quasi-doublons écartées"


@pytest.fixture
def _no_outbound_network(monkeypatch):  # noqa: ANN001,ANN201
    """Any attempt to open an outbound TCP connection raises. A statistical claim must never
    depend on a network call (FR-55)."""
    def _refuse(*_args, **_kwargs):  # noqa: ANN002,ANN003,ANN202
        raise AssertionError("outbound network attempted while regenerating the sentence")

    monkeypatch.setattr(socket.socket, "connect", _refuse)
    monkeypatch.setattr(socket, "create_connection", _refuse)


def _from_the_record(run: dict, *, qualification: str) -> StatementInputs:
    """Rebuild the sentence's inputs from the exported payload and **nothing else**.

    Every value here is read out of ``run``. If a number in the sentence were not in the record,
    this function could not supply it and the comparison below would fail — which is precisely what
    FR-23 asks to be asserted.
    """
    return StatementInputs(
        kind=run["estimate_kind"],
        unit_fr=RUN_UNIT_FR,
        population_units=run["population_families"],
        sample_units=run["sample_size"],
        relevant_units=run["relevant_found"] or 0,
        confidence=run["confidence"],
        piece_count=run["population_pieces"],
        count_upper_units=run["count_upper"],
        prevalence_upper=run["prevalence_upper"],
        count_upper_pieces=run["count_upper_pieces"],
        relevant_pieces=run["relevant_pieces"],
        scope=run["scope"],
        run_ordinal=run["run_ordinal"],
        freshness_fr=qualification)


def test_the_sentence_is_regenerated_from_the_record_character_for_character(
    tmp_path: Path, monkeypatch, _no_outbound_network
) -> None:
    """The round trip. Complete a real run through the product's own routes, take the exported
    payload, rebuild the inputs from it alone, recompose — and compare to the shipped string."""
    _store, client, _ = _matter(tmp_path, monkeypatch)
    run = _start(client, sample_size=3)
    _judge_all(client, run)
    done = _complete(client, run["run_id"])

    assert done["statement_fr"] is not None
    regenerated = statement_fr(
        _from_the_record(done, qualification=done["run_qualification_fr"]))
    assert regenerated == done["statement_fr"]


def test_the_regeneration_needs_no_field_the_record_does_not_carry(
    tmp_path: Path, monkeypatch, _no_outbound_network
) -> None:
    """The round trip is only a proof if the record is the ONLY source. Strip the payload down to
    the keys the regeneration reads and rebuild from that — a value that had been quietly coming
    from somewhere else would raise a KeyError here rather than passing unnoticed."""
    _store, client, _ = _matter(tmp_path, monkeypatch)
    run = _start(client, sample_size=3)
    _judge_all(client, run, relevant=1)
    done = _complete(client, run["run_id"])

    keys = (
        "estimate_kind", "population_families", "sample_size", "relevant_found", "confidence",
        "population_pieces", "count_upper", "prevalence_upper", "count_upper_pieces",
        "relevant_pieces", "scope", "run_ordinal", "run_qualification_fr")
    record = {k: done[k] for k in keys}
    regenerated = statement_fr(
        _from_the_record(record, qualification=record["run_qualification_fr"]))
    assert regenerated == done["statement_fr"]


def test_a_census_regenerates_too_and_still_states_no_percentage(
    tmp_path: Path, monkeypatch, _no_outbound_network
) -> None:
    """The disjoint registers each have to survive the round trip. A census regenerating as a bound
    would be the §0.2 failure re-created by the reconstruction rather than by the product."""
    _store, client, _ = _matter(tmp_path, monkeypatch, cut_at_rank=1)
    run = _start(client, sample_size=5)
    assert run["is_census"] is True
    _judge_all(client, run)
    done = _complete(client, run["run_id"])

    assert done["estimate_kind"] == "census"
    regenerated = statement_fr(
        _from_the_record(done, qualification=done["run_qualification_fr"]))
    assert regenerated == done["statement_fr"]
    assert "%" not in regenerated


def test_the_matter_s_copied_sentence_regenerates_from_the_bound_payload(
    tmp_path: Path, monkeypatch, _no_outbound_network
) -> None:
    """The other exported artefact: ``/bound``'s ``copy_text``, the string a lawyer actually pastes.
    Regenerated from the payload alone — the wall and the freshness among the fields, because they
    are IN the sentence and therefore have to be in the record that reproduces it."""
    _store, client, _ = _matter(tmp_path, monkeypatch)
    run = _start(client, sample_size=3)
    _judge_all(client, run)
    _complete(client, run["run_id"])

    bound = client.get(f"/api/matters/{MATTER}/bound").json()
    regenerated = statement_fr(StatementInputs(
        kind=bound["kind"],
        unit_fr=bound["unit_fr"],
        population_units=bound["population"],
        sample_units=bound["sample_size"],
        relevant_units=bound["relevant_found"],
        confidence=bound["confidence"],
        piece_count=bound["piece_count"],
        count_upper_units=bound["count_upper"],
        prevalence_upper=bound["prevalence_upper"],
        count_upper_pieces=bound["count_upper_pieces"],
        relevant_pieces=bound["relevant_pieces"],
        scope=bound["scope"],
        run_ordinal=bound["run_ordinal"],
        reviewed_on=_date_of(bound["reviewed_at"]),
        freshness_fr=bound["status_fr"]))
    assert regenerated == bound["copy_text"]


def _date_of(iso: str):  # noqa: ANN202
    from datetime import datetime
    return datetime.fromisoformat(iso).date()
