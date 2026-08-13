"""The *audit record*'s identity: its chains, its catalogue of recordable acts, and the versioned
recipe for the value each entry chains over (FR-24, FR-53, AD-43, AD-22).

Three things live here, and they live in the Domain because none of them is a storage concern.

**The chain identity (AD-43).** A chain is ``(tenant, chain_scope)``, where ``chain_scope`` is a
*matter* identifier or :data:`TENANT_CHAIN` for the matterless *tenant* chain that carries
provisioning, scope grants, configuration changes and security events. FR-24's *"every entry carries
a matter"* is amended by AD-43 to *"every entry carries a matter, **or names the tenant chain
explicitly**"* — hence a column of its own rather than a ``matter IS NULL`` convention, so that an
act belonging to no *matter* is never confused with an act whose *matter* was dropped on the way in.

The scope is not a filing preference. FR-53 requires a gap, a reordering or a truncation to be
detectable **by a reader holding only the export**, and an export is per *matter* (FR-26). Under one
chain per *tenant*, a *matter*'s export has a hole wherever a sibling *matter* wrote in between, and
its links cannot be recomputed at all — each is taken over an entry the reader is not entitled to
see (FR-24 scopes the read by *RBAC scope*). The reader would find tampering on an untampered
record, every time.

**The catalogue.** FR-24 enumerates what must be recorded. A list in a requirements document is not
a mechanism, so the enumeration lives here as data: every verb the runtime writes, the FR-24 class
it discharges, which chain it belongs on and whether a human or a system component performs it. A
verb absent from the catalogue cannot be written (the store refuses it) and fails the build (a
structural check); a class the catalogue claims to cover with no verb behind it fails the build; a
class not yet built is declared PENDING **with the story that owns it**, on the fitness driver's
precedent — a named hole rather than an invisible one.

**Verbs are historical data and are never renamed.** Entries written under a verb keep it forever,
and FR-24 requires acts to be countable and filterable; renaming ``open-piece`` to ``open_piece``
would silently orphan every entry already written under the old spelling. The catalogue therefore
carries both spellings the eleven prior stories introduced (kebab and snake), and a test freezes
them. Consistency is not worth an unreadable past.

Pure core: stdlib only, no adapter import, no I/O.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from apx.core.domain.override import (
    GROUND_CONTRADICTS_MACHINE,
    GROUND_GUARD_BYPASS,
    GROUND_REGISTER_EXIT,
    check_ground,
)

# ── the chain identity (AD-43) ────────────────────────────────────────────────────────────────

#: The ``chain_scope`` of the matterless per-*tenant* chain. Empty rather than ``None`` so the
#: column is NOT NULL and the primary key of the head row needs no COALESCE.
TENANT_CHAIN = ""

CHAIN_MATTER = "matter"
CHAIN_TENANT = "tenant"


def chain_scope_of(matter: str | None) -> str:
    """The ``chain_scope`` an entry belongs to: its *matter*, or the *tenant* chain."""
    return matter if matter else TENANT_CHAIN


def chain_label_fr(chain_scope: str) -> str:
    """How a chain names itself to a reader (FR-24: an entry names its chain explicitly)."""
    return f"affaire « {chain_scope} »" if chain_scope else "chaîne du cabinet"


# ── the actor (FR-24: system-initiated entries name the system component) ──────────────────────

SYSTEM_ACTOR_PREFIX = "system:"

#: The closed set of system components that may appear as an actor. Closed on purpose: FR-24 says
#: system-initiated entries "name the system component as actor rather than attributing them to a
#: user", and a free-text system actor is how ``"unknown"`` came back under a new name.
SYSTEM_COMPONENTS: frozenset[str] = frozenset({
    "auth",            # failed logins, lockouts, MFA refusals (FR-48)
    "import-worker",   # the resumable ingestion worker (AD-17)
    "cascade",         # the judgment cascade
    "ranker",          # a ranking run
    "backup",          # scheduled backup / restore machinery
    "provisioning",    # tenant / first-administrator provisioning, which has no human author
    "startup",         # start-up gates: encryption, head journal, collation
    "config",          # a configuration value set outside the interactive surface (AD-25)
    "maintenance",     # key rotation and other operator maintenance (AD-31)
    "backfill",        # a migration that recovers rows whose human author is unrecoverable
})


class UnknownActor(ValueError):
    """An actor that is neither a person's display name nor a catalogued system component."""


