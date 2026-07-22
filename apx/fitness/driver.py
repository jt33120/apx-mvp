"""The end-to-end fitness driver (FR-55, AD-2).

Enumerates the FR-55 pipeline as stages. Each stage is either **ASSERTED** (the
capability exists and is checked here) or **PENDING** with its owning story (it
does not exist yet). The driver runs every ASSERTED stage and fails on
regression; it prints the PENDING stages and the model-degradation list from the
same source of truth. **It never marks a PENDING stage green** — faking a stage
would be the v1 "demo-shaped" failure in miniature.

Today ASSERTED: the app boots, and the structural checks pass. Everything down-
stream is PENDING against the story that builds it.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from dataclasses import dataclass

ASSERTED = "ASSERTED"
PENDING = "PENDING"


@dataclass(frozen=True)
class Stage:
    name: str
    story: str
    state: str
    needs_model: bool = False
    invariant: str = ""
    check: Callable[[], None] | None = None  # raises on failure; only for ASSERTED


def _app_boots() -> None:
    """The FastAPI app imports and constructs — the 'start' stage."""
    from fastapi import FastAPI

    from apx.api.app import app

    assert isinstance(app, FastAPI), "apx.api.app.app is not a FastAPI application"


def _checks_pass() -> None:
    """The structural-property checks hold — the 'checks-green' stage."""
    from apx.checks import import_contracts

    result = import_contracts.run()
    assert result.ok, f"structural checks failed:\n{result.detail}"


# The pipeline. Order is the FR-55 sequence. `needs_model=True` marks a capability
# that does NOT survive the model provider's absence (the degradation list, AC4).
STAGES: list[Stage] = [
    Stage("start (app boots offline)", "1.1/1.2", ASSERTED, check=_app_boots),
    Stage("structural checks pass", "1.1/1.2", ASSERTED, check=_checks_pass),
    Stage("ingest a folder", "2.1", PENDING),
    Stage("index the corpus", "2.8", PENDING),
    Stage("retrieve over both engines", "3.1/3.2", PENDING),
    Stage("rank (relevance judgement)", "4.2", PENDING, needs_model=True),
    Stage("justifications", "4.6", PENDING, needs_model=True),
    Stage("place the line", "4.8", PENDING, needs_model=True),
    Stage("produce an audit record", "5.5", PENDING),
    Stage(
        "confidence bound",
        "5.4",
        PENDING,
        needs_model=True,
        invariant="regenerable from the audit record with NO model call",
    ),
    Stage("export the retained set", "6.1", PENDING),
]


def run() -> int:
    failures = 0
    print("APX offline fitness — end-to-end pipeline")
    for stage in STAGES:
        if stage.state == ASSERTED:
            assert stage.check is not None
            try:
                stage.check()
                print(f"  [ASSERTED] {stage.name}")
            except Exception as exc:  # noqa: BLE001 — report any regression, do not crash
                failures += 1
                print(f"  [FAIL]     {stage.name}: {exc}")
        else:
            inv = f" — invariant: {stage.invariant}" if stage.invariant else ""
            print(f"  [PENDING {stage.story}] {stage.name}{inv}")

    # AC4: the model-degradation list is GENERATED from the stages, not described.
    degraded = [s.name for s in STAGES if s.needs_model]
    print("\nWithout the model provider, these capabilities do not survive:")
    for name in degraded:
        print(f"  - {name}")

    if failures:
        print(f"\n{failures} asserted stage(s) regressed.", file=sys.stderr)
        return 1
    asserted = sum(1 for s in STAGES if s.state == ASSERTED)
    pending = sum(1 for s in STAGES if s.state == PENDING)
    print(
        f"\nFitness frame green: {asserted} asserted, {pending} pending "
        "(grows with the pipeline)."
    )
    return 0
