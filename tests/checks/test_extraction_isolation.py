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


def test_the_real_extraction_subprocess_captures_stderr() -> None:
    # The shipped adapter (msg.py) uses capture_output=True, so the real tree passes.
    r = ih.extraction_subprocess_captures_stderr()
    assert r.ok and "captures stderr" in r.detail


# ── the strengthenings the review asked for: the checks are wider than "literal-None" / "import" ──
def _probe(tmp_path: Path, name: str, src: str) -> Path:
    d = tmp_path / name
    d.mkdir()
    (d / f"{name}.py").write_text(src, encoding="utf-8")
    return d


def _sp_src(extra: str) -> str:
    """An extraction-looking module with one ``subprocess.run`` call taking ``extra`` kwargs."""
    return f"import subprocess, sys\ndef f():\n    subprocess.run(['x'], {extra})\n"


def test_subprocess_seal_catches_os_level_spawns_not_only_the_subprocess_import(
        tmp_path: Path) -> None:
    # os.system/exec/spawn are process spawns that need no `import subprocess` (AD-28's call leg).
    for name, src in {
        "ossystem": "import os\ndef f():\n    os.system('x')\n",
        "osexecv": "import os\ndef f():\n    os.execv('/bin/x', ['x'])\n",
        "ptyspawn": "import pty\ndef f():\n    pty.spawn(['x'])\n",
    }.items():
        r = ih.no_subprocess_call_outside_extraction([_probe(tmp_path, name, src)])
        assert not r.ok, f"{name} should fire (a process spawn outside extraction)"


def test_stderr_seal_catches_omission_stdout_and_sys_stderr_not_only_literal_none(
        tmp_path: Path) -> None:
    # omission → inherited; STDOUT merges into the JSON channel; sys.stderr is the parent fd.
    for name, extra in {"omit": "", "stdout": "stderr=subprocess.STDOUT",
                        "sysstderr": "stderr=sys.stderr"}.items():
        r = ih.extraction_subprocess_captures_stderr([_probe(tmp_path, name, _sp_src(extra))])
        assert not r.ok, f"{name} should fire (stderr not captured)"


def test_stderr_seal_passes_when_stderr_is_captured(tmp_path: Path) -> None:
    for name, extra in {"capture": "capture_output=True", "pipe": "stderr=subprocess.PIPE",
                        "devnull": "stderr=subprocess.DEVNULL"}.items():
        r = ih.extraction_subprocess_captures_stderr([_probe(tmp_path, name, _sp_src(extra))])
        assert r.ok, name


def test_gpl_seal_catches_dynamic_import_of_extract_msg(tmp_path: Path) -> None:
    for name, src in {
        "importlib": "import importlib\ndef f():\n    importlib.import_module('extract_msg')\n",
        "dunder": "def f():\n    __import__('extract_msg')\n",
    }.items():
        r = ih.no_extract_msg_import_outside_worker([_probe(tmp_path, name, src)])
        assert not r.ok and "extract_msg" in r.detail, name