def system_actor(component: str) -> str:
    """The audit actor for a system-initiated act. Raises on an uncatalogued component."""
    if component not in SYSTEM_COMPONENTS:
        raise UnknownActor(f"uncatalogued system component: {component!r}")
    return f"{SYSTEM_ACTOR_PREFIX}{component}"


def is_system_actor(actor: str) -> bool:
    return actor.startswith(SYSTEM_ACTOR_PREFIX)


#: Never an actor. An entry attributed to nobody is worse than no entry at all: it is countable,
#: filterable and looks defensible. ``SqlStore.save`` defaulted to this for eleven stories.
FORBIDDEN_ACTORS: frozenset[str] = frozenset({"", "unknown", "system", "anonymous", "n/a"})


def check_actor(actor: str) -> str:
    """The actor, or raise. A system actor must name a catalogued component."""
    if actor.strip().lower() in FORBIDDEN_ACTORS:
        raise UnknownActor(f"an audit entry may not be attributed to {actor!r}")
    if is_system_actor(actor):
        component = actor[len(SYSTEM_ACTOR_PREFIX):]
        if component not in SYSTEM_COMPONENTS:
            raise UnknownActor(f"uncatalogued system component: {component!r}")
    return actor


# ── the FR-24 act classes ─────────────────────────────────────────────────────────────────────

CLASS_VALIDATION = "validation_act"
CLASS_CASE_THEORY = "case_theory"
CLASS_VERSION_IDENTITY = "version_identity"
CLASS_VALUE_MODIFIED = "value_modified"
CLASS_VALUE_ACCEPTED = "value_accepted"
CLASS_LINE_POSITION = "line_position"
CLASS_PIN = "pin"
CLASS_SAMPLING_RUN = "sampling_run"
CLASS_OVERRIDE = "override"
CLASS_RETRIEVAL = "retrieval"
CLASS_IMPORT_JOB = "import_job"
CLASS_CONFIG_CHANGE = "config_change"
CLASS_SCOPE_GRANT = "scope_grant"

#: FR-24's enumeration, as classes. "Modified versus accepted as-is" is two classes, not one,
#: because FR-24 §614 makes them asymmetric: a modification is an edit, while "accepted" exists
#: ONLY where a *validation act* occurred over the value — never by default, elapsed time or a
#: screen visit. Folding them together is how "accepted" acquires a default.
FR24_CLASSES: tuple[str, ...] = (
    CLASS_VALIDATION,
    CLASS_CASE_THEORY,
    CLASS_VERSION_IDENTITY,
    CLASS_VALUE_MODIFIED,
    CLASS_VALUE_ACCEPTED,
    CLASS_LINE_POSITION,
    CLASS_PIN,
    CLASS_SAMPLING_RUN,
    CLASS_OVERRIDE,
    CLASS_RETRIEVAL,
    CLASS_IMPORT_JOB,
    CLASS_CONFIG_CHANGE,
    CLASS_SCOPE_GRANT,
)

#: Classes the runtime carries outside FR-24's enumeration: the chain's own lifecycle (AD-43's
#: anchoring), and security events (FR-48). Catalogued so that no verb is ever classless.
CLASS_CHAIN_LIFECYCLE = "chain_lifecycle"
CLASS_SECURITY_EVENT = "security_event"

#: An FR-24 class with no writer yet, and the story that owns it. The fitness driver's precedent:
#: a stage is ASSERTED with a check or PENDING with nothing, and never faked in between. A class
#: here fails the build if a verb claims it (it is not pending if something writes it) and fails
#: the build if its story number is absent.
PENDING_CLASSES: dict[str, str] = {
    CLASS_VALIDATION: "5.8",     # the validation act
    CLASS_VALUE_ACCEPTED: "5.8",  # "accepted as-is" exists only where a validation act occurred
}


# ── the catalogue ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class RecordableAct:
    """One catalogued act: the verb stored on the entry, the FR-24 class it discharges, the chain
    it belongs on, whether a person or a system component performs it, and — when FR-25 applies —
    **which of its three grounds** makes the act an *override*.

    The override is a SECOND axis, not a class. An act has exactly one FR-24 class, and a *pin* is
    a pin (FR-24 enumerates "every *pin*") **and** an override (FR-25: it contradicts a ranked
    order the tool produced with a stated confidence). Folding the two together forces a choice
    between discharging one requirement and discharging the other, and the count that follows from
    the class — "this matter has 0 overrides" on a matter with forty pins — is wrong in the
    flattering direction, which is the direction that does not get reported."""

    verb: str
    act_class: str
    chain: str          # CHAIN_MATTER | CHAIN_TENANT
    system: bool = False  # True when only a system component performs it
    override: str | None = None  # an FR-25 ground, or None when the act is not an override

    def __post_init__(self) -> None:
        if self.chain not in (CHAIN_MATTER, CHAIN_TENANT):
            raise ValueError(f"unknown chain kind: {self.chain!r}")
        if self.override is not None:
            check_ground(self.override)  # UnknownOverrideGround on a fourth ground


