"""The declared per-*tenant* configuration schema — customisation is data, never code (AD-24).

This is the single source of truth for what is configurable per *tenant*: every key from
AD-24's bind list (taxonomy, *RBAC scopes*, model provider & endpoint, configured sources,
chunking configuration, exclusion list, the cascade share ceiling, the off-corpus refusal, the
interface language). It lives in the **core** (pure — no adapter import): the store persists a
key's value as a data row and validates it against *this* schema; the API edits it through the
one audited surface (AD-25); a structural check reads it to prove no default disables the
guarantee its key governs.

Two invariants this module makes true and a check enforces:

- **Every key has a default** — a fail-closed install is still a working install.
- **No default disables the guarantee its key governs** — the v1 defect was the off-corpus gate
  shipped *disabled by default*, a guess wearing the costume of a proof. A key that governs a
  switchable guarantee declares ``preserves_guarantee``, the predicate its default must satisfy;
  ``config_defaults_preserve_guarantees`` (a build gate) asserts it for the whole schema.

No *tenant*-specific identifier or name appears here (AD-24): the keys are generic, the values
are provisioned as data.
"""

from __future__ import annotations

import json
import math
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from apx.core.domain.cascade import Band
from apx.core.domain.taxonomy_label import UNLABELLED

# the stage-2 band values a line-retain policy may name (Story 4.8) — an unknown band can never
# leak into the cut. Derived from the closed Band vocabulary, so the two never drift.
_BAND_VALUES: frozenset[str] = frozenset(b.value for b in Band)

# The value kinds a configuration value may take. Kept small and JSON-serialisable so the store
# can hold every value in one text column and the surface can validate generically.
Kind = str  # one of _KINDS below
_KINDS = ("bool", "int", "float", "str", "str_list")


class ConfigError(ValueError):
    """An unknown configuration key, or a value that does not match its key's declared type.
    Raised by the surface so a bad edit is refused with a typed error — never silently defaulted
    (AD-25: every change is validated against the declared schema)."""


@dataclass(frozen=True)
class ConfigKey:
    """One configuration-as-data key: its type, its default, the guarantee it governs, and —
    where that guarantee is switchable — the predicate its default must satisfy."""

    name: str
    kind: Kind
    default: Any
    governs: str  # the human-readable guarantee/behaviour this key controls (documentation)
    # A key that governs a guarantee that could be switched *off* declares the predicate a value
    # must satisfy to keep the guarantee intact. The default MUST satisfy it (a build gate checks
    # it). A key that only tunes behaviour (language, endpoint, taxonomy) leaves this None.
    preserves_guarantee: Callable[[Any], bool] | None = None
    # A change to this key invalidates derived retrieval/ranking artefacts (AD-23). No artefact
    # exists yet (epics 4–5); the flag is recorded on the audited change as the future hook.
    affects_retrieval: bool = False
    allowed: tuple[Any, ...] | None = None  # a closed value set, when the key is an enum
    # A domain predicate every WRITE must satisfy (a numeric range, say) — enforced by ``coerce``
    # on every set, so the surface refuses a nonsensical value, not only the build. Distinct from
    # ``preserves_guarantee`` (a DEFAULT-only check): a value may be a deliberate, audited policy
    # choice (disabling a boolean guarantee) yet still have to be *in range* (a share in (0, 1]).
    valid: Callable[[Any], bool] | None = None

    def coerce(self, value: Any) -> Any:
        """Validate ``value`` against this key's declared type + domain and return the canonical
        form. Raises ``ConfigError`` on a type mismatch, a value outside a closed ``allowed`` set,
        or one that fails the ``valid`` domain predicate — never coerces silently across kinds (a
        string ``"true"`` is not a bool) and never accepts an out-of-range number (AC2: every
        change is validated against the declared schema)."""
        v = _coerce_kind(self.name, self.kind, value)
        if self.allowed is not None and v not in self.allowed:
            raise ConfigError(
                f"{self.name}: {v!r} is not one of {list(self.allowed)}")
        if self.valid is not None and not self.valid(v):
            raise ConfigError(f"{self.name}: {v!r} is outside the permitted range")
        return v

    def default_preserves_guarantee(self) -> bool:
        """Whether this key's default keeps the guarantee it governs intact (trivially True for a
        key that governs no switchable guarantee)."""
        return self.preserves_guarantee is None or bool(self.preserves_guarantee(self.default))


