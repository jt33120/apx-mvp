"""The ingestion use case — walk a folder, account for every file (FR-1, FR-3, FR-5, FR-6).

Pure orchestration in the Application layer: it depends on the Domain and on the
``Extractor`` port, never on an adapter (AD-4). It produces an ``IngestionResult``
whose inventory holds the guarantee — ``submitted = in corpus + failures +
exclusions`` — with nothing lost silently. It persists nothing; a store adapter
does that. This slice does less than FR-1/3/5/6 (no idempotency, no container
expansion, no RBAC, no audit); those thicken it in their own stories. It never
fakes a count.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from apx.core.domain.dedup import text_key
from apx.core.domain.extraction import ExtractOutcome
from apx.core.domain.failures import ErrorClass
from apx.core.domain.identity import content_hash, piece_id
from apx.core.domain.inventory import Inventory
from apx.core.ports.extraction import Extractor

SCHEMA_VERSION = "slice-a"

# Filesystem noise: a declared, countable exclusion class, not a silent drop (FR-6).
NOISE_NAMES = frozenset({".DS_Store", "Thumbs.db", "desktop.ini", ".gitkeep"})


@dataclass(frozen=True)
class IngestedPiece:
    id: str
    matter: str
    tenant: str
    content_hash: str  # hash of raw bytes — exact-file identity (AD-40)
    text_key: str      # hash of normalised text — the near-duplicate key (judgment cascade)
    provenance_path: str
    custodian: str
    extraction_method: str
    extractor_version: str
    schema_version: str
    ingestion_timestamp: datetime
    full_text: str
    text_version: str


@dataclass(frozen=True)
class IngestedFailure:
    filename: str
    submitted_path: str
    matter: str
    tenant: str
    error_class: ErrorClass
    detail: str | None = None


@dataclass(frozen=True)
class IngestionResult:
    pieces: list[IngestedPiece] = field(default_factory=list)
    failures: list[IngestedFailure] = field(default_factory=list)
    exclusions: list[str] = field(default_factory=list)  # provenance paths excluded as noise

    @property
    def inventory(self) -> Inventory:
        submitted = len(self.pieces) + len(self.failures) + len(self.exclusions)
        return Inventory(
            submitted=submitted,
            in_corpus=len(self.pieces),
            failures=len(self.failures),
            exclusions=len(self.exclusions),
        )


def _is_noise(path: Path) -> bool:
    return path.name in NOISE_NAMES


def ingest_folder(
    folder: Path,
    matter: str,
    tenant: str,
    extractor: Extractor,
    *,
    custodian: str = "custodian-undeclared",
) -> IngestionResult:
    """Walk ``folder`` recursively; every file lands in exactly one of three places."""
    result = IngestionResult()
    now = datetime.now(UTC)
    for path in sorted(p for p in folder.rglob("*") if p.is_file()):
        prov = str(path.relative_to(folder))
        if _is_noise(path):
            result.exclusions.append(prov)
            continue
        try:
            outcome: ExtractOutcome = extractor.extract(path)
        except Exception as exc:  # noqa: BLE001 — any extractor crash is a failure, not an outage
            result.failures.append(
                IngestedFailure(
                    path.name, prov, matter, tenant, ErrorClass.EXTRACTION_ERROR, str(exc)
                )
            )
            continue
        if not outcome.ok:
            result.failures.append(
                IngestedFailure(
                    path.name, prov, matter, tenant,
                    outcome.error_class or ErrorClass.UNKNOWN,
                )
            )
            continue
        raw = path.read_bytes()
        ch = content_hash(raw)
        result.pieces.append(
            IngestedPiece(
                id=piece_id(ch, matter),
                matter=matter,
                tenant=tenant,
                content_hash=ch,
                text_key=text_key(outcome.text),
                provenance_path=prov,
                custodian=custodian,
                extraction_method=outcome.method,
                extractor_version=outcome.version,
                schema_version=SCHEMA_VERSION,
                ingestion_timestamp=now,
                full_text=outcome.text,
                text_version=outcome.version,
            )
        )
    # The guarantee must hold on every result (FR-6 / SM-3 shape).
    result.inventory.require_consistent()
    return result
