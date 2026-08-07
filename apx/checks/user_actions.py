"""The registry of user-reachable actions, and the two gates that keep it honest (Story 4.12).

FR-21: *"No control in the product performs a hard deletion of a* pièce*, a* chunk*, an* audit
record *entry, a* change log *entry or a* failure register *entry; anything a user could read as
deletion is a reversible, labelled, recorded state change, **asserted by a bounded runtime probe
over an enumerated registry of user-reachable actions**."*

That sentence needs three things, and this module owns two of them:

1. **The registry** — :data:`USER_ACTIONS`, one row per user-reachable action. An action is
   reachable either as a **mutating HTTP route** (``@app.post/put/patch/delete`` in
   ``apx/api/app.py``) or as an **Application-layer use-case seam** (a public function in
   ``apx/core/app/`` that takes a Ports-typed parameter — the shape AD-4 forces on every seam). A
   row is one or the other, never both, so the two legs stay independently checkable.
2. **The two structural properties** (FR-56) — :func:`user_action_registry_is_complete` (an action
   that exists but is not registered fails the build, and so does a registry row naming an action
   that no longer exists) and :func:`deletion_shaped_actions_declare_their_reversal` (an action
   whose **source shape** reads as deletion must declare that it does, and must name its reversal).
3. The **bounded runtime probe** itself lives in ``tests/probe/test_never_hard_delete.py``: it
   executes every state-changing registered action against a real seeded *matter* and asserts no
   evidential table's row count falls. It consumes this registry as its bound.

:data:`TRANSIENT_TABLES` is the written, reasoned allow-list of tables whose rows may legitimately
go away — AD-7's *"one named exception exists and is written here so it is not invented
elsewhere"*, generalised. Everything not on it is **evidential by default**, so a table a later
story adds is protected without anyone remembering to protect it.
"""

from __future__ import annotations

import ast
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

from apx.checks.import_contracts import CheckResult
from apx.checks.payload_schema import _parse

_APX_ROOT = Path(__file__).resolve().parent.parent
_API_ROOT = _APX_ROOT / "api"
_CORE_APP = _APX_ROOT / "core" / "app"
# EVERY HTTP verb is a user-reachable action, not only the mutating four: seven GET endpoints in
# this product write an `audit_record` row on each call (`audit_query`, `audit_piece_open`), so a
# registry that saw only POST/PUT/PATCH/DELETE would leave real writers to an evidential table
# outside the probe. The mutating four additionally MUST declare `changes_state` (see the check).
_HTTP_METHODS = frozenset({"get", "post", "put", "patch", "delete", "head", "options"})
_MUTATING_METHODS = frozenset({"post", "put", "patch", "delete"})
# Route-registration shapes this check cannot resolve to a (method, path) pair — a router prefix or
# a sub-application prefix is composed at include time. Their PRESENCE fails the check closed rather
# than letting a route go unseen. ``mount`` is here too, with one written exemption below.
_UNRESOLVABLE_ROUTING = frozenset({"add_api_route", "include_router", "add_route", "mount",
                                   "websocket", "add_websocket_route"})
# The one mount this product makes: the static front-end bundle. It declares no API route, so it is
# named here rather than blocking the check — AD-7's "written here so it is not invented elsewhere".
_MOUNT_EXEMPTION = "StaticFiles"

# A user could read any of these as "it deleted my thing". Matched against the WORD PARTS of a route
# path or a use-case name (never a loose substring), plus the HTTP method DELETE. ``discard`` is in
# the list because it is THIS product's own word for setting a pièce aside (Story 4.7): the day an
# action carries it, the honesty gate must apply.
_DELETION_SHAPED = frozenset({
    "delete", "remove", "clear", "purge", "revoke", "withdraw", "drop", "reset", "wipe", "reject",
    "revert", "discard", "erase", "destroy", "expire", "archive", "truncate", "unpin", "retire",
})


