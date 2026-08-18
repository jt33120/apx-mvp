"""The Story 5.4 structural checks, each proven to FIRE (FR-23 / FR-55 / FR-56).

A check that has never been seen to fail is a check nobody has verified. Every leg below is shown
green on the real tree and red on a synthetic module carrying the violation it exists for.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import apx.core.domain.statement as statement_module
from apx.checks.forward_looking import (
    _banned_hit,
    _banned_hit_in_text,
    no_banned_confidence_phrasing,
)
from apx.checks.isolation_harness import _APX_ROOT
from apx.checks.statement import (
    the_sentence_has_one_composer,
    the_sentence_is_composed_offline,
    unfitness_offers_no_line_move,
)

_STATEMENT = _APX_ROOT / "core" / "domain" / "statement.py"


def _module(tmp_path: Path, name: str, src: str) -> Path:
    path = tmp_path / f"{name}.py"
    path.write_text(src, encoding="utf-8")
    return path


def _web(tmp_path: Path, name: str, src: str) -> Path:
    root = tmp_path / "src"
    root.mkdir(exist_ok=True)
    (root / name).write_text(src, encoding="utf-8")
    return root


# ── statement-one-composer ──────────────────────────────────────────────────────────────────────

def test_the_one_composer_check_passes_the_real_tree() -> None:
    assert the_sentence_has_one_composer().ok


def test_it_fires_when_a_second_python_module_composes_the_sentence(tmp_path: Path) -> None:
    src = (
        "def say(n, m):\n"
        '    return f"{n} familles sur {m} ont été tirées au hasard ; aucune."\n')
    r = the_sentence_has_one_composer([_module(tmp_path, "second", src)])
    assert not r.ok and "one sentence, one composer" in r.detail


def test_it_fires_when_the_CLIENT_composes_the_sentence(tmp_path: Path) -> None:
    """The client is the worst place for a second composer: a claim assembled there can silently
    omit the RBAC scope and the staleness the server puts inside the string."""
    web = _web(tmp_path, "panel.tsx",
               'const s = `Avec une confiance de ${c}%, au plus ${n}`;\n')
    r = the_sentence_has_one_composer([_module(tmp_path, "clean", "x = 1\n")], web_root=web)
    assert not r.ok and "in the client" in r.detail


def test_it_folds_the_typographic_apostrophe_the_client_actually_writes(tmp_path: Path) -> None:
    """The client writes ``n’est`` and Python writes ``n'est``. A fragment list that did not fold
    them would police one file and wave the other through — the one-sided comparison this story
    found in the banned-phrasing list."""
    web = _web(tmp_path, "panel.tsx", "const s = 'Aucune borne n’est énoncée : ...';\n")
    r = the_sentence_has_one_composer([_module(tmp_path, "clean", "x = 1\n")], web_root=web)
    assert not r.ok and "in the client" in r.detail


def test_the_one_composer_check_fails_closed_on_an_unparseable_module(tmp_path: Path) -> None:
    r = the_sentence_has_one_composer([_module(tmp_path, "broken", "def (:\n")])
    assert not r.ok


# ── statement-composed-offline ──────────────────────────────────────────────────────────────────

def test_the_offline_check_passes_the_real_tree() -> None:
    assert the_sentence_is_composed_offline().ok


def test_it_fires_when_the_composer_reaches_the_network(tmp_path: Path) -> None:
    src = "import httpx\n\n\ndef statement_fr(x):\n    return httpx.get(x).text\n"
    r = the_sentence_is_composed_offline(_module(tmp_path, "networked", src))
    assert not r.ok and "must render with the network absent" in r.detail


def test_it_fires_when_the_closure_leaves_the_domain(tmp_path: Path) -> None:
    """A composer reaching a PORT would make its offline guarantee rest on an adapter's
    behaviour rather than on its own."""
    src = ("from apx.core.ports.freshness import FreshnessReader\n\n\n"
           "def statement_fr(x):\n    return x\n")
    r = the_sentence_is_composed_offline(_module(tmp_path, "ported", src))
    assert not r.ok and "leaves the" in r.detail


def test_it_fires_when_the_composer_module_is_missing(tmp_path: Path) -> None:
    """An absence-check is worthless if its subject can vanish: a property whose subject does not
    exist is unverifiable, never satisfied (FR-56)."""
    r = the_sentence_is_composed_offline(tmp_path / "not-here.py")
    assert not r.ok and "unverifiable" in r.detail


def _apx_imports(path: Path) -> set[str]:
    """Every ``apx.*`` module one file imports, absolute or relative — the fixture the transitive
    leg stands on, read from the source rather than believed from a comment."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("apx"):
            out.add(node.module or "")
        elif isinstance(node, ast.Import):
            out.update(a.name for a in node.names if a.name.startswith("apx"))
    return out


