"""A fixture for `unknown_cardinality_never_summed`: it adds `unknown_cardinality_entries` into a
total — exactly what AD-38 forbids ("an unknown cardinality is never summed into any total"). The
check must fire on this file."""

from __future__ import annotations


def a_dishonest_total(inv: object) -> int:
    # AD-38 violation: folding the unknown-cardinality count into a single number.
    return inv.in_corpus + inv.unknown_cardinality_entries