@dataclass(frozen=True)
class UserAction:
    """One user-reachable action. ``route`` is ``(METHOD, path)`` for an HTTP action, ``use_case``
    is ``"module.function"`` for an Application-layer seam — **exactly one** is set.

    ``changes_state`` means **this action writes an evidential row** — a *pièce*, a *chunk*, an
    *audit record* entry, a *change log* entry, a *failure register* entry, or any other table not
    on the :data:`TRANSIENT_TABLES` allow-list. It is what the runtime probe uses as its bound, so
    it is not taken on trust: a mutating HTTP verb may not declare it False (checked here), and the
    probe asserts at runtime that every True really writes and every False really does not.
    Refreshing one's own ``session`` row — which every authenticated request does — is transient
    auth bookkeeping and deliberately does **not** count.

    ``reads_as_deletion`` marks the acts a user could read as destruction; those carry a non-blank
    ``reversal`` naming how the act is undone (FR-21/FR-5). ``note`` records **why** the shape is
    what it is, in the source, where the next reader will find it."""

    name: str
    changes_state: bool
    note: str
    route: tuple[str, str] | None = None
    use_case: str | None = None
    reads_as_deletion: bool = False
    reversal: str | None = None

    def __post_init__(self) -> None:
        if (self.route is None) == (self.use_case is None):
            raise ValueError(
                f"{self.name}: an action is reachable as a route OR a use-case seam, never both "
                "and never neither — the two completeness legs are checked independently")
        if self.reads_as_deletion and not (self.reversal or "").strip():
            raise ValueError(
                f"{self.name}: an action a user could read as deletion names its reversal — "
                "that is what makes it a reversible, labelled, recorded state change (FR-21)")

    @property
    def parts(self) -> frozenset[str]:
        """The word parts of the action's source shape — the route path or the use-case name — split
        on every non-alphanumeric character, so ``remove_pin`` yields ``{remove, pin}`` and a token
        can never match by accident inside a longer word."""
        raw = self.route[1] if self.route is not None else (self.use_case or "")
        out, word = [], ""
        for ch in raw:
            if ch.isalnum():
                word += ch.lower()
            elif word:
                out.append(word)
                word = ""
        if word:
            out.append(word)
        return frozenset(out)

    @property
    def looks_like_deletion(self) -> bool:
        """Decided from the SOURCE — an HTTP ``DELETE``, or a deletion-shaped word in the path or
        the use-case name — never from :attr:`reads_as_deletion`, which is the author's claim and
        is what the check verifies against this."""
        if self.route is not None and self.route[0] == "DELETE":
            return True
        return bool(self.parts & _DELETION_SHAPED)


def _http(
    method: str, path: str, name: str, note: str, *, changes_state: bool = True,
    reads_as_deletion: bool = False, reversal: str | None = None,
) -> UserAction:
    return UserAction(
        name=name, changes_state=changes_state, note=note, route=(method, path),
        reads_as_deletion=reads_as_deletion, reversal=reversal)


def _seam(
    use_case: str, note: str, *, changes_state: bool, reads_as_deletion: bool = False,
    reversal: str | None = None,
) -> UserAction:
    return UserAction(
        name=use_case, changes_state=changes_state, note=note, use_case=use_case,
        reads_as_deletion=reads_as_deletion, reversal=reversal)


def _read(path: str, name: str, note: str, *, changes_state: bool = False) -> UserAction:
    """A GET endpoint. Most write nothing; the seven that record an audit entry on serve declare
    ``changes_state=True`` and ARE probed — an audit entry is a row in the very table FR-21
    protects, so an audited read is a state-changing user-reachable action."""
    return _http("GET", path, name, note, changes_state=changes_state)