def _coerce_kind(name: str, kind: Kind, value: Any) -> Any:
    if kind == "bool":
        if isinstance(value, bool):
            return value
        raise ConfigError(f"{name}: expected a boolean, got {type(value).__name__}")
    if kind == "int":
        # a bool is an int in Python — reject it explicitly so `True` is not read as 1
        if isinstance(value, bool) or not isinstance(value, int):
            raise ConfigError(f"{name}: expected an integer, got {type(value).__name__}")
        return value
    if kind == "float":
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise ConfigError(f"{name}: expected a number, got {type(value).__name__}")
        f = float(value)
        if not math.isfinite(f):  # reject NaN/Infinity — they break == and any range check
            raise ConfigError(f"{name}: expected a finite number, got {value!r}")
        return f
    if kind == "str":
        if not isinstance(value, str):
            raise ConfigError(f"{name}: expected a string, got {type(value).__name__}")
        return value
    if kind == "str_list":
        if not isinstance(value, list) or not all(isinstance(x, str) for x in value):
            raise ConfigError(f"{name}: expected a list of strings")
        return list(value)
    raise ConfigError(f"{name}: unknown kind {kind!r}")  # unreachable for a well-formed schema


def _keys(*keys: ConfigKey) -> dict[str, ConfigKey]:
    return {k.name: k for k in keys}


# The default filesystem-noise exclusion patterns (FR-6, Story 2.7): OS/editor detritus that is
# never a pièce — matched against a file's basename with fnmatch (globs allowed). This is the
# authoritative default for the `exclusion_list` config key AND the fallback for direct ingestion
# callers; a tenant may replace it wholesale via `set_config` (configuration-as-data, AD-24).
DEFAULT_EXCLUSION_LIST = [
    ".DS_Store", "Thumbs.db", "desktop.ini", ".gitkeep",  # classic OS / VCS-placeholder noise
    "~$*", ".~lock.*",                                     # Office / LibreOffice lock files
    "._*",                                                 # AppleDouble forks (incl. __MACOSX/)
]


