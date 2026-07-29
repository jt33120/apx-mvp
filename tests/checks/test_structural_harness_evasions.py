"""Story 1.12 review regressions — each check catches the IDIOMATIC evasion the adversarial review
found (aliased/from-imports, a collection-constant tenant branch, real vector-store API names, an
attribute-form translator, a codeset-qualified locale, …), not only its original strawman fixture.
Written as temp modules so every evasion shape is locked without a fixture directory each.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from apx.checks import forward_looking as fl
from apx.checks import isolation_harness as ih


def _mod(tmp_path: Path, src: str) -> Path:
    (tmp_path / "m.py").write_text(src, encoding="utf-8")
    return tmp_path


# (label, check, violating source) — each MUST fire; a MISS is the review's "inflated claim" defect.
_EVASIONS = [
    ("egress-aliased-import", ih.no_egress_call_site_outside_adapters,
     "import requests as r\ndef x(d): r.post('http://e', json=d)\n"),
    ("egress-from-import-urlopen", ih.no_egress_call_site_outside_adapters,
     "from urllib.request import urlopen\ndef x(u): return urlopen(u)\n"),
    ("egress-from-socket-import", ih.no_egress_call_site_outside_adapters,
     "from socket import create_connection\ndef x(): return create_connection(('e', 443))\n"),
    ("tenant-in-module-const-list", ih.no_tenant_identifier_in_source,
     "T = ['a', 'b']\ndef r(tenant):\n    return 1 if tenant in T else 0\n"),
    ("relative-import-of-fixtures", ih.no_runtime_import_from_tests,
     "from ._fixtures import demo\nhandler = demo\n"),
    ("embedder-by-encode-method", fl.embedder_has_one_implementation,
     "class AEmbedder:\n    def encode(self, t): return []\n"
     "class BEmbedder:\n    def encode(self, t): return []\n"),
    ("embedder-disguised-by-port-shape", fl.embedder_has_one_implementation,
     "class RealEmbedder:\n    def embed(self, t): return []\n"        # named
     "class Bow:\n    dimensions = 1024\n    def encode(self, t): return []\n"),  # disguised shape
    ("index-recreate-collection", fl.destructive_index_ops_single_entry,
     "def a(s): s.recreate_collection()\ndef b(s): s.recreate_collection()\n"),
    ("index-raw-drop-truncate", fl.destructive_index_ops_single_entry,
     "def a(s): s.execute('DROP INDEX i')\ndef b(s): s.execute('TRUNCATE t')\n"),
    ("index-bulk-delete", fl.destructive_index_ops_single_entry,
     "def a(s): s.query(C).delete()\ndef b(s): s.execute('DELETE FROM chunk')\n"),
    ("post-filter-docs-rbac", fl.no_post_filter_in_retrieval,
     "def apply(docs, rbac): return [d for d in docs if d in rbac]\n"),
    ("attribute-form-translator", fl.no_natural_language_translation_key,
     "import i18n\ndef g(): return i18n.t('Please try again later')\n"),
    ("f-string-translation-key", fl.no_natural_language_translation_key,
     "def g(t): return t(f'Hello {t}')\n"),
    ("setlocale-with-codeset", fl.no_hardcoded_locale,
     "from locale import setlocale, LC_ALL\ndef s(): setlocale(LC_ALL, 'fr_FR.UTF-8')\n"),
    ("model-confidence-off-verdict", fl.no_model_reported_confidence,
     "def s(verdict): return verdict.confidence\n"),
]


@pytest.mark.parametrize(("label", "check", "src"), _EVASIONS, ids=[e[0] for e in _EVASIONS])
def test_check_catches_the_idiomatic_evasion(label, check, src, tmp_path) -> None:  # noqa: ANN001
    r = check([_mod(tmp_path, src)])
    assert not r.ok, f"{label}: {r.name} MISSED the evasion — {r.detail}"


def test_egress_check_does_not_flag_non_network_socket_use(tmp_path: Path) -> None:
    # narrowed socket leg: gethostname/inet_aton are NOT connection-opening, must not false-positive
    src = "import socket\ndef host(): return socket.gethostname()\n"
    assert ih.no_egress_call_site_outside_adapters([_mod(tmp_path, src)]).ok


def test_egress_check_does_not_flag_urllib_parse(tmp_path: Path) -> None:
    src = "from urllib.parse import quote\ndef e(s): return quote(s)\n"
    assert ih.no_egress_call_site_outside_adapters([_mod(tmp_path, src)]).ok


def test_confidence_check_does_not_flag_a_domain_result(tmp_path: Path) -> None:
    # a statistical confidence on a domain result (subject not a model response) is legitimate
    src = "def show(result): return result.confidence\n"
    assert fl.no_model_reported_confidence([_mod(tmp_path, src)]).ok


def test_destructive_index_check_does_not_flag_single_row_delete(tmp_path: Path) -> None:
    # a single-row `session.delete(obj)` (one positional arg) is NOT a bulk wipe — must not fire,
    # in two functions (the real store has several such calls). Only a no-arg bulk `.delete()` is.
    src = "def a(s, o): s.delete(o)\ndef b(s, o): s.delete(o)\n"
    assert fl.destructive_index_ops_single_entry([_mod(tmp_path, src)]).ok
