"""The structural-property checks harness (AD-33).

Run with ``python -m apx.checks``. Executes every registered check and exits
non-zero if **any** fails. Structured as a list so later stories (1.12) append
checks without editing the runner — the deny-list (AD-3), the egress check
(AD-45), the one-chunk-writer rule (AD-8), no-post-filter (AD-14),
no-secret-in-source (AD-51), and the rest land here, not elsewhere, so a cut
cannot drop them.

Story 1.1 registers exactly one check: the layering rule (core imports no
adapter, AD-4), green on the empty tree.
"""

from __future__ import annotations

import sys
from collections.abc import Callable

from apx.checks import layering
from apx.checks.layering import CheckResult

# The registry. Each entry names its pattern and the AD it enforces (AD-33).
# Later stories append here; they do not rewrite the runner.
CHECKS: list[Callable[[], CheckResult]] = [
    layering.run,
]


def main() -> int:
    failures = 0
    for check in CHECKS:
        result = check()
        status = "PASS" if result.ok else "FAIL"
        print(f"[{status}] {result.name} ({result.ad})")
        if not result.ok:
            failures += 1
            if result.detail:
                print(result.detail)
    if failures:
        print(f"\n{failures} structural-property check(s) failed.", file=sys.stderr)
        return 1
    print(f"\nAll {len(CHECKS)} structural-property check(s) passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
