"""Deliberately violating fixture: a runtime module importing a hosted SDK.

Proves the egress deny-list (AD-45) fires. Never imported by any apx runtime
module; pytest does not collect tests/_fixtures.
"""
import boto3  # noqa: F401 — the forbidden hosted-provider edge, on purpose
