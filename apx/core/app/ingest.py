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


def enumerate_units(folder: Path) -> list[str]:
    """The submitted *units* of an import (AD-17): every file under ``folder``, folder-relative
    and sorted — the set frozen at enumeration. A container's members are expanded within their
    own unit at processing time (reusing the expander); they are not pre-enumerated here (that
    finer per-member granularity is Story 2.4)."""
    return sorted(str(p.relative_to(folder)) for p in folder.rglob("*") if p.is_file())


def _ingest_one(
    path: Path,
    prov: str,
    depth: int,
    *,
    result: IngestionResult,
    matter: str,
    tenant: str,
    custodian: str,
    extractor: Extractor,
    expander: Expander | None,
    now: datetime,
    tmpdir: Path,
    counter: list[int],
    max_bytes: int | None,
) -> None:
    """Route one file into exactly one of pieces / failures / exclusions (containers expanded to
    their members, recursively). Shared by ``ingest_folder`` (the whole-folder path) and
    ``ingest_one_file`` (the resumable per-unit worker path)."""
    if _is_noise(path.name):
        result.exclusions.append(prov)
        return

    # AD-17 memory bound: a single unit over its configured size is a `resource-exhausted`
    # register entry — never read whole into memory nor expanded — so one huge file cannot
    # exhaust the worker.
    if max_bytes is not None and path.is_file() and path.stat().st_size > max_bytes:
        result.failures.append(IngestedFailure(
            path.name, prov, matter, tenant, ErrorClass.RESOURCE_EXHAUSTED,
            f"{path.stat().st_size} bytes exceeds the configured per-unit bound"))
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
                if counter[0] >= MAX_MEMBERS:
                    break
                counter[0] += 1
                member_path = tmpdir / f"m{counter[0]}{Path(name).suffix}"
                member_path.write_bytes(content)
                _ingest_one(
                    member_path, f"{prov}/{name}", depth + 1, result=result, matter=matter,
                    tenant=tenant, custodian=custodian, extractor=extractor, expander=expander,
                    now=now, tmpdir=tmpdir, counter=counter, max_bytes=max_bytes)

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
            id=piece_id(tenant, ch, matter),
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


def ingest_one_file(
    path: Path,
    prov: str,
    matter: str,
    tenant: str,
    extractor: Extractor,
    *,
    custodian: str = "custodian-undeclared",
    expander: Expander | None = None,
    now: datetime | None = None,
    max_bytes: int | None = None,
) -> IngestionResult:
    """Ingest exactly one submitted file — a *unit* of work (AD-17). It lands as pieces, a
    failure, or a noise exclusion; a container expands atomically within this one result. The
    resumable worker (Story 2.2) commits one of these per unit."""
    result = IngestionResult()
    stamp = now or datetime.now(UTC)
    with tempfile.TemporaryDirectory(prefix="apx-expand-") as tmp:
        _ingest_one(
            path, prov, 0, result=result, matter=matter, tenant=tenant, custodian=custodian,
            extractor=extractor, expander=expander, now=stamp, tmpdir=Path(tmp), counter=[0],
            max_bytes=max_bytes)
    return result


def ingest_folder(
    folder: Path,
    matter: str,
    tenant: str,
    extractor: Extractor,
    *,
    custodian: str = "custodian-undeclared",
    expander: Expander | None = None,
    max_bytes: int | None = None,
) -> IngestionResult:
    """Walk ``folder`` recursively; every file lands in exactly one of three places (containers
    expanded to their members). The synchronous whole-folder path (Story 2.1 and tests); the
    resumable worker (Story 2.2) drives ``ingest_one_file`` per unit instead. ``expander`` is
    optional — without it, containers are ingested as ordinary files (contents unexpanded)."""
    result = IngestionResult()
    now = datetime.now(UTC)
    counter = [0]
    with tempfile.TemporaryDirectory(prefix="apx-expand-") as tmp:
        tmpdir = Path(tmp)
        for path in sorted(p for p in folder.rglob("*") if p.is_file()):
            _ingest_one(
                path, str(path.relative_to(folder)), 0, result=result, matter=matter,
                tenant=tenant, custodian=custodian, extractor=extractor, expander=expander,
                now=now, tmpdir=tmpdir, counter=counter, max_bytes=max_bytes)
    # The guarantee must hold on every result (FR-6 / SM-3 shape).
    result.inventory.require_consistent()
    return result
