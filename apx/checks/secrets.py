"""Secret-management structural properties (story 1.8; AD-47, FR-51/FR-56). Two static checks:

- **no_secret_in_source:** no secret VALUE appears in the shipping source (`apx/`) or in
  committed configuration (`docker/`, `deploy/`, `.github/`, the root config files) — a named
  credential (a GitHub PAT, an ``sk-``/``AKIA``/``xox…`` token, a PEM key), a bare high-entropy
  token, a **pure-hex key** (the app's own key format — low per-char entropy, caught by length),
  or a real password embedded in a DSN. Quoted literals AND unquoted config values are scanned;
  a placeholder / env-reference / URL is not flagged. Test files are scanned for named
  credentials only (they legitimately carry high-entropy fixtures). Fails closed on an
  unreadable file.
- **no_secret_column_in_models:** no model column stores a provider credential / key / token —
  secrets live in the environment, never in a store that is dumped, logged or exported.
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
# a bare high-entropy token (≥24 chars); a pure-hex key (≥32, caught by length not entropy)
_TOKEN = re.compile(r"[A-Za-z0-9+/_-]{24,}={0,2}")
_HEX = re.compile(r"\A[0-9a-fA-F]{32,}\Z")
_QUOTED = re.compile(r"""["']([^"'\s]{20,})["']""")      # a quoted string literal's contents
_ASSIGN_RHS = re.compile(r"""[:=]\s*([^\s#'"]{20,})""")  # an unquoted config value after = or :
_URL_PASSWORD = re.compile(r"://[^:/@\s]+:([^@/\s]{8,})@")  # the password in a user:pass@ DSN
_ENTROPY_BITS = 4.0
# A chunk that is an env reference or a placeholder carries no secret value.
_ENV_REF = re.compile(
    r"environ|getenv|\$\{|\$\(|:-|:\?|<[A-Za-z]|example|placeholder|changeme|xxxx")
# A URL / XML namespace / DSN body is not itself a secret (its embedded password is handled apart).
_URLISH = re.compile(r"://|xmlns|schemas\.|www\.|\.(?:org|com|net|io|ai|gov|edu)\b")

_TEXT_SUFFIXES = {".py", ".toml", ".yml", ".yaml", ".sh", ".ini", ".env", ".example", ".cfg",
                  ".json", ".pem", ".key", ".crt"}
_FULL_SCAN_DIRS = ("apx", "docker", "deploy", ".github")
_ROOT_CONFIG = ("pyproject.toml", "Dockerfile", "docker-compose.yml", "alembic.ini")
# Never scanned: vendored / generated / tooling / planning trees.
_EXCLUDE_PARTS = {"web", "node_modules", ".venv", ".git", "_bmad", "_bmad-output", ".claude"}


def _shannon_entropy(s: str) -> float:
    counts = {c: s.count(c) for c in set(s)}
    n = len(s)
    return -sum((k / n) * math.log2(k / n) for k in counts.values())


def _token_is_secret(token: str, *, hex_ok: bool) -> bool:
    if _URLISH.search(token):
        return False
    if hex_ok and _HEX.match(token):
        return True  # a pure-hex key — the app accepts hex keys, whose entropy sits below 4.0
    return bool(_TOKEN.fullmatch(token)) and _shannon_entropy(token) >= _ENTROPY_BITS


def _scan_line(line: str, *, mode: str, is_python: bool) -> str | None:
    """`mode` is 'full' (named + token legs) or 'named' (named-credential patterns only, for
    test files). Named patterns run on the whole line; the token legs run per-chunk so a
    placeholder elsewhere on the line cannot excuse a real token beside it. Python lines get the
    quoted leg only (bare code is not a value); config lines also get the unquoted-value leg."""
    for label, pattern in _CREDENTIAL_PATTERNS.items():
        if pattern.search(line):
            return f"looks like a {label}"
    if mode != "full":
        return None
    # a real password embedded in a DSN (the URL body is skipped, but not its credential); the
    # regex already requires ≥8 chars, and a non-placeholder user:pass@ in committed config is
    # a secret regardless of entropy (a short test password like `apxci` is not captured).
    for password in _URL_PASSWORD.findall(line):
        if not _ENV_REF.search(password):
            return "a password embedded in a connection URL"
    chunks = [(c, True) for c in _QUOTED.findall(line)]
    if not is_python:
        chunks += [(c, False) for c in _ASSIGN_RHS.findall(line)]  # unquoted config values
    for chunk, quoted in chunks:
        if _ENV_REF.search(chunk) or _URLISH.search(chunk):
            continue
        for token in _TOKEN.findall(chunk):
            # hex leg only for quoted values (an unquoted git SHA lives in a `uses:` line)
            if _token_is_secret(token, hex_ok=quoted):
                return f"a high-entropy token ({len(token)} chars) that looks like a secret"
    return None


def _scannable(path: Path) -> bool:
    return (path.suffix in _TEXT_SUFFIXES or path.name in ("Dockerfile", "Procfile")) and not (
        set(path.parts) & _EXCLUDE_PARTS)


def _default_targets() -> list[tuple[Path, str]]:
    targets: list[tuple[Path, str]] = []
    for base in _FULL_SCAN_DIRS:
        root = _REPO_ROOT / base
        if root.is_dir():
            targets += [(p, "full") for p in sorted(root.rglob("*"))
                        if p.is_file() and _scannable(p)]
    targets += [(_REPO_ROOT / n, "full") for n in _ROOT_CONFIG if (_REPO_ROOT / n).is_file()]
    targets += [(p, "full") for p in sorted(_REPO_ROOT.glob("*.example")) if p.is_file()]
    # test files: named-credential leg only (they carry legitimate high-entropy fixtures)
    tests = _REPO_ROOT / "tests"
    if tests.is_dir():
        targets += [(p, "named") for p in sorted(tests.rglob("*.py"))
                    if "_fixtures" not in p.parts]
    seen: set[Path] = set()
    return [(p, m) for p, m in targets if not (p in seen or seen.add(p))]


def _iter_targets(roots: Iterable[Path]) -> list[tuple[Path, str]]:
    out: list[tuple[Path, str]] = []
    for root in roots:
        if root.is_dir():
            out += [(p, "full") for p in sorted(root.rglob("*")) if p.is_file() and _scannable(p)]
        elif root.is_file():
            out.append((root, "full"))
    return out


def no_secret_in_source(roots: Iterable[Path] | None = None) -> CheckResult:
    """No secret value appears in source or committed/example configuration (FR-51/FR-56)."""
    name, ad = "no secret in source or committed config", "AD-47"
    targets = _iter_targets(roots) if roots is not None else _default_targets()
    for path, mode in targets:
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return CheckResult(name, ad, False,
                               f"cannot read {path.name} (failing closed, cannot verify)")
        is_python = path.suffix == ".py"
        for lineno, line in enumerate(text.splitlines(), 1):
            found = _scan_line(line, mode=mode, is_python=is_python)
            if found is not None:
                rel = path.relative_to(_REPO_ROOT) if path.is_relative_to(_REPO_ROOT) else path
                return CheckResult(name, ad, False,
                                   f"{rel}:{lineno} {found} — secrets live in the environment, "
                                   "never in source or committed config (FR-51/AD-47)")
    return CheckResult(name, ad, True, f"no secret value in {len(targets)} source/config file(s)")


# Column-name shapes that would mean a provider credential / raw key / token is stored.
_FORBIDDEN_SECRET_COLUMNS = (
    "api_key", "apikey", "api_secret", "access_token", "refresh_token", "bearer",
    "private_key", "encryption_key", "secret_key", "client_secret", "webhook",
    "token", "credential", "passphrase", "key_material", "dsn",
)
# Columns whose name matches a shape above but are legitimately present (a one-way hash; an
# encrypted TOTP shared secret, AD-15) — matched by EXACT name.
_ALLOWED_SECRET_ISH = {"mfa_secret", "password_hash", "text_key", "chunking_config_version"}


def no_secret_column_in_models(metadata: MetaData | None = None) -> CheckResult:
    """No model column stores a provider credential / key / token (AD-47). Secrets live in the
    environment. `mfa_secret`/`password_hash` (encrypted TOTP secret; one-way hash) are allowed."""
    name, ad = "no secret column in the data model", "AD-47"
    tables = (metadata if metadata is not None else _base_metadata()).tables
    for tname, table in tables.items():
        for col in table.columns:
            low = col.name.lower()
            if low in _ALLOWED_SECRET_ISH:
                continue
            if any(pat in low for pat in _FORBIDDEN_SECRET_COLUMNS):
                return CheckResult(name, ad, False,
                                   f"{tname}.{col.name} looks like a stored credential/key/token — "
                                   "secrets are held in the environment, never in a store that is "
                                   "dumped, logged or exported (AD-47)")
    return CheckResult(name, ad, True, "no provider-credential, key or token column in the model")


def run() -> list[CheckResult]:
    return [no_secret_in_source(), no_secret_column_in_models()]
