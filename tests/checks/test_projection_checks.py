"""The content-free projection structural checks (story 1.10, AD-26). Green on the real registry,
RED on the fixtures (the failure paths AC5 requires); and the AD-45 egress check is proven to live
in the uncuttable checks unit, not in this (predicted-to-be-dropped) projection unit (AC4).
"""

from __future__ import annotations

from pathlib import Path

from apx.checks import import_contracts
from apx.checks.__main__ import CHECKS
from apx.checks.projection import (
    projection_emitted_only_by_registry,
    projectors_declare_attestation,
)
from apx.core.projection import Attestation, RegisteredProjector, ValueKind

_FIXTURES = Path(__file__).resolve().parents[1] / "_fixtures" / "projection_violations"
_PROJECTION_MODULE = Path(__file__).resolve().parents[2] / "apx" / "core" / "projection.py"


# ── the Projection type is emitted only by the registry (AD-26/FR-31 ii) ──
def test_real_source_emits_projections_only_from_the_registry() -> None:
    assert projection_emitted_only_by_registry().ok


def test_an_out_of_registry_projection_construction_is_caught() -> None:
    result = projection_emitted_only_by_registry([_FIXTURES / "out_of_registry"])
    assert not result.ok and "outside the registry" in result.detail


def test_emission_check_fails_closed_on_unparseable(tmp_path: Path) -> None:
    (tmp_path / "broken.py").write_text("def oops(:\n", encoding="utf-8")
    assert not projection_emitted_only_by_registry([tmp_path]).ok


# ── every projector declares a content-free attestation (AD-26/FR-31 iii) ──
def test_real_registry_projectors_all_declare_a_valid_attestation() -> None:
    assert projectors_declare_attestation().ok


def test_a_text_derived_projector_with_no_floor_is_caught() -> None:
    bad = {"leaky": RegisteredProjector(
        "leaky", Attestation(kinds=(ValueKind.ATTESTED_AGGREGATE,)), lambda s: {})}
    result = projectors_declare_attestation(bad)
    assert not result.ok and "attestation" in result.detail


def test_a_projector_with_no_value_kind_is_caught() -> None:
    bad = {"empty": RegisteredProjector("empty", Attestation(kinds=()), lambda s: {})}
    assert not projectors_declare_attestation(bad).ok


# ── AC4: the AD-45 egress check lives in the uncuttable unit, not the projection unit ──
def test_egress_check_is_in_the_harness_and_not_in_the_projection_unit() -> None:
    # the no-fourth-egress-path check (AD-45) is registered in the harness, so it cannot be cut
    # without editing the harness itself...
    assert import_contracts.run in CHECKS
    # ...and it is owned by import_contracts, NOT the projection unit — so dropping the projection
    # unit (which the work breakdown predicts) leaves the egress guarantee intact (the AD-26→AD-45
    # split).
    assert import_contracts.run.__module__ == "apx.checks.import_contracts"
    source = _PROJECTION_MODULE.read_text(encoding="utf-8")
    assert "import_contracts" not in source and "importlinter" not in source
