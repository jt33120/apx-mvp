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
    ConfigKey(
        "chunking_config_version", "str", "v1",
        governs="the chunking configuration identity carried into every chunk id (AD-9/AD-40)",
        affects_retrieval=True,
    ),
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
        "exclusion_list", "str_list", [],
        governs="filename/path patterns excluded from ingestion",
    ),
    ConfigKey(
        "taxonomy", "str_list", [],
        governs="the tenant's classification taxonomy (seeded at provisioning)",
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


# ── storage encoding: one JSON text value per (tenant, key) row ─────────────────────────────────
def dumps_value(value: Any) -> str:
    """Encode a validated value for the one text column the store holds it in (stable, sorted)."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def loads_value(raw: str) -> Any:
    return json.loads(raw)
