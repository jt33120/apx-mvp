"""Storage footprint and the pre-flight capacity check (story 1.11, AD-32).

The product **states** a *tenant*'s storage footprint at the *design target* rather than a firm
discovering it at 70 %, and a pre-flight check **refuses** an *import job* projected not to fit —
at submission, not mid-run. The per-*pièce* estimate is a **declared figure**, honest about being
an estimate to be calibrated against the 2.13 timed run; its presence and the refusal are the
guarantee. Pure core: stdlib only.
"""

from __future__ import annotations

from dataclasses import dataclass

# A declared per-*pièce* byte estimate — extracted text + provenance + audit + index overhead.
# An ESTIMATE, to be calibrated against the story-2.13 timed 5 000-*pièce* run; stated, not hidden.
BYTES_PER_PIECE = 40_000
DESIGN_TARGET_PIECES = 100_000
# Reserve headroom over the raw projection: WAL, temp, index churn and the next backup copy.
DEFAULT_SAFETY_MARGIN = 0.30


def _human(num_bytes: int) -> str:
    value = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(value) < 1024 or unit == "TB":
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} {unit}"
        value /= 1024
    return f"{value:.1f} TB"


@dataclass(frozen=True)
class Footprint:
    """A stated storage footprint for a *pièce* count."""

    piece_count: int
    bytes_per_piece: int
    total_bytes: int

    @property
    def human(self) -> str:
        return _human(self.total_bytes)


@dataclass(frozen=True)
class CapacityVerdict:
    """The pre-flight decision: does the projected *import job* fit the free space, with margin?"""

    projected_pieces: int
    projected_bytes: int      # the raw projection
    required_bytes: int       # projection + safety margin (what must actually be free)
    free_bytes: int
    fits: bool
    headroom_bytes: int       # free - required (negative when it does not fit)

    @property
    def reason(self) -> str:
        need, free = _human(self.required_bytes), _human(self.free_bytes)
        if self.fits:
            return (f"{self.projected_pieces} pièce(s) project to "
                    f"{_human(self.projected_bytes)} ({need} with margin); {free} free")
        return (f"import refused: {self.projected_pieces} pièce(s) need {need} but only {free} is "
                "free — free space or reduce the job (AD-32)")


def footprint(piece_count: int, *, bytes_per_piece: int = BYTES_PER_PIECE) -> Footprint:
    """The stated storage footprint for ``piece_count`` *pièces*."""
    n = max(0, piece_count)
    return Footprint(n, bytes_per_piece, n * bytes_per_piece)


def design_target_footprint() -> Footprint:
    """The stated footprint at the *design target* (100 000 *pièces*) — AD-32's stated figure."""
    return footprint(DESIGN_TARGET_PIECES)


def fits(
    free_bytes: int, projected_pieces: int, *, safety_margin: float = DEFAULT_SAFETY_MARGIN,
    bytes_per_piece: int = BYTES_PER_PIECE,
) -> CapacityVerdict:
    """The pre-flight capacity decision (AD-32): does ``projected_pieces`` fit ``free_bytes`` with a
    safety margin? Refuse before the *import job* starts, not at 70 %."""
    projected = footprint(projected_pieces, bytes_per_piece=bytes_per_piece).total_bytes
    required = int(projected * (1.0 + safety_margin))
    return CapacityVerdict(
        projected_pieces=max(0, projected_pieces), projected_bytes=projected,
        required_bytes=required, free_bytes=free_bytes, fits=free_bytes >= required,
        headroom_bytes=free_bytes - required)