def test_it_follows_a_transitive_import_rather_than_only_the_first_hop(tmp_path: Path) -> None:
    """The composer itself can look clean while a Domain module it imports reaches out. The real
    tree exercises this leg: statement.py imports sampling.py, which imports confidence.py — and
    since story 7.6, freshness.py as well, because ``RerankCost`` draws the French for its cause
    from FR-58's own trigger table rather than composing a second copy of the phrase.

    This asserted the closure's SIZE, and a size is the weaker referent: it has to be edited every
    time a legitimate Domain import is added, which teaches the next author to bump the number
    rather than to look. What the leg is actually about is that the walk goes past the first hop, so
    that is what is asserted — ``confidence`` is reached only through ``sampling``."""
    r = the_sentence_is_composed_offline()
    assert r.ok, r.detail

    # The chain the leg depends on, established independently of the check's own walk — the old
    # assertion took it on trust from a docstring and would have gone on passing if it broke.
    domain = Path(statement_module.__file__).resolve().parent
    first_hop = _apx_imports(domain / "statement.py")
    assert any(m.endswith("domain.sampling") for m in first_hop), (
        f"the composer no longer imports sampling; this leg tests nothing ({sorted(first_hop)})")
    second_hop = _apx_imports(domain / "sampling.py")
    assert any(m.endswith("domain.confidence") for m in second_hop), (
        f"sampling no longer imports confidence; this leg tests nothing ({sorted(second_hop)})")

    # and the check's closure is bigger than the composer's own imports, i.e. the walk recursed
    size = int(re.search(r"closure is (\d+) Domain module", r.detail).group(1))
    assert size > 1, r.detail


# ── unfitness-offers-no-line-move ───────────────────────────────────────────────────────────────

def test_the_unfitness_check_passes_the_real_tree() -> None:
    assert unfitness_offers_no_line_move().ok


def test_it_fires_when_the_rule_names_the_line_move_remedy(tmp_path: Path) -> None:
    src = 'REMEDY = "re-line"\n\n\ndef unfitness(**kw):\n    return REMEDY\n'
    r = unfitness_offers_no_line_move(_module(tmp_path, "remedy", src))
    assert not r.ok and "never a re-cut" in r.detail


def test_it_fires_when_the_api_ships_no_declaration(tmp_path: Path) -> None:
    """A finding computed and never shipped is a property with no surface (FR-56)."""
    api = _module(tmp_path, "app", "class BoundOut:\n    kind: str\n")
    r = unfitness_offers_no_line_move(_STATEMENT, api=api)
    assert not r.ok and "no surface" in r.detail


def test_it_fires_when_a_client_can_move_the_line_without_reading_the_finding(
    tmp_path: Path
) -> None:
    """Story 4.9's surface does not exist yet. When it lands, the guard is already here — and it
    demands the affordance be REMOVED, not greyed: a greyed control still proposes the act."""
    web = _web(tmp_path, "line.tsx", "function moveTheLine() { return 1; }\n")
    r = unfitness_offers_no_line_move(_STATEMENT, web_root=web)
    assert not r.ok and "must be REMOVED" in r.detail


def test_a_client_that_moves_the_line_AND_reads_the_finding_passes(tmp_path: Path) -> None:
    web = _web(tmp_path, "line.tsx",
               "function moveTheLine(b) { return b.unfit_fr ? null : 1; }\n")
    r = unfitness_offers_no_line_move(_STATEMENT, web_root=web)
    assert r.ok and "client file(s) that can move the line read it" in r.detail


# ── no-banned-confidence-phrasing: LIVE and multilingual since Story 5.4 ────────────────────────

def test_the_banned_phrasing_check_passes_the_real_tree() -> None:
    assert no_banned_confidence_phrasing().ok


def test_it_catches_the_FRENCH_claim_the_product_would_actually_write() -> None:
    """The list was English-only and GREEN for eleven stories while every user-facing string in the
    product was French — a comparison whose right-hand side was not the thing on its left."""
    assert _banned_hit("risque d'avoir manqué une pièce pertinente") is not None
    assert _banned_hit("la probabilité que rien ne reste dans le jeu écarté") is not None
    assert _banned_hit("aucune chance qu'il reste quoi que ce soit") is not None