# ── The schema (AD-24's bind list). Ordered as the surface presents it. ────────────────────────
CONFIG_SCHEMA: dict[str, ConfigKey] = _keys(
    ConfigKey(
        "interface_language", "str", "fr",
        governs="the interface language the tenant's users see",
        allowed=("fr", "en", "de", "lb"),  # France + Luxembourg (de/lb) markets
    ),
    ConfigKey(
        "mfa_required", "bool", False,
        governs="whether a second factor (TOTP) is demanded of the tenant's users (FR-48)",
    ),
    ConfigKey(
        "model_provider", "str", "mistral",
        governs="which inference provider serves the judgment LLM (AD-27)",
    ),
    ConfigKey(
        "model_endpoint", "str", "https://api.mistral.ai/v1",
        governs="the OpenAI-compatible endpoint the inference profile calls (AD-27) — a "
                "tenant's non-default value is honoured by the live judge",
        affects_retrieval=True,
    ),
    ConfigKey(
        "model_name", "str", "mistral-small-latest",
        governs="the model the inference endpoint serves (AD-27)",
        affects_retrieval=True,
    ),
    # No `chunking_config_version` config key (AD-40, and the Story 2.8 lesson for the embedder): a
    # free-string version a tenant could set independently of the chunking PARAMS can lie — it would
    # stamp e.g. "v1" on chunks a different configuration actually produced. Instead the chunking
    # parameters are configuration-as-data and the version is DERIVED from them
    # (`chunking.ChunkingConfig.version`), so the identity on every chunk cannot diverge from what
    # produced the chunks. The values themselves await the 2.13 chunk-yield measurement.
    ConfigKey(
        "chunking_target_chars", "int", 1200,
        governs="the target passage size in characters the deterministic chunker aims for; its "
                "content-derived identity is carried into every chunk id (FR-11/AD-40)",
        valid=lambda v: 100 <= v <= 100_000,  # a real passage size; the value awaits the 2.13 run
        affects_retrieval=True,
    ),
    # No embedder config keys (AD-11: "no configuration-as-data key … selects one"). The ONE
    # embedder is hardcoded (`Bgem3Embedder`); its own `model_id`/`model_version` stamp every chunk
    # (so the stamp cannot diverge from the model that produced the vector — AD-11 detectability),
    # and the vector width is the frozen `models.EMBEDDING_DIM`, asserted at admission (Story 2.8).
    ConfigKey(
        "backup_interval_hours", "int", 24,
        governs="the interval within which a backup must succeed before the tenant is flagged "
                "overdue (AD-32)",
        valid=lambda v: 1 <= v <= 8760,  # 1 hour … 1 year — a real cadence, never nonsensical
    ),
    ConfigKey(
        "configured_sources", "str_list", [],
        governs="the enumerated data sources a corpus may be drawn from (AD-16)",
    ),
    ConfigKey(
        "exclusion_list", "str_list", DEFAULT_EXCLUSION_LIST,
        governs="filesystem-noise filename patterns excluded from ingestion (FR-6)",
    ),
    ConfigKey(
        "taxonomy", "str_list", [],
        governs="the tenant's classification taxonomy (seeded at provisioning)",
        # Every label is a non-blank string, and the `unlabelled` sentinel is RESERVED (FR-40): a
        # real category may never collide with the explicit absence value (per-pièce labelling reads
        # this list to validate an assignment against it — Story 4.5).
        valid=lambda v: all(isinstance(x, str) and x.strip() and x != UNLABELLED for x in v),
    ),
    # ── import-job capacity bounds (AD-17): configuration-as-data, never hard-coded, each a
    # failure-register class rather than an outage ──
    ConfigKey(
        "import_unit_max_bytes", "int", 209_715_200,  # 200 MiB — a single pièce over this is
        governs="the per-unit size ceiling above which an import unit becomes a "
                "`resource-exhausted` register entry rather than being read whole into memory "
                "(AD-17)",
        valid=lambda v: 1 <= v <= 8_589_934_592,  # 1 byte … 8 GiB — a real ceiling, never nonsense
    ),
    ConfigKey(
        "import_max_attempts", "int", 3,
        governs="the number of attempts after which a unit that keeps killing the worker is "
                "quarantined as its own register entry and the job proceeds (AD-17)",
        valid=lambda v: 1 <= v <= 100,  # at least one attempt; a sane upper bound
    ),
    # ── container-expansion bounds (AD-17/AD-38): a breach is a `container-unopenable` register
    # entry of cardinality `unknown`, never an outage or an OOM ──
    ConfigKey(
        "container_max_depth", "int", 6,
        governs="the maximum nesting depth of containers expanded; a container deeper than this "
                "is a `container-unopenable` register entry, never recursed (AD-17)",
        valid=lambda v: 1 <= v <= 64,  # at least one level; a sane ceiling against runaway nesting
    ),
    ConfigKey(
        "container_max_members", "int", 5000,
        governs="the maximum members expanded from one top-level unit, so a container fan-out "
                "cannot exhaust the machine (AD-17)",
        valid=lambda v: 1 <= v <= 1_000_000,
    ),
    ConfigKey(
        "container_max_expansion_ratio", "int", 100,
        governs="the maximum ratio of total expanded bytes to a container's own size; a container "
                "exceeding it is a `container-unopenable` entry — a zip bomb, not an outage",
        valid=lambda v: 1 <= v <= 100_000,  # 1:1 … a generous ceiling, legit archives well under
    ),
    ConfigKey(
        "attachments_per_message_max", "int", 1000,
        governs="the maximum attachments expanded from one email/message before it is a "
                "`container-unopenable` entry (AD-17)",
        valid=lambda v: 1 <= v <= 100_000,
    ),
    # ── the retained-ranking-versions bound (Story 4.7, FR-16): unbounded versioning against a
    # never-delete rule (AD-7) is unbounded state, so retention is bounded by config. Versions
    # referenced by a bound/pin/export/audit are EXEMPT; the retirement of over-bound versions is a
    # `retired` state transition through AD-7's one admin entry point (deferred, never a DELETE). ──
    ConfigKey(
        "retained_ranking_versions_max", "int", 20,
        governs="the number of ranking versions retained per matter before old, unreferenced ones "
                "may be retired (FR-16) — a never-delete-safe capacity bound",
        valid=lambda v: 1 <= v <= 100_000,  # at least one version kept; a sane ceiling
    ),
    # ── the line's recall-first placement policy (Story 4.8, FR-17): config-as-data. The tool
    # recommends the cut after the deepest pièce whose stage-2 band is a retain-band. Recall over
    # precision — the UNCERTAIN band is retained by default, never discarded. Every entry must be a
    # real Band value, so an unknown band can never silently widen or void the cut. ──
    ConfigKey(
        "line_retain_bands", "str_list", ["confident-relevant", "uncertain"],
        governs="the stage-2 bands the recommended line retains (Story 4.8/FR-17) — recall-first: "
                "the cut falls after the deepest pièce in one of these bands",
        valid=lambda v: bool(v) and all(x in _BAND_VALUES for x in v),  # non-empty, real bands only
        # This key decides WHERE the recommended cut falls, so changing it makes an already-placed
        # line — and any confidence bound drawn over the population that line defines — stale
        # (FR-58's "a configuration change affecting retrieval, ranking or the estimator"). Without
        # the flag a firm could widen the retain policy and the committed line would keep reading
        # fresh, which is the failure AD-23 is written for.
        affects_retrieval=True,
    ),
    # ── the two switchable guarantees — the v1 defects, encoded as build-checked predicates ──
    ConfigKey(
        "off_corpus_refusal_enabled", "bool", True,
        governs="the honest 'not in the corpus' refusal (AD-20) — never a similarity guess",
        preserves_guarantee=lambda v: v is True,  # v1 shipped this gate DISABLED by default
        affects_retrieval=True,
    ),
    ConfigKey(
        "cascade_stage3_max_share", "float", 0.5,
        governs="the ceiling on the share of a matter that may reach the LLM stage (AD-18) — the "
                "system's biggest cost and egress",
        # WRITE domain: a share must be a real fraction in (0, 1] — 1.0 is the deliberate widest
        # policy (audited), but 0, negative, >1 or non-finite are nonsense and are refused on set.
        valid=lambda v: 0.0 < v <= 1.0,
        # DEFAULT must keep the guarantee on: strictly < 1 (v1's off-corpus gate shipped disabled;
        # a default of 1.0 would send everything to the LLM). Checked on the default by the build.
        preserves_guarantee=lambda v: 0.0 < v < 1.0,
        affects_retrieval=True,
    ),
    ConfigKey(
        "similarity_threshold", "float", 0.3,
        governs="the minimum cosine similarity a semantic (suggestive) result must meet; recorded "
                "on every result set (FR-12/AD-20). Semantic retrieval NEVER proves absence.",
        # WRITE domain: a cosine similarity lives in [-1, 1].
        valid=lambda v: -1.0 <= v <= 1.0,
        # DEFAULT must keep retrieval ON: a threshold of 1.0 admits only vectors identical to the
        # query — i.e. nothing — which is the v1 off-corpus-gate-disabled shape (addendum §4). The
        # value itself awaits the Story 2.13 measurement + Epic 4 gold-set tuning.
        preserves_guarantee=lambda v: v < 1.0,
        affects_retrieval=True,
    ),
    # ── the relevance-cascade stage-2 band boundaries (Story 4.2, FR-38/AD-18): config-as-data.
    # Stage 2 scores each representative pièce (cosine to the case-theory vector) and bands it:
    # score ≥ HIGH → confident-relevant, ≤ LOW → confident-discard, between → the UNCERTAIN band the
    # LLM judges. LOW < HIGH is asserted where the config is read (a cross-key relation a single-key
    # predicate cannot express). The VALUES await the Epic-4 gold-set tuning. ──
    ConfigKey(
        "cascade_uncertain_low", "float", 0.35,
        governs="the stage-2 score at/below which a pièce is confident-discard; between this and "
                "cascade_uncertain_high is the uncertain band the LLM judges (FR-38/AD-18)",
        valid=lambda v: -1.0 <= v <= 1.0,  # a cosine threshold
        # DEFAULT keeps an interior band (not collapsed onto a cosine extreme, which would band
        # everything one way and defeat the cascade's cost guarantee).
        preserves_guarantee=lambda v: -1.0 < v < 1.0,
        affects_retrieval=True,
    ),
    ConfigKey(
        "cascade_uncertain_high", "float", 0.65,
        governs="the stage-2 score at/above which a pièce is confident-relevant; below it and "
                "above cascade_uncertain_low is the uncertain band the LLM judges (FR-38/AD-18)",
        valid=lambda v: -1.0 <= v <= 1.0,
        preserves_guarantee=lambda v: -1.0 < v < 1.0,
        affects_retrieval=True,
    ),
    ConfigKey(
        "cascade_calibration_sample", "int", 20,
        governs="the number of confident-band pièces sampled INTO the LLM stage per run so the "
                "cascade's own calibration is measurable (FR-38/AD-18) — a mandatory sample",
        valid=lambda v: 0 <= v <= 100_000,
        # DEFAULT keeps the mandatory sample non-empty: calibration cannot be measured from zero
        # confident-band judgements. A tenant may not silently switch it off.
        preserves_guarantee=lambda v: v > 0,
        affects_retrieval=True,
    ),
    # ── FR-23's unfitness threshold (Story 5.4): when the sample comes back mostly relevant, the
    # finding is about the ORDER, not about where it was cut. ──
    ConfigKey(
        "unfit_relevant_share", "float", 0.5,
        governs="the share of a sampling run's judged units that, once relevant, declares the "
                "ranking version UNFIT for this matter — the product then says so in words, offers "
                "a re-rank with a revised case theory, and does NOT offer a line move (FR-23)",
        # WRITE domain: a share of a sample. Zero would declare every run unfit including one that
        # found nothing; above 1 is unreachable and would silently switch the declaration off.
        valid=lambda v: 0.0 < v <= 1.0,
        # DEFAULT keeps the declaration reachable: at 1.0 only a sample that came back relevant to
        # the last unit would ever trigger it, which is the "switched off in all but one case"
        # shape. Half is the stated rule — at or above half, the order is not ordering.
        preserves_guarantee=lambda v: v < 1.0,
    ),
)

