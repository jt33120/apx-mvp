"""Store tests against in-memory SQLite: persistence, idempotency, and the
Chinese-wall scope PRE-filter. Real SQL, real constraints — not a fixture.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from apx.adapters.extraction.files import FileExtractor
from apx.adapters.judge.criteria import CriteriaJudge
from apx.adapters.store_postgres.models import Base
from apx.adapters.store_postgres.store import ScopeDenied, SqlStore
from apx.core.app.ingest import ingest_folder
from apx.core.app.triage import triage_pieces


@pytest.fixture
def store() -> SqlStore:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    return SqlStore(sessionmaker(bind=engine, future=True))


def _matter(root: Path) -> None:
    (root / "a.txt").write_text("pièce une", encoding="utf-8")
    (root / "b.md").write_text("# pièce deux", encoding="utf-8")
    (root / "bad.jpg").write_bytes(b"nope")  # unsupported-format -> failure


def _ingest(root: Path, matter: str):
    return ingest_folder(root, matter=matter, tenant="t", extractor=FileExtractor())


def test_save_then_read_durable_inventory(tmp_path: Path, store: SqlStore) -> None:
    _matter(tmp_path)
    out = store.save(_ingest(tmp_path, "m"), actor="Me Dupont", scope="wall-1")
    assert out.pieces_written == 2 and out.failures_written == 1
    inv = store.inventory("m", "t", {"wall-1"})
    assert inv.in_corpus == 2 and inv.open_register_entries == 1 and inv.is_consistent()


def test_re_ingesting_does_not_duplicate(tmp_path: Path, store: SqlStore) -> None:
    _matter(tmp_path)
    r = _ingest(tmp_path, "m")
    store.save(r, actor="Me Dupont", scope="wall-1")
    store.save(r, actor="Me Dupont", scope="wall-1")
    inv = store.inventory("m", "t", {"wall-1"})
    assert inv.in_corpus == 2 and inv.open_register_entries == 1  # not doubled (AD-40)


def test_scope_prefilter_hides_matters_outside_the_wall(tmp_path: Path, store: SqlStore) -> None:
    _matter(tmp_path)
    store.save(_ingest(tmp_path, "m-a"), actor="Me Dupont", scope="wall-A")
    store.save(_ingest(tmp_path, "m-b"), actor="Me Dupont", scope="wall-B")

    # A user holding only wall-A sees m-a and NOT m-b.
    assert {m.matter for m in store.matters("t", {"wall-A"})} == {"m-a"}
    # Holding both walls sees both.
    assert {m.matter for m in store.matters("t", {"wall-A", "wall-B"})} == {"m-a", "m-b"}
    # No scope -> nothing (fail closed).
    assert store.matters("t", set()) == []


def test_reading_a_matter_outside_scope_is_refused(tmp_path: Path, store: SqlStore) -> None:
    _matter(tmp_path)
    store.save(_ingest(tmp_path, "m-b"), actor="Me Dupont", scope="wall-B")
    with pytest.raises(ScopeDenied):
        store.inventory("m-b", "t", {"wall-A"})  # holds the wrong wall
    with pytest.raises(ScopeDenied):
        store.inventory("does-not-exist", "t", {"wall-A"})  # existence not disclosed


def test_deduplicate_collapses_copies_modulo_formatting(tmp_path: Path, store: SqlStore) -> None:
    # Different bytes (so distinct pieces by content_hash) but the SAME text modulo
    # whitespace/case -> one near-duplicate cluster.
    (tmp_path / "a.txt").write_text("Le contrat est signé.", encoding="utf-8")
    (tmp_path / "b.txt").write_text("le   CONTRAT  est signé.", encoding="utf-8")
    (tmp_path / "c.txt").write_text("Autre pièce, distincte.", encoding="utf-8")
    store.save(_ingest(tmp_path, "m"), actor="Me Dupont", scope="wall-1")

    d = store.deduplicate("m", "t", {"wall-1"})
    assert d.submitted == 3 and d.distinct == 2 and d.duplicates == 1
    assert d.submitted == d.distinct + d.duplicates  # nothing lost — copies kept, collapsed
    (g,) = d.groups
    assert g.size == 2 and set(g.members) == {"a.txt", "b.txt"}


def test_deduplicate_is_scope_checked(tmp_path: Path, store: SqlStore) -> None:
    (tmp_path / "a.txt").write_text("pièce", encoding="utf-8")
    store.save(_ingest(tmp_path, "m-b"), actor="Me Dupont", scope="wall-B")
    with pytest.raises(ScopeDenied):
        store.deduplicate("m-b", "t", {"wall-A"})  # the wall pre-filters triage too


def test_judge_persists_reversible_labels_and_audits(tmp_path: Path, store: SqlStore) -> None:
    (tmp_path / "bail.txt").write_text("Contrat de bail commercial signé.", encoding="utf-8")
    (tmp_path / "facture.txt").write_text("Facture EDF, 150 euros.", encoding="utf-8")
    store.save(_ingest(tmp_path, "m"), actor="Me Dupont", scope="wall-1")

    reps = store.representatives("m", "t", {"wall-1"})
    assert len(reps) == 2  # two distinct pieces to judge
    store.save_labels("m", "t", {"wall-1"}, triage_pieces(reps, "bail", CriteriaJudge()),
                      "criteria", actor="me")

    summ = store.labels("m", "t", {"wall-1"})
    assert summ.judged == 2 and summ.relevant == 1 and summ.uncertain == 1 and summ.discarded == 0
    by = {p.provenance: p.label for p in summ.pieces}
    assert by["bail.txt"] == "relevant" and by["facture.txt"] == "uncertain"

    # reversible: re-judge with a criterion that matches the other piece — the label is overwritten
    reps2 = store.representatives("m", "t", {"wall-1"})
    store.save_labels("m", "t", {"wall-1"}, triage_pieces(reps2, "facture", CriteriaJudge()),
                      "criteria", actor="me")
    by2 = {p.provenance: p.label for p in store.labels("m", "t", {"wall-1"}).pieces}
    assert by2["facture.txt"] == "relevant" and by2["bail.txt"] == "uncertain"

    # the act is on the audit trail (two judgments + the ingestion), and it verifies
    trail = store.read_audit("m", "t", {"wall-1"})
    actions = [e.action for e in trail.entries]
    assert actions.count("judge") == 2 and "ingest" in actions and trail.verified


def test_labels_are_scope_checked(tmp_path: Path, store: SqlStore) -> None:
    (tmp_path / "a.txt").write_text("pièce", encoding="utf-8")
    store.save(_ingest(tmp_path, "m-b"), actor="Me Dupont", scope="wall-B")
    with pytest.raises(ScopeDenied):
        store.representatives("m-b", "t", {"wall-A"})
    with pytest.raises(ScopeDenied):
        store.labels("m-b", "t", {"wall-A"})


def test_search_finds_pieces_by_term_case_insensitively(tmp_path: Path, store: SqlStore) -> None:
    (tmp_path / "a.txt").write_text("Le contrat de bail commercial.", encoding="utf-8")
    (tmp_path / "b.txt").write_text("Facture EDF, 150 euros.", encoding="utf-8")
    store.save(_ingest(tmp_path, "m"), actor="Me Dupont", scope="wall-1")
    res = store.search("t", {"wall-1"}, "BAIL")  # case-insensitive
    assert res.total == 1
    assert res.hits[0].provenance == "a.txt" and "bail" in res.hits[0].snippet.lower()


def test_search_is_scope_constrained_and_does_not_leak(tmp_path: Path, store: SqlStore) -> None:
    da, db = tmp_path / "a", tmp_path / "b"
    da.mkdir()
    db.mkdir()
    (da / "x.txt").write_text("un secret terme partage", encoding="utf-8")
    (db / "y.txt").write_text("un autre secret terme partage", encoding="utf-8")
    store.save(_ingest(da, "m-a"), actor="Me Dupont", scope="wall-A")
    store.save(_ingest(db, "m-b"), actor="Me Dupont", scope="wall-B")

    # Holding only wall-A: the shared term is found in m-a, never in m-b (the wall).
    res = store.search("t", {"wall-A"}, "partage")
    assert res.total == 1 and {h.matter for h in res.hits} == {"m-a"}
    # Both walls -> both; no scope -> nothing (fail closed).
    assert store.search("t", {"wall-A", "wall-B"}, "partage").total == 2
    assert store.search("t", set(), "partage").total == 0


def test_search_empty_query_returns_nothing(tmp_path: Path, store: SqlStore) -> None:
    (tmp_path / "a.txt").write_text("un texte", encoding="utf-8")
    store.save(_ingest(tmp_path, "m"), actor="Me Dupont", scope="wall-1")
    assert store.search("t", {"wall-1"}, "   ").total == 0


# ── Story 2.1: the persist boundary — the empty-scope guard, the 0/0 matter, the case theory ──

def test_save_fails_closed_on_an_empty_scope(tmp_path: Path, store: SqlStore) -> None:
    # AC6: a null/empty/whitespace scope raises at the persist boundary and writes nothing —
    # no code path may default to permissive (defence in depth beneath the API's _held_wall).
    from sqlalchemy import func, select

    from apx.adapters.store_postgres.chunk_writer import UnauthorizedScope
    from apx.adapters.store_postgres.models import MatterScope, Piece
    _matter(tmp_path)
    r = _ingest(tmp_path, "m")
    for bad in ("", "   "):
        with pytest.raises(UnauthorizedScope):
            store.save(r, actor="Me Dupont", scope=bad, matter="m", tenant="t")
    with store._sf() as s:
        assert s.scalar(select(func.count()).select_from(Piece)) == 0
        assert s.scalar(select(func.count()).select_from(MatterScope)) == 0


def test_a_zero_piece_result_still_creates_a_durable_matter(store: SqlStore) -> None:
    # AC5: an empty result + explicit matter/tenant creates the matter at a consistent 0/0
    # inventory (the folder of zero readable files — a completed job, never a silent no-op).
    from apx.core.app.ingest import IngestionResult
    out = store.save(IngestionResult(), actor="Me Dupont", scope="wall-1", matter="m", tenant="t")
    assert out.pieces_written == 0 and out.failures_written == 0
    inv = store.inventory("m", "t", {"wall-1"})   # does not raise -> the matter is durable
    assert inv.submitted_pieces == 0 and inv.in_corpus == 0 and inv.open_register_entries == 0 \
        and inv.is_consistent()
    # the ingest audit entry is written even at 0 pieces (the full-audit-trail non-negotiable)
    trail = store.read_audit("m", "t", {"wall-1"})
    assert [e.action for e in trail.entries] == ["ingest"] and trail.verified


def test_case_theory_is_persisted_and_a_skip_never_wipes_it(
    tmp_path: Path, store: SqlStore
) -> None:
    # AC7: a provided case theory round-trips on the matter; a later skip (None) never wipes it;
    # a first ingest without one leaves NULL. Versioning is Epic 4 — this is a single value.
    from apx.adapters.store_postgres.models import MatterScope
    _matter(tmp_path)
    r = _ingest(tmp_path, "m")
    store.save(r, actor="Me Dupont", scope="wall-1", matter="m", tenant="t",
               case_theory="contestation licenciement")
    with store._sf() as s:
        assert s.get(MatterScope, {"tenant": "t", "matter": "m"}).case_theory \
            == "contestation licenciement"
    # re-ingest, theory omitted (None)
    store.save(r, actor="Me Dupont", scope="wall-1", matter="m", tenant="t")
    with store._sf() as s:
        assert s.get(MatterScope, {"tenant": "t", "matter": "m"}).case_theory \
            == "contestation licenciement"                  # not wiped by the skip
    # an empty theory is a skip too
    store.save(r, actor="Me Dupont", scope="wall-1", matter="m", tenant="t", case_theory="")
    with store._sf() as s:
        assert s.get(MatterScope, {"tenant": "t", "matter": "m"}).case_theory \
            == "contestation licenciement"                  # "" normalized at the boundary, no wipe
    store.save(r,
        actor="Me Dupont", scope="wall-1", matter="m2", tenant="t")  # a fresh matter, no theory
    with store._sf() as s:
        assert s.get(MatterScope, {"tenant": "t", "matter": "m2"}).case_theory is None