def test_it_catches_a_translator_s_near_miss_that_is_on_no_literal_list() -> None:
    """Shapes, not only literals: "le risque de ne rien avoir manqué" makes exactly the §0.2 claim
    and nobody would think to write it down in advance."""
    assert _banned_hit("le risque de ne rien avoir manqué") is not None
    assert _banned_hit("quel risque avons-nous de passer à côté d'une pièce") is not None


def test_it_catches_the_english_and_italian_forms_FR_23_names() -> None:
    assert _banned_hit("risk of having missed a relevant document") is not None
    assert _banned_hit("chance that nothing relevant was missed") is not None
    assert _banned_hit("rischio di aver mancato un documento rilevante") is not None


def test_it_does_not_fire_on_the_sentence_the_product_actually_says() -> None:
    """A check that cries wolf is a check somebody deletes. The real claim — a prevalence with its
    confidence named — must pass, and so must prose that uses a risk word innocently."""
    assert _banned_hit(
        "Avec une confiance de 95 %, au plus 21 des 1400 familles étaient pertinentes") is None
    assert _banned_hit("recensement : les 1400 pièces écartées ont toutes été examinées") is None
    assert _banned_hit(
        "sampled with vanishing probability by a uniform assignment at these sizes") is None


def test_it_scans_the_client_too_because_that_is_where_the_strings_live(tmp_path: Path) -> None:
    """FR-23 says *any locale's string set*, and the largest one in this build is apx/web/src."""
    web = tmp_path / "src"
    web.mkdir()
    (web / "panel.tsx").write_text(
        "const s = 'risque d\\u2019avoir manqué une pièce';\n", encoding="utf-8")
    import apx.checks.forward_looking as fl
    original = fl._WEB_ROOT
    try:
        fl._WEB_ROOT = web
        r = no_banned_confidence_phrasing()
        assert not r.ok and "the lawyer actually reads" in r.detail
    finally:
        fl._WEB_ROOT = original


# ══ the adversarial review's confirmed check holes, each proven closed ═══════════════════════════

def test_the_offline_check_no_longer_fails_open_on_importlib(tmp_path: Path) -> None:
    """CONFIRMED [HIGH]. Adding `importlib.import_module("httpx").post(...)` to the composer left
    all 89 checks green while the confidence-bound sentence was being POSTed to a third party."""
    src = ('import importlib\n\n\ndef statement_fr(x):\n'
           '    return importlib.import_module("httpx").post("u", json={}).text\n')
    r = the_sentence_is_composed_offline(_module(tmp_path, "dyn", src))
    assert not r.ok and "httpx" in r.detail


def test_the_offline_check_catches_the_dunder_import_too(tmp_path: Path) -> None:
    src = 'def statement_fr(x):\n    return __import__("requests").get("u").text\n'
    r = the_sentence_is_composed_offline(_module(tmp_path, "dunder", src))
    assert not r.ok and "requests" in r.detail


def test_a_module_named_at_runtime_is_unverifiable_never_assumed_clean(tmp_path: Path) -> None:
    """A closure walk that shrugged at `import_module(name)` would answer "no network" when the
    honest answer is "cannot tell" — which is how a check on an absence fails open."""
    src = ('import importlib\n\n\ndef statement_fr(x, name):\n'
           '    return importlib.import_module(name).go(x)\n')
    r = the_sentence_is_composed_offline(_module(tmp_path, "runtime", src))
    assert not r.ok and "named at RUNTIME" in r.detail


def test_relative_imports_resolve_to_the_right_package() -> None:
    """CONFIRMED. Every `ImportFrom` with level != 0 returned [] — invisible both as a violation
    and as a closure EDGE, so any egress one relative hop away was never walked."""
    import ast

    from apx.checks.statement import _COMPOSER_MODULE, _dotted_of, _imported_modules, _module_path
    pkg = _dotted_of(_COMPOSER_MODULE)
    assert pkg == "apx.core.domain.statement"
    assert _imported_modules(ast.parse("from . import worklist").body[0], pkg) == [
        "apx.core.domain", "apx.core.domain.worklist"]
    # one level up leaves the Domain — the check must SEE it in order to refuse it
    assert "apx.core.ports" in _imported_modules(ast.parse("from .. import ports").body[0], pkg)
    # a package resolves to its __init__, so the walk does not stop at the first sub-package
    assert _module_path("apx.core.domain") is not None
    assert _module_path("apx.core.domain.worklist") is not None


