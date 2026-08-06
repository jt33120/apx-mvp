"""The FR-21/FR-56 gates (Story 4.12): the registry of user-reachable actions is complete on both
legs and both ways, and an action whose source shape reads as deletion names its reversal.

Passes the real tree; fires on a route that exists but is not registered, on a ``core/app`` seam
that exists but is not registered, on a stale row naming an action that no longer exists, and on a
deletion-shaped action that does not declare itself. Fails closed on an unparseable file."""

from __future__ import annotations

from pathlib import Path

import pytest

from apx.checks.user_actions import (
    TRANSIENT_TABLES,
    USER_ACTIONS,
    UserAction,
    deletion_shaped_actions_declare_their_reversal,
    evidential_tables,
    user_action_registry_is_complete,
)

_SEAM_SRC = (
    "from apx.core.ports.pin import PinRecorder\n"
    "\n"
    "def do_something(recorder: PinRecorder, *, tenant: str) -> int:\n"
    "    return recorder.pin_piece(tenant=tenant)\n"
    "\n"
    "def _private(recorder: PinRecorder) -> None:\n"
    "    ...\n"
    "\n"
    "def no_port(x: int) -> int:\n"
    "    return x\n"
)


def _api(tmp_path: Path, src: str, name: str = "app") -> Path:
    """A stand-in ``apx/api/`` tree — the check scans the DIRECTORY, so a route module added beside
    ``app.py`` is seen too."""
    d = tmp_path / "api"
    d.mkdir(exist_ok=True)
    (d / f"{name}.py").write_text(src, encoding="utf-8")
    return d


def _core_app(
    tmp_path: Path, src: str = _SEAM_SRC, name: str = "seam", sub: str | None = None
) -> Path:
    d = tmp_path / "core_app"
    d.mkdir(exist_ok=True)
    target = d if sub is None else d / sub
    target.mkdir(exist_ok=True)
    (target / f"{name}.py").write_text(src, encoding="utf-8")
    return d


def _route_row(method: str = "POST", path: str = "/api/one", **kw) -> UserAction:  # noqa: ANN003
    kw.setdefault("changes_state", True)
    return UserAction(name=f"{method} {path}", note="fixture", route=(method, path), **kw)


def _seam_row() -> UserAction:
    return UserAction(
        name="seam.do_something", changes_state=True, note="fixture", use_case="seam.do_something")


_ONE_ROUTE = '@app.post("/api/one")\ndef one() -> None:\n    ...\n'


# ── the real tree ────────────────────────────────────────────────────────────────────────────────
def test_the_real_tree_passes_both_checks() -> None:
    assert user_action_registry_is_complete().ok
    assert deletion_shaped_actions_declare_their_reversal().ok


def test_the_registry_covers_the_whole_triage_control_surface() -> None:
    # the point of leg B: label / line / pin / justification are reachable ONLY at the use-case
    # seam until Story 4.10 routes them, so a route-only registry would miss all of them.
    seams = {a.use_case for a in USER_ACTIONS if a.use_case}
    assert {
        "label.assign_taxonomy_label", "label.revert_taxonomy_label", "line.place_line",
        "line.move_line", "pin.pin_piece", "pin.remove_pin",
        "justification.record_justification", "justification.reject_justification",
        "rank.produce_ranking",
    } <= seams


# ── leg A: the mutating HTTP surface ─────────────────────────────────────────────────────────────
def test_fires_on_a_route_that_exists_but_is_not_registered(tmp_path: Path) -> None:
    src = _ONE_ROUTE + '@app.delete("/api/two")\ndef two() -> None:\n    ...\n'
    r = user_action_registry_is_complete(
        [_route_row(), _seam_row()], api=_api(tmp_path, src), core_app=_core_app(tmp_path))
    assert not r.ok and "not in USER_ACTIONS" in r.detail and "/api/two" in r.detail


def test_fires_on_a_stale_registered_route(tmp_path: Path) -> None:
    r = user_action_registry_is_complete(
        [_route_row(), _route_row(path="/api/gone"), _seam_row()],
        api=_api(tmp_path, _ONE_ROUTE), core_app=_core_app(tmp_path))
    assert not r.ok and "no longer exist" in r.detail and "/api/gone" in r.detail


def test_a_read_route_is_a_registrable_action_too(tmp_path: Path) -> None:
    # a GET is NOT exempt: seven GET endpoints in this product write an audit_record row on serve,
    # so a registry that saw only the mutating four would leave real writers outside the probe.
    src = _ONE_ROUTE + '@app.get("/api/read")\ndef read() -> None:\n    ...\n'
    r = user_action_registry_is_complete(
        [_route_row(), _seam_row()], api=_api(tmp_path, src), core_app=_core_app(tmp_path))
    assert not r.ok and "/api/read" in r.detail


def test_an_api_route_declaring_its_methods_is_seen(tmp_path: Path) -> None:
    src = (_ONE_ROUTE + '@app.api_route("/api/two", methods=["DELETE", "POST"])\n'
           'def two() -> None:\n    ...\n')
    r = user_action_registry_is_complete(
        [_route_row(), _seam_row()], api=_api(tmp_path, src), core_app=_core_app(tmp_path))
    assert not r.ok and "DELETE" in r.detail and "/api/two" in r.detail


