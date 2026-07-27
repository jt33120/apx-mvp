"""The content-freedom of the projection primitive, proven structurally (story 1.10, AD-26/FR-31):
seed a tenant's data with a unique content token in EVERY content-bearing field, and a secret
value in the environment, then assert neither appears in any registered projector's output — nor
in the union of all projectors' output for that tenant. This exercises the real gather-plus-project
path (``store.projection_snapshot`` → ``project_all``), not a hand-built content-free input.
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

TOKEN = "ZZQUNIQUECONTENTTOKENZZ"          # a seeded content token — must never surface
SECRET = "ZZQSEEDEDSECRETVALUE0123456789ZZ"  # a seeded secret value (FR-31 ↔ FR-51)
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


def test_no_projector_leaks_a_seeded_content_token(store: SqlStore, monkeypatch) -> None:
    monkeypatch.setenv("SEEDED_API_KEY", SECRET)  # a secret shaped like a real one
    _seed(store)
    projections = project_all(store.projection_snapshot(TENANT))
    for p in projections:  # every registered projector, individually
        blob = json.dumps({"projector": p.projector, "values": dict(p.values)}, default=str)
        assert TOKEN not in blob, f"{p.projector} leaked the content token"
        assert SECRET not in blob, f"{p.projector} leaked the secret value"


def test_the_union_of_all_projectors_is_content_free(store: SqlStore, monkeypatch) -> None:
    # the attestation floor is not composable: two projectors each content-free can jointly
    # identify, so the UNION of all projectors' output for one tenant is scanned too (AD-26 i).
    monkeypatch.setenv("SEEDED_API_KEY", SECRET)
    _seed(store)
    union = "\n".join(projection_strings(project_all(store.projection_snapshot(TENANT))))
    assert TOKEN not in union
    assert SECRET not in union


def test_the_projection_still_reports_the_content_free_counts(store: SqlStore) -> None:
    # content-free does not mean empty: the counts/versions ARE emitted (just nothing identifying)
    _seed(store)
    by_name = {p.projector: p for p in project_all(store.projection_snapshot(TENANT))}
    assert by_name["corpus_counts"].values == {"pieces": 1, "failures": 1, "matters": 1}
    assert by_name["error_class_histogram"].values == {"by_class": {"unreadable": 1}}
    assert by_name["versions"].values == {"schema": ["s1"], "extractor": ["v1"]}
