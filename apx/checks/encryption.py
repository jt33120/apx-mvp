"""Encryption structural properties (story 1.7; AD-31, AD-33). Two static checks:

- **sensitive_columns_are_encrypted (allowlist model):** EVERY string-typed (``String``/``Text``,
  including a ``Mapped[str]`` column with an inferred type) model column must be ``EncryptedText``
  UNLESS its name is on an explicit plaintext allowlist (routing/identity/categorical keys, the
  searchable text index). So a NEW content-bearing column — any name, even one declared with an
  inferred type — is encrypted-by-default: leaving it plaintext fails the build unless someone
  consciously adds it to the allowlist. ``piece.full_text`` is additionally asserted NOT
  encrypted (the AD-31 named exception; encrypting it would break exhaustive search, FR-13).
- **startup_gate_is_fail_closed:** a static leg asserts the gate names both layers and raises,
  and — on the real gate — a BEHAVIOURAL leg actually executes ``startup_gate`` and asserts it
  refuses a missing-key and a missing-volume env (AST-sniffing alone is gameable by a
  warn-and-continue gate carrying an unrelated ``raise``).

Both fail closed on an unparseable file.
"""

from __future__ import annotations

import ast
from collections.abc import Iterable
from pathlib import Path

from apx.checks.import_contracts import CheckResult
from apx.checks.payload_schema import _fail_closed, _load_trees

_APX_ROOT = Path(__file__).resolve().parent.parent
_MODELS_FILE = _APX_ROOT / "adapters" / "store_postgres" / "models.py"
_STARTUP_FILE = _APX_ROOT / "api" / "startup.py"

_ENCRYPTED = "EncryptedText"
_STRING_TYPES = {"String", "Text", _ENCRYPTED}
# The AD-31 named exception — MUST NOT be application-encrypted (a searchable surface protected
# by volume encryption; encrypting it would break exhaustive search / the index).
_FORBIDDEN_ENCRYPTED = {("Piece", "full_text")}
# The ONLY string columns allowed to stay plaintext: routing/identity/categorical keys, the
# one-way password hash, operator-identity login fields, and the AD-31 exempt text index. Any
# other string column must be EncryptedText. Keep this list conscious and small — adding to it
# is the deliberate act of declaring a column non-content.
_PLAINTEXT_ALLOWLIST = {
    "id", "tenant", "matter", "scope", "user_id", "piece_id", "chunk_id", "job_id",
    "content_hash", "text_key", "text_identity",
    "extraction_method", "extractor_version", "schema_version", "text_version",
    "full_text_version", "chunking_config_version", "piece_date_status", "external_ref",
    "error_class", "resolution_state", "action", "chain", "label", "judge", "outcome",
    "email", "password_hash", "display_name",
    "full_text",  # the AD-31 exempt deterministic text index (also asserted un-encrypted below)
}
# Table-qualified plaintext columns — used where the bare name is too generic to allow globally.
# ``tenant_setting.key``/``value`` are configuration-as-data metadata (a language code, an
# endpoint, thresholds, taxonomy labels) — configuration the admin surface reads and DISPLAYS in
# the clear, comparable to the already-plaintext ``matter``/``scope`` names and less sensitive than
# a matter (client) name. Kept plaintext by conscious decision (weighed against a code review that
# flagged the free-text keys): the disk is covered by AD-31's volume layer; the audited
# before/after already lives in the encrypted ``audit_record.detail``; and application-encrypting
# it would couple config into 1.8's single-PK re-key/backfill machinery (``ENCRYPTED_COLUMNS``),
# which a rotation would silently skip on this composite-PK table — a rotation bug for marginal
# benefit on admin-set, admin-displayed values. Revisit (a cheap one-column change) if a key ever
# needs to hold client-secret content rather than operational config.
_PLAINTEXT_ALLOWLIST_QUALIFIED = {
    ("TenantSetting", "key"),
    ("TenantSetting", "value"),
    # Story 2.2 import-job ledger: operational, non-content columns. ``state`` is a categorical
    # lifecycle enum (like ``resolution_state``/``action``); ``spool_path`` is a server-internal
    # staging path (the data volume + a uuid job id — no matter/custodian/filename content). The
    # confidential columns on these tables (actor, custodian, case_theory, provenance_path) are
    # EncryptedText; these are kept plaintext by conscious decision.
    ("ImportJob", "state"),
    ("ImportJob", "spool_path"),
    ("ImportUnit", "state"),
}


