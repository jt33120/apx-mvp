"""The payload record and the chunk identity — pure domain (story 1.3, AC1/AC4).

The date invariant, the completeness gate, and deterministic (never counter-allocated)
chunk identity. No DB here; the writer and its DDL are the adapter's tests.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from apx.core.domain.identity import chunk_id, piece_id
from apx.core.domain.payload import (
    DATE_STATUSES,
    IncompletePayload,
    PayloadRecord,
    field_names,
)

_TS = datetime(2026, 7, 23, 12, 0, tzinfo=UTC)


def _payload(**overrides: object) -> PayloadRecord:
    base = dict(
        tenant="cabinet",
        matter="pole-penal",
        source_piece_id="p1",
        content_hash="h",
        provenance_path="/dossier/a.pdf",
        custodian="me@cabinet",
        extraction_method="text",
        extractor_version="pypdf-6.14.2",
        schema_version="1",
        chunking_config_version="c1",
        ingestion_timestamp=_TS,
        position=0,
        full_text="le contrat de bail",
        text_identity="t-id",
        text_version="tv1",
        piece_date=date(2020, 1, 1),
        piece_date_status="determined",
    )
    base.update(overrides)
    return PayloadRecord(**base)  # type: ignore[arg-type]


# ── chunk identity (AC4) ──


def test_chunk_id_is_deterministic() -> None:
    a = chunk_id("piece-abc", "tv1", 3, "c1")
    b = chunk_id("piece-abc", "tv1", 3, "c1")
    assert a == b and len(a) == 64


def test_chunk_id_varies_with_every_component() -> None:
    base = chunk_id("piece-abc", "tv1", 3, "c1")
    assert chunk_id("piece-xyz", "tv1", 3, "c1") != base  # different piece
    assert chunk_id("piece-abc", "tv1", 4, "c1") != base  # different position
    assert chunk_id("piece-abc", "tv1", 3, "c2") != base  # different chunking config
    assert chunk_id("piece-abc", "tv2", 3, "c1") != base  # different extraction → new gen


def test_chunk_id_reflects_re_extraction_as_a_new_generation() -> None:
    """AD-40's asserted test: a re-extraction (a changed full_text_version) yields a NEW
    chunk id — the old chunk is retired by state, never overwritten in place."""
    v1 = chunk_id("piece-abc", "extractor-v1", 0, "c1")
    v2 = chunk_id("piece-abc", "extractor-v2", 0, "c1")
    assert v1 != v2


def test_chunk_id_and_piece_id_reject_empty_inputs() -> None:
    with pytest.raises(ValueError):
        chunk_id("", "tv1", 0, "c1")
    with pytest.raises(ValueError):
        chunk_id("p", "", 0, "c1")  # empty full_text_version
    with pytest.raises(ValueError):
        chunk_id("p", "tv1", 0, "")
    with pytest.raises(ValueError):
        chunk_id("p", "tv1", -1, "c1")
    with pytest.raises(ValueError):
        piece_id("", "h", "m")  # empty tenant


# ── the payload is complete and non-nullable (AC1) ──


def test_a_complete_payload_validates() -> None:
    assert _payload().validate() is not None


def test_the_field_set_is_frozen_and_excludes_rbac_scope() -> None:
    names = field_names()
    assert "rbac_scope" not in names  # AD-9/AD-13: scope is a write-time arg, never a field
    assert "scope" not in names
    # the mandatory provenance is present
    for expected in ("tenant", "matter", "custodian", "source_piece_id", "position",
                     "chunking_config_version", "schema_version", "piece_date_status"):
        assert expected in names


@pytest.mark.parametrize(
    "field",
    ["tenant", "matter", "source_piece_id", "content_hash", "provenance_path", "custodian",
     "extraction_method", "extractor_version", "schema_version", "chunking_config_version",
     "full_text", "text_identity", "text_version"],
)
def test_an_empty_mandatory_field_is_rejected(field: str) -> None:
    with pytest.raises(IncompletePayload):
        _payload(**{field: ""}).validate()
    with pytest.raises(IncompletePayload):
        _payload(**{field: "   "}).validate()  # whitespace is not a value


def test_a_negative_or_boolean_position_is_rejected() -> None:
    with pytest.raises(IncompletePayload):
        _payload(position=-1).validate()
    with pytest.raises(IncompletePayload):
        _payload(position=True).validate()  # a bool is not a position


# ── the date invariant (AC1) ──


def test_determined_requires_a_date() -> None:
    with pytest.raises(IncompletePayload):
        _payload(piece_date=None, piece_date_status="determined").validate()


def test_undetermined_forbids_a_date() -> None:
    with pytest.raises(IncompletePayload):
        _payload(piece_date=date(2020, 1, 1), piece_date_status="undetermined").validate()


def test_undetermined_with_no_date_is_valid() -> None:
    assert _payload(piece_date=None, piece_date_status="undetermined").validate() is not None


def test_an_unknown_date_status_is_rejected() -> None:
    with pytest.raises(IncompletePayload):
        _payload(piece_date=None, piece_date_status="maybe").validate()
    assert DATE_STATUSES == frozenset({"determined", "undetermined"})


def test_a_non_date_piece_date_is_rejected() -> None:
    with pytest.raises(IncompletePayload):  # a string is not a date
        _payload(piece_date="2020-01-01", piece_date_status="determined").validate()
    with pytest.raises(IncompletePayload):  # a datetime is not a pure date
        _payload(
            piece_date=datetime(2020, 1, 1, tzinfo=UTC), piece_date_status="determined"
        ).validate()
