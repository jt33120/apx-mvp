"""The structural-property checks harness (AD-33).

Run with ``python -m apx.checks``. Executes every registered check and exits
non-zero if **any** fails. Structured as a list so later stories (1.12) append
checks without editing the runner — the deny-list (AD-3), the egress check
(AD-45), the one-chunk-writer rule (AD-8), no-post-filter (AD-14),
no-secret-in-source (AD-51), and the rest land here, not elsewhere, so a cut
cannot drop them.

Registered: the import-contracts check (layering AD-4 + egress deny-list AD-45/AD-27).
Green on the empty tree; a dropped or broken contract fails the build.
"""

from __future__ import annotations

import sys
from collections.abc import Callable

from apx.checks import (
    configuration,
    credential_storage,
    encryption,
    import_contracts,
    payload_schema,
    scope_admin,
    secrets,
    tenant_isolation,
)
from apx.checks.import_contracts import CheckResult

# The registry. Each entry names its pattern and the AD it enforces (AD-33).
# Later stories append here; they do not rewrite the runner.
CHECKS: list[Callable[[], CheckResult]] = [
    import_contracts.run,
    # story 1.3 — the frozen payload schema (AD-9, AD-40, AD-7).
    payload_schema.one_chunk_writer,
    payload_schema.scope_arg_required,
    payload_schema.chunk_columns_enumerated,
    payload_schema.no_cascade_delete,
    # story 1.4 — tenant isolation at the boundary (AD-12).
    tenant_isolation.tenant_not_null_on_owned_tables,
    tenant_isolation.scoped_access_carries_tenant,
    tenant_isolation.identity_is_tenant_qualified,
    # story 1.5 — owned auth (AD-15).
    credential_storage.no_reversible_credential_storage,
    credential_storage.jwt_decode_pins_algorithms,
    # story 1.6 — grant-time authorisation (FR-49).
    scope_admin.scope_mutations_are_audited,
    # story 1.7 — encryption at rest & a fail-closed start (AD-31).
    encryption.sensitive_columns_are_encrypted,
    encryption.startup_gate_is_fail_closed,
    # story 1.8 — secret & key management (AD-47/FR-51).
    secrets.no_secret_in_source,
    secrets.no_secret_column_in_models,
    # story 1.9 — configuration-as-data & the provisioning surface (AD-24/AD-25).
    configuration.no_tenant_conditional_in_core,
    configuration.config_defaults_preserve_guarantees,
    configuration.documented_config_keys_exist,
    configuration.config_reference_is_complete,
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
