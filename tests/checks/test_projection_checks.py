"""The content-free projection structural checks (story 1.10, AD-26). Green on the real registry,
RED on the fixtures (the failure paths AC5 requires); and the AD-45 egress check is proven to live
in the uncuttable checks unit, not in this (predicted-to-be-dropped) projection unit (AC4).
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

from apx.checks import import_contracts
from apx.checks.projection import (
    projection_emitted_only_by_registry,
    projectors_declare_attestation,
    snapshot_fields_are_content_free,
)
from apx.checks.registry import CHECKS
from apx.core.projection import Attestation, RegisteredProjector, Snapshot, ValueKind

_FIXTURES = Path(__file__).resolve().parents[1] / "_fixtures" / "projection_violations"
_APX = Path(__file__).resolve().parents[2] / "apx"


# ── the Projection type is emitted only by the registry (AD-26/FR-31 ii) ──
def test_real_source_emits_projections_only_from_the_registry() -> None:
    assert projection_emitted_only_by_registry().ok


def test_a_bare_name_out_of_registry_construction_is_caught() -> None:
    result = projection_emitted_only_by_registry([_FIXTURES / "out_of_registry"])
    assert not result.ok and "outside the registry" in result.detail


def test_an_attribute_form_construction_is_caught() -> None:
    # `projection.Projection(...)` — a normal qualified-import style a bare-name check missed
    result = projection_emitted_only_by_registry([_FIXTURES / "attribute_form"])
    assert not result.ok and "outside the registry" in result.detail


def test_the_runtime_seal_refuses_direct_construction() -> None:
    # the static check is build-time defence; the runtime seal makes "built only by the registry"
    # literally true — alias/getattr/subclass/attribute all land in __post_init__ and raise.
    import pytest

    from apx.core import projection
    with pytest.raises(RuntimeError):
        projection.Projection("rogue", (), {"leaked": "x"})
    alias = projection.Projection
    with pytest.raises(RuntimeError):
        alias("rogue", (), {"leaked": "x"})


def test_emission_check_fails_closed_on_unparseable(tmp_path: Path) -> None:
    (tmp_path / "broken.py").write_text("def oops(:\n", encoding="utf-8")
    assert not projection_emitted_only_by_registry([tmp_path]).ok


# ── the projector input Snapshot is content-free (AD-26/FR-31) ──
def test_real_snapshot_is_content_free() -> None:
    assert snapshot_fields_are_content_free().ok


def test_widening_the_snapshot_with_an_unvetted_field_is_caught() -> None:
    @dataclasses.dataclass(frozen=True)
    class LeakySnapshot(Snapshot):
        matter_names: tuple[str, ...] = ()  # a name — un-vetted content, must fail the build

    result = snapshot_fields_are_content_free(LeakySnapshot)
    assert not result.ok and "matter_names" in result.detail


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
    # ...and NEITHER projection module (core + checks — both belong to the droppable unit) carries
    # the egress-check MACHINERY (the import-linter subprocess), so the egress guarantee does not
    # secretly ride on the projection unit. (checks/projection.py legitimately imports CheckResult
    # from import_contracts, so grep for the machinery — importlinter/lint-imports/subprocess.)
    egress_machinery = ("importlinter", "lint-imports", "subprocess")
    for module in ("core/projection.py", "checks/projection.py"):
        source = (_APX / module).read_text(encoding="utf-8")
        assert not any(marker in source for marker in egress_machinery), module