# Keys provisioning may seed as part of establishing a tenant (AD-25 names the taxonomy).
PROVISIONED_KEYS: tuple[str, ...] = ("taxonomy",)


def is_known(key: str) -> bool:
    return key in CONFIG_SCHEMA


def require_key(key: str) -> ConfigKey:
    spec = CONFIG_SCHEMA.get(key)
    if spec is None:
        raise ConfigError(f"unknown configuration key {key!r}")
    return spec


def coerce(key: str, value: Any) -> Any:
    """Validate a value for a known key, or raise ``ConfigError`` (unknown key or bad value)."""
    return require_key(key).coerce(value)


def default_of(key: str) -> Any:
    return require_key(key).default


def default_config() -> dict[str, Any]:
    """Every key at its default — the configuration of a freshly provisioned, never-edited
    tenant."""
    return {name: spec.default for name, spec in CONFIG_SCHEMA.items()}


@dataclass(frozen=True)
class ExpansionBounds:
    """The container-expansion capacity bounds (AD-17) as one value object, so the ingestion use
    case and the expander adapters share exactly the configured numbers — never a hard-coded
    constant. Built from a tenant's config by ``expansion_bounds``; ``defaults()`` gives the
    freshly-provisioned values for callers with no tenant in hand (tests, the sync path)."""

    max_depth: int
    max_members: int
    max_expansion_ratio: int
    attachments_per_message_max: int

    @classmethod
    def defaults(cls) -> ExpansionBounds:
        return cls(
            max_depth=default_of("container_max_depth"),
            max_members=default_of("container_max_members"),
            max_expansion_ratio=default_of("container_max_expansion_ratio"),
            attachments_per_message_max=default_of("attachments_per_message_max"),
        )