# ── the registry ─────────────────────────────────────────────────────────────────────────────────
USER_ACTIONS: tuple[UserAction, ...] = (
    # ── the HTTP surface (apx/api/app.py) ──
    _http("POST", "/api/login", "login",
          "mints a session row and NOTHING evidential — verified by the probe. A failed attempt "
          "and a lockout ARE audited (FR-48); a successful login is not itself an audit_record "
          "entry, because what the record carries is the acts the session then performs",
          changes_state=False),
    _http("POST", "/api/logout", "logout",
          "deletes the caller's session row (store.delete_session), writes no audit entry and "
          "touches nothing evidential — auth state, never evidential material; nothing a lawyer "
          "could read as their document going away",
          changes_state=False, reads_as_deletion=True,
          reversal="log in again — a session is minted, never restored, and no evidential row was "
                   "involved either way"),
    _http("POST", "/api/me/password", "change-own-password",
          "rewrites one credential hash in place AND reaps every live session of that user "
          "(store.delete_user_sessions) so the change takes effect — session rows leave, "
          "evidential rows do not",
          reads_as_deletion=True,
          reversal="log in again with the new password; nothing evidential was removed to reverse"),
    _http("POST", "/api/admin/users", "create-user", "inserts a user_account row"),
    _http("POST", "/api/admin/users/{user_id}/grant", "grant-scope",
          "inserts a user_scope row, audited (FR-49)"),
    _http("POST", "/api/admin/users/{user_id}/revoke", "revoke-scope",
          "removes the user_scope grant row — authorisation state, not evidential material; the "
          "grant and the revocation are both audit_record entries (FR-49)",
          reads_as_deletion=True,
          reversal="grant the wall again (POST /api/admin/users/{user_id}/grant) — both acts stay "
                   "in the audit record"),
    _http("POST", "/api/admin/matters/{matter}/rescope", "rescope-matter",
          "updates the matter's wall in place; every pièce and chunk stays (AD-9: scope is "
          "resolved at query time, never stamped on the row)"),
    _http("POST", "/api/admin/users/{user_id}/admin", "set-admin-flag",
          "updates the admin flag and reaps that user's session rows so the change takes effect — "
          "audited; no evidential row is touched",
          reads_as_deletion=True,
          reversal="set the flag back; the grant and the ungrant are both audit_record entries"),
    _http("PUT", "/api/admin/config/{key}", "set-config-key",
          "writes a configuration row with its provenance — configuration is data (AD-24)"),
    _http("POST", "/api/admin/dr/truncation/clear", "clear-truncation",
          "an audited OVERRIDE that stamps cleared_at/reason on the marker — a truncation is never "
          "repaired and the marker row is never removed (AD-35/AD-25)",
          reads_as_deletion=True,
          reversal="nothing is removed to reverse — the marker row stays, carrying who cleared it, "
                   "when and why"),
    _http("POST", "/api/ingest", "ingest-folder-route",
          "adds pièces, chunks and failure-register entries; never removes"),
    _http("POST", "/api/ingest-upload", "ingest-upload-route",
          "enqueues an import job the worker drains; adds only. A job whose enqueue FAILED is "
          "rolled back by delete_import_job — transient orchestration, no pièce touched"),
    _http("PUT", "/api/matters/{matter}/case-theory", "set-case-theory",
          "appends a new case_theory_version; prior versions stay readable (FR-37)"),
    _http("DELETE", "/api/matters/{matter}/case-theory", "withdraw-case-theory",
          "the withdrawal is an APPENDED case_theory_version carrying no text — the HTTP verb is "
          "DELETE, the act is an insert (AD-7)",
          reads_as_deletion=True,
          reversal="PUT a new text; every prior version, including the withdrawal, stays readable"),
    _http("POST", "/api/matters/{matter}/judge", "judge-matter",
          "upserts piece_label rows (session.merge) atomically with one audit entry — a re-judge "
          "overwrites a value, never removes a row"),
    # RETIRED in Story 5.1 (decision A1): POST /recall/review and GET /recall/sample drew from
    # and bounded the Story-2.x LABEL PILE. Epic 5's discarded set is the Epic-4 derived view, so
    # both are superseded by the sampling-run routes below. Their recall_review rows stay readable
    # forever (AD-7) — this registry describes actions that EXIST, and these no longer do.

    # ── Story 4.10: the triage table. Note what is NOT here — no route sets a côté, a rank or a
    # confidence: those are derived views (AD-39/AD-19) and the table only renders them. ──
    _http("PUT", "/api/matters/{matter}/pieces/{piece_id}/label", "set-piece-label",
          "appends one taxonomy_label_entry — the ONE editable cell of the table; it changes that "
          "cell and nothing else (FR-20/FR-40)"),
    _http("POST", "/api/matters/{matter}/pieces/{piece_id}/label/revert", "revert-piece-label",
          "reverting a label APPENDS a new change-log entry carrying the restored value — the "
          "entry it reverts stays readable (AD-7/FR-20)",
          reads_as_deletion=True,
          reversal="set the label again, or revert to any earlier seq — every value the pièce ever "
                   "carried stays in the ledger"),

    # ── the read surface. Registered so nothing is invisible; the SEVEN that write an audit entry
    # on serve are state-changing and probed like any other write (FR-45 + FR-21). ──
    _read("/api/health", "read-health", "liveness; touches no store"),
    _read("/api/me", "read-own-identity", "the session's identity; a read"),
    _read("/api/admin/users", "read-users", "the tenant's users; a read"),
    _read("/api/admin/config", "read-config", "configuration-as-data values; a read"),
    _read("/api/admin/config/provenance", "read-config-provenance", "where each value came from"),
    _read("/api/admin/diagnostics", "read-diagnostics", "the content-free projection; a read"),
    _read("/api/admin/dr", "read-dr-status", "backup/restore + truncation status; a read"),
    _read("/api/imports/{job_id}", "read-import-progress", "an import job's progress; a read"),
    _read("/api/matters", "read-matters", "the matters within the caller's walls; a read"),
    _read("/api/matters/{matter}/audit", "read-audit-trail", "the audit record itself; a read"),
    _read("/api/matters/{matter}/case-theory", "read-case-theory", "the current theory; a read"),
    _read("/api/matters/{matter}/case-theory/versions", "read-case-theory-history",
          "every retained version; a read"),
    _read("/api/matters/{matter}/register", "read-matter-register", "the failure register; a read"),
    _read("/api/register", "read-register", "the failure register across matters; a read"),
    _read("/api/register/export", "export-register",
          "AUDITED on serve — an export of the register is a recorded act (FR-45/FR-49)",
          changes_state=True),
    _read("/api/matters/{matter}/triage", "read-triage", "the deduplication summary; a read"),
    _read("/api/matters/{matter}/labels", "read-labels", "the current triage labels; a read"),
    _read("/api/matters/{matter}/inventory", "read-inventory", "the six-field denominator; a read"),
    _read("/api/matters/{matter}/triage-table", "read-triage-table",
          "the whole triage surface for one ranking version — order, line, pins, labels and counts "
          "read against that one version so the parts cannot drift (AD-23); a pure read"),
    _read("/api/matters/{matter}/pieces/{piece_id}/label/log", "read-piece-change-log",
          "one row's append-only change log, previous → new (FR-20); a read"),
    _read("/api/matters/{matter}/change-log", "read-matter-change-log",
          "the matter-level change log, newest first (FR-20); a read"),
    _read("/api/matters/{matter}/freshness", "read-freshness",
          "the verdict on every stamped derived artefact — a COMPARISON of stamps, never a stored "
          "flag (FR-58/AD-23); a read that resolves nothing"),
    _read("/api/matters/{matter}/worklist", "read-worklist",
          "the derived worklist: one line per stale artefact, OFFERING a recomputation the user "
          "must start (FR-58); a read that queues nothing"),
    _read("/api/matters/{matter}/bound", "read-bound",
          "the current confidence bound with its freshness and the copy string that carries its "
          "staleness (FR-58); a read"),
    _read("/api/matters/{matter}/bound/export", "export-bound",
          "AUDITED on serve when it succeeds — an export of the bound is a recorded egress act "
          "(FR-53/FR-58). A STALE bound is refused 409 and writes nothing: the refusal is not an "
          "export", changes_state=True),
    # ── Story 5.1: the sampling run. The population is the Epic-4 DERIVED discarded view, so a
    # run records the ranking version and the position of the line — FR-22's freeze. ──
    _read("/api/matters/{matter}/sampling/sizing", "sampling-sizing",
          "how many families reach a target bound; a pure preview that writes nothing, audits "
          "nothing and starts nothing"),
    _read("/api/matters/{matter}/sampling/runs/current", "read-sampling-run",
          "one run with its frozen draw and the DERIVED verdict on its population; a read"),
    _read("/api/matters/{matter}/sampling/runs", "list-sampling-runs",
          "every run of the matter including abandoned ones, with their verdicts (AD-7); a read"),
    _http("POST", "/api/matters/{matter}/sampling/runs", "start-sampling-run",
          "inserts one sampling_run + its sampling_run_item rows + one artefact_stamp + one "
          "audit_record entry, in one transaction (AD-22) — the draw and its freeze cannot come "
          "apart"),
    _http("POST", "/api/matters/{matter}/sampling/runs/{run_id}/verdicts",
          "record-sampling-verdict",
          "appends one sampling_verdict row + one audit entry; a correction is a NEW row with a "
          "greater seq, never an edit (FR-24)"),
    _http("POST", "/api/matters/{matter}/sampling/runs/{run_id}/complete", "complete-sampling-run",
          "updates the run's status/tally/bound in place and appends one audit entry — no row is "
          "removed, and the drawn items and verdicts are untouched"),
    _http("POST", "/api/matters/{matter}/sampling/runs/{run_id}/abandon", "abandon-sampling-run",
          "flips the run's status to abandoned and appends one audit entry. Reads as giving up an "
          "hour of verdicts, so it declares itself: the draw and EVERY verdict stay readable "
          "forever (AD-7)",
          reads_as_deletion=True,
          reversal="start a new run — the abandoned one keeps its frozen identifier list and its "
                   "verdicts, and both stay readable through GET /sampling/runs"),
    _read("/api/pieces/{piece_id}", "read-piece-meta", "viewer metadata; a read"),
    _read("/api/pieces/{piece_id}/layout", "read-piece-layout", "the stored OCR layout; a read"),
    _read("/api/search", "search-corpus", "the combined search surface; not itself audited"),
    _read("/api/search/suggestive", "search-suggestive",
          "AUDITED on serve — writes one audit_record query entry (FR-45)", changes_state=True),
    _read("/api/search/exhaustive", "search-exhaustive",
          "AUDITED on serve — writes one audit_record query entry (FR-45)", changes_state=True),
    _read("/api/search/suggestive/export", "export-suggestive",
          "AUDITED on serve — writes one audit_record query entry (FR-45)", changes_state=True),
    _read("/api/search/exhaustive/export", "export-exhaustive",
          "AUDITED on serve — writes one audit_record query entry (FR-45)", changes_state=True),
    _read("/api/pieces/{piece_id}/original", "open-piece-original",
          "AUDITED on serve — writes one audit_record open entry (FR-45)", changes_state=True),
    _read("/api/pieces/{piece_id}/render", "open-piece-render",
          "AUDITED on serve — writes one audit_record open entry (FR-45)", changes_state=True),
    _read("/api/pieces/{piece_id}/page/{page}", "open-piece-page",
          "AUDITED on serve — writes one audit_record open entry (FR-45)", changes_state=True),

    # ── the Application-layer seams (apx/core/app/*.py) — the acts the FR-20 table will reach ──
    _seam("cascade.run_cascade",
          "pure compute over the ports (scorer + judge); touches no store", changes_state=False),
    _seam("embedding.error_class_for",
          "classifies an embedder error; pure", changes_state=False),
    _seam("embedding.embed_result",
          "builds the chunk payloads; the write happens in the ingestion use case",
          changes_state=False),
    _seam("ingest.ingest_one_file",
          "adds one pièce with its chunks, or a failure-register entry; never removes",
          changes_state=True),
    _seam("ingest.ingest_folder",
          "adds pièces, chunks and failure-register entries; never removes", changes_state=True),
    _seam("justification.record_justification",
          "inserts one piece_justification row, write-once (Story 4.6)", changes_state=True),
    _seam("justification.read_justification",
          "reads and containment-verifies at show time", changes_state=False),
    _seam("justification.reject_justification",
          "sets the tool's assessment aside by APPENDING a justification_rejection entry — the "
          "justification row itself is untouched and still readable (Story 4.6)",
          changes_state=True, reads_as_deletion=True,
          reversal="justification.restore_justification appends a restoring entry; the whole "
                   "rejection log stays readable"),
    _seam("justification.restore_justification",
          "appends a restoring entry to the rejection ledger", changes_state=True),
    _seam("label.assign_taxonomy_label",
          "appends one taxonomy_label_entry — the change log (Story 4.5)", changes_state=True),
    _seam("label.revert_taxonomy_label",
          "reverting is a NEW change-log entry carrying the restored value, never an erasure of "
          "the entry it reverts (Story 4.5/FR-20)",
          changes_state=True, reads_as_deletion=True,
          reversal="assign or revert again — every value the pièce ever carried stays in the "
                   "ledger"),
    _seam("line.place_line",
          "appends a line_placement entry naming the last retained pièce (Story 4.8)",
          changes_state=True),
    _seam("line.read_current_line", "reads the current placement", changes_state=False),
    _seam("line.price_line_move",
          "projects the cost of a move; writes nothing (Story 4.9)", changes_state=False),
    _seam("line.move_line",
          "appends a new placement with the priced statement shown; the prior placement stays",
          changes_state=True),
    _seam("pin.pin_piece",
          "appends a pin_entry as an override with its mandatory reason (Story 4.11/FR-25)",
          changes_state=True),
    _seam("pin.remove_pin",
          "removing a pin APPENDS a `removed` entry — the pin's whole history stays readable "
          "(Story 4.11/AD-7)",
          changes_state=True, reads_as_deletion=True,
          reversal="pin.pin_piece again; the ledger keeps every pin and every removal"),
    _seam("pin.read_current_pins", "reads the in-force pins", changes_state=False),
    _seam("rank.produce_ranking",
          "mints a ranking version and inserts its ranked entries; an earlier version's rows stay "
          "(AD-23 — a version-pinned read must still resolve)", changes_state=True),
    _seam("triage.triage_pieces",
          "runs the judge over the pièces and returns the outcome; the persistence is the caller's",
          changes_state=False),
    # the read subpackage (apx/core/app/read/) — pure reads: the audit of an open is the EDGE's
    # separate write on serve (FR-45), never a side effect of these seams, so none changes state.
    _seam("read.piece.open_piece",
          "scope-gated viewer metadata; a pure read (the open is audited by the edge on serve)",
          changes_state=False),
    _seam("read.render.render_piece",
          "a read plus a pure transform to sanitised HTML; the edge audits the served open",
          changes_state=False),
    _seam("read.scan.read_scan_page",
          "a read of one scanned page plus its OCR layout; the edge audits the served open",
          changes_state=False),
    _seam("read.deterministic.search_exhaustive",
          "the deterministic exhaustive engine; a read (the query is audited at the edge)",
          changes_state=False),
    _seam("read.semantic.search_semantic",
          "the suggestive semantic engine; a read (the query is audited at the edge)",
          changes_state=False),
    # Story 4.10 — the triage surface's read seams. Pure reads: the côté they carry is DERIVED at
    # read time from the order, the line and the pins, never stored (AD-39).
    _seam("read.triage_table.read_triage_table",
          "the whole table for one ranking version; a read that stores nothing and decides nothing",
          changes_state=False),
    _seam("read.triage_table.read_piece_change_log",
          "one row's change log, paired previous → new; a read", changes_state=False),
    _seam("read.triage_table.read_matter_change_log",
          "the matter-level change log, newest first; a read", changes_state=False),
    # Story 4.13 — freshness. Reads only: staleness is a COMPARISON of the stamp an artefact was
    # produced under against the current observables, and nothing here resolves it — FR-58 resolves
    # staleness only by an explicit user act that produces a NEW artefact.
    _seam("read.freshness.read_freshness",
          "compares each artefact's recorded stamp with the current observables; stores nothing "
          "and queues nothing", changes_state=False),
    _seam("read.freshness.read_worklist",
          "derives the worklist from the assessments — a view, never a stored queue; a read",
          changes_state=False),
    _seam("read.freshness.read_bound",
          "the current confidence bound plus the verdict on it; a read", changes_state=False),
    # Story 5.1 — the sampling run's owning seams (AD-37). The four acts write; the two reads do
    # not, and nothing here resolves an invalidation: FR-22 resolves it only by a human redraw.
    _seam("sampling.size_for_target_bound",
          "sizes a draw against a target bound; a pure preview over the port, writes nothing",
          changes_state=False),
    _seam("sampling.start_sampling_run",
          "the owning seam for the draw: one sampling_run, its items, its stamp and one audit "
          "entry in one transaction", changes_state=True),
    _seam("sampling.record_sampling_verdict",
          "appends one sampling_verdict row and one audit entry; refuses an invalidated or closed "
          "run rather than recording against a population that moved", changes_state=True),
    _seam("sampling.complete_sampling_run",
          "tallies, bounds over the unit drawn and audits — atomically; refuses a run that is not "
          "fully judged (an unjudged family is not a verdict of not-relevant, AD-19)",
          changes_state=True),
    _seam("sampling.abandon_sampling_run",
          "flips the run to abandoned and audits; the draw and the verdicts stay readable (AD-7)",
          changes_state=True),
    _seam("read.sampling.read_sampling_run",
          "one run plus the DERIVED invalidated-in-flight verdict; a read that resolves nothing",
          changes_state=False),
    _seam("read.sampling.read_sampling_runs",
          "the matter's run history, newest first; a read", changes_state=False),
)


