"""The *override* — what makes an act one, what it costs, and how the cost reaches the record
(Story 5.6, FR-25 / AD-37 / AD-22).

FR-25 is one sentence with three grounds: contradicting a machine assertion made with stated
confidence, taking a *failure register* entry out of ``open`` without successful *ingestion*, or
bypassing a system guard. An act on any of those grounds **cannot be committed without a free-text
reason**, stored verbatim, attributed and timestamped.

Three things live here, and all three exist because the alternative is three copies.

**The grounds.** An override names *which* ground it rests on. Not decoration: "is this an
override?" is a judgement someone made once, and an act that carries the answer without carrying
the reasoning invites the next act to be classified by whether its verb reads like one. The
catalogue (:mod:`apx.core.domain.audit`) imports these; this module imports nothing from it, so the
rule stays independent of the list it is applied to.

**One validator.** "The reason is mandatory" was implemented twice before this module existed —
once for *pins* (a typed error) and once for the truncation override (a bare ``ValueError``) — and
a third was about to be written for the register. Two implementations of one rule drift, and the
one that drifts is the one that stops refusing. :func:`validate_override_reason` is the only place
the word *mandatory* means anything, and a structural check (``override-reason-one-validator``)
fails the build if a write path validates anywhere else.

**One renderer, and its inverse.** FR-25 says *verbatim*. An audit ``detail`` is a flat string
carrying several fields, so a reason containing ``reason=``, a newline or the separator itself must
still come back out unchanged. :func:`override_detail` puts the reason **last**, behind a separator
that cannot occur before it, and :func:`reason_from_detail` returns everything after it — so the
round trip is exact for **any** reason, including one written to break it.

Pure core: stdlib only, no adapter import, no I/O.
"""

from __future__ import annotations

# ── FR-25's three grounds ─────────────────────────────────────────────────────────────────────

#: Contradicting a machine assertion made with stated confidence — a *pin* moving one *pièce*
#: across **the line** against the ranked order, and anything later that overrules a derived
#: figure the tool published with a confidence beside it.
GROUND_CONTRADICTS_MACHINE = "contradicts-a-machine-assertion"

#: Taking a *failure register* entry out of ``open`` without successful *ingestion* (FR-5). The
#: document never entered the *corpus* and now never will; the count that says so stops saying it.
GROUND_REGISTER_EXIT = "register-exit-without-ingestion"

#: Bypassing a system guard — clearing the truncation marker that names an incomplete *audit
#: record* on the face of every export (AD-35), and any later guard whose whole purpose is to stay
#: in the way.
GROUND_GUARD_BYPASS = "bypasses-a-system-guard"

#: The three, and only the three. A fourth ground is a change to FR-25, not to a call site.
GROUNDS: tuple[str, ...] = (
    GROUND_CONTRADICTS_MACHINE,
    GROUND_REGISTER_EXIT,
    GROUND_GUARD_BYPASS,
)

#: How each ground says itself to the lawyer reading the trail (FR-25 — an *override* is an
#: arguable decision, so the surface must be able to say what was overridden without a glossary).
GROUND_FR: dict[str, str] = {
    GROUND_CONTRADICTS_MACHINE: "contredit une assertion de l'outil",
    GROUND_REGISTER_EXIT: "sort une entrée du registre sans ingestion réussie",
    GROUND_GUARD_BYPASS: "contourne une garde du système",
}


class UnknownOverrideGround(ValueError):
    """A ground FR-25 does not name. Refused where an act is catalogued, so a typo cannot invent a
    fourth ground that no surface, count or export knows how to read."""


def check_ground(ground: str) -> str:
    """The ground, or raise :class:`UnknownOverrideGround`."""
    if ground not in GROUNDS:
        raise UnknownOverrideGround(f"not one of FR-25's three grounds: {ground!r}")
    return ground


def ground_label_fr(ground: str) -> str:
    """The French sentence for a ground, or the ground itself if it is not one of the three (a
    reader is never shown nothing; an unknown ground shows as itself rather than as blank)."""
    return GROUND_FR.get(ground, ground)


# ── the mandatory reason ──────────────────────────────────────────────────────────────────────

