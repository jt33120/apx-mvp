"""A legitimate defensive guard: comparing a tenant to the EMPTY string (a sentinel for
"unassigned") is not a branch on a specific firm's identity and must NOT be flagged (the MED-5
false positive the check must avoid). AST-scanned only, never imported."""

from __future__ import annotations


def is_assigned(row):
    return row.tenant != ""  # a sentinel/empty check, not per-tenant behaviour
