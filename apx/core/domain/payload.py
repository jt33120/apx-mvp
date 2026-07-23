"""The payload record — the complete, versioned provenance a *chunk* is written with
(FR-8, AD-9, AD-40). Pure domain: no DB, no adapter.

This is the increment's one irreversible decision made concrete. Every indexed *chunk*
carries a full provenance record, and the record cannot be written incomplete: the
writer validates a ``PayloadRecord`` at the boundary and refuses — loudly, with a typed
error — anything missing a mandatory field or breaking the date invariant. Adding a
mandatory field *later* means re-indexing every installed site blind, so the field set
is fixed here and made right once.

Two fields the record deliberately does **not** carry (AD-9, AD-13, AD-40): *RBAC scope*
and any *scope* alias. Scope is not provenance that travels on the row — it is a
write-time authorisation resolved from the authoritative ``matter_scope`` at query time,
so a re-scope takes effect at the next read with nothing to propagate. It reaches the
writer as a separate required argument, never as a field here. *Custodian* is provenance
and is carried on the *pièce*, never on the *chunk* row. (Today the *pièce* holds a legacy
scalar ``custodian`` column from the pre-BMAD build; AD-9's ``CUSTODIAN_LINK`` *set* — a
custodian set unioned across imports, and no column on ``piece`` either — is owed to a later
story. 1.3 fixes only the *chunk* dimension: custodian is never a chunk column.)
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import date, datetime

_DETERMINED = "determined"
_UNDETERMINED = "undetermined"
DATE_STATUSES = frozenset({_DETERMINED, _UNDETERMINED})


class PayloadError(Exception):
    """A payload could not be written as given. Carries a human reason; the writer
    turns it into a *failure-register*-shaped rejection (the register table is 2.6)."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class IncompletePayload(PayloadError):
    """A mandatory field is missing, empty, or the date invariant is broken. The
    *chunk* is rejected at the boundary — never written with a default (FR-8)."""


# The mandatory string fields — each must be present and non-empty. `rbac_scope` is
# deliberately absent (a write-time argument, never a field). `position` (int) and the
# date pair are validated separately by their own invariants.
_MANDATORY_STRINGS = (
    "tenant",
    "matter",
    "source_piece_id",
    "content_hash",
    "provenance_path",
    "custodian",
    "extraction_method",
    "extractor_version",
    "schema_version",
    "chunking_config_version",
    "full_text",
    "text_identity",
    "text_version",
)


@dataclass(frozen=True)
class PayloadRecord:
    """The complete provenance one *chunk* write requires (FR-8). No ``rbac_scope``
    field, by design (AD-9/AD-13/AD-40). ``validate()`` is the boundary gate; the writer
    calls it and refuses an invalid record rather than defaulting anything."""

    tenant: str
    matter: str
    source_piece_id: str
    content_hash: str
    provenance_path: str
    custodian: str
    extraction_method: str
    extractor_version: str
    schema_version: str
    chunking_config_version: str
    ingestion_timestamp: datetime
    position: int
    full_text: str
    text_identity: str
    text_version: str
    piece_date: date | None
    piece_date_status: str

    def validate(self) -> PayloadRecord:
        """Return self if the record is complete and consistent; else raise
        ``IncompletePayload``. Enforces: every mandatory string non-empty; a
        non-negative ``position``; a real ``ingestion_timestamp``; and the date
        invariant — ``piece_date`` is set iff the status is ``determined`` and the
        status is one of the two permitted values (AC1)."""
        for name in _MANDATORY_STRINGS:
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise IncompletePayload(f"mandatory field '{name}' is missing or empty")
        if not isinstance(self.ingestion_timestamp, datetime):
            raise IncompletePayload("ingestion_timestamp is required")
        bad_position = (
            not isinstance(self.position, int)
            or isinstance(self.position, bool)
            or self.position < 0
        )
        if bad_position:
            raise IncompletePayload("position must be a non-negative integer")
        if self.piece_date_status not in DATE_STATUSES:
            raise IncompletePayload(
                f"piece_date_status must be one of {sorted(DATE_STATUSES)}, "
                f"got {self.piece_date_status!r}"
            )
        # a borne date is a `date`, never a string and never a `datetime` (which is a date
        # subclass): the column is DATE, and a smuggled datetime/str would round-trip wrong.
        if self.piece_date is not None and (
            not isinstance(self.piece_date, date) or isinstance(self.piece_date, datetime)
        ):
            raise IncompletePayload("piece_date must be a date (not a datetime, not a string)")
        determined = self.piece_date is not None
        if determined != (self.piece_date_status == _DETERMINED):
            raise IncompletePayload(
                "piece_date must be set iff piece_date_status is 'determined' "
                "(a date and an 'undetermined' status, or a status of 'determined' with "
                "no date, is never written)"
            )
        return self


def field_names() -> tuple[str, ...]:
    """The payload's field names, in declaration order — used by tests to prove the set
    is exactly what was frozen (no silent addition of a mandatory field)."""
    return tuple(f.name for f in fields(PayloadRecord))
