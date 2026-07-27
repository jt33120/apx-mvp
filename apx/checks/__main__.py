"""The structural-property checks harness (AD-33).

Run with ``python -m apx.checks``. Executes every registered check and exits
non-zero if **any** fails. The registry lives in ``apx.checks.registry`` (so the
manifest can compare against it without importing this runnable module); story
1.12 adds a MANIFEST (``apx.checks.manifest``) that makes "a property with no
check" a build failure, and the manifest's own meta-checks are registered here
like any other — the harness checks itself.

Green on the empty tree; a dropped or broken contract fails the build.
"""

from __future__ import annotations

import sys

from apx.checks.registry import CHECKS


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