def test_fails_closed_on_an_api_route_whose_methods_are_not_readable(tmp_path: Path) -> None:
    src = _ONE_ROUTE + '@app.api_route("/api/two", methods=VERBS)\ndef two() -> None:\n    ...\n'
    r = user_action_registry_is_complete(
        [_route_row()], api=_api(tmp_path, src), core_app=_core_app(tmp_path))
    assert not r.ok and "methods" in r.detail and "failing closed" in r.detail


def test_the_non_decorator_registration_form_is_seen(tmp_path: Path) -> None:
    src = _ONE_ROUTE + 'app.post("/api/two")(handler)\n'
    r = user_action_registry_is_complete(
        [_route_row(), _seam_row()], api=_api(tmp_path, src), core_app=_core_app(tmp_path))
    assert not r.ok and "/api/two" in r.detail


def test_a_static_mount_is_exempt_but_any_other_mount_fails_closed(tmp_path: Path) -> None:
    ok_src = _ONE_ROUTE + 'app.mount("/", StaticFiles(directory=d), name="ui")\n'
    assert user_action_registry_is_complete(
        [_route_row(), _seam_row()], api=_api(tmp_path, ok_src), core_app=_core_app(tmp_path)).ok
    bad = _ONE_ROUTE + 'app.mount("/legacy", legacy_app)\n'
    r = user_action_registry_is_complete(
        [_route_row()], api=_api(tmp_path, bad), core_app=_core_app(tmp_path))
    assert not r.ok and "mount" in r.detail and "failing closed" in r.detail


# ── leg B: the Application-layer seams ───────────────────────────────────────────────────────────
def test_fires_on_a_use_case_seam_that_exists_but_is_not_registered(tmp_path: Path) -> None:
    r = user_action_registry_is_complete(
        [_route_row()], api=_api(tmp_path, _ONE_ROUTE), core_app=_core_app(tmp_path))
    assert not r.ok and "seam.do_something" in r.detail and "use-case seam" in r.detail


def test_fires_on_a_stale_registered_use_case(tmp_path: Path) -> None:
    stale = UserAction(name="seam.gone", changes_state=True, note="f", use_case="seam.gone")
    r = user_action_registry_is_complete(
        [_route_row(), _seam_row(), stale],
        api=_api(tmp_path, _ONE_ROUTE), core_app=_core_app(tmp_path))
    assert not r.ok and "seam.gone" in r.detail and "no longer exist" in r.detail


def test_a_seam_nested_in_a_block_or_a_class_is_still_seen(tmp_path: Path) -> None:
    # leg B walks the whole AST, not just the module top level: a seam inside `try:` or defined as
    # a public method of a public class is still a user-reachable seam.
    src = (
        "from apx.core.ports.pin import PinRecorder\n"
        "try:\n"
        "    def hidden(recorder: PinRecorder) -> None:\n"
        "        ...\n"
        "except ImportError:\n"
        "    pass\n"
        "class Facade:\n"
        "    def act(self, recorder: PinRecorder) -> None:\n"
        "        ...\n")
    r = user_action_registry_is_complete(
        [_route_row()], api=_api(tmp_path, _ONE_ROUTE),
        core_app=_core_app(tmp_path, src, name="nested"))
    assert not r.ok and "nested.hidden" in r.detail and "nested.Facade.act" in r.detail


def test_a_port_reached_through_a_module_alias_is_still_seen(tmp_path: Path) -> None:
    src = ("import apx.core.ports.pin as p\n"
           "\n"
           "def act(recorder: p.PinRecorder) -> None:\n"
           "    ...\n")
    r = user_action_registry_is_complete(
        [_route_row()], api=_api(tmp_path, _ONE_ROUTE),
        core_app=_core_app(tmp_path, src, name="aliased"))
    assert not r.ok and "aliased.act" in r.detail


def test_a_private_or_portless_function_is_not_a_seam(tmp_path: Path) -> None:
    # `_private` takes a port but is not public; `no_port` is public but takes none — neither is a
    # user-reachable seam, so registering only `do_something` is complete.
    assert user_action_registry_is_complete(
        [_route_row(), _seam_row()], api=_api(tmp_path, _ONE_ROUTE),
        core_app=_core_app(tmp_path)).ok


def test_a_seam_hidden_in_a_subpackage_is_still_seen(tmp_path: Path) -> None:
    # core/app has a `read/` subpackage; a state-changing seam dropped into one must not be
    # invisible to the registry — the check recurses and names it `read.piece.open_piece`-style.
    r = user_action_registry_is_complete(
        [_route_row(), _seam_row()], api=_api(tmp_path, _ONE_ROUTE),
        core_app=_core_app(tmp_path, sub="read", name="hidden"))
    assert not r.ok and "read.hidden.do_something" in r.detail


