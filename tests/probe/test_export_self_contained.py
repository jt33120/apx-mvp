"""The exported *matter* record is self-contained (Story 5.7, FR-26).

> *"The export is self-contained: a reader with the export and no access to the system can
> reconstruct every number in it. Asserted by test that recomputes from the export in a process
> with no access to the application's stores."*

That last clause is the whole test, and it is why this file lives under ``tests/probe/`` rather
than beside the store tests: an assertion run in the same process as the store proves nothing about
what a *bâtonnier* can do with a file. The document is serialised, handed to a **subprocess** whose
environment carries no ``DATABASE_URL`` and whose import of anything under
``apx.adapters.store_postgres`` is made to fail, and that process recomputes the numbers and
reports.

Two things are therefore proven at once:

1. **The reader needs nothing but the file.** Every number on the document is recomputable from
   the document.
2. **The reader gets nothing but the file.** A numbers-only document carries no client content —
   asserted by searching the serialised bytes for strings the store holds and the tier forbids,
   which is the check a stripping implementation would fail on the field somebody forgot.
"""

from __future__ import annotations

import dataclasses
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from apx.adapters.store_postgres.models import Base
from apx.adapters.store_postgres.store import SqlStore
from apx.core.app.ingest import IngestedFailure, IngestionResult
from apx.core.domain.cascade import Band, CascadeResult, PieceJudgement, Stage
from apx.core.domain.config import CascadeConfig
from apx.core.domain.failures import ErrorClass
from apx.core.domain.matter_record import MatterRecord, Tier
from apx.core.domain.ranking import RankingIdentityInputs, assemble_identity, rank_cascade
from apx.core.domain.triage_sets import PinSide

TENANT, MATTER, WALL = "t", "Vinci / Sogea", "contentieux"
THEORY = "Le retard est imputable au maître d'ouvrage — pièces 12 à 41."
PIN_REASON = "aveu implicite au §4 — décisif malgré le rang"
CUSTODIAN = "Me Martin"
FILENAME = "scelle-confidentiel.pdf"
_CFG = CascadeConfig(uncertain_low=0.35, uncertain_high=0.65, calibration_sample=20,
                     stage3_max_share=0.5)
_PAIRS = [("a", Band.CONFIDENT_RELEVANT, 0.9), ("b", Band.CONFIDENT_RELEVANT, 0.7),
          ("c", Band.CONFIDENT_DISCARD, 0.2), ("d", Band.CONFIDENT_DISCARD, 0.1)]

#: What the reader's process must recompute, and what it must never be able to reach. Kept as data
#: so the subprocess script and the assertions here cannot drift apart.
_READER = r'''
import json, os, sys, importlib

# ── the reader has no store ───────────────────────────────────────────────────────────────────
assert not os.environ.get("DATABASE_URL"), "the reader must hold no database URL"

class _NoStore:
    """Refuse every import under the store adapter — a bâtonnier has the file and nothing else.

    ``find_spec`` (not the removed ``find_module``): raising from the finder propagates out of the
    import statement, so the block is total rather than advisory."""
    def find_spec(self, name, path=None, target=None):
        if name.startswith("apx.adapters"):
            raise ImportError(f"the reader has no access to {name}")
        return None

sys.meta_path.insert(0, _NoStore())
try:
    importlib.import_module("apx.adapters.store_postgres.store")
except ImportError:
    pass
else:                                            # pragma: no cover — the guard itself failing
    print(json.dumps({"error": "the reader could import the store"}))
    raise SystemExit(1)

# ── recompute, from the document alone ────────────────────────────────────────────────────────
doc = json.loads(sys.stdin.read())
cover, denom = doc["cover"], {d["key"]: d["count"] for d in doc["denominator"]}

out = {
    # SM-3's identity, recomputed from the printed counts (AD-38)
    "identity_holds": denom["submitted_pieces"] == (
        denom["in_corpus"] + denom["open_register_entries"]
        + denom["overridden_register_entries"]),
    "submitted": denom["submitted_pieces"],
    # every count the document states, re-derived from its own rows
    "line_positions": len(doc["line_history"]),
    "pins": len(doc["pins"]),
    "overrides_listed": len(doc["overrides"]),
    "overrides_total": doc["overrides_total"],
    "theory_versions": len(doc["case_theory"]),
    # what the reader can conclude about continuity, from the document's own face (AD-43)
    "recomputable_chains": [c["chain_scope"] for c in cover["chains"]
                            if c["recomputable_from_this_document"]],
    "chains_stated": len(cover["chains"]),
    "scope": cover["scope"],
    "tier": cover["tier"],
    "degraded": cover["degraded_extracts"] > 0,
    "pending_sections": sorted(p["key"] for p in doc["pending"]),
}
print(json.dumps(out))
'''


def _identity():  # noqa: ANN202
    inputs = RankingIdentityInputs(
        case_theory_version_id=None, model_provider="mistral",
        model_endpoint="https://api.mistral.ai/v1", model_name="mistral-small-latest",
        prompt_version="cascade-question-v1", temperature=0.0, sampling={"top_p": 1.0},
        embedder_model_id="bge-m3", embedder_model_version="1.5",
        chunking_config_version="chunk-v1", schema_version="slice-a")
    return assemble_identity(
        inputs=inputs, basis="intrinsic", uncertain_low=0.35, uncertain_high=0.65,
        calibration_sample=20, stage3_max_share=0.5)


def _order():  # noqa: ANN202
    judgements = [
        PieceJudgement.judged(piece_id=pid, family_id=f"fam-{pid}", is_representative=True,
                              stage_reached=Stage.STAGE_2, band=band, score=score)
        for pid, band, score in _PAIRS
    ]
    result = CascadeResult(
        judgements=tuple(judgements), families={j.family_id: (j.piece_id,) for j in judgements},
        unscored=(), stage3_share=0.5, over_stage3_floor=False, basis="intrinsic")
    return rank_cascade(result, _CFG)


