"""The evaluation harness (Story 2.12, FR-54 / AD-34): ingest the gold corpus through the REAL
ingestion path and verify the denominator at the design target (SM-3).

A fake embedder is substituted at the port boundary (AD-11): the eval run indexes through the same
``admit`` seam as production, but never loads the real BGE-M3 model in CI. The recall figure at *the
line* (SM-2) needs a ranker (Epic 3/4, which does not exist yet), so that harness lands with the
ranker; the merge gate (``apx/checks/gold_gate.py``) makes Epic 4 unable to merge without it.
"""

from __future__ import annotations

from apx.adapters.extraction.composite import CompositeExtractor
from apx.adapters.extraction.files import FileExtractor
from apx.adapters.extraction.msg import MsgExtractor
from apx.adapters.store_postgres.admission import admit
from apx.adapters.store_postgres.store import SqlStore
from apx.core.app.ingest import ingest_one_file
from apx.core.domain.inventory import Inventory
from apx.core.ports.embedding import Embedder
from eval.corpus_source import load_manifest, resolve


def real_extractor() -> CompositeExtractor:
    """The worker's extractor composition — ``.msg`` routes to the out-of-process, GPL-isolated
    MsgExtractor, everything else to FileExtractor — built here without importing the queue
    submodule (which pulls in Procrastinate). This is the real extraction path, not a fixture."""
    return CompositeExtractor([MsgExtractor(), FileExtractor()])


def ingest_gold_corpus(
    store: SqlStore, embedder: Embedder, *, tenant: str, matter: str, scope: str, actor: str,
) -> Inventory:
    """Ingest every gold-manifest item through the real ingestion path (``ingest_one_file`` →
    ``admit``), one unit at a time, as the worker does per unit — at the FULL corpus size (the
    design target for the eval, not a sample). No expander is wired: this corpus contains no
    expandable containers (a test guards that), so each file is one unit matching the manifest's
    one-item-per-file ground truth. Production wires a ``CompositeExpander``, so a corpus augmented
    with containers would need it too. Returns the matter's inventory; SM-3
    (``submitted == in_corpus + open``) must hold against it."""
    extractor = real_extractor()
    for item in load_manifest()["items"]:
        result = ingest_one_file(
            resolve(item["rel"]), item["id"], matter, tenant, extractor, custodian="eval-corpus")
        admit(store, embedder, result, scope=scope, actor=actor, matter=matter, tenant=tenant,
              audit=False)
    return store.inventory(matter, tenant, {scope})


def recall_at_the_line(ranker: object) -> float:
    """Recall at *the line* against the gold set (SM-2) — the metric the merge gate (AD-34) guards.

    It needs a ranker and a notion of *the line*, which are Epic 3/4 and do not exist yet, so this
    raises until they do. When they land it will ingest the corpus, run ``ranker`` to place *the
    line*, and return the fraction of the gold RETAINED pièces (``eval.gold_mapping.mapped_gold``)
    that fall above it — recorded on every CI run and ratcheted against the first measured baseline.
    Per PRD §7 SM-2 there is NO absolute target: the metric that matters is that it runs at all."""
    raise NotImplementedError(
        "recall_at_the_line needs a ranker and *the line* (Epic 3/4); the merge gate (AD-34) blocks"
        " ranking code from merging until this is wired and executed in CI")