# ── the evidential / transient partition ─────────────────────────────────────────────────────────
# Tables whose rows may legitimately go away, each with its written reason. EVERYTHING ELSE IS
# EVIDENTIAL — a table a later story adds is protected without anyone remembering to protect it.
TRANSIENT_TABLES: Mapping[str, str] = {
    "session": (
        "authentication state, not evidential material: a session row is deleted on logout "
        "(store.delete_session), on expiry, when its user is gone, on a password change and when "
        "the user's admin flag changes (store.delete_user_sessions). Deleting one destroys no "
        "record of anything that happened — the acts a session performed stay in the append-only "
        "audit record, which is what FR-21 protects. Note honestly: logout itself writes NO audit "
        "entry; it is a credential expiry, not an evidential act."),
    "user_scope": (
        "an authorisation grant, not evidential material: revoking removes the grant row, and both "
        "the grant and the revocation are audit_record entries (FR-49). The act is reversed by "
        "granting the wall again."),
    "import_job": (
        "transient import orchestration: a job whose enqueue failed is rolled back so the matter's "
        "upload path is not wedged. No pièce, chunk or failure-register entry it produced is "
        "touched."),
    "import_unit": (
        "the per-file rows of a transient import job; they go only with the job above, and only "
        "when that job never ran."),
}