@pytest.fixture
def store() -> SqlStore:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    s = SqlStore(sessionmaker(bind=engine, future=True))
    s.save(
        IngestionResult(failures=[IngestedFailure(
            filename=FILENAME, submitted_path=f"/dossier/{FILENAME}", matter=MATTER,
            tenant=TENANT, error_class=ErrorClass.PASSWORD_PROTECTED, detail="x",
            custodian=CUSTODIAN)]),
        actor="Me Dupont", scope=WALL, matter=MATTER, tenant=TENANT)
    s.record_ranking(
        tenant=TENANT, matter=MATTER, actor="Claire Fontaine", identity=_identity(),
        order=_order())
    s.append_case_theory_version(
        tenant=TENANT, matter=MATTER, actor="Claire Fontaine", text=THEORY)
    placed = s.place_line(tenant=TENANT, matter=MATTER, actor="Claire Fontaine", scopes={WALL})
    s.move_line(
        tenant=TENANT, matter=MATTER, actor="Claire Fontaine", scopes={WALL},
        last_retained_piece_id="c", expected_seq=placed.seq,
        priced_statement="400 pièces de plus à lire")
    s.pin_piece(tenant=TENANT, matter=MATTER, actor="Claire Fontaine", scopes={WALL},
                piece_id="d", side=PinSide.RETAIN, reason=PIN_REASON)
    return s


def _document(store: SqlStore, tier: Tier) -> MatterRecord:
    return store.export_matter_record(
        tenant=TENANT, matter=MATTER, actor="Claire Fontaine", scopes={WALL}, tier=tier)


def _serialise(record: MatterRecord) -> str:
    """The document as bytes a reader could be handed. ``dataclasses.asdict`` walks the whole tree,
    which is exactly the property that makes the tier's omissions checkable: a field that was never
    populated cannot appear here."""
    return json.dumps(dataclasses.asdict(record), ensure_ascii=False, default=str)


def _read_without_a_store(payload: str) -> dict:
    """Run the reader in a subprocess that has no ``DATABASE_URL`` and cannot import the store."""
    env = {k: v for k, v in os.environ.items() if k != "DATABASE_URL"}
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[2])
    proc = subprocess.run(  # noqa: S603
        [sys.executable, "-c", _READER], input=payload, env=env,
        capture_output=True, text=True, timeout=120, check=False)
    assert proc.returncode == 0, f"the reader failed: {proc.stderr[-2000:]}"
    return json.loads(proc.stdout.strip().splitlines()[-1])


# ── AC-8: every number is recomputable from the document alone ────────────────────────────────

@pytest.mark.parametrize("tier", [Tier.NUMBERS_ONLY, Tier.FULL])
def test_a_reader_with_no_store_recomputes_every_number(store: SqlStore, tier: Tier) -> None:
    record = _document(store, tier)
    read = _read_without_a_store(_serialise(record))

    assert read["identity_holds"]                       # SM-3, re-derived from the printed counts
    assert read["submitted"] == record.denominator[0].count
    assert read["line_positions"] == len(record.line_history) == 2
    assert read["pins"] == len(record.pins) == 1
    assert read["theory_versions"] == len(record.case_theory) == 1
    assert read["overrides_total"] == record.overrides_total
    assert read["scope"] == WALL and read["tier"] == tier.value


def test_the_reader_is_told_which_chain_this_document_alone_proves(store: SqlStore) -> None:
    # AD-43: the matter's own chain is recomputable from a scoped export and the tenant chain is
    # not — the document says which, and the reader can act on that without the system
    read = _read_without_a_store(_serialise(_document(store, Tier.NUMBERS_ONLY)))
    assert read["chains_stated"] >= 1
    assert read["recomputable_chains"] == [MATTER]


def test_the_reader_is_told_what_is_not_built_rather_than_a_zero(store: SqlStore) -> None:
    read = _read_without_a_store(_serialise(_document(store, Tier.NUMBERS_ONLY)))
    assert read["pending_sections"] == ["accepted_as_is", "validation_acts"]


# ── AC-6: the reader gets nothing but the file, and numbers-only carries no content ────────────

def test_the_numbers_only_bytes_contain_no_client_content(store: SqlStore) -> None:
    # the check a stripping implementation fails on the one field somebody forgot: search the
    # SERIALISED document for strings the store holds and this tier forbids
    payload = _serialise(_document(store, Tier.NUMBERS_ONLY))
    for forbidden in (THEORY, PIN_REASON, CUSTODIAN, FILENAME):
        assert forbidden not in payload, forbidden


def test_the_full_tier_is_the_one_that_carries_it(store: SqlStore) -> None:
    payload = _serialise(_document(store, Tier.FULL))
    assert THEORY in payload and PIN_REASON in payload


def test_the_reader_process_really_cannot_reach_the_store(store: SqlStore) -> None:
    # the guard itself is asserted: a reader that could import the store would make every
    # assertion above vacuous, and this is the failure that would be invisible
    probe = _READER.replace(
        'print(json.dumps(out))',
        'print(json.dumps({"reached": False}))')
    env = {k: v for k, v in os.environ.items() if k != "DATABASE_URL"}
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[2])
    proc = subprocess.run(  # noqa: S603
        [sys.executable, "-c", probe], input=_serialise(_document(store, Tier.NUMBERS_ONLY)),
        env=env, capture_output=True, text=True, timeout=120, check=False)
    assert proc.returncode == 0, proc.stderr[-2000:]
    assert '"error"' not in proc.stdout          # the guard did not report a reachable store