# ── leg A hardening: not only @app., not only app.py, and no unreadable route shape ──────────────
def test_a_route_on_a_router_object_is_still_seen(tmp_path: Path) -> None:
    src = '@router.post("/api/two")\ndef two() -> None:\n    ...\n'
    r = user_action_registry_is_complete(
        [_route_row(), _seam_row()], api=_api(tmp_path, _ONE_ROUTE + src),
        core_app=_core_app(tmp_path))
    assert not r.ok and "/api/two" in r.detail  # moving a route off `app` does not hide it


def test_a_route_module_beside_app_py_is_still_seen(tmp_path: Path) -> None:
    api = _api(tmp_path, _ONE_ROUTE)
    _api(tmp_path, '@app.post("/api/later")\ndef later() -> None:\n    ...\n', name="triage")
    r = user_action_registry_is_complete(
        [_route_row(), _seam_row()], api=api, core_app=_core_app(tmp_path))
    assert not r.ok and "/api/later" in r.detail


def test_fails_closed_on_an_unresolvable_routing_shape(tmp_path: Path) -> None:
    src = _ONE_ROUTE + "app.include_router(other)\n"
    r = user_action_registry_is_complete(
        [_route_row()], api=_api(tmp_path, src), core_app=_core_app(tmp_path))
    assert not r.ok and "include_router" in r.detail and "failing closed" in r.detail


def test_fails_closed_on_a_route_path_that_is_not_a_literal(tmp_path: Path) -> None:
    src = _ONE_ROUTE + '@app.post(PREFIX + "/two")\ndef two() -> None:\n    ...\n'
    r = user_action_registry_is_complete(
        [_route_row()], api=_api(tmp_path, src), core_app=_core_app(tmp_path))
    assert not r.ok and "not a literal" in r.detail


# ── failing closed ───────────────────────────────────────────────────────────────────────────────
def test_fails_closed_on_an_unparseable_api_module(tmp_path: Path) -> None:
    r = user_action_registry_is_complete(
        [_route_row()], api=_api(tmp_path, "def (:\n"), core_app=_core_app(tmp_path))
    assert not r.ok and "failing closed" in r.detail


def test_fails_closed_on_an_unparseable_core_app_module(tmp_path: Path) -> None:
    r = user_action_registry_is_complete(
        [_route_row()], api=_api(tmp_path, _ONE_ROUTE),
        core_app=_core_app(tmp_path, "def (:\n", name="broken"))
    assert not r.ok and "failing closed" in r.detail


# ── the deletion-shaped gate ─────────────────────────────────────────────────────────────────────
def test_fires_when_a_delete_route_does_not_declare_itself() -> None:
    r = deletion_shaped_actions_declare_their_reversal([_route_row("DELETE", "/api/thing")])
    assert not r.ok and "reads as deletion in the source" in r.detail


@pytest.mark.parametrize(
    "shape", ["/api/x/purge", "/api/x/clear", "/api/x/revoke", "/api/x/wipe", "/api/x/reset"])
def test_fires_on_a_deletion_shaped_path(shape: str) -> None:
    assert not deletion_shaped_actions_declare_their_reversal([_route_row(path=shape)]).ok


def test_fires_on_a_deletion_shaped_use_case_name() -> None:
    row = UserAction(name="x.remove_thing", changes_state=True, note="f", use_case="x.remove_thing")
    assert not deletion_shaped_actions_declare_their_reversal([row]).ok


def test_a_token_inside_a_longer_word_is_not_a_deletion_shape() -> None:
    # word-part matching, never a loose substring: "cleared" / "removal" are not "clear" / "remove"
    assert deletion_shaped_actions_declare_their_reversal([_route_row(path="/api/cleared")]).ok


def test_a_declared_deletion_shaped_action_with_a_reversal_passes() -> None:
    ok = _route_row("DELETE", "/api/thing", reads_as_deletion=True, reversal="write it again")
    assert deletion_shaped_actions_declare_their_reversal([ok]).ok


# ── the row's own invariants ─────────────────────────────────────────────────────────────────────
def test_a_row_is_a_route_or_a_seam_never_both_and_never_neither() -> None:
    with pytest.raises(ValueError, match="never both"):
        UserAction(name="x", changes_state=True, note="n", route=("POST", "/a"), use_case="m.f")
    with pytest.raises(ValueError, match="never both"):
        UserAction(name="x", changes_state=True, note="n")


def test_a_deletion_claim_without_a_reversal_is_refused_at_construction() -> None:
    with pytest.raises(ValueError, match="names its reversal"):
        UserAction(name="x", changes_state=True, note="n", route=("DELETE", "/a"),
                   reads_as_deletion=True)


# ── the evidential / transient partition ─────────────────────────────────────────────────────────
def test_a_table_is_evidential_until_someone_writes_down_why_it_is_not() -> None:
    assert evidential_tables({"piece", "audit_record", "session"}) == {"piece", "audit_record"}
    # fail-closed: a table nobody has thought about yet is protected
    assert "a_table_a_later_story_adds" in evidential_tables({"a_table_a_later_story_adds"})


def test_every_transient_table_carries_a_written_reason() -> None:
    assert TRANSIENT_TABLES and all(r.strip() for r in TRANSIENT_TABLES.values())