def _column_type_name(value: ast.expr | None) -> str | None:
    """The type token of a ``mapped_column(TYPE, ...)`` call — the first positional arg's name
    (``EncryptedText`` from ``EncryptedText("ctx")``, ``Text``, ``String`` from ``String(64)``),
    or ``None`` when there is no positional type (the type is inferred from the annotation)."""
    if not (isinstance(value, ast.Call) and isinstance(value.func, ast.Name)
            and value.func.id == "mapped_column" and value.args):
        return None
    arg = value.args[0]
    if isinstance(arg, ast.Name):
        return arg.id
    if isinstance(arg, ast.Call) and isinstance(arg.func, ast.Name):
        return arg.func.id  # String(64) or EncryptedText("ctx")
    return None


def _annotation_is_str(annotation: ast.expr | None) -> bool:
    """True if the column annotation is ``Mapped[str]`` or ``Mapped[str | None]`` — i.e. a
    string column even when ``mapped_column`` has no positional type (SQLAlchemy infers String)."""
    if not (isinstance(annotation, ast.Subscript) and isinstance(annotation.value, ast.Name)
            and annotation.value.id == "Mapped"):
        return False
    inner = annotation.slice
    names = {n.id for n in ast.walk(inner) if isinstance(n, ast.Name)}
    return "str" in names


def _is_mapped_column(value: ast.expr | None) -> bool:
    return (isinstance(value, ast.Call) and isinstance(value.func, ast.Name)
            and value.func.id == "mapped_column")


def sensitive_columns_are_encrypted(roots: Iterable[Path] | None = None) -> CheckResult:
    """Every string column is EncryptedText unless allowlisted; the text index is not encrypted."""
    name, ad = "content-bearing columns are application-encrypted", "AD-31"
    roots = list(roots) if roots is not None else [_MODELS_FILE]
    trees, unparseable = _load_trees(roots)
    if unparseable:
        return _fail_closed(name, ad, unparseable)

    for _path, tree in trees:
        for cls in ast.walk(tree):
            if not isinstance(cls, ast.ClassDef):
                continue
            for stmt in cls.body:
                if not (isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name)
                        and _is_mapped_column(stmt.value)):
                    continue
                attr = stmt.target.id
                type_name = _column_type_name(stmt.value)
                if (cls.name, attr) in _FORBIDDEN_ENCRYPTED and type_name == _ENCRYPTED:
                    return CheckResult(name, ad, False,
                                       f"{cls.name}.{attr} is {_ENCRYPTED} — it is an AD-31 named "
                                       "exception (the searchable text index) and must stay "
                                       "plaintext; encrypting it breaks exhaustive search (FR-13)")
                string_capable = type_name in _STRING_TYPES or (
                    type_name is None and _annotation_is_str(stmt.annotation))
                allowed = attr in _PLAINTEXT_ALLOWLIST or (
                    cls.name, attr) in _PLAINTEXT_ALLOWLIST_QUALIFIED
                if string_capable and type_name != _ENCRYPTED and not allowed:
                    shown = type_name or "an inferred String"
                    return CheckResult(name, ad, False,
                                       f"{cls.name}.{attr} is {shown}, not {_ENCRYPTED}, and is "
                                       "not on the plaintext allowlist — a content-bearing column "
                                       "must be application-encrypted at rest (AD-31)")
    return CheckResult(name, ad, True,
                       "every string column is EncryptedText or an allowlisted key; the text "
                       "index is not encrypted")


