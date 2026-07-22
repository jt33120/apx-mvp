"""Failure-path regression: the layering check is *live*, not decorative (AC5).

A guard that never fires is indistinguishable from no guard. These tests assert
both directions:

- the real ``apx`` tree PASSES the core→adapter contract (green on empty), and
- a deliberately violating fixture (``core_fake`` importing ``adapter_fake``)
  makes import-linter REPORT a violation and exit non-zero.

The second is the permanent form of "the check is live" — it keeps the AC5
demonstration honest after the one-off manual review (see README). It enforces
AD-4 via a static import-graph tool; it is not a runtime feature test.
"""

from __future__ import annotations

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


def test_layering_check_reports_a_violation_on_a_violating_fixture() -> None:
    exe = shutil.which("lint-imports")
    assert exe is not None, "lint-imports not on PATH — run `uv sync --group dev`"

    proc = subprocess.run(
        [exe, "--config", ".importlinter"],
        cwd=FIXTURE,
        capture_output=True,
        text=True,
    )

    # The contract MUST be broken: non-zero exit and the offending module named.
    assert proc.returncode != 0, (
        "layering contract did not fail on a deliberately violating fixture — "
        "the check is not live"
    )
    output = proc.stdout + proc.stderr
    assert "core_fake" in output, f"expected the violation to name core_fake:\n{output}"
