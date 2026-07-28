"""Story 2.3 (AD-28) extraction-isolation specifics, beyond the generic green-on-tree /
fires-on-fixture harness: the GPL parser is imported ONLY by the out-of-process worker, the
product ``.msg`` adapter is clean, the one subprocess call site is that adapter, and the stderr
rule is scoped to the extraction adapters. These prove the seal is load-bearing, not vacuous.
"""

from __future__ import annotations

import ast
from pathlib import Path

from apx.checks import isolation_harness as ih

_EXTRACTION = Path(ih.__file__).resolve().parents[1] / "adapters" / "extraction"


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        names.update(ih._import_modules(node))
    return names


def test_only_the_out_of_process_worker_imports_the_gpl_parser() -> None:
    # The product .msg adapter must NOT import extract_msg (GPL); only the worker, run out-of-
    # process, does — the process boundary is the licence boundary (AD-28).
    assert "extract_msg" in _imports(_EXTRACTION / "msg_worker.py")
    assert "extract_msg" not in _imports(_EXTRACTION / "msg.py")


def test_the_gpl_seal_is_green_only_because_the_worker_is_exempt() -> None:
    # Green-on-tree is NOT vacuous: the worker genuinely imports extract_msg, so pointing the
    # check at the extraction dir WITHOUT the real-tree exemption fires on the worker's own import.
    assert ih.no_extract_msg_import_outside_worker().ok                 # real tree: worker exempt
    fired = ih.no_extract_msg_import_outside_worker([_EXTRACTION])      # roots → exemption off
    assert not fired.ok and "extract_msg" in fired.detail


def test_the_subprocess_call_site_lives_in_the_msg_adapter() -> None:
    assert "subprocess" in _imports(_EXTRACTION / "msg.py")             # the one exec boundary
    assert ih.no_subprocess_call_outside_extraction().ok               # exempt inside extraction


def test_the_stderr_rule_is_scoped_to_the_extraction_adapters() -> None:
    r = ih.no_stderr_none_in_extraction()
    assert r.ok and "adapters/extraction" in r.detail