def _act(
    verb: str, act_class: str, chain: str, *, system: bool = False, override: str | None = None,
) -> RecordableAct:
    return RecordableAct(verb, act_class, chain, system, override)


# The chain's own lifecycle (AD-43 / D4).
ACT_CHAIN_OPENED = "chain_opened"

# Import and the failure register (FR-5, FR-24 import_job).
ACT_INGEST = "ingest"
ACT_RETRY = "retry"
ACT_BULK_RETRY = "bulk-retry"
ACT_EXPORT_REGISTER = "export-register"
# An entry leaves `open` without the document ever entering the corpus (FR-5 / FR-25, Story 5.6).
ACT_REGISTER_OVERRIDE = "register_override"

# The judgment cascade and the per-*pièce* record (FR-24 value_modified).
ACT_JUDGE = "judge"
ACT_PIECE_LABELLED = "piece_labelled"
ACT_JUSTIFICATION_RECORDED = "justification_recorded"
ACT_JUSTIFICATION_REJECTED = "justification_rejected"
ACT_JUSTIFICATION_RESTORED = "justification_restored"

# The case theory (FR-37).
ACT_CASE_THEORY_WRITTEN = "case_theory_written"
ACT_CASE_THEORY_WITHDRAWN = "case_theory_withdrawn"

# The version identity (FR-39/AD-23).
ACT_RANKING_RECORDED = "ranking_recorded"

# The line (FR-17/FR-19) and the pin (FR-43).
ACT_LINE_PLACED = "line_placed"
ACT_LINE_MOVED = "line_moved"
ACT_PIN_OVERRIDE = "pin_override"
ACT_PIN_REMOVED = "pin_removed"

# The sampling run and its bound (FR-22/FR-23).
ACT_SAMPLING_RUN_START = "sampling-run-start"
ACT_SAMPLING_VERDICT = "sampling-verdict"
ACT_SAMPLING_RUN_COMPLETE = "sampling-run-complete"
ACT_SAMPLING_RUN_ABANDON = "sampling-run-abandon"
ACT_EXPORT_BOUND = "export-bound"

# Reads and retrievals (AD-14/FR-15).
ACT_SEARCH = "search"
ACT_EXPORT_SEARCH = "export-search"
ACT_OPEN_PIECE = "open-piece"

# Configuration (AD-25) and the tenant's own administration (FR-49).
ACT_CONFIG_CHANGED = "config_changed"
ACT_TENANT_PROVISIONED = "tenant_provisioned"
ACT_CREATE_USER = "create_user"
ACT_GRANT_SCOPE = "grant_scope"
ACT_REVOKE_SCOPE = "revoke_scope"
ACT_RESCOPE_MATTER = "rescope_matter"
ACT_GRANT_ADMIN = "grant_admin"
ACT_REVOKE_ADMIN = "revoke_admin"
ACT_KEY_ROTATED = "key_rotated"
ACT_TRUNCATION_OVERRIDE = "truncation_override"

# Security events (FR-48) — system-initiated, on the tenant chain.
ACT_LOGIN_FAILED = "login_failed"
ACT_LOGIN_LOCKED_OUT = "login_locked_out"
ACT_LOGIN_MFA_UNENROLLED = "login_mfa_unenrolled"
ACT_LOGIN_MFA_FAILED = "login_mfa_failed"