class MissingOverrideReason(ValueError):
    """An *override* was attempted without a reason (FR-25). **Nothing is written** — not the act,
    not the audit entry. Subclasses ``ValueError`` because the shipped paths raised that before
    this type existed and every caller catching it must keep working; the type exists so a caller
    that wants to tell "you owe me a sentence" from "that argument is nonsense" now can."""


def validate_override_reason(reason: str | None) -> str:
    """The reason, or raise :class:`MissingOverrideReason`. The **only** implementation of FR-25's
    *mandatory*.

    Blank and whitespace-only are refused, and nothing else is. The PRD's assumption register
    (A-14) contemplates a minimum meaningful length; it is deliberately **not** enforced here. A
    length floor is trivially satisfied by a dozen identical characters, so it would buy nothing
    real while making the refusal about typing rather than about deciding — and a user who has
    learned that the field wants *volume* writes volume. FR-25's own counter-metric (SM-C2) watches
    reason quality as a trend instead, which is the honest instrument for it.

    The reason is returned **unstripped**: FR-25 says *verbatim*, and the record keeps what was
    written, not a tidied version of it."""
    if reason is None or not reason.strip():
        raise MissingOverrideReason(
            "an override requires a one-line reason (FR-25) — nothing was written")
    return reason


# ── the reason, verbatim, in the record ───────────────────────────────────────────────────────

#: The separator between an override entry's structured fields and its verbatim reason. The
#: extractor is exact because the reason is always last and the FIRST occurrence opens it: a reason
#: containing this very string round-trips unchanged (see :func:`reason_from_detail`).
REASON_MARK = "reason="


class ReasonMarkInAField(ValueError):
    """A structured field whose key or value contains :data:`REASON_MARK`. Refused rather than
    rendered: the extractor finds the FIRST mark, so a field carrying one ahead of the reason would
    make :func:`reason_from_detail` return that field's tail instead of what the lawyer wrote — and
    it would look like a reason, be countable as one, and read as one.

    This is reachable from client data, not only from a typo: *matter* names are chosen by the
    firm. Refusing loudly beats escaping, because an escaped reason is no longer verbatim."""


def override_detail(reason: str, **fields: object) -> str:
    """One override entry's ``detail``: its structured fields, then the reason **verbatim, last**.

    Fields render as ``key=value`` in the order given, space-separated, ahead of the reason. Keep
    them to code-defined identifiers, enums, integers and identity hashes: anything a person can
    name — a *matter*, a filename — belongs in its own column, and passing one here raises
    :class:`ReasonMarkInAField` the moment it happens to contain the mark.

    The reason is never escaped, quoted or truncated — FR-25 says *verbatim*, and an audit record
    that tidies what a lawyer wrote is not quoting her. The consequence is that ``detail`` is not a
    parseable field list past the mark, and that is deliberate: :func:`reason_from_detail` is the
    one reader.

    A blank reason is refused here too, not only at the call site — the renderer is the last place
    the record could still acquire an empty one."""
    validate_override_reason(reason)
    for key, value in fields.items():
        if REASON_MARK in key or REASON_MARK in str(value):
            raise ReasonMarkInAField(
                f"field {key!r} carries {REASON_MARK!r}, which would be read as the reason")
    head = " ".join(f"{k}={v}" for k, v in fields.items())
    return f"{head} {REASON_MARK}{reason}" if head else f"{REASON_MARK}{reason}"


def reason_from_detail(detail: str) -> str | None:
    """The verbatim reason inside an override's ``detail``, or ``None`` when there is none.

    Reads from the **left**: the FIRST :data:`REASON_MARK` opens the reason, and everything after
    it — separators, newlines, further ``reason=`` occurrences and all — is the reason. Taking the
    LAST occurrence instead would silently swallow the leading part of any reason that contains the
    mark, and :func:`override_detail` guarantees the structured fields ahead of it never do: a
    field's key is a code-defined identifier and its value is an identifier, an integer or a
    truncated hash, so the first occurrence is always the renderer's own.

    ``None`` — rather than ``""`` — where the mark is absent, so "this entry carries no reason"
    stays distinguishable from "this entry's reason is empty", which cannot happen and whose
    appearance would be a defect worth seeing rather than smoothing over."""
    at = detail.find(REASON_MARK)
    if at < 0:
        return None
    return detail[at + len(REASON_MARK):]
