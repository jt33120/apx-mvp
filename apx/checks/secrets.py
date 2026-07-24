"""Secret-management structural properties (story 1.8; AD-47, FR-51/FR-56). Two static checks:

- **no_secret_in_source:** no secret VALUE appears in the shipping source (`apx/`, excluding the
  bundled web assets) or in committed/example configuration — a known credential pattern (a
  GitHub PAT, an ``sk-``/``AKIA``/``xox…`` token, a PEM private key) or a bare high-entropy token.
  It does not fire on an environment *reference* or a ``${VAR}``/``:?``/``:-`` placeholder. This
  is the mistake that ends a client relationship; it fails the build.
- **no_secret_column_in_models:** no model column stores a provider credential / API key / raw
  key — secrets live in the environment, never in a store that is dumped, logged or exported.

Both fail closed on a file that cannot be read. The seeded-secret RAW-STORE and LOG assertions
(a secret must appear in no store and no log line) are runtime tests, not these static checks.
"""

from __future__ import annotations

import math
import re
from collections.abc import Iterable
from pathlib import Path

from sqlalchemy import MetaData

from apx.checks.import_contracts import CheckResult
from apx.checks.tenant_isolation import _base_metadata

_REPO_ROOT = Path(__file__).resolve().parents[2]

# Named credential shapes — an unambiguous real secret wherever it appears.
_CREDENTIAL_PATTERNS = {
    "GitHub token": re.compile(r"gh[posru]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}"),
    "OpenAI/Anthropic key": re.compile(r"sk-(?:ant-)?[A-Za-z0-9_-]{20,}"),
    "AWS access key": re.compile(r"AKIA[0-9A-Z]{16}"),
    "Slack token": re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),
    "GitLab token": re.compile(r"glpat-[A-Za-z0-9_-]{20}"),
    "PEM private key": re.compile(r"-----BEGIN (?:[A-Z]+ )?PRIVATE KEY-----"),
}
# A bare high-entropy token (a provider key with no recognizable prefix — the dangerous case).
# `=` is not a mid-token char (only base64 trailing padding), so `key=Value` code is not glued
# into one long token.
_TOKEN = re.compile(r"[A-Za-z0-9+/_-]{28,}={0,2}")
# In Python, a secret is a STRING LITERAL — scan quoted contents only, so long code identifiers
# (`response_model=AuditTrailOut`) are never mistaken for a token. Config values are scanned whole.
_QUOTED = re.compile(r"""["']([^"'\s]{24,})["']""")
_ENTROPY_BITS = 4.0
# A line that is an env reference or a placeholder carries no secret value — skip the entropy leg
# (never the named-pattern leg: a real PAT next to a placeholder is still a real PAT).
_ENV_REF = re.compile(r"environ|getenv|\$\{|:-|:\?|<[A-Za-z]|example|placeholder|changeme|xxxx")
# A URL / XML-namespace / DSN is not a secret (its path segments are high-entropy but public).
_URLISH = re.compile(r"://|xmlns|schemas\.|www\.|\.(?:org|com|net|io|ai|gov|edu)\b")
# Committed configuration scanned in addition to apx/ source.
_CONFIG_FILES = (
    "pyproject.toml", "Dockerfile", "docker-compose.yml", "docker/entrypoint.sh",
    "alembic.ini", ".github/workflows/ci.yml",
)
_TEXT_SUFFIXES = {".py", ".toml", ".yml", ".yaml", ".sh", ".ini", ".env", ".example", ".cfg"}


def _shannon_entropy(s: str) -> float:
    counts = {c: s.count(c) for c in set(s)}
    n = len(s)
    return -sum((k / n) * math.log2(k / n) for k in counts.values())


def _default_targets() -> list[Path]:
    files = [
        p for p in (_REPO_ROOT / "apx").rglob("*.py") if "web" not in p.parts
    ]
    files += [_REPO_ROOT / name for name in _CONFIG_FILES if (_REPO_ROOT / name).is_file()]
    files += [p for p in _REPO_ROOT.glob("*.example")]
    return files


def _iter_targets(roots: Iterable[Path]) -> Iterable[Path]:
    for root in roots:
        if root.is_dir():
            for path in sorted(root.rglob("*")):
                if path.is_file() and (path.suffix in _TEXT_SUFFIXES or path.name == "Dockerfile"):
                    yield path
        elif root.is_file():
            yield root


def _scan_line(line: str) -> str | None:
    """Return a description of the secret found on this line, or None. The named-credential leg
    runs on the whole line (a leaked PAT is a leak even in a comment); the bare-token leg runs
    only on QUOTED string contents (a secret in source is a string literal — code identifiers,
    file paths and comments are not quoted, so they never false-positive)."""
    for label, pattern in _CREDENTIAL_PATTERNS.items():
        if pattern.search(line):
            return f"looks like a {label}"
    if _ENV_REF.search(line):
        return None  # an env reference / placeholder carries no secret value
    for chunk in _QUOTED.findall(line):
        if _URLISH.search(chunk):
            continue  # a URL / namespace / DSN, not a secret
        for token in _TOKEN.findall(chunk):
            if _shannon_entropy(token) >= _ENTROPY_BITS:
                return f"a high-entropy token ({len(token)} chars) that looks like a secret"
    return None


def no_secret_in_source(roots: Iterable[Path] | None = None) -> CheckResult:
    """No secret value appears in source or committed/example configuration (FR-51/FR-56)."""
    name, ad = "no secret in source or committed config", "AD-47"
    targets = list(_iter_targets(roots)) if roots is not None else _default_targets()
    for path in targets:
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return CheckResult(name, ad, False,
                               f"cannot read {path.name} (failing closed, cannot verify)")
        for lineno, line in enumerate(text.splitlines(), 1):
            found = _scan_line(line)
            if found is not None:
                rel = path.relative_to(_REPO_ROOT) if path.is_relative_to(_REPO_ROOT) else path
                return CheckResult(name, ad, False,
                                   f"{rel}:{lineno} {found} — secrets live in the environment, "
                                   "never in source or committed config (FR-51/AD-47)")
    return CheckResult(name, ad, True,
                       f"no secret value in {len(targets)} source/config file(s)")


# Column-name shapes that would mean a provider credential / raw key is stored in a data store.
_FORBIDDEN_SECRET_COLUMNS = (
    "api_key", "apikey", "api_secret", "access_token", "refresh_token",
    "private_key", "encryption_key", "secret_key", "client_secret",
)


def no_secret_column_in_models(metadata: MetaData | None = None) -> CheckResult:
    """No model column stores a provider credential / API key / raw key (AD-47). Secrets live in
    the environment. (`mfa_secret` is a TOTP shared secret, encrypted, and not in this set.)"""
    name, ad = "no secret column in the data model", "AD-47"
    tables = (metadata if metadata is not None else _base_metadata()).tables
    for tname, table in tables.items():
        for col in table.columns:
            low = col.name.lower()
            if any(pat in low for pat in _FORBIDDEN_SECRET_COLUMNS):
                return CheckResult(name, ad, False,
                                   f"{tname}.{col.name} looks like a stored credential/key — "
                                   "secrets are held in the environment, never in a store that is "
                                   "dumped, logged or exported (AD-47)")
    return CheckResult(name, ad, True, "no provider-credential or key column in the data model")


def run() -> list[CheckResult]:
    return [no_secret_in_source(), no_secret_column_in_models()]
