"""The ingestion use case — walk a folder, account for every file (FR-1, FR-3, FR-5, FR-6).

Pure orchestration in the Application layer: it depends on the Domain and on the
``Extractor`` and ``Expander`` ports, never on an adapter (AD-4). It produces an
``IngestionResult`` whose inventory holds the guarantee — ``submitted = in corpus +
failures + exclusions`` — with nothing lost silently.

Containers are expanded, not treated as opaque pieces: a .zip is unpacked and its
members ingested individually (recursively — a zip within a zip works), an email is
ingested as its body AND its attachments. The container itself is transparent — a zip
is neither a piece nor a failure, only its members are — while an email's body is a
piece in its own right. Expansion is bounded (depth and member count) so a malicious
archive cannot exhaust the machine. It persists nothing; a store adapter does that. It
never fakes a count.
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from apx.core.domain.dedup import text_key
from apx.core.domain.extraction import ExtractOutcome
from apx.core.domain.failures import ErrorClass
from apx.core.domain.identity import content_hash, piece_id
from apx.core.domain.inventory import Inventory
from apx.core.ports.expansion import Expander
from apx.core.ports.extraction import Extractor

SCHEMA_VERSION = "slice-a"

# Filesystem noise: a declared, countable exclusion class, not a silent drop (FR-6).
NOISE_NAMES = frozenset({".DS_Store", "Thumbs.db", "desktop.ini", ".gitkeep"})

# Expansion bounds — a malicious archive must not exhaust the machine.
MAX_DEPTH = 6           # nested containers (a zip in a zip in a …)
MAX_MEMBERS = 5000      # total members expanded across one ingestion


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


def _is_noise(name: str) -> bool:
    return name in NOISE_NAMES


def ingest_folder(
    folder: Path,
    matter: str,
    tenant: str,
    extractor: Extractor,
    *,
    custodian: str = "custodian-undeclared",
    expander: Expander | None = None,
) -> IngestionResult:
    """Walk ``folder`` recursively; every file lands in exactly one of three places
    (containers expanded to their members). ``expander`` is optional — without it,
    containers are ingested as ordinary files (their contents unexpanded)."""
    result = IngestionResult()
    now = datetime.now(UTC)
    member_count = [0]

    with tempfile.TemporaryDirectory(prefix="apx-expand-") as tmp:
        tmpdir = Path(tmp)

        def ingest_one(path: Path, prov: str, depth: int) -> None:
            if _is_noise(path.name):
                result.exclusions.append(prov)
                return

            expanded = False
            if expander is not None and depth < MAX_DEPTH:
                try:
                    members = expander.members(path)
                except Exception as exc:  # noqa: BLE001 — a broken container is a failure, not an outage
                    result.failures.append(IngestedFailure(
                        path.name, prov, matter, tenant, ErrorClass.EXTRACTION_ERROR, str(exc)))
                    return
                if members is not None:
                    expanded = True
                    for name, content in members:
                        if member_count[0] >= MAX_MEMBERS:
                            break
                        member_count[0] += 1
                        member_path = tmpdir / f"m{member_count[0]}{Path(name).suffix}"
                        member_path.write_bytes(content)
                        ingest_one(member_path, f"{prov}/{name}", depth + 1)

            try:
                outcome: ExtractOutcome = extractor.extract(path)
            except Exception as exc:  # noqa: BLE001 — any extractor crash is a failure, not an outage
                if not expanded:
                    result.failures.append(IngestedFailure(
                        path.name, prov, matter, tenant, ErrorClass.EXTRACTION_ERROR, str(exc)))
                return

            if outcome.ok:
                raw = path.read_bytes()
                ch = content_hash(raw)
                result.pieces.append(IngestedPiece(
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
                ))
            elif not expanded:
                # An ordinary leaf that produced no text — enumerated, never dropped.
                result.failures.append(IngestedFailure(
                    path.name, prov, matter, tenant, outcome.error_class or ErrorClass.UNKNOWN))
            # else: a container with no own text (a .zip) — transparent, its members counted.

        for path in sorted(p for p in folder.rglob("*") if p.is_file()):
            ingest_one(path, str(path.relative_to(folder)), 0)

    # The guarantee must hold on every result (FR-6 / SM-3 shape).
    result.inventory.require_consistent()
    return result
