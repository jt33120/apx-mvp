"""The proof of exhaustive search names the documents the firm decided to live without.

Retro action **B2** — the Epic-5 retrospective's re-review of story 5.6 by the adversarial
fleet. Defect H1, reproduced by hand before this file was written.

An *override* (FR-25) is the one act that takes a document out of ``open`` although it never entered
the *corpus*. The exhaustive engine's face — the sentence a lawyer copies, the export a *bâtonnier*
receives, the seal the client renders — named ``open_register_entries`` and stopped there. So the
sequence was:

    before the override:  "Le registre liste 1 pièce(s) au registre" ......... amber, qualified
    after  the override:  "Le registre liste 0 pièce(s) au registre" ......... GREEN, unqualified

Nothing about the corpus had changed. A signed decision to live without a document made the
strongest claim this product makes — *nothing relevant was lost silently* — read as unqualified.
FR-25 exists to keep that number visible, and this is the surface where it is worth the most.

The client's seal (``ExhaustivePanel`` in ``apx/web/src/App.tsx``) carries the same condition and
the same three-term equation; it has no test runner in this repository, so it is covered by
``npm run typecheck`` / ``build`` and by the server sentence asserted here — stated rather than
implied.
"""

from __future__ import annotations

import re
from pathlib import Path

from fastapi.testclient import TestClient

from apx.adapters.store_postgres.store import SqlStore
from apx.api.app import app
from apx.core.app.ingest import IngestedFailure, IngestionResult
from apx.core.domain.failures import ErrorClass
from tests.api.test_ingest_api import _login, _prepare, _reset_state  # noqa: F401 — autouse

TENANT, WALL, MATTER, ME = "t", "wall", "m", "me@x.fr"


def _ready(tmp_path: Path, monkeypatch, *, error_class: ErrorClass):  # noqa: ANN001, ANN202
    """One readable pièce and one document the tool could not read — the register entry an
    override will close."""
    store = _prepare(tmp_path, monkeypatch)
    store.create_user(TENANT, ME, "motdepasse", "Me Durand", {WALL})
    folder = tmp_path / "dossier"
    folder.mkdir()
    (folder / "bail.txt").write_text(
        "Contrat de bail commercial, clause résolutoire.", encoding="utf-8")
    client = TestClient(app)
    _login(client, ME, pw="motdepasse")
    client.post("/api/ingest", json={"folder": str(folder), "matter": MATTER, "scope": WALL})
    # the failing document, recorded through the store's own save path
    store.save(
        IngestionResult(pieces=[], failures=[IngestedFailure(
            filename="scelle.pdf", submitted_path="/dossier/scelle.pdf", matter=MATTER,
            tenant=TENANT, error_class=error_class, detail="illisible", custodian="Me Martin")]),
        scope=WALL, actor="Me Durand", matter=MATTER, tenant=TENANT)
    return store, client


def _search(client: TestClient) -> dict:
    r = client.get("/api/search/exhaustive", params={"q": "bail"})
    assert r.status_code == 200, r.text
    return r.json()


def _face(client: TestClient) -> str:
    """The sentence the export carries — the same composer as the panel's."""
    r = client.get("/api/search/exhaustive/export", params={"q": "bail"})
    assert r.status_code == 200, r.text
    found = re.search(r'<div class="disc">(.*?)</div>', r.text, re.S)
    assert found is not None, r.text
    return found.group(1)


def _override(store: SqlStore) -> None:
    entry = store.register(MATTER, TENANT, {WALL})[0]
    assert store.override_register_entry(
        entry_id=entry.id, tenant=TENANT, actor="Me Durand", scopes={WALL},
        reason="scellé restitué au greffe, le client renonce à le produire") == "overridden"


def test_the_face_names_the_overridden_count(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    """The defect, on the document that leaves the building."""
    store, client = _ready(tmp_path, monkeypatch, error_class=ErrorClass.PASSWORD_PROTECTED)
    before = _face(client)
    assert "1 pièce(s) au registre" in before

    _override(store)

    after = _face(client)
    assert "0 pièce(s) au registre" in after
    assert "1 pièce(s) écartée(s) sur dérogation motivée" in after, (
        "an override made a qualified absence read as an unqualified one")


def test_the_denominator_on_the_wire_still_reconciles(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    """SM-3's three terms reach the client, so the equation it prints adds up. It printed
    ``submitted = in_corpus + open`` and the third term was not on the panel at all."""
    store, client = _ready(tmp_path, monkeypatch, error_class=ErrorClass.PASSWORD_PROTECTED)
    _override(store)
    d = _search(client)["denominator"]
    assert d["overridden_register_entries"] == 1
    assert d["submitted_pieces"] == (
        d["in_corpus"] + d["open_register_entries"] + d["overridden_register_entries"])


def test_an_overridden_archive_still_says_its_contents_are_unknown(
    tmp_path: Path, monkeypatch,  # noqa: ANN001
) -> None:
    """The worst shape of the same defect: the entry stood for an UNKNOWN number of pièces, and the
    override erased the *"dont N au contenu inconnu"* clause along with the count. The absence claim
    then rested on a hole whose size nobody knows, and said nothing about it."""
    store, client = _ready(tmp_path, monkeypatch, error_class=ErrorClass.CONTAINER_UNOPENABLE)
    assert "au contenu inconnu" in _face(client)

    _override(store)

    after = _face(client)
    assert "au contenu inconnu" in after, "an override is not a discovery about contents"
    assert "1 pièce(s) écartée(s) sur dérogation motivée" in after
    assert _search(client)["denominator"]["unknown_cardinality_entries"] == 1


def test_a_matter_with_no_override_reads_exactly_as_before(
    tmp_path: Path, monkeypatch,  # noqa: ANN001
) -> None:
    """The clause appears only when there is something to say. A sentence that always carried
    *"et 0 pièce(s) écartée(s)"* would train the reader to skip the line that matters."""
    _store, client = _ready(tmp_path, monkeypatch, error_class=ErrorClass.PASSWORD_PROTECTED)
    assert "dérogation" not in _face(client)
