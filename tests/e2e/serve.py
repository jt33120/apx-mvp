"""A seeded APX, served on a real port, for the browser tests (story 7.8's harness).

**Why this exists.** Three stories in a row were split with the same sentence: *the client has no
test runner at all, so no property in that half is falsifiable by this repository*. That sentence
was true, and using it to defer the work rather than to fix the gap is how a product ends up with a
green build and an unusable screen. This is the fix.

It composes the product the way the container does — **one** process serving the API and the built
SPA from the same origin, because ``apx/api/app.py`` mounts ``apx/web/dist`` at ``/`` when a build
is present. Testing a Vite dev server with a proxy would exercise a composition no deployment uses.

It lives under ``tests/`` and not under ``apx/``: everything under ``apx/`` is scanned by the
structural checks, and a seeding entry point is not product code. Run it directly, or let
Playwright's ``webServer`` start it.

The data it seeds is fixed and small, and it is thrown away with the temporary directory: no
fixture here is a claim about a real firm (the context pack's prospect relationships are stale, and
no client corpus exists).
"""

from __future__ import annotations

import os
import secrets
import sys
import tempfile
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]

TENANT = "cabinet"
WALL = "mur-a"
MATTER = "affaire-a"
EMAIL = "avocat@cabinet.test"
PASSWORD = "motdepasse-e2e"
DISPLAY_NAME = "Me Durand"

#: Six distinct *pièces*, so near-duplicate families are one per pièce unless a test says otherwise.
_FILES = {
    "bail.txt": "Contrat de bail commercial signé le 3 mars, clause résolutoire.",
    "facture.txt": "Facture EDF, cent cinquante euros, échéance avril.",
    "note.txt": "Note interne sur la clause résolutoire du bail commercial.",
    "annexe.txt": "Annexe technique au bail, plan des locaux et surfaces.",
    "courriel.txt": "Courriel du gérant au bailleur, refus de la mise en demeure.",
    "constat.txt": "Constat d'huissier du 12 juin, état des lieux de sortie.",
}


def _environment(root: Path) -> str:
    """A throwaway SQLite database and data volume, pinned into the environment before anything
    imports the store — ``DATABASE_URL`` is read at import time in more than one place."""
    data = root / "data"
    data.mkdir(parents=True, exist_ok=True)
    url = f"sqlite:///{root / 'apx.db'}"
    os.environ["DATABASE_URL"] = url
    os.environ["APX_DATA_PATH"] = str(data)
    # Generated, not a literal — for the reason given below about the encryption key, and because
    # CLAUDE.md's rule is stronger than the check that enforces it: *secrets never enter the
    # repository, in any form, including tests and fixtures*. A session key written in
    # source is one.
    os.environ["APX_SECRET_KEY"] = secrets.token_urlsafe(32)
    # AD-31 fails closed with no key, and AD-35's start-up gate refuses a tenant whose head the
    # journal cannot corroborate — so both are pinned INTO THE THROWAWAY ROOT rather than skipped.
    # A harness that disabled either would be exercising a composition no deployment has, which is
    # the sibling of the defect story 7.4 found (a path exercised only where it cannot fail).
    #
    # Generated per run, never a literal: this repository is public, and a 32-byte key written in
    # source is a secret in the repository whatever its stated purpose (FR-51/AD-47).
    os.environ.setdefault("APX_ENCRYPTION_KEY", secrets.token_urlsafe(32))
    os.environ["APX_HEAD_JOURNAL"] = str(root / "heads.journal")
    # AD-31's SECOND layer is an operator ATTESTATION that the volume itself is encrypted, and the
    # start-up gate refuses to boot without it. It is set here for the same reason ``conftest.py``
    # sets it: the "volume" is a temporary directory holding six invented French sentences, deleted
    # with the run. It is an attestation about a throwaway, not a claim about a deployment — and the
    # gate's own behaviour when it is ABSENT is asserted in ``tests/api/test_startup_gate.py``,
    # which is where that property belongs.
    os.environ.setdefault("APX_VOLUME_ENCRYPTED", "1")
    os.environ["APX_INGEST_ROOT"] = str(root / "dossiers")
    os.environ.setdefault("APX_WEB_DIST", str(_REPO / "apx" / "web" / "dist"))
    return url


def seed(root: Path) -> None:
    """A firm, a lawyer, a wall, and a *matter* with a real corpus — ingested through the product's
    own path, never written straight into the tables."""
    url = _environment(root)

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from apx.adapters.store_postgres.models import Base
    from apx.adapters.store_postgres.store import SqlStore

    engine = create_engine(url, future=True)
    Base.metadata.create_all(engine)
    store = SqlStore(sessionmaker(bind=engine, future=True))
    store.create_user(TENANT, EMAIL, PASSWORD, DISPLAY_NAME, {WALL}, is_admin=True)

    folder = root / "dossiers" / MATTER
    folder.mkdir(parents=True, exist_ok=True)
    for name, text in _FILES.items():
        (folder / name).write_text(text, encoding="utf-8")

    from fastapi.testclient import TestClient

    from apx.api.app import app

    with TestClient(app) as client:
        r = client.post(
            "/api/login", json={"tenant": TENANT, "email": EMAIL, "password": PASSWORD})
        assert r.status_code == 200, r.text
        r = client.post(
            "/api/ingest", json={"folder": str(folder), "matter": MATTER, "scope": WALL})
        assert r.status_code == 200, r.text


def main() -> None:
    root = Path(os.environ.get("APX_E2E_ROOT") or tempfile.mkdtemp(prefix="apx-e2e-"))
    seed(root)
    print(f"apx e2e: seeded {root}", file=sys.stderr, flush=True)

    import uvicorn

    from apx.api.app import app

    uvicorn.run(
        app, host="127.0.0.1", port=int(os.environ.get("APX_E2E_PORT", "8099")),
        log_level="warning")


if __name__ == "__main__":
    main()
