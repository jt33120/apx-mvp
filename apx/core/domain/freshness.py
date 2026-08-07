"""Freshness and staleness of derived artefacts — the pure vocabulary (Story 4.13, FR-58 / AD-23 /
AD-40).

A *derived artefact* — a ranked order, a position of **the line**, a *confidence bound* — is
computed from inputs that keep moving afterwards. AD-23's second half is about what happens then:
*staleness is explicit and never self-resolving*.

**Staleness here is a DERIVED VIEW, never a stored flag.** A stored ``stale`` boolean has to be
*set* by every writer, and a writer that forgets leaves the artefact **falsely fresh** — precisely
the failure AD-23 names (*"300 pièces arrive, the sentence still reads '1 400 in the discarded set',
nothing is marked stale and it remains exportable as current"*). A **comparison cannot forget**: an
input that moved is visible whether or not anyone remembered to announce it. So an artefact records
the :class:`FreshnessStamp` of its inputs at production time, and :func:`assess_freshness` decides
freshness by comparing that stamp with the current one at read time — the same shape as the
retained/discarded sets (AD-39), the current label (4.5), the current line (4.8) and the current pin
(4.11).

Two load-bearing properties live here, both pure and testable without a DB:

- **The trigger list is closed and enumerated** (:data:`TRIGGERS`), and :class:`FreshnessStamp` has
  **exactly one observable field per trigger**. The structural check
  ``every_staleness_trigger_has_an_observable`` asserts the two match *both ways* and fails closed,
  so a trigger nobody observes — or an observable naming no trigger — turns the build red.

- **No clock reaches the decision.** Nothing here imports a time source and no observable is a
  timestamp: staleness is never resolved by the passage of time, by a background recomputation or
  by being viewed (FR-58). The structural check ``freshness_is_never_time_based`` asserts it over
  this module's own source.

This module stores nothing and imports Domain only (AD-4).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, fields
from typing import Any

# ── the artefact kinds that carry a stamp (AD-23's Binds list, as far as this build has built) ──
# The *review-effort estimate* and a persisted *exhaustive result set* are also bound by AD-23 but
# do not exist as artefacts here: the estimate has no story yet, and an exhaustive result set is
# computed at read time and never persisted (Story 3.2 / AD-20) — it is fresh by construction
# because it has no lifetime in which an input could move. Adding a kind here is how a future
# artefact joins; the completeness check below is written over the TRIGGER list, not this one, so
# this tuple can never falsely claim coverage of a trigger.
KIND_RANKING = "ranking"
KIND_LINE = "line"
KIND_BOUND = "bound"
# Story 5.1: a *sampling run* is a stamped derived artefact too, and FR-22's
# "invalidated-in-flight" is precisely this comparison read on a run that is still open. The kind
# is separate from ``bound`` because a run has a lifetime BEFORE it has a bound — the window in
# which the population can move under an hour of verdicts is exactly what FR-22 is about.
KIND_SAMPLING_RUN = "sampling_run"
ARTEFACT_KINDS: tuple[str, ...] = (KIND_RANKING, KIND_LINE, KIND_BOUND, KIND_SAMPLING_RUN)


@dataclass(frozen=True)
class Trigger:
    """One enumerated input whose change makes a derived artefact stale (FR-58 / AD-23 / AD-40).

    ``key`` is both the trigger's identity and the name of its observable field on
    :class:`FreshnessStamp` — the two cannot drift because they are the same string. ``fr`` is the
    French phrase the surface says when this input is the one that changed (FR-58: the assessment
    **names which input changed**, never a bare "stale"). ``source`` names the requirement the
    trigger comes from, so the list stays auditable against the spine.
    """

    key: str
    fr: str
    source: str


# The COMPLETE, CLOSED trigger list. Seven from FR-58, AD-23's eighth (a re-extraction of any
# *pièce*, AD-40) and FR-23's ninth (the population a bound was drawn from). Order is the order the
# surface names them in.
TRIGGERS: tuple[Trigger, ...] = (
    Trigger("ranking_version_no", "un nouveau classement", "FR-58"),
    Trigger("line_seq", "un déplacement de la ligne", "FR-58"),
    Trigger("pin_ledger_seq", "une épingle posée ou retirée", "FR-58"),
    Trigger("case_theory_version_no", "une révision de la théorie du cas", "FR-58"),
    Trigger("config_digest", "une modification de configuration", "FR-58"),
    Trigger("scope_identity", "un changement de périmètre", "FR-58"),
    Trigger("corpus_count", "une importation dans le dossier", "FR-58"),
    Trigger("extraction_digest", "une ré-extraction d'une pièce", "AD-40"),
    # FR-23's clause, which AD-23's seven-plus-one does not name separately: a *confidence bound*
    # is stale when "the population it was drawn from" has changed. Story 5.1 (planning decision
    # A1) fixed WHICH population that is: the Epic-4 DERIVED discarded view, never the Story-2.x
    # label pile. Formally this observable is now redundant — the derived set is a function of
    # ``ranking_version_no`` + ``line_seq`` + ``pin_ledger_seq``, all three already watched. It is
    # kept because inferring "no input we watch moved, therefore the population is unchanged" is a
    # comparison against a NEARLY-right referent, and it fails toward *falsely fresh* the day
    # someone adds a fourth input to the derivation. A direct digest is the EXACT referent, costs
    # one query the stamp already makes, and cannot be defeated by a future change to the
    # derivation. Redundant evidence about the one artefact quoted to a judge is not waste.
    Trigger("discard_population", "une modification du jeu écarté", "FR-23"),
)

TRIGGER_KEYS: tuple[str, ...] = tuple(t.key for t in TRIGGERS)
_TRIGGER_BY_KEY: Mapping[str, Trigger] = {t.key: t for t in TRIGGERS}


def trigger(key: str) -> Trigger:
    """The trigger a stamp field belongs to. Raises on an unknown key — a changed input the product
    cannot name is not something to render vaguely."""
    try:
        return _TRIGGER_BY_KEY[key]
    except KeyError as exc:  # pragma: no cover - the structural check makes this unreachable
        raise ValueError(f"unknown staleness trigger: {key!r}") from exc


@dataclass(frozen=True)
class FreshnessStamp:
    """The observable state of **every** enumerated input at one moment (FR-58 / AD-23).

    Exactly one field per :data:`TRIGGERS` entry, named identically. Every observable is **exact**,
    not approximate — a staleness that can be missed is worse than none, because it is asserted as
    freshness:

    - ``ranking_version_no`` — the *matter*'s highest ``ranking_version.version_no``. Monotonic.
    - ``line_seq`` — the highest ``line_placement.seq`` for the artefact's version; ``None`` when no
      line is placed. Monotonic per version.
    - ``pin_ledger_seq`` — the sum over *pièces* of each one's highest ``pin_entry.seq``. Every pin
      act appends with a strictly greater per-*pièce* seq, so the sum strictly increases: a pin
      added **and** a pin removed both move it, which a count would not.
    - ``case_theory_version_no`` — the *matter*'s highest case-theory ``version_no``, ``0`` when
      none. A *withdrawal* is itself a version (FR-37), so withdrawing triggers.
    - ``config_digest`` — a hash over the effective values of every configuration key declaring
      ``affects_retrieval`` (``core.domain.config``). Reusing that existing flag means the trigger
      list and the audited change reason cannot drift apart, and a new key is covered the moment
      its author sets the flag they already have to set.
    - ``scope_identity`` — the *matter*'s current ``matter_scope.scope`` (one scope per *matter*:
      the Chinese-wall unit, AD-13).
    - ``corpus_count`` — the number of *pièces* in the *matter*. Nothing is ever hard-deleted (AD-7,
      proven by Story 4.12's probe), so this is **monotonic** and every ingestion moves it.
    - ``extraction_digest`` — a hash over ``piece_id \\x00 text_identity`` for every *pièce*, in
      ``piece_id`` byte order. Both are ASCII hex, so the digest is collation-independent — the same
      reason AD-23's tie-break is computed over the *pièce* identity hash and never over collated
      text.
    - ``discard_population`` — a hash over the identities of the *pièces* in the **derived
      discarded set** (``derive_triage_sets(order, line, pins).discarded``) for the version being
      stamped, in ``piece_id`` byte order: **the population a *confidence bound* and a *sampling
      run* are drawn over** (FR-23/FR-22, and the population fixed by planning decision A1). A
      digest, not a count, because a change that moves one *pièce* out of the set and another in
      leaves the count identical while the population is a different set — and a bound is a
      statement about a set, not about a cardinality.

    ``corpus_count`` and ``extraction_digest`` both move on an ingestion, and collapsing them would
    be cheaper. They stay apart because FR-58 requires the assessment to **name which input
    changed**, and *"300 pièces are in the dossier that the ranking never saw"* and *"a pièce was
    re-read"* are different sentences to a lawyer and different offers on the *worklist*.

    **No field is a timestamp.** A clock as an input is how staleness resolves itself by the passage
    of time, which FR-58 forbids; ``freshness_is_never_time_based`` asserts it structurally.
    """

    ranking_version_no: int
    line_seq: int | None
    pin_ledger_seq: int
    case_theory_version_no: int
    config_digest: str
    scope_identity: str
    corpus_count: int
    extraction_digest: str
    discard_population: str

    def value(self, key: str) -> Any:
        """The observable for one trigger key. Raises on an unknown key (never a default)."""
        return getattr(self, trigger(key).key)

    def to_json(self) -> str:
        """Canonical JSON with sorted keys — the store persists it in one text column, exactly as
        ``ranking_version.identity_json`` does, so the same bytes decode on any machine."""
        return json.dumps(
            {f.name: getattr(self, f.name) for f in fields(self)},
            sort_keys=True, separators=(",", ":"), ensure_ascii=False)

    @classmethod
    def from_json(cls, raw: str) -> FreshnessStamp:
        """Decode a persisted stamp. **Fails closed**: a missing, unknown or extra field raises
        rather than defaulting. A stamp that cannot be read in full is not evidence of freshness,
        and a partially-decoded stamp would silently compare equal on the fields it did read."""
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"unreadable freshness stamp: {exc}") from exc
        if not isinstance(data, dict):
            raise ValueError("a freshness stamp must be a JSON object")
        expected = {f.name for f in fields(cls)}
        missing = sorted(expected - set(data))
        unknown = sorted(set(data) - expected)
        if missing or unknown:
            raise ValueError(
                f"freshness stamp fields do not match (missing={missing}, unknown={unknown})")
        return cls(**data)


@dataclass(frozen=True)
class Freshness:
    """The verdict on one derived artefact: **which inputs changed**, never a bare boolean
    (FR-58).

    ``fresh`` is *derived from* ``changed`` rather than stored beside it, so the two cannot
    disagree: there is no constructor path producing "fresh" with a non-empty ``changed``.

    ``superseded`` says whether a NEWER artefact of the same kind exists — a ranking version that
    has been re-run, a placement that has been moved, a bound that has been re-sampled. A superseded
    artefact stays in this list because it is still readable and its verdict is still true of it
    (nothing is deleted, AD-7), but it is **not work**: the recomputation it would offer has already
    been performed. Offering it again would mean the offer never discharges — the user accepts the
    re-rank and the banner still demands one — which turns an honest alarm into wallpaper.
    """

    kind: str
    artefact_id: str
    changed: tuple[str, ...]  # trigger keys, in TRIGGERS order
    superseded: bool = False

    @property
    def fresh(self) -> bool:
        return not self.changed

    @property
    def stale(self) -> bool:
        return bool(self.changed)

    @property
    def changed_fr(self) -> tuple[str, ...]:
        """The French phrases for the changed inputs, in TRIGGERS order — what the banner says."""
        return tuple(trigger(k).fr for k in self.changed)

    def reason(self) -> str:
        """One line naming every changed input — the string an export refusal and a copied bound
        both carry, so staleness cannot be separated from the number (FR-58)."""
        if not self.changed:
            return "à jour"
        return "périmé : " + ", ".join(self.changed_fr)


# ── which inputs each artefact kind actually depends on ─────────────────────────────────────────
# The eight triggers are the complete list of things that CAN move. They are not all inputs to
# every artefact, and pretending otherwise is not the safe choice — it is a different failure. A
# banner that says *"votre classement date d'avant votre déplacement de la ligne"* is **false**:
# placing or moving the line touches only ``line_placement``, and the ranked order is unchanged,
# byte for byte. A product that raises a false alarm on an act the user just performed teaches her
# to dismiss the banner, and then the true alarm — 300 pièces arrived — is dismissed with it.
#
# So each kind narrows the list, and every narrowing is argued here. The DEFAULT for a kind not
# listed is **all eight** (:func:`inputs_for`), so a future artefact nobody thought about goes stale
# on everything: too often, never too rarely.
_ALL: frozenset[str] = frozenset(TRIGGER_KEYS)
INPUTS_BY_KIND: Mapping[str, frozenset[str]] = {
    # The ranked order is produced by the cascade over the corpus. **The line** and the *pins* are
    # applied to it afterwards to derive the sets (AD-39); neither is an input to the order, and
    # both are asserted never to touch it (``ranking_order_ignores_the_pin``, and ``place_line``
    # writes only the placement ledger). A NEW ranking version IS kept: it supersedes this one, and
    # a lawyer reading version 1 while version 2 exists must be told.
    KIND_RANKING: _ALL - {"line_seq", "pin_ledger_seq", "discard_population"},
    # A placement cuts one ranking version, so everything the order depends on it depends on too,
    # plus its own supersession (a later placement bumps ``line_seq``). A *pin* overrides the line
    # for exactly one pièce (FR-43) — it does not move the cut, and the placement it names is still
    # the placement in force.
    KIND_LINE: _ALL - {"pin_ledger_seq", "discard_population"},
    # The *confidence bound* depends on EVERY observable, verbatim from FR-58 and FR-23: it is a
    # statement about a population, drawn from a corpus, under a scope, at a configuration, over an
    # order cut by a line and overridden by pins. This is the artefact the requirement was written
    # for, and the structural check asserts this entry is the complete list. The ranking and the
    # line exclude ``discard_population`` because the relevance verdict is not an input to either:
    # the cascade produces the order, and the label ledger is downstream of it (asserted by
    # ``label_not_a_ranking_input``).
    KIND_BOUND: _ALL,
    # A *sampling run* (Story 5.1) depends on every observable for the same reason the bound does,
    # and one more: its population IS the derived discarded view, so a pin — which moves exactly one
    # pièce across the line (FR-43) — changes the very set it drew from. FR-22's list ("ingestion,
    # re-ranking or a line move") is a floor, not a ceiling, and under-invalidating a run means an
    # hour of verdicts silently answering the wrong question. The structural check asserts this
    # entry is the complete enumeration.
    KIND_SAMPLING_RUN: _ALL,
}


def inputs_for(kind: str) -> tuple[str, ...]:
    """The trigger keys this artefact kind depends on, in :data:`TRIGGERS` order. An unlisted kind
    depends on **all eight** — a new artefact is over-invalidated, never under-invalidated."""
    depends = INPUTS_BY_KIND.get(kind, _ALL)
    return tuple(k for k in TRIGGER_KEYS if k in depends)


def compare_stamps(
    recorded: FreshnessStamp, current: FreshnessStamp, *, kind: str | None = None
) -> tuple[str, ...]:
    """The pure comparison: the trigger keys whose observable differs, in :data:`TRIGGERS` order,
    restricted to the inputs ``kind`` depends on (all eight when ``kind`` is None).

    Iterating :data:`TRIGGERS` (rather than the dataclass fields) is deliberate — the ORDER the
    surface names inputs in is the trigger list's order, and a field the trigger list does not know
    about would be silently ignored here. It cannot exist: the structural check makes the two sets
    equal.
    """
    keys = inputs_for(kind) if kind is not None else TRIGGER_KEYS
    changed = tuple(k for k in keys if recorded.value(k) != current.value(k))
    return _subsume(changed, keys)


# One observable implies another, so reporting both would name an act that never happened. Naming
# the implied one is a false statement to a lawyer, and this product's whole argument is that it
# does not make those. Never the other way round: an implication only ever REMOVES a redundant name
# from a set that is already non-empty, so no staleness is hidden.
#
# - ``extraction_digest`` covers EVERY pièce's text identity, so an ingestion moves it too — but
#   nobody re-read anything.
# - ``discard_population`` is a digest over the DERIVED discarded set (Story 5.1), which is a
#   function of the ranked order, **the line** and the *pins*. Any of those three moving moves it,
#   and saying *"le jeu écarté a changé"* beside *"un déplacement de la ligne"* would present one
#   act as two. It is kept as an observable precisely because it is the EXACT referent — it fires
#   on its own the day the derivation gains an input nobody added a trigger for.
_IMPLIED_BY: Mapping[str, tuple[str, ...]] = {
    "extraction_digest": ("corpus_count",),
    "discard_population": ("ranking_version_no", "line_seq", "pin_ledger_seq"),
}


def _subsume(changed: tuple[str, ...], keys: tuple[str, ...]) -> tuple[str, ...]:
    """Drop an observable whose change is fully explained by another that also changed.

    An implying observable counts only when it is itself an input of the artefact being assessed: if
    it is not, the implied observable is the only evidence there is and must be reported. Several
    observables may imply the same one (the derived discarded set has three causes); ANY of them
    firing is enough to explain it."""
    fired = set(changed)
    return tuple(
        k for k in changed
        if not any(
            implier in fired and implier in keys for implier in _IMPLIED_BY.get(k, ())))


def assess_freshness(
    *, kind: str, artefact_id: str, recorded: FreshnessStamp, current: FreshnessStamp,
    superseded: bool = False,
) -> Freshness:
    """Assess one derived artefact against the inputs it depends on. Pure — no clock, no I/O, no
    store."""
    if kind not in ARTEFACT_KINDS:
        raise ValueError(f"unknown artefact kind: {kind!r}")
    return Freshness(
        kind=kind, artefact_id=artefact_id,
        changed=compare_stamps(recorded, current, kind=kind), superseded=superseded)


def config_digest(values: Mapping[str, Any]) -> str:
    """The ``config_digest`` observable: a stable hash over the effective values of the
    retrieval/ranking/estimator-affecting configuration keys. Canonical JSON with sorted keys, so
    insertion order and dict iteration order cannot change the digest."""
    return hashlib.sha256(
        json.dumps(dict(values), sort_keys=True, separators=(",", ":"),
                   ensure_ascii=False).encode("utf-8")).hexdigest()


def population_digest(piece_ids: Iterable[str]) -> str:
    """The ``discard_population`` observable: a hash over the *pièce* identities in the **derived**
    discarded set (Story 5.1 / decision A1 — never the label pile), supplied **sorted by
    ``piece_id``**. The caller sorts because the set is derived in Python from the ranked order, not
    read back from SQL: the digest must be a function of the *membership*, not of the rank order the
    derivation happened to produce, or a re-rank that discarded exactly the same *pièces* in a
    different order would read as a changed population. ASCII hex, so byte order is codepoint order
    and the digest is collation-independent."""
    digest = hashlib.sha256()
    for piece_id in piece_ids:
        digest.update(piece_id.encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def extraction_digest(pairs: Iterable[tuple[str, str]]) -> str:
    """The ``extraction_digest`` observable over ``(piece_id, text_identity)`` pairs.

    The caller supplies the pairs **ordered by ``piece_id``** (the store orders in SQL). Both values
    are ASCII hex, so byte order is codepoint order and the digest is collation-independent — a
    re-extraction that changed one *pièce*'s text identity moves it, and a rebuilt machine with a
    different ``LC_COLLATE`` computes the same value (the AD-23 property that makes AD-32's restore
    assertion survive).
    """
    digest = hashlib.sha256()
    for piece_id, text_identity in pairs:
        digest.update(piece_id.encode("utf-8"))
        digest.update(b"\x00")
        digest.update(text_identity.encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()
