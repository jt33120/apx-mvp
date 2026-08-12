"""The fitness driver is honest: it asserts what exists and never fakes a stage."""

from __future__ import annotations

from apx.fitness import driver
from apx.fitness.driver import ASSERTED, PENDING, Stage


def test_driver_is_green_today() -> None:
    assert driver.run() == 0


def test_a_regressed_asserted_stage_turns_the_driver_red(monkeypatch) -> None:
    def _boom() -> None:
        raise RuntimeError("simulated regression")

    broken = Stage("start (app boots offline)", "1.1", ASSERTED, check=_boom)
    monkeypatch.setattr(driver, "STAGES", [broken, *driver.STAGES[1:]])
    assert driver.run() == 1


def test_pending_stages_are_never_run_as_asserted() -> None:
    # A PENDING stage carries no check and is never executed as green — the guard
    # against demo-shaped faking.
    for stage in driver.STAGES:
        if stage.state == PENDING:
            assert stage.check is None, f"PENDING stage {stage.name!r} must not carry a check"
        else:
            assert stage.state == ASSERTED and stage.check is not None


def test_degradation_list_is_generated_from_the_stages() -> None:
    degraded = [s.name for s in driver.STAGES if s.needs_model]
    assert degraded, "the model-degradation list must be non-empty and derived from stages"
    # FR-55 enumerates it: "the ranking, the justifications, the priced statement".
    joined = " ".join(degraded).lower()
    assert "rank" in joined and "justification" in joined and "line" in joined


def test_the_confidence_sentence_is_NOT_in_the_degradation_list() -> None:
    """FR-55 names this exclusion in as many words: *"the confidence bound sentence is regenerable
    from the audit record **without** a model call — a statistical statement must never depend on a
    network call — and this is asserted here."*

    Until Story 5.4 the confidence-bound stage was PENDING and marked ``needs_model``, and the
    degradation-list assertion above matched on the word *"confidence"* — so the test that existed
    to enumerate what the model's absence costs was asserting that it cost the one capability
    FR-55 says it must not. Asserted positively now, and in both directions: the sentence is a
    stage, it is ASSERTED, and it does not need the model."""
    sentence = [s for s in driver.STAGES if "confidence bound" in s.name.lower()]
    assert len(sentence) == 1, "the confidence-bound sentence must be exactly one stage"
    assert not sentence[0].needs_model, (
        "the confidence bound sentence must render with the provider absent (FR-55)")
    assert sentence[0].check is not None, (
        "an offline guarantee with no check is a description, not a fitness function (FR-56)")
    assert not any("confidence" in s.name.lower() for s in driver.STAGES if s.needs_model)
