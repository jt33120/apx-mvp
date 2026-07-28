"""The check registry — the single list the runner executes and the manifest checks against.

Extracted from ``__main__`` (story 1.12) so ``apx.checks.manifest`` can compare the manifest to the
LIVE registry by function identity without importing the runnable ``__main__`` module. Appending a
check here is one of the two edits a new structural property needs; the matching manifest row (and
its README line) is the other, and the meta-checks fail the build if the two ever drift apart.

Each entry names its pattern and the AD it enforces (AD-33). Later stories append; they do not
rewrite the runner. Green on the empty tree; a dropped or broken contract fails the build.
"""

from __future__ import annotations

from collections.abc import Callable

from apx.checks import (
    configuration,
    credential_storage,
    encryption,
    forward_looking,
    import_contracts,
    isolation_harness,
    manifest,
    payload_schema,
    projection,
    scope_admin,
    secrets,
    tenant_isolation,
)
from apx.checks.import_contracts import CheckResult

# The registry. Each entry names its pattern and the AD it enforces (AD-33). Kept in lock-step with
# `apx.checks.manifest.PROPERTY_MANIFEST` by the manifest meta-checks (a drift fails the build).
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
    # story 1.10 — the content-free projection primitive (AD-26/FR-31).
    projection.projection_emitted_only_by_registry,
    projection.snapshot_fields_are_content_free,
    projection.projectors_declare_attestation,
    # story 1.12 — the structural-properties harness: real-now checks (AD-16/AD-45/AD-24).
    isolation_harness.no_runtime_import_from_tests,
    isolation_harness.no_fixture_path_in_runtime,
    isolation_harness.no_egress_call_site_outside_adapters,
    isolation_harness.no_tenant_identifier_in_source,
    # story 2.2 — the resumable import job: the queue is sealed behind one submodule (AD-17).
    isolation_harness.no_queue_import_outside_submodule,
    # story 2.3 — extraction runs out-of-process & licence-isolated (AD-28).
    isolation_harness.no_extract_msg_import_outside_worker,
    isolation_harness.no_subprocess_call_outside_extraction,
    isolation_harness.no_stderr_none_in_extraction,
    # story 1.12 — forward-looking checks: live, vacuous now, fixture-proven (FR-9/10/14/…/23).
    forward_looking.embedder_has_one_implementation,
    forward_looking.destructive_index_ops_single_entry,
    forward_looking.no_post_filter_in_retrieval,
    forward_looking.no_natural_language_translation_key,
    forward_looking.no_hardcoded_locale,
    forward_looking.no_model_reported_confidence,
    forward_looking.no_banned_confidence_phrasing,
    # story 1.12 — the manifest meta-checks: the harness checks ITSELF (AD-33/FR-56).
    manifest.every_structural_property_has_a_registered_check,
    manifest.every_registered_check_is_in_the_manifest,
    manifest.verbs_are_not_conflated,
    manifest.floor_of_13_has_a_structural_check,
    manifest.manifest_matches_readme,
    manifest.readme_lists_every_property,
]
