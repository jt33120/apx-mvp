"""The import-contract guards are live, not decorative (AD-4, AD-45, AD-27).

Covers layering (core→adapter) and the egress deny-list (hosted SDKs), and the
per-contract *floor*: a required contract that is dropped or broken must fail,
never pass green. These are static import-graph checks, not runtime tests.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

FIXTURES = Path(__file__).resolve().parents[1] / "_fixtures"


def test_all_required_contracts_pass_on_the_real_tree() -> None:
    from apx.checks import import_contracts

    result = import_contracts.run()
    assert result.ok, f"required import contracts should all hold:\n{result.detail}"


def test_check_is_cwd_independent(tmp_path: Path) -> None:
    from apx.checks import import_contracts

    cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        result = import_contracts.run()
    finally:
        os.chdir(cwd)
    assert result.ok, f"the check must be cwd-independent, got:\n{result.detail}"


def test_a_dropped_required_contract_fails(monkeypatch) -> None:
    """The floor: if a REQUIRED contract is absent from the run, the check fails."""
    from apx.checks import import_contracts

    monkeypatch.setattr(
        import_contracts,
        "REQUIRED_CONTRACTS",
        import_contracts.REQUIRED_CONTRACTS | {"a contract that does not exist"},
    )
    result = import_contracts.run()
    assert not result.ok, "a missing required contract must fail the check"
    assert "missing" in result.detail.lower()


def _broken(fixture: str, needle: str) -> None:
    exe = shutil.which("lint-imports")
    assert exe is not None, "lint-imports not on PATH — run `uv sync --group dev`"
    proc = subprocess.run(
        [exe, "--config", ".importlinter"],
        cwd=FIXTURES / fixture,
        capture_output=True,
        text=True,
    )
    output = proc.stdout + proc.stderr
    assert proc.returncode != 0, f"the contract did not fail — the guard is dead:\n{output}"
    assert "BROKEN" in output.upper(), f"expected a BROKEN contract (it evaluated):\n{output}"
    assert needle in output, f"expected the violation to name {needle}:\n{output}"


def test_layering_guard_reports_broken_on_a_core_to_adapter_import() -> None:
    _broken("layering_violation", "core_fake")


def test_egress_guard_reports_broken_on_a_hosted_sdk_import() -> None:
    _broken("egress_violation", "bad_egress")