_CATALOGUE: tuple[RecordableAct, ...] = (
    _act(ACT_CHAIN_OPENED, CLASS_CHAIN_LIFECYCLE, CHAIN_TENANT),

    _act(ACT_INGEST, CLASS_IMPORT_JOB, CHAIN_MATTER),
    _act(ACT_RETRY, CLASS_IMPORT_JOB, CHAIN_MATTER),
    # A bulk retry and a register export are acts of the RBAC SCOPE, not of one matter: both run
    # over the whole scope-filtered register and cross matters by construction. The chain records
    # where an act is counted; the `matter` column still records the filter it named, when it named
    # one. Putting a filtered bulk retry on its matter's chain and an unfiltered one on the tenant's
    # would make the same verb land in two places by a rule no reader of the export could see.
    _act(ACT_BULK_RETRY, CLASS_IMPORT_JOB, CHAIN_TENANT),
    _act(ACT_EXPORT_REGISTER, CLASS_IMPORT_JOB, CHAIN_TENANT),
    # On the TENANT chain for the reason above and one more: a register entry's *matter* may be
    # UNDETERMINED (the column is nullable, and such an entry is admin-only, FR-49). Filing the
    # ones that have a matter on the matter chain and the ones that do not on the tenant chain
    # would put one verb in two places by a rule no reader of the export could see. The `matter`
    # column still records what the act was about, and a matter's trail read returns tenant-chain
    # entries naming it, so the override is counted where the lawyer looks for it.
    _act(ACT_REGISTER_OVERRIDE, CLASS_OVERRIDE, CHAIN_TENANT, override=GROUND_REGISTER_EXIT),

    _act(ACT_JUDGE, CLASS_VALUE_MODIFIED, CHAIN_MATTER),
    _act(ACT_PIECE_LABELLED, CLASS_VALUE_MODIFIED, CHAIN_MATTER),
    _act(ACT_JUSTIFICATION_RECORDED, CLASS_VALUE_MODIFIED, CHAIN_MATTER),
    _act(ACT_JUSTIFICATION_REJECTED, CLASS_VALUE_MODIFIED, CHAIN_MATTER),
    _act(ACT_JUSTIFICATION_RESTORED, CLASS_VALUE_MODIFIED, CHAIN_MATTER),

    _act(ACT_CASE_THEORY_WRITTEN, CLASS_CASE_THEORY, CHAIN_MATTER),
    _act(ACT_CASE_THEORY_WITHDRAWN, CLASS_CASE_THEORY, CHAIN_MATTER),

    _act(ACT_RANKING_RECORDED, CLASS_VERSION_IDENTITY, CHAIN_MATTER),

    _act(ACT_LINE_PLACED, CLASS_LINE_POSITION, CHAIN_MATTER),
    _act(ACT_LINE_MOVED, CLASS_LINE_POSITION, CHAIN_MATTER),
    # A pin keeps CLASS_PIN — FR-24 enumerates "every *pin*" — and carries the override ground
    # beside it (FR-25): it moves one *pièce* against a ranked order the tool published with a
    # confidence. Two requirements, one act, two axes.
    _act(ACT_PIN_OVERRIDE, CLASS_PIN, CHAIN_MATTER, override=GROUND_CONTRADICTS_MACHINE),
    # Removing a pin LIFTS a contradiction rather than making one, so it is not an override and
    # costs no reason (Story 4.11's own reading, kept).
    _act(ACT_PIN_REMOVED, CLASS_PIN, CHAIN_MATTER),

    _act(ACT_SAMPLING_RUN_START, CLASS_SAMPLING_RUN, CHAIN_MATTER),
    _act(ACT_SAMPLING_VERDICT, CLASS_SAMPLING_RUN, CHAIN_MATTER),
    _act(ACT_SAMPLING_RUN_COMPLETE, CLASS_SAMPLING_RUN, CHAIN_MATTER),
    _act(ACT_SAMPLING_RUN_ABANDON, CLASS_SAMPLING_RUN, CHAIN_MATTER),
    _act(ACT_EXPORT_BOUND, CLASS_SAMPLING_RUN, CHAIN_MATTER),

    _act(ACT_SEARCH, CLASS_RETRIEVAL, CHAIN_TENANT),
    _act(ACT_EXPORT_SEARCH, CLASS_RETRIEVAL, CHAIN_TENANT),
    _act(ACT_OPEN_PIECE, CLASS_RETRIEVAL, CHAIN_MATTER),

    _act(ACT_CONFIG_CHANGED, CLASS_CONFIG_CHANGE, CHAIN_TENANT),
    _act(ACT_TENANT_PROVISIONED, CLASS_SCOPE_GRANT, CHAIN_TENANT),
    _act(ACT_CREATE_USER, CLASS_SCOPE_GRANT, CHAIN_TENANT),
    _act(ACT_GRANT_SCOPE, CLASS_SCOPE_GRANT, CHAIN_TENANT),
    _act(ACT_REVOKE_SCOPE, CLASS_SCOPE_GRANT, CHAIN_TENANT),
    # the matter is the subject of a re-scope, so the act belongs on the matter's own chain;
    # the authority under which it was made travels in the detail (FR-24, FR-49).
    _act(ACT_RESCOPE_MATTER, CLASS_SCOPE_GRANT, CHAIN_MATTER),
    _act(ACT_GRANT_ADMIN, CLASS_SCOPE_GRANT, CHAIN_TENANT),
    _act(ACT_REVOKE_ADMIN, CLASS_SCOPE_GRANT, CHAIN_TENANT),
    _act(ACT_KEY_ROTATED, CLASS_CONFIG_CHANGE, CHAIN_TENANT),
    # Filed under CLASS_CONFIG_CHANGE until Story 5.6, for want of a live class rather than because
    # it is one: clearing the marker that names an incomplete record on every export changes no
    # configuration, it takes a guard out of the way. The class is read from the catalogue at read
    # time and never persisted on the row, so moving it orphans nothing already written.
    _act(ACT_TRUNCATION_OVERRIDE, CLASS_OVERRIDE, CHAIN_TENANT, override=GROUND_GUARD_BYPASS),

    _act(ACT_LOGIN_FAILED, CLASS_SECURITY_EVENT, CHAIN_TENANT, system=True),
    _act(ACT_LOGIN_LOCKED_OUT, CLASS_SECURITY_EVENT, CHAIN_TENANT, system=True),
    _act(ACT_LOGIN_MFA_UNENROLLED, CLASS_SECURITY_EVENT, CHAIN_TENANT, system=True),
    _act(ACT_LOGIN_MFA_FAILED, CLASS_SECURITY_EVENT, CHAIN_TENANT, system=True),
)

