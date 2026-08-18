"""§5 of the *matter* record says what it did, and quotes the sentence it produced.

Retro action **B2** — the Epic-5 retrospective's re-review of story 5.7 by the adversarial
fleet. Defects H4 and H5, both reproduced by hand before this file was written, both on the
document a *bâtonnier* reads.

**H4 — the wrong referent, on a court document.** ``SamplingRunLine.reviewed`` was fed
``relevant_found``. A draw of two hundred families that found three false discards printed
``reviewed: 3``: the number of *relevant pièces the draw turned up* under the word *reviewed*. It is
the strongest possible reading for the firm, in the one document produced to be read against it, and
it is this project's recurring defect — a comparison whose right-hand side is not the same thing as
its left, always failing toward the flattering side.

**H5 — the sentence never arrived.** ``_assemble_matter_record`` has taken a ``bound_sentences`` map
since Story 5.4 and no caller ever filled it. So ``bound_sentence_fr`` was ``None`` on every record
ever exported, and the document's own contract says what that means: *"§5 carries the run's numbers
and no sentence — which is what 'no sentence was composed' looks like."* One had been composed. The
*confidence bound* is the sentence a firm says to a judge; it is the reason the sampling epic
exists, and it was not in the export of the record.
"""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from tests.api.test_ingest_api import _login, _prepare, _reset_state  # noqa: F401 — autouse
from tests.api.test_sampling_api import (
    MATTER,
    _complete,
    _judge_all,
    _matter,
    _start,
)


def _record(client: TestClient, tier: str = "numbers-only") -> dict:
    r = client.post(f"/api/matters/{MATTER}/record/export?tier={tier}")
    assert r.status_code == 200, r.text
    return r.json()


def _one_completed_run(tmp_path: Path, monkeypatch, *, relevant: int):  # noqa: ANN001, ANN202
    """A real draw over the derived discarded set, every family judged, the run completed — so it
    carries a bound and §5 has something to report."""
    _store, client, _order = _matter(tmp_path, monkeypatch, cut_at_rank=1)
    run = _start(client, sample_size=99)          # a census over the small discarded set
    _judge_all(client, run, relevant=relevant)
    completed = _complete(client, run["run_id"])
    return client, completed


# ── B2/H4 — two numbers, two names ────────────────────────────────────────────────────────────

def test_reviewed_counts_what_was_reviewed_not_what_was_found(
    tmp_path: Path, monkeypatch,  # noqa: ANN001
) -> None:
    """The defect itself. The two numbers must DIFFER in this test, or it would pass on the broken
    code — which is exactly why the draw is judged with one relevant family out of several."""
    client, completed = _one_completed_run(tmp_path, monkeypatch, relevant=1)
    drawn = len(completed["drawn"])
    assert drawn > 1, "a draw of one would make the two numbers agree by accident"

    line = _record(client)["sampling_runs"][0]
    assert line["drawn"] == drawn
    assert line["reviewed"] == drawn, "every drawn family carries a verdict"
    assert line["relevant_found"] == 1
    assert line["reviewed"] != line["relevant_found"]


def test_a_partly_judged_run_reports_the_verdicts_it_actually_has(
    tmp_path: Path, monkeypatch,  # noqa: ANN001
) -> None:
    """``reviewed`` is a tally, not a status. A run judged half way says so, and ``relevant_found``
    stays 0 because the run has not completed and holds no result yet."""
    _store, client, _order = _matter(tmp_path, monkeypatch, cut_at_rank=1)
    run = _start(client, sample_size=99)
    first = run["drawn"][0]["unit"]["family_id"]
    r = client.post(
        f"/api/matters/{MATTER}/sampling/runs/{run['run_id']}/verdicts",
        json={"family_id": first, "relevant": True})
    assert r.status_code == 200, r.text

    line = _record(client)["sampling_runs"][0]
    assert line["reviewed"] == 1
    assert line["drawn"] == len(run["drawn"]) > 1
    assert line["relevant_found"] == 0


# ── B2/H5 — the bound reaches the document ────────────────────────────────────────────────────

def test_the_bound_sentence_reaches_the_exported_record(
    tmp_path: Path, monkeypatch,  # noqa: ANN001
) -> None:
    """The sentence a firm says to a judge, on the document that goes to the judge."""
    client, _completed = _one_completed_run(tmp_path, monkeypatch, relevant=0)
    line = _record(client)["sampling_runs"][0]
    assert line["bound_sentence_fr"], "a sentence WAS composed; the record said none had been"


def test_the_sentence_is_the_composer_s_own_word_for_word(
    tmp_path: Path, monkeypatch,  # noqa: ANN001
) -> None:
    """It is QUOTED from the ONE composer and never rebuilt from the numeric fields: every path
    through that composer carries the wall and the freshness, and a document that re-assembled the
    sentence from ``population_size`` and ``relevant_found`` would drop both (FR-58/FR-23).

    Asserted as an identity against the run surface rather than by looking for substrings, so a
    second composer growing anywhere fails this rather than passing it in different words."""
    client, completed = _one_completed_run(tmp_path, monkeypatch, relevant=0)
    on_the_run_surface = completed["statement_fr"]
    assert on_the_run_surface

    in_the_record = _record(client)["sampling_runs"][0]["bound_sentence_fr"]
    assert in_the_record == on_the_run_surface
    # and the two things a rebuild would have lost
    assert "wall" in in_the_record, "the sentence names the wall it was computed under"
    assert "inchangées depuis le tirage" in in_the_record


def test_both_tiers_carry_the_sentence(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    """The bound is counts, a version and a wall — no client content — so the numbers-only document
    carries it too. A bound absent from the default tier would make the safe export the one that
    cannot state the firm's own result."""
    client, _completed = _one_completed_run(tmp_path, monkeypatch, relevant=0)
    numbers = _record(client, "numbers-only")["sampling_runs"][0]["bound_sentence_fr"]
    full = _record(client, "full")["sampling_runs"][0]["bound_sentence_fr"]
    assert numbers and numbers == full


def test_a_run_that_supports_nothing_composes_no_sentence(
    tmp_path: Path, monkeypatch,  # noqa: ANN001
) -> None:
    """The honest absence, kept. An open run has no result, so §5 carries its numbers and NO
    sentence — and now that means what it says, because a composed one would have arrived."""
    _store, client, _order = _matter(tmp_path, monkeypatch, cut_at_rank=1)
    _start(client, sample_size=99)
    line = _record(client)["sampling_runs"][0]
    assert line["status"] == "open"
    assert line["bound_sentence_fr"] is None