def evidential_tables(all_tables: Iterable[str]) -> frozenset[str]:
    """The tables whose row count may never fall: every mapped table MINUS the written transient
    allow-list. Fail-closed by construction — a new table is evidential until someone writes down,
    here, why it is not."""
    return frozenset(all_tables) - frozenset(TRANSIENT_TABLES)


# ── leg A: every HTTP route actually declared anywhere under apx/api/ ────────────────────────────
def _literal_path(call: ast.Call) -> str | None:
    if call.args and isinstance(call.args[0], ast.Constant) \
            and isinstance(call.args[0].value, str):
        return call.args[0].value
    return None


def _api_route_methods(call: ast.Call) -> list[str] | None:
    """The literal ``methods=[...]`` of an ``api_route`` registration, upper-cased. ``None`` when it
    is not a readable literal — the caller then fails closed rather than guessing."""
    for kw in call.keywords:
        if kw.arg != "methods":
            continue
        if not isinstance(kw.value, ast.List | ast.Tuple):
            return None
        out = []
        for elt in kw.value.elts:
            if not (isinstance(elt, ast.Constant) and isinstance(elt.value, str)):
                return None
            out.append(elt.value.upper())
        return out
    return None


def _mount_is_exempt(call: ast.Call) -> bool:
    """``app.mount(prefix, StaticFiles(...))`` — the static front-end bundle, which declares no API
    route. Any OTHER mount composes a prefix this check cannot resolve, so it fails closed."""
    return any(
        isinstance(a, ast.Call) and (
            (isinstance(a.func, ast.Name) and a.func.id == _MOUNT_EXEMPTION)
            or (isinstance(a.func, ast.Attribute) and a.func.attr == _MOUNT_EXEMPTION))
        for a in call.args)


