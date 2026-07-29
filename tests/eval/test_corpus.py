"""The lifted gold corpus is present, complete, and licence-recorded (Story 2.12, FR-54/FR-33).

The corpus is a CONFIGURED DATA SOURCE under ``eval/`` — never a fixture (FR-33): these tests prove
it is complete, that every gold item resolves to a real file, and that the recorded licence /
provenance pins the exact distribution used.
"""

from __future__ import annotations

import email

from eval.corpus_source import (
    CORPUS_ROOT,
    corpus_digest,
    load_manifest,
    load_provenance,
    resolve,
)

_CONTAINER_SUFFIXES = {".zip", ".7z", ".tar", ".gz", ".mbox", ".msg"}

_GOLD_PERTINENCE = {"pertinent", "référence", "edge", "borderline", "rebut"}


def test_the_manifest_is_complete() -> None:
    m = load_manifest()
    assert set(m) >= {"use_case", "dossiers", "items"}
    assert len(m["items"]) == 139 and len(m["dossiers"]) == 8


def test_every_gold_item_resolves_to_a_real_file() -> None:
    for item in load_manifest()["items"]:
        assert resolve(item["rel"]).is_file(), f"{item['id']}: {item['rel']} does not resolve"


def test_the_gold_pertinence_labels_are_the_expected_five_values() -> None:
    assert {it["gold_pertinence"] for it in load_manifest()["items"]} == _GOLD_PERTINENCE


def test_the_licence_provenance_is_recorded_and_pins_this_distribution() -> None:
    # FR-54: licence verification of the SPECIFIC distribution is an explicit, recorded step.
    prov = load_provenance()
    assert prov["licence"]["third_party_encumbrance"] == "none"
    assert prov["privacy"]["contains_real_client_data"] is False
    # the recorded digest matches the corpus as lifted — a drift is a detectable, reviewable event
    assert prov["distribution"]["distribution_sha256"] == corpus_digest()


def test_the_corpus_is_a_configured_source_not_a_test_fixture() -> None:
    # FR-33: the corpus lives under eval/, never under tests/ (a fixture) — it enters only through
    # ingestion as a configured source, so no runtime or test fixture path reaches it.
    assert CORPUS_ROOT.parent.name == "eval"
    assert "tests" not in CORPUS_ROOT.parts


def test_the_corpus_holds_no_expandable_containers() -> None:
    # the harness wires no expander (each file is one unit); guard that no item is a container — an
    # archive by extension, or a .eml carrying attachments — so the one-item-per-file denominator
    # matches production, which DOES wire a CompositeExpander (review LOW).
    for item in load_manifest()["items"]:
        path = resolve(item["rel"])
        assert path.suffix.lower() not in _CONTAINER_SUFFIXES, f"{item['id']} is a container"
        if path.suffix.lower() == ".eml":
            message = email.message_from_bytes(path.read_bytes())
            attachments = [p for p in message.walk() if p.get_content_disposition() == "attachment"]
            assert not attachments, f"{item['id']} is a .eml with attachments (would expand)"
