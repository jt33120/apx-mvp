"""The worklist names its subjects, and FR-23's line discharges (story 7.7).

Retro action **C5**, part 1 — and the precondition of the story that ships the re-rank gesture.

Two defects, both live, both harmless only while no re-rank control existed. Story 7.6 shipped that
control.

**The FR-23 line rendered as a lie.** ``STALE_SUBJECT`` in the client held four kinds and
``ranking_unfit`` was not one of them, so ``STALE_SUBJECT[line.kind] ?? line.kind`` printed the raw
constant; the template then prefixed the line with *« — périmé depuis : »* and printed the FR-23
**finding** as though it were a staleness cause. The *ranking version* is not stale — it is current,
and not ranking anything.

**And the line never discharged.** ``read_worklist`` appended it whenever the *bound* carried a
finding, with nothing comparing that finding's *ranking version* against the one in force. The rule
it was breaking is written in ``worklist.py``'s own docstring, and applied to every other line.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from apx.adapters.store_postgres.queue import _run_ranking
from apx.core.domain.freshness import KIND_LINE, KIND_RANKING, Freshness
from apx.core.domain.worklist import (
    KIND_RANKING_UNFIT,
    OFFER_RERANK_REVISED_THEORY,
    OFFER_RESAMPLE,
    subject_fr,
    subjects_are_total,
    worklist_line,
)
from tests.api.test_ingest_api import _login, _prepare, _reset_state  # noqa: F401 — autouse
from tests.api.test_sampling_api import (
    MATTER,
    TENANT,
    WALL,
    _complete,
    _judge_all,
    _matter,
    _start,
)
from tests.scoring_fakes import FixedJudge
from tests.worker.test_ranking_job import _Embedder, _scorer

_WEB = Path(__file__).resolve().parents[2] / "apx" / "web" / "src"


def _worklist(client: TestClient) -> list[dict]:
    r = client.get(f"/api/matters/{MATTER}/worklist")
    assert r.status_code == 200, r.text
    return r.json()


def _rerank(store) -> None:  # noqa: ANN001
    """A real new *ranking version*, produced the way the product produces one (story 7.6's job).

    Enqueuing alone changes nothing — the cascade is the worker's — so a test that only POSTed the
    route would be asserting against a *matter* where nothing had happened."""
    order = [e.piece_id for e in store.read_ranked_order(
        tenant=TENANT, matter=MATTER, scopes={WALL}) if e.rank is not None]
    store.create_ranking_job(
        job_id="rerank", tenant=TENANT, matter=MATTER, scope=WALL, actor="Me Durand",
        now=datetime.now(UTC))
    _run_ranking(store, "rerank", embedder=_Embedder(), judge=FixedJudge(), scorer=_scorer(order))
    assert store.read_ranking_job("rerank").state == "done"


def _unfit_matter(tmp_path: Path, monkeypatch):  # noqa: ANN001, ANN202
    """A *matter* whose sample came back entirely relevant — FR-23's finding, on the wire."""
    store, client, order = _matter(tmp_path, monkeypatch)
    run = _start(client, sample_size=3)
    _judge_all(client, run, relevant=3)
    done = _complete(client, run["run_id"])
    assert done["unfit_fr"] is not None
    return store, client, order


def _unfit_line(client: TestClient) -> dict:
    return next(ln for ln in _worklist(client) if ln["kind"] == KIND_RANKING_UNFIT)


# ── the line says what it is about ────────────────────────────────────────────────────────────

def test_the_unfitness_line_names_the_ranking_never_the_raw_kind(
    tmp_path: Path, monkeypatch,  # noqa: ANN001
) -> None:
    """The defect itself, on the wire. It printed ``ranking_unfit`` to a lawyer."""
    _store, client, _order = _unfit_matter(tmp_path, monkeypatch)
    line = _unfit_line(client)
    assert line["subject_fr"].startswith("Le classement n°")
    assert "ranking_unfit" not in line["subject_fr"]
    assert line["offer"] == OFFER_RERANK_REVISED_THEORY


def test_the_unfitness_line_is_not_described_as_stale(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    """The *ranking version* is current and simply not ranking anything. The client prefixed every
    line with *« — périmé depuis : »*, which of this one is false."""
    _store, client, _order = _unfit_matter(tmp_path, monkeypatch)
    line = _unfit_line(client)
    assert "périmé" not in line["reason_fr"]
    assert "ne trie pas ce dossier" in line["reason_fr"]


def test_the_unfitness_reason_is_the_composer_s_own_sentence_word_for_word(
    tmp_path: Path, monkeypatch,  # noqa: ANN001
) -> None:
    """Quoted, never rebuilt: the declaration names the share it crossed and states that moving the
    line would not help, and it is the sentence that reaches an exported record. A second composer
    is how a surface eventually says something the record does not."""
    _store, client, _order = _unfit_matter(tmp_path, monkeypatch)
    bound = client.get(f"/api/matters/{MATTER}/bound").json()
    assert _unfit_line(client)["reason_fr"] == bound["unfit_fr"]


def test_the_subject_names_the_version_the_bound_measured(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    """AD-23. The version used to be appended by the SCREEN, from the ranking it happened to be
    showing — the same number as the artefact's only while the two cannot diverge."""
    _store, client, _order = _unfit_matter(tmp_path, monkeypatch)
    bound = client.get(f"/api/matters/{MATTER}/bound").json()
    assert _unfit_line(client)["subject_fr"] == f"Le classement n° {bound['ranking_version_no']}"


def test_a_staleness_line_still_says_it_is_stale(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    """The ordinary line is unchanged in meaning — the fix must not make the common case vaguer."""
    store, client, _order = _matter(tmp_path, monkeypatch)
    _start(client, sample_size=2)                       # a run, so a sampling_run artefact exists
    _rerank(store)                                      # and a NEW version, so it is stale
    lines = [ln for ln in _worklist(client) if ln["kind"] != KIND_RANKING_UNFIT]
    assert lines, "nothing was stale; this test would prove nothing"
    for line in lines:
        assert line["reason_fr"].startswith("périmé depuis : ")
        assert line["subject_fr"] and "_" not in line["subject_fr"]


# ── the line discharges ───────────────────────────────────────────────────────────────────────

def test_a_re_rank_discharges_the_unfitness_line(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    """The defect, reversed. The lawyer accepts *« Reclasser avec une théorie du cas révisée »*,
    gets a new version — and the banner went on accusing, because the *bound* still records the old
    version's finding and no new run has measured the new one. One paragraph per act."""
    store, client, _order = _unfit_matter(tmp_path, monkeypatch)
    assert any(ln["kind"] == KIND_RANKING_UNFIT for ln in _worklist(client))

    _rerank(store)

    assert not any(ln["kind"] == KIND_RANKING_UNFIT for ln in _worklist(client)), (
        "the finding is about a ranking version that is no longer in force, and it went on "
        "demanding an act the lawyer has already performed")


def test_the_discharge_is_not_a_disappearance(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    """Silence would be dishonest. It is not silence: the artefacts drawn over the old version are
    now stale, so the worklist carries the re-sample offer — the next act, and the only one that can
    measure whether the NEW version ranks."""
    store, client, _order = _unfit_matter(tmp_path, monkeypatch)

    _rerank(store)

    lines = _worklist(client)
    # The assertion is about the OFFER, not about which artefact carries it. A completed run and
    # the bound drawn from it are two artefacts of one act, and ``_OFFER_BY_KIND`` deliberately
    # gives them the same offer because *"abandon and redraw"* and *"re-sample"* are one gesture to
    # a lawyer. Asserting the carrier would pin an implementation detail as though it were the
    # promise.
    assert any(ln["offer"] == OFFER_RESAMPLE for ln in lines), (
        f"the lawyer was left with nothing to do: {[ln['kind'] for ln in lines]}")


# ── the register is total, and the fallback is gone ───────────────────────────────────────────

def test_every_kind_a_line_can_carry_has_a_french_subject() -> None:
    """A kind added without a subject fails here rather than printing itself to a lawyer."""
    assert subjects_are_total()


def test_an_unknown_kind_raises_rather_than_rendering_itself() -> None:
    """The old shape was ``STALE_SUBJECT[line.kind] ?? line.kind`` — a fallback that turns a missing
    translation into rendered content. That is precisely how ``ranking_unfit`` reached a screen."""
    with pytest.raises(ValueError, match="no French subject"):
        subject_fr("something_new", 1)


def test_a_version_bound_kind_with_no_version_raises() -> None:
    """AD-23 forbids an unqualified reference to a *ranking version*, and an assessment always
    carries one — ``FreshnessStamp.ranking_version_no`` is an int, never None."""
    for kind in (KIND_RANKING, KIND_LINE):
        with pytest.raises(ValueError, match="names a ranking version"):
            worklist_line(Freshness(kind=kind, artefact_id="a", changed=("corpus_count",)))


def test_the_client_holds_no_subject_map_of_its_own() -> None:
    """AC3 — deleted, not extended. A second register in the client is a second place for a kind to
    go missing, and the failure mode is silent by construction.

    Comments are stripped first: this file's own explanation of what was removed quotes the phrase,
    and a check that cannot tell a comment from rendered markup would forbid explaining itself."""
    source = (_WEB / "triage.tsx").read_text(encoding="utf-8")
    rendered = re.sub(r"/\*.*?\*/", "", source, flags=re.S)
    assert "STALE_SUBJECT" not in rendered
    assert "périmé depuis" not in rendered, (
        "the screen still composes a staleness phrase; whether a line is one is the line's to say")
