"""The fail-closed start-up gate (story 1.7, AD-31).

Encryption is split across two layers, and the deployment refuses to start unless BOTH are
in place — no permissive default, no warning-and-continue:

  1. the **application-layer key** (``APX_ENCRYPTION_KEY``) — present, and decoding to a
     usable 32-byte AES-256 key; this is what encrypts every content-bearing column; and
  2. the **data volume** — attested encrypted (``APX_VOLUME_ENCRYPTED``), the layer that
     protects the two named searchable surfaces (the ``halfvec`` column and the deterministic
     text index) that cannot themselves be application-encrypted.

The application cannot portably *prove* block-device encryption from inside a container, so
the volume layer is an explicit, **non-default** operator attestation — the same
deployment-attestation pattern as ``APX_COOKIE_SECURE``/``APX_TRUST_FORWARDED_FOR`` — that
must be backed by real dm-crypt/LUKS (single-machine install) or provider-managed volume
encryption (hosted). The cryptographic teeth are the key gate above, which is real.

``startup_gate`` is a pure function (unit-testable per branch) wired into the FastAPI
``lifespan`` — so a real boot exercises it, while ``from apx.api.app import app`` stays
importable in test collection.
"""

from __future__ import annotations

import os
from collections.abc import Mapping

from apx.core.domain.crypto import MissingEncryptionKey, load_key_from_env

_VOLUME_ENV = "APX_VOLUME_ENCRYPTED"
_TRUTHY = ("1", "true", "yes")


class StartupRefused(RuntimeError):
    """Start-up is refused because an encryption layer is not in place (AD-31)."""


def _volume_attested(env: Mapping[str, str]) -> bool:
    return env.get(_VOLUME_ENV, "").strip().lower() in _TRUTHY


def startup_gate(env: Mapping[str, str] | None = None) -> None:
    """Refuse to start unless both encryption layers are in place. Raises
    :class:`StartupRefused` naming every missing layer; returns ``None`` when the deployment
    is safe to serve. No permissive default — absence is refusal."""
    source = os.environ if env is None else env
    problems: list[str] = []
    try:
        load_key_from_env(source)  # application-layer encryption key (AD-31 layer 1)
    except MissingEncryptionKey as exc:
        problems.append(f"application encryption key: {exc}")
    if not _volume_attested(source):  # data-volume encryption (AD-31 layer 2)
        problems.append(
            f"data volume is not attested as encrypted (set {_VOLUME_ENV}=1, backed by "
            "dm-crypt/LUKS or a provider-managed encrypted volume)"
        )
    if problems:
        raise StartupRefused(
            "APX refuses to start — encryption is not fully in place (AD-31): "
            + "; ".join(problems)
        )
