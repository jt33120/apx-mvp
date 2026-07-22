"""Deliberately violating fixture: a fake 'core' that imports a fake 'adapter'.

This is the failure-path proof for AC5 — it MUST make the layering contract
report a violation. It is never imported by any runtime module under apx/
(AD-16); pytest is configured not to collect tests/_fixtures.
"""
from adapter_fake import marker  # noqa: F401  — the forbidden edge, on purpose