ACTS: dict[str, RecordableAct] = {a.verb: a for a in _CATALOGUE}


class UncataloguedAct(ValueError):
    """A verb no catalogue entry describes. Refused at the write, so a typo cannot manufacture an
    act class that no filter, count or export will ever surface."""


def act(verb: str) -> RecordableAct:
    """The catalogued act for ``verb``, or raise :class:`UncataloguedAct`."""
    found = ACTS.get(verb)
    if found is None:
        raise UncataloguedAct(f"uncatalogued audit act: {verb!r}")
    return found


def covered_classes() -> frozenset[str]:
    """Every act class at least one catalogued verb writes."""
    return frozenset(a.act_class for a in _CATALOGUE)


def verbs_for(act_class: str) -> tuple[str, ...]:
    return tuple(a.verb for a in _CATALOGUE if a.act_class == act_class)


# ── the override axis (FR-25) ─────────────────────────────────────────────────────────────────

def is_override(verb: str) -> bool:
    """Whether this verb records an *override* (FR-25). **This is the only correct way to count
    overrides.** Counting ``act_class == CLASS_OVERRIDE`` instead reports zero on a matter with
    forty pins, because a pin's class is CLASS_PIN — the count would be over a set that is not the
    set being counted, and it would look right on every matter that has never pinned anything.

    An uncatalogued verb is not an override; it is refused at the write (:func:`act`), and this
    predicate stays total so a read over historical rows can never raise."""
    found = ACTS.get(verb)
    return found is not None and found.override is not None


def override_ground(verb: str) -> str | None:
    """Which of FR-25's three grounds makes this verb an *override*, or ``None``."""
    found = ACTS.get(verb)
    return found.override if found is not None else None


def override_verbs() -> tuple[str, ...]:
    """Every catalogued verb that records an *override*, in catalogue order."""
    return tuple(a.verb for a in _CATALOGUE if a.override is not None)


# ── the chained content (FR-53) ───────────────────────────────────────────────────────────────

#: The recipe every entry written before Story 5.5 chained over: five fields and a timestamp, with
#: the *matter* rendered as the empty string when absent.
CONTENT_V1 = 1

#: The recipe from Story 5.5: the chain scope is named, and the application and payload-schema
#: versions FR-24 requires recorded are inside the chained value rather than beside it. The version
#: prefix makes the two recipes non-colliding by construction — no v1 content can ever be produced
#: by the v2 recipe, so an entry cannot be replayed under the other reading.
CONTENT_V2 = 2

CONTENT_VERSIONS: tuple[int, ...] = (CONTENT_V1, CONTENT_V2)


class UnknownContentVersion(ValueError):
    """An entry whose content version this build has no recipe for — never guessed at."""


