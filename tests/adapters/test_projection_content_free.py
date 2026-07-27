"""The content-freedom of the projection primitive, proven end-to-end (story 1.10, AD-26/FR-31):
seed a tenant's data with a unique content token in EVERY content-bearing field, then assert it
appears in NO registered projector's output — nor in the union of all projectors' output for that
tenant. This exercises the real gather-plus-project path (``store.projection_snapshot`` →
``project_all``), not a hand-built content-free input. (Structural backstops: the
``snapshot_fields_are_content_free`` check forbids widening the input to carry content; the seeded
SECRET tie to FR-51 lands with the REDACTED-kind projector of the 6.2 diagnostic export.)
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from apx.adapters.store_postgres.models import Base
from apx.adapters.store_postgres.store import SqlStore
from apx.core.app.ingest import IngestedFailure, IngestedPiece, IngestionResult
from apx.core.domain.failures import ErrorClass
from apx.core.projection import project_all, projection_strings

TOKEN = "ZZQUNIQUECONTENTTOKENZZ"  # a seeded content token — must never surface
TENANT = f"cabinet-{TOKEN}"


@pytest.fixture
def store() -> SqlStore:
    engine = create_engine("sqlite://", future=True)
    Base.metadata.create_all(engine)
    return SqlStore(sessionmaker(bind=engine, future=True))


def _seed(store: SqlStore) -> None:
    piece = IngestedPiece(
        id="p1", matter=f"matter-{TOKEN}", tenant=TENANT, content_hash="c" * 8, text_key="t" * 8,
        provenance_path=f"/secret/{TOKEN}/contract.pdf", custodian=f"custodian-{TOKEN}",
        extraction_method="text", extractor_version="v1", schema_version="s1",
        ingestion_timestamp=datetime.now(UTC), full_text=f"the contract mentions {TOKEN}",
        text_version="v1")
    failure = IngestedFailure(
        filename=f"{TOKEN}-broken.docx", submitted_path=f"/secret/{TOKEN}/broken.docx",
        matter=f"matter-{TOKEN}", tenant=TENANT, error_class=ErrorClass.UNREADABLE,
        detail=f"could not read {TOKEN}")
    store.save(IngestionResult(pieces=[piece], failures=[failure]), "wall", actor=f"actor-{TOKEN}")


def test_no_projector_leaks_a_seeded_content_token(store: SqlStore) -> None:
    _seed(store)
    for p in project_all(store.projection_snapshot(TENANT)):  # every registered projector
        blob = json.dumps({"projector": p.projector, "values": dict(p.values)}, default=str)
        assert TOKEN not in blob, f"{p.projector} leaked the content token"


def test_the_union_of_all_projectors_is_content_free(store: SqlStore) -> None:
    # the attestation floor is not composable: two projectors each content-free can jointly
    # identify, so the UNION of all projectors' output for one tenant is scanned too (AD-26 i).
    _seed(store)
    union = "\n".join(projection_strings(project_all(store.projection_snapshot(TENANT))))
    assert TOKEN not in union


def test_versions_projector_bounds_a_content_bearing_version(store: SqlStore) -> None:
    # a version identifier is code identity by contract; defence-in-depth bounds it to a machine
    # token, so an extractor that smuggled content into its version does NOT emit it verbatim.
    leaky = f"extractor-{TOKEN}"  # 33 chars — over the version bound
    piece = IngestedPiece(
        id="p1", matter="m", tenant=TENANT, content_hash="c" * 8, text_key="t" * 8,
        provenance_path="/x.pdf", custodian="c", extraction_method="text", extractor_version=leaky,
        schema_version="s1", ingestion_timestamp=datetime.now(UTC), full_text="x", text_version="v")
    store.save(IngestionResult(pieces=[piece]), "wall", actor="a")
    versions = {p.projector: p for p in project_all(
        store.projection_snapshot(TENANT))}["versions"].values
    assert TOKEN not in json.dumps(versions)          # the smuggled content is not emitted
    assert "«non-conforming»" in versions["extractor"]


def test_the_projection_still_reports_the_content_free_counts(store: SqlStore) -> None:
    # content-free does not mean empty: the counts/versions ARE emitted (just nothing identifying)
    _seed(store)
    by_name = {p.projector: p for p in project_all(store.projection_snapshot(TENANT))}
    assert by_name["corpus_counts"].values == {"pieces": 1, "failures": 1, "matters": 1}
    assert by_name["error_class_histogram"].values == {"by_class": {"unreadable": 1}}
    assert by_name["versions"].values == {"schema": ["s1"], "extractor": ["v1"]}