def _declared_routes(root: Path) -> tuple[set[tuple[str, str]], list[str]]:
    """Every HTTP route declared under ``root`` — **every verb**, not only the mutating four, since
    seven GET endpoints here write an audit entry on each call. Recognises the decorator form
    ``@<anything>.get/post/put/patch/delete/head/options(path)``, the ``@<anything>.api_route(path,
    methods=[...])`` form, and the non-decorator call form ``<anything>.post(path)(handler)`` — so a
    route moved onto an ``APIRouter``, into a new module, or off the decorator syntax stays visible.

    The second element lists the reasons to **fail closed**: a file that will not parse, a path that
    is not a literal, ``api_route`` with unreadable ``methods``, or a registration shape whose real
    path is composed elsewhere (``include_router`` / ``add_api_route`` / a non-static ``mount`` /
    a websocket). Failing closed is the point: a shape this check cannot read must stop the build,
    not pass it."""
    found: set[tuple[str, str]] = set()
    blocked: list[str] = []

    def _record(call: ast.Call, attr: str, where: str) -> None:
        path = _literal_path(call)
        if path is None:
            blocked.append(
                f"{where} declares a route whose path is not a literal — an unreadable path is an "
                "unregistrable action")
            return
        if attr == "api_route":
            methods = _api_route_methods(call)
            if methods is None:
                blocked.append(
                    f"{where} uses api_route() without a readable methods=[...] literal — this "
                    "check cannot tell which verbs it registers")
                return
            for m in methods:
                found.add((m.upper(), path))
        else:
            found.add((attr.upper(), path))

    for file in sorted(root.rglob("*.py")):
        if "__pycache__" in file.parts:
            continue
        tree = _parse(file)
        if tree is None:
            blocked.append(f"{file.name} will not parse")
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                    and node.func.attr in _UNRESOLVABLE_ROUTING:
                if not (node.func.attr == "mount" and _mount_is_exempt(node)):
                    blocked.append(
                        f"{file.name} uses {node.func.attr}() — this check cannot resolve the real "
                        "path of a route registered that way; teach it the shape before shipping "
                        "it")
            # the non-decorator form: app.post("/x")(handler) — an outer call over a route call
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Call) \
                    and isinstance(node.func.func, ast.Attribute) \
                    and node.func.func.attr in _HTTP_METHODS | {"api_route"}:
                _record(node.func, node.func.func.attr, f"{file.name}:<call form>")
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            for dec in node.decorator_list:
                if not (isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute)):
                    continue
                if dec.func.attr in _HTTP_METHODS | {"api_route"}:
                    _record(dec, dec.func.attr, f"{file.name}:{node.name}")
    return found, blocked


