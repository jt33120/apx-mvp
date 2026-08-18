"""The *ranking version* identity has one source, and it is the judge (Story 7.3, AD-23).

The runtime property is proven in ``tests/test_rank_command.py``. This is the guard that keeps the
next composer from growing somewhere else with its own plausible literals — which is not a
hypothetical: before this story every construction site in the repository was a fixture asserting
``temperature=0.0, sampling={"top_p": 1.0}`` for a request that sends no sampling parameter at all.
"""

from __future__ import annotations

from pathlib import Path

from apx.checks.ranking_identity_source import the_ranking_identity_has_one_source

_FIXTURES = Path(__file__).resolve().parent.parent / "_fixtures" / "ranking_identity"


def test_it_is_green_on_the_runtime() -> None:
    result = the_ranking_identity_has_one_source()
    assert result.ok, result.detail
    assert "core/app/rank.py" in result.detail


def test_a_clean_tree_passes() -> None:
    """One composer and no config read — the shape the runtime has."""
    result = the_ranking_identity_has_one_source([_FIXTURES / "clean"])
    assert result.ok, result.detail


def test_a_second_composer_fails() -> None:
    result = the_ranking_identity_has_one_source([_FIXTURES / "second_composer"])
    assert not result.ok
    assert "app.py" in result.detail and "second composer" in result.detail


def test_reading_the_model_from_config_outside_the_judge_door_fails() -> None:
    """The mechanism of the defect: a second reading of `model_name` beside the judge, which can
    disagree with the judge that was actually composed."""
    result = the_ranking_identity_has_one_source([_FIXTURES / "config_read"])
    assert not result.ok
    assert "model_name" in result.detail and "preference" in result.detail


def test_it_fails_closed_when_its_own_door_is_missing() -> None:
    """A check that cannot find the composer it guards is not passing — it is looking at the wrong
    tree, and a green light from there is the worst possible answer."""
    result = the_ranking_identity_has_one_source([_FIXTURES / "config_read" / "api"])
    assert not result.ok
    assert "not in the tree" in result.detail
