"""Failure-path regression: the layering check is *live*, not decorative (AC5).

A guard that never fires is indistinguishable from no guard. These tests assert:

- the real ``apx`` tree PASSES the core→adapter contract (green on empty);
- ``layering.run()`` is **cwd-independent** — it gives the same verdict from a
  subdirectory (it must not cry wolf off-root);
- a deliberately violating fixture makes import-linter report a **BROKEN**
  contract (not merely a non-zero exit — a config error would also be non-zero;
  asserting "BROKEN" proves the contract actually evaluated and failed).

It enforces AD-4 via a static import-graph tool; it is not a runtime feature test.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

FIXTURE = Path(__file__).resolve().parents[1] / "_fixtures" / "layering_violation"


def test_layering_check_passes_on_the_real_tree() -> None:
    from apx.checks import layering

    result = layering.run()
    assert result.ok, (
        f"core→adapter layering contract should pass on the real tree:\n{result.detail}"
    )


def test_layering_check_is_cwd_independent(tmp_path: Path) -> None:
    """Run from an unrelated directory; the verdict must still be a real PASS."""
    from apx.checks import layering

    cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        result = layering.run()
    finally:
        os.chdir(cwd)
    assert result.ok, f"layering.run() must be cwd-independent, got:\n{result.detail}"


def test_layering_check_reports_a_broken_contract_on_a_violating_fixture() -> None:
    exe = shutil.which("lint-imports")
    assert exe is not None, "lint-imports not on PATH — run `uv sync --group dev`"

    proc = subprocess.run(
        [exe, "--config", ".importlinter"],
        cwd=FIXTURE,
        capture_output=True,
        text=True,
    )
    output = proc.stdout + proc.stderr

    # Non-zero AND a BROKEN contract — the contract evaluated and failed as a
    # contract, not as a config/collection error (a "package not found" error is
    # also non-zero and would name core_fake, but never prints BROKEN).
    assert proc.returncode != 0, f"the contract did not fail — the check is not live:\n{output}"
    assert "BROKEN" in output.upper(), (
        f"expected a BROKEN contract (proving it evaluated), got:\n{output}"
    )
    assert "core_fake" in output, f"expected the violation to name core_fake:\n{output}"