def expansion_bounds(get: Callable[[str], Any]) -> ExpansionBounds:
    """Build the bounds from a per-key getter (e.g. ``lambda k: store.get_config(tenant, k)``)."""
    return ExpansionBounds(
        max_depth=int(get("container_max_depth")),
        max_members=int(get("container_max_members")),
        max_expansion_ratio=int(get("container_max_expansion_ratio")),
        attachments_per_message_max=int(get("attachments_per_message_max")),
    )


@dataclass(frozen=True)
class CascadeConfig:
    """The relevance-cascade's stage boundaries (Story 4.2, FR-38/AD-18) as one value object, built
    from a tenant's configuration-as-data — so the cascade orchestrator and any future ranking act
    share exactly the configured numbers, never a hard-coded constant. ``defaults()`` gives the
    freshly-provisioned values for callers with no tenant in hand (tests)."""

    uncertain_low: float
    uncertain_high: float
    calibration_sample: int
    stage3_max_share: float

    def __post_init__(self) -> None:
        # LOW < HIGH is a cross-key relation a single-key ``preserves_guarantee`` cannot express:
        # a degenerate band (low ≥ high) would leave no uncertain band OR invert the confident
        # bands. Refuse it here, where the config is assembled (AD-25: never a silent nonsense).
        if not self.uncertain_low < self.uncertain_high:
            raise ConfigError(
                f"cascade band inverted: cascade_uncertain_low ({self.uncertain_low}) must be "
                f"strictly below cascade_uncertain_high ({self.uncertain_high})")

    def band_of(self, score: float) -> str:
        """The stage-2 band a score falls in: 'confident-relevant' at/above HIGH, 'confident-
        discard' at/below LOW, else 'uncertain' (the band the LLM judges)."""
        if score >= self.uncertain_high:
            return "confident-relevant"
        if score <= self.uncertain_low:
            return "confident-discard"
        return "uncertain"

    @classmethod
    def defaults(cls) -> CascadeConfig:
        return cls(
            uncertain_low=default_of("cascade_uncertain_low"),
            uncertain_high=default_of("cascade_uncertain_high"),
            calibration_sample=default_of("cascade_calibration_sample"),
            stage3_max_share=default_of("cascade_stage3_max_share"),
        )


def cascade_config(get: Callable[[str], Any]) -> CascadeConfig:
    """Build the cascade's stage boundaries from a per-key getter (e.g.
    ``lambda k: store.get_config(tenant, k)``)."""
    return CascadeConfig(
        uncertain_low=float(get("cascade_uncertain_low")),
        uncertain_high=float(get("cascade_uncertain_high")),
        calibration_sample=int(get("cascade_calibration_sample")),
        stage3_max_share=float(get("cascade_stage3_max_share")),
    )


# ── storage encoding: one JSON text value per (tenant, key) row ─────────────────────────────────
def dumps_value(value: Any) -> str:
    """Encode a validated value for the one text column the store holds it in (stable, sorted)."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def loads_value(raw: str) -> Any:
    return json.loads(raw)