def _find_gate(
    trees: Iterable[tuple[Path, ast.Module]],
) -> tuple[ast.FunctionDef, ast.Module] | None:
    for _path, tree in trees:
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "startup_gate":
                return node, tree
    return None


def _names_and_strings(tree: ast.Module) -> set[str]:
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            out.add(node.id)
        elif isinstance(node, ast.Attribute):
            out.add(node.attr)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            out.add(node.value)
    return out


def _gate_behaves_fail_closed() -> str | None:
    """Execute the REAL startup_gate: it must accept a fully-provisioned env and REFUSE a
    missing-key and a missing-volume env. Returns an error string on the first failure, else
    None. This is the ungameable leg — a warn-and-continue gate fails here even if it carries an
    unrelated ``raise`` that satisfies the AST leg."""
    import tempfile

    from apx.api.startup import StartupRefused, startup_gate
    from apx.core.domain.crypto import generate_key

    # a fully-provisioned env carries all three durability preconditions the gate now enforces:
    # the encryption key, the volume attestation (AD-31), and a writable head journal (AD-35).
    journal = f"{tempfile.mkdtemp(prefix='apx-gate-')}/heads.journal"
    good = {
        "APX_ENCRYPTION_KEY": generate_key(), "APX_VOLUME_ENCRYPTED": "1",
        "APX_HEAD_JOURNAL": journal,
    }
    try:
        startup_gate(good)
    except Exception as exc:  # noqa: BLE001 — any refusal of a good env is a failure
        return f"startup_gate refused a fully-provisioned env: {exc!r}"
    for label, bad in (
        ("a missing key", {"APX_VOLUME_ENCRYPTED": "1"}),
        ("a missing volume attestation", {"APX_ENCRYPTION_KEY": good["APX_ENCRYPTION_KEY"]}),
        ("an empty env", {}),
    ):
        try:
            startup_gate(bad)
            return f"startup_gate did NOT refuse {label} — not fail-closed (AD-31)"
        except StartupRefused:
            continue
    return None


def startup_gate_is_fail_closed(roots: Iterable[Path] | None = None) -> CheckResult:
    """``startup_gate`` names both layers and raises (static), and — on the real gate — actually
    refuses a missing-key and a missing-volume env (behavioural)."""
    name, ad = "the start-up gate fails closed on both layers", "AD-31"
    is_real = roots is None
    roots = list(roots) if roots is not None else [_STARTUP_FILE]
    trees, unparseable = _load_trees(roots)
    if unparseable:
        return _fail_closed(name, ad, unparseable)

    found = _find_gate(trees)
    if found is None:
        return CheckResult(name, ad, False, "no startup_gate function found (AD-31 gate absent)")
    gate, gate_tree = found
    tokens = _names_and_strings(gate_tree)
    if "load_key_from_env" not in tokens:
        return CheckResult(name, ad, False,
                           "startup_gate does not check the application key layer "
                           "(load_key_from_env) — AD-31 requires both layers")
    if "APX_VOLUME_ENCRYPTED" not in tokens:
        return CheckResult(name, ad, False,
                           "startup_gate does not check the data-volume layer "
                           "(APX_VOLUME_ENCRYPTED) — AD-31 requires both layers")
    if not any(isinstance(n, ast.Raise) for n in ast.walk(gate)):
        return CheckResult(name, ad, False,
                           "startup_gate never raises — a warning-and-continue is not a "
                           "fail-closed gate (AD-31: no permissive default)")
    if is_real:  # the ungameable leg: run the real gate against bad envs
        problem = _gate_behaves_fail_closed()
        if problem is not None:
            return CheckResult(name, ad, False, problem)
    return CheckResult(name, ad, True,
                       "startup_gate checks the key and volume layers, raises, and refuses a "
                       "missing-layer env")


def run() -> list[CheckResult]:
    return [sensitive_columns_are_encrypted(), startup_gate_is_fail_closed()]