# ── leg B: the Application-layer seams — public functions taking a Ports-typed parameter ─────────
def _port_names(tree: ast.Module) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("apx.core.ports"):
            names |= {a.asname or a.name for a in node.names}
        # `import apx.core.ports.pin as p` / `from apx.core import ports` — the port type is then
        # reached through a module alias, so the ALIAS itself marks a port-typed annotation.
        elif isinstance(node, ast.Import):
            for a in node.names:
                if a.name.startswith("apx.core.ports"):
                    names.add(a.asname or a.name.split(".")[-1])
        elif isinstance(node, ast.ImportFrom) and (node.module or "") in ("apx.core", "apx"):
            names |= {a.asname or a.name for a in node.names if a.name in ("ports", "core")}
    return names


def _mentions_ports(tree: ast.Module) -> bool:
    """The module references ``apx.core.ports`` in SOME import shape. Used to fail closed: if it
    does and :func:`_port_names` found nothing, the shape is one this check cannot read — and an
    unreadable seam module must stop the build, not be silently skipped."""
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and "apx.core.ports" in (node.module or ""):
            return True
        if isinstance(node, ast.Import) and any(
                a.name.startswith("apx.core.ports") for a in node.names):
            return True
    return False


def _takes_a_port(fn: ast.FunctionDef | ast.AsyncFunctionDef, ports: set[str]) -> bool:
    """A parameter annotated by a port type — directly (``recorder: PinRecorder``), through a module
    alias (``recorder: ports.PinRecorder``), or as a forward-ref string."""
    a = fn.args
    for arg in (*a.posonlyargs, *a.args, *a.kwonlyargs):
        ann = arg.annotation
        if ann is None:
            continue
        if isinstance(ann, ast.Constant) and isinstance(ann.value, str):
            if any(p in ann.value for p in ports):
                return True
            continue
        for n in ast.walk(ann):
            if isinstance(n, ast.Name) and n.id in ports:
                return True
            if isinstance(n, ast.Attribute) and (
                    n.attr in ports
                    or (isinstance(n.value, ast.Name) and n.value.id in ports)):
                return True
    return False


def _module_label(root: Path, path: Path) -> str:
    """The dotted module label of ``path`` relative to ``root`` — ``read/piece.py`` → ``read.piece``
    — so a seam hidden in a SUBPACKAGE of ``core/app`` is named, not invisible."""
    parts = list(path.relative_to(root).with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts) if parts else root.name


def _qualified(tree: ast.Module, fn: ast.AST) -> str | None:
    """The dotted name of ``fn`` within its module, including any enclosing classes
    (``Store.record``). ``None`` when the function, or anything enclosing it, is private."""
    chain: list[str] = []

    def walk(node: ast.AST, prefix: list[str]) -> str | None:
        for child in ast.iter_child_nodes(node):
            if child is fn:
                chain.extend([*prefix, getattr(fn, "name", "?")])
                return "ok"
            if isinstance(child, ast.ClassDef):
                if walk(child, [*prefix, child.name]):
                    return "ok"
            elif isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef | ast.If | ast.Try
                            | ast.With | ast.For | ast.While):
                if walk(child, prefix):
                    return "ok"
        return None

    if walk(tree, []) is None:
        return None
    return None if any(part.startswith("_") for part in chain) else ".".join(chain)