def test_the_unfitness_check_demands_FR_23_s_worklist_line(tmp_path: Path) -> None:
    """CONFIRMED by three lenses: FR-23 has four clauses and the worklist line had no code at all.
    A requirement two-thirds implemented reads, from the outside, like one that is finished."""
    import apx.checks.statement as st
    original = st._APX_ROOT
    fake = tmp_path / "apx"
    (fake / "core" / "domain").mkdir(parents=True)
    (fake / "core" / "domain" / "worklist.py").write_text(
        "def worklist_lines(a):\n    return ()\n", encoding="utf-8")
    (fake / "api").mkdir(parents=True)
    (fake / "api" / "app.py").write_text("unfit_fr = 1\n", encoding="utf-8")
    try:
        st._APX_ROOT = fake
        r = unfitness_offers_no_line_move(_STATEMENT, web_root=tmp_path / "nowhere")
        assert not r.ok and "builds no unfitness line" in r.detail
    finally:
        st._APX_ROOT = original


# ── the banned-phrasing holes ────────────────────────────────────────────────────────────────────

def test_it_folds_the_typographic_apostrophe_the_check_itself_was_blind_to() -> None:
    """CONFIRMED by two lenses. Four banned literals are written with ASCII `'` and French copy uses
    U+2019, so the §0.2 claim in correct French typography passed the check that exists for it —
    while the sibling check added by this same story folded it and its docstring named the hazard.
    The lesson was applied to the new check and not to the one it was learned from."""
    assert _banned_hit("aucun risque d’avoir écarté une pièce pertinente") is not None
    assert _banned_hit("aucune chance qu’il reste une pièce pertinente") is not None


def test_it_survives_a_long_qualifying_clause_between_the_risk_and_the_claim() -> None:
    """CONFIRMED. Six intervening words let the exact banned literal reappear intact behind a
    qualifying clause — and a qualifying clause is precisely what a careful author adds."""
    assert _banned_hit(
        "Risque, sur la base de l'échantillon aléatoire de 200 familles gelées le 3 mars, "
        "d'avoir manqué une pièce pertinente : 1,5 %.") is not None


def test_it_catches_the_claim_made_positively_with_no_risk_word_at_all() -> None:
    """CONFIRMED. *certitude*, *garantie*, *assurance* — and the bare claim, which carries neither
    a risk word nor an assertion word."""
    assert _banned_hit("Garantie à 95 % qu'il ne reste rien de pertinent.") is not None
    assert _banned_hit(
        "Assurance à 98,5 % que le lot écarté ne contient plus aucune pièce "
        "pertinente.") is not None
    assert _banned_hit("Aucun document pertinent ne subsiste dans le lot écarté.") is not None
    assert _banned_hit("Risque résiduel de 1,5 % sur les pièces écartées") is not None


def test_it_does_not_block_the_build_over_this_product_s_own_legal_vocabulary() -> None:
    """CONFIRMED. The raw-text legs collapsed a whole file into one string, so two unrelated
    adjacent labels composed a "hit" and *risque de forclusion* + *pièce manquante* — core French
    triage vocabulary — failed the build accusing the author of the §0.2 claim. The predictable
    answer to a check that cries wolf is to widen it until it says nothing."""
    assert _banned_hit("Risque de forclusion — la pièce manquante n'a pas été produite") is None
    assert _banned_hit_in_text(
        'const a = "3 risques identifiés";\nconst b = "2 pièces manquantes";') is None
    assert _banned_hit(
        "Recensement : les 1400 pièces écartées ont toutes été examinées ; "
        "aucune n'était pertinente") is None


def test_a_docstring_is_held_to_the_literals_and_exempt_from_the_shapes() -> None:
    """A docstring is documentation, not a string set. Prose explaining why a claim is forbidden
    has to be able to describe it; a VERBATIM banned phrase in one still fails the build, which is
    the Story 5.3 precedent."""
    from apx.checks.forward_looking import _literal_hit
    descriptive = "the recall guarantee behind triage: what a discard decision may have missed"
    assert _banned_hit(descriptive) is not None      # as a user-facing literal: caught
    assert _literal_hit(descriptive) is None         # as a docstring: documentation, not a claim
    assert _literal_hit("risk of having missed a relevant document") is not None
