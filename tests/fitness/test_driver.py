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
    # It must include ranking, justifications and the priced/confidence statement (AC4).
    joined = " ".join(degraded).lower()
    assert "rank" in joined and "justification" in joined and "confidence" in joined