def _declared_use_cases(root: Path) -> tuple[set[str], list[str]]:
    """Every public Ports-taking callable under ``root`` — the AD-4 seam shape.

    **Recursive over the tree** (``core/app`` has a ``read/`` subpackage) and **recursive over the
    AST** (a seam nested in an ``if`` / ``try`` / ``with``, or defined as a public method of a
    public class, is still a seam). Names are qualified by their enclosing classes, so two ``run``
    methods never collide. Returns the set and the reasons to fail closed: a file that will not
    parse, or a
    module that imports from ``apx.core.ports`` in a shape this check cannot read — the latter would
    otherwise make a whole seam module silently invisible."""
    found: set[str] = set()
    blocked: list[str] = []
    for path in sorted(root.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        tree = _parse(path)
        if tree is None:
            blocked.append(f"{path.name} will not parse")
            continue
        ports = _port_names(tree)
        if not ports:
            if _mentions_ports(tree):
                blocked.append(
                    f"{path.name} imports from apx.core.ports in a shape this check cannot read — "
                    "an unreadable seam module would be silently invisible to the registry")
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            if not _takes_a_port(node, ports):
                continue
            qualified = _qualified(tree, node)
            if qualified is not None:
                found.add(f"{_module_label(root, path)}.{qualified}")
    return found, blocked


def user_action_registry_is_complete(
    actions: Iterable[UserAction] | None = None, *, api: Path | None = None,
    core_app: Path | None = None,
) -> CheckResult:
    """Every user-reachable action is registered, and every registered action still exists —
    **both legs, both ways** (FR-21/FR-56).

    Leg A is the HTTP surface — **every verb**, because seven GET endpoints here write an audit
    entry on each call. Leg B is the Application-layer seams (a public ``core/app`` callable taking
    a Ports-typed parameter). Leg B is not decoration: label, line, pin and justification are
    reachable ONLY at that seam until Story 4.10 routes them, so leg A alone would let the whole
    triage-control surface ship unregistered. A missing row and a stale row both fail — the registry
    the probe walks is only a bound if it cannot drift.

    Note what this check deliberately does NOT do: it does not police ``changes_state`` by name or
    by verb. A blanket "a POST changes state" rule would be **false** here — ``login`` and
    ``logout`` write nothing but a ``session`` row — and a false rule teaches people to work around
    it. The flag is instead pinned by two stronger facts: the probe covers **every route row
    regardless of the flag**, so no HTTP action can be exempted by setting it; and the probe
    asserts at runtime that every ``changes_state=True`` action really writes an evidential row and
    every ``changes_state=False`` one really does not. The flag is verified by execution, not
    trusted."""
    name, ad = "the user-action registry is complete", "AD-7"
    rows = tuple(USER_ACTIONS if actions is None else actions)
    routes, blocked = _declared_routes(_API_ROOT if api is None else api)
    if blocked:
        return CheckResult(name, ad, False, f"{blocked[0]} — failing closed")
    seams, seams_blocked = _declared_use_cases(_CORE_APP if core_app is None else core_app)
    if seams_blocked:
        return CheckResult(name, ad, False, f"{seams_blocked[0]} — failing closed")
    registered_routes = {a.route for a in rows if a.route is not None}
    registered_seams = {a.use_case for a in rows if a.use_case is not None}
    for label, declared, registered in (
        ("HTTP route", routes, registered_routes),
        ("core/app use-case seam", seams, registered_seams),
    ):
        missing = sorted(str(x) for x in declared - registered)  # type: ignore[operator]
        if missing:
            return CheckResult(
                name, ad, False,
                f"{len(missing)} {label}(s) exist but are not in USER_ACTIONS: {missing} — an "
                "action outside the registry is outside the probe that proves it destroys nothing "
                "(FR-21/FR-56)")
        stale = sorted(str(x) for x in registered - declared)  # type: ignore[operator]
        if stale:
            return CheckResult(
                name, ad, False,
                f"{len(stale)} registered {label}(s) no longer exist: {stale} — a stale row makes "
                "the registry look complete while the probe walks nothing")
    return CheckResult(
        name, ad, True,
        f"{len(registered_routes)} HTTP routes + {len(registered_seams)} use-case seams "
        f"registered; {sum(1 for a in rows if a.changes_state)} change state and are probed")


def deletion_shaped_actions_declare_their_reversal(
    actions: Iterable[UserAction] | None = None,
) -> CheckResult:
    """An action whose **source shape** reads as deletion declares that it does, and names its
    reversal (FR-21/FR-5/AD-7).

    The shape is read off the source — an HTTP ``DELETE``, or a deletion-shaped word in the route
    path or the use-case name — never off ``reads_as_deletion``, which is the author's claim. So
    the claim cannot be quietly set to ``False`` to dodge the rule: the second leg of the same
    pattern ``justification_names_its_evidence`` uses. (The converse is deliberately permitted: an
    action may volunteer ``reads_as_deletion`` — ``logout`` does — because over-declaring costs a
    reader nothing and under-declaring is the failure this exists to catch.)"""
    name, ad = "a deletion-shaped action names its reversal", "AD-7"
    rows = tuple(USER_ACTIONS if actions is None else actions)
    shaped = [a for a in rows if a.looks_like_deletion]
    for action in shaped:
        if not action.reads_as_deletion:
            return CheckResult(
                name, ad, False,
                f"{action.name} reads as deletion in the source but is not declared as one — "
                "anything a user could read as deletion is a reversible, labelled, recorded state "
                "change, and says so here (FR-21)")
        if not (action.reversal or "").strip():
            return CheckResult(
                name, ad, False,
                f"{action.name} is declared a deletion-shaped act but names no reversal (FR-21)")
    declared = sum(1 for a in rows if a.reads_as_deletion)
    return CheckResult(
        name, ad, True,
        f"{len(shaped)} deletion-shaped action(s) in the source, {declared} declared, each naming "
        "its reversal")
