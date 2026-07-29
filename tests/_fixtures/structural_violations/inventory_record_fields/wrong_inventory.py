"""A fixture for `inventory_record_fields_enumerated`: an Inventory record MISSING the `retired`
field (AD-38 requires exactly the six). The check must fire on this file."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Inventory:
    submitted_pieces: int
    in_corpus: int
    open_register_entries: int
    excluded_as_noise: int = 0
    unknown_cardinality_entries: int = 0
    # `retired` is deliberately MISSING — AD-38's six-field record is incomplete.