def chained_content(
    *,
    version: int,
    seq: int,
    tenant: str,
    chain_scope: str,
    matter: str | None,
    actor: str,
    action: str,
    detail: str,
    timestamp: str,
    app_version: str,
    schema_version: str,
) -> str:
    """The exact string an entry's chain value is taken over, per its own content version.

    The verifier reads the version **from the entry**, never from the code's current opinion:
    Story 5.5 changed the recipe, and recomputing an older entry with the newer one would turn a
    correct record unverifiable in a single deploy — the very alarm the chain exists to raise."""
    if version == CONTENT_V1:
        return f"{seq}|{tenant}|{matter or ''}|{actor}|{action}|{detail}|{timestamp}"
    if version == CONTENT_V2:
        return (
            f"v2|{seq}|{tenant}|{chain_scope}|{matter or ''}|{actor}|{action}|"
            f"{detail}|{timestamp}|{app_version}|{schema_version}"
        )
    raise UnknownContentVersion(f"no chain recipe for content version {version!r}")


def chain_value(prev_chain: str, content: str) -> str:
    """The chain value of an entry whose predecessor chained to ``prev_chain``."""
    return hashlib.sha256(f"{prev_chain}\x00{content}".encode()).hexdigest()


# ── verification: one verifier, over one or many chains (FR-53) ───────────────────────────────

@dataclass(frozen=True)
class VerifiableEntry:
    """One entry as a verifier sees it: plaintext, with the recipe version it was written under.
    ``actor`` and ``detail`` are ``None`` when the ciphertext could not be authenticated — an
    unreadable field cannot be verified, and the chain fails closed rather than skipping it."""

    tenant: str
    chain_scope: str
    seq: int
    matter: str | None
    actor: str | None
    action: str
    detail: str | None
    timestamp: str
    chain: str
    content_version: int
    app_version: str | None
    schema_version: str | None


@dataclass(frozen=True)
class ChainVerdict:
    """What a reader can conclude about ONE chain. ``anchored`` is False when the chain's starting
    value was not supplied — every link after the first is still proved, and the first is taken as
    given rather than silently counted as proved."""

    chain_scope: str
    entries: int
    verified: bool
    anchored: bool
    broken_at: int | None = None   # the sequence number of the first link that did not hold


def verify_chains(
    entries: list[VerifiableEntry], anchors: dict[str, str] | None = None
) -> tuple[ChainVerdict, ...]:
    """Verify every chain present in ``entries``, independently, in chain-scope order.

    Independently is the point (AD-43): a reader holding only one *matter*'s entries recomputes
    that *matter*'s chain end to end and concludes about it alone. A verifier that folded the
    chains together would report a gap at every point another chain wrote — which is what a single
    per-*tenant* chain did to every per-*matter* export.

    ``anchors`` maps a chain scope to the value its first entry chains onto: ``""`` for the
    *tenant* chain (the root), and the anchoring entry's chain value for a *matter* chain. An
    absent anchor is reported, never assumed.
    """
    supplied = anchors or {}
    scopes = sorted({e.chain_scope for e in entries})
    verdicts: list[ChainVerdict] = []
    for scope in scopes:
        rows = sorted((e for e in entries if e.chain_scope == scope), key=lambda e: e.seq)
        anchor = supplied.get(scope, "" if scope == TENANT_CHAIN else None)  # type: ignore[arg-type]
        anchored = anchor is not None
        prev = anchor if anchored else None
        broken: int | None = None
        for i, e in enumerate(rows):
            if e.seq != i + 1:                       # a gap, a reorder, or a truncated head
                broken = e.seq
                break
            if e.actor is None or e.detail is None:  # an unreadable field cannot be authenticated
                broken = e.seq
                break
            if prev is None:   # an unanchored chain's first link: taken as given, never as proved
                prev = e.chain
                continue
            content = chained_content(
                version=e.content_version, seq=e.seq, tenant=e.tenant, chain_scope=e.chain_scope,
                matter=e.matter, actor=e.actor, action=e.action, detail=e.detail,
                timestamp=e.timestamp, app_version=e.app_version or "",
                schema_version=e.schema_version or "")
            if chain_value(prev, content) != e.chain:
                broken = e.seq
                break
            prev = e.chain
        verdicts.append(ChainVerdict(
            chain_scope=scope, entries=len(rows), verified=broken is None,
            anchored=anchored, broken_at=broken))
    return tuple(verdicts)
