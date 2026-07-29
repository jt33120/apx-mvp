"""A fixture for `unknown_cardinality_never_summed`: it folds the forbidden counts into a total via
the builtin `sum(...)` — the canonical way to total a list, which AD-38 forbids exactly as much as
`+` ("never summed into any total"). The check must fire on this file."""

from __future__ import annotations


def a_dishonest_total(inv: object) -> int:
    # AD-38 violation: collapsing the denominator into one int via sum().
    return sum([inv.in_corpus, inv.unknown_cardinality_entries, inv.excluded_as_noise])
