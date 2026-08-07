"""The three Story-5.1 structural gates, proven LIVE (FR-22/FR-23/AD-39/AD-7/AD-23).

Each check is exercised three ways: it passes the real tree, it FIRES on a scratch copy carrying a
deliberate violation, and it FAILS CLOSED on something it cannot read. A check nobody has watched
fail is a check nobody knows is connected — the Epic 4 lesson about silent reviewers, applied to
the harness itself. The real tree is never modified: every violation is injected into a copy under
``tmp_path``.
"""

from __future__ import annotations

from pathlib import Path

from apx.checks.no_legacy_bound import no_new_legacy_bound_is_written
from apx.checks.sampling_freeze import a_sampling_run_freezes_its_identifiers
from apx.checks.sampling_population import sampling_population_is_the_derived_view

_APX = Path(__file__).resolve().parents[2] / "apx"
_STORE = _APX / "adapters" / "store_postgres" / "store.py"
_MODELS = _APX / "adapters" / "store_postgres" / "models.py"


def _mutated(tmp_path: Path, source: Path, old: str, new: str, name: str = "copy.py") -> Path:
    """A scratch COPY of a real module with one deliberate edit. The real tree is untouched."""
    text = source.read_text(encoding="utf-8")
    assert old in text, f"the anchor is no longer in {source.name}: {old!r}"
    target = tmp_path / name
    target.write_text(text.replace(old, new, 1), encoding="utf-8")
    return target


def _module(tmp_path: Path, name: str, src: str) -> Path:
    path = tmp_path / f"{name}.py"
    path.write_text(src, encoding="utf-8")
    return path


# ── the population is the DERIVED discarded set, not the label pile (decision A1) ────────────────

def test_the_population_check_passes_the_real_tree() -> None:
    assert sampling_population_is_the_derived_view().ok


def test_it_fires_when_the_derivation_stops_going_through_derive_triage_sets(
    tmp_path: Path
) -> None:
    copy = _mutated(
        tmp_path, _STORE,
        "        sets = derive_triage_sets(", "        sets = _not_the_derivation(")
    r = sampling_population_is_the_derived_view(copy)
    assert not r.ok and "derive_triage_sets" in r.detail


def test_it_fires_when_the_draw_and_the_observable_stop_sharing_one_derivation(
    tmp_path: Path
) -> None:
    """The leg that matters most: a run drawn over one set and invalidated against another is the
    falsely-fresh defect with a new cause."""
    copy = _mutated(
        tmp_path, _STORE,
        "        derived = self._derived_discarded(session, tenant, matter, version_no)\n"
        "        discarded = derived[1] if derived is not None else ()",
        "        discarded = ()   # the observable no longer watches the population")
    r = sampling_population_is_the_derived_view(copy)
    assert not r.ok and "_compute_stamp" in r.detail and "same derivation" in r.detail


def test_it_fires_when_a_sampling_function_reads_the_label_pile(tmp_path: Path) -> None:
    copy = _mutated(
        tmp_path, _STORE,
        "        derived = self._derived_discarded(session, tenant, matter, version_no)",
        "        _ = LabelRecord.label\n"
        "        derived = self._derived_discarded(session, tenant, matter, version_no)")
    r = sampling_population_is_the_derived_view(copy)
    assert not r.ok and "LabelRecord" in r.detail and "decision A1" in r.detail


def test_the_population_check_fails_closed_when_the_seam_is_renamed(tmp_path: Path) -> None:
    copy = _mutated(
        tmp_path, _STORE, "    def start_sampling_run(", "    def start_run_renamed(")
    r = sampling_population_is_the_derived_view(copy)
    assert not r.ok and "failing closed" in r.detail


def test_the_population_check_fails_closed_on_an_unparseable_module(tmp_path: Path) -> None:
    r = sampling_population_is_the_derived_view(_module(tmp_path, "broken", "def (:\n"))
    assert not r.ok and "cannot parse" in r.detail


# ── the freeze is a shape: identifiers, not a seed (FR-22) ───────────────────────────────────────

def test_the_freeze_check_passes_the_real_tree() -> None:
    assert a_sampling_run_freezes_its_identifiers().ok


def test_it_fires_when_a_freeze_column_becomes_nullable(tmp_path: Path) -> None:
    copy = _mutated(
        tmp_path, _MODELS,
        "    last_retained_piece_id: Mapped[str] = mapped_column(String(64), nullable=False)\n"
        "    pin_ledger_seq: Mapped[int] = mapped_column(Integer, nullable=False)",
        "    last_retained_piece_id: Mapped[str] = mapped_column(String(64), nullable=True)\n"
        "    pin_ledger_seq: Mapped[int] = mapped_column(Integer, nullable=False)")
    r = a_sampling_run_freezes_its_identifiers(copy)
    assert not r.ok and "last_retained_piece_id" in r.detail and "not a freeze" in r.detail


def test_it_fires_when_the_identifier_list_is_dropped_for_a_seed(tmp_path: Path) -> None:
    """FR-22's own sentence, made structural: deleting the item table to keep only the run's seed
    fails the build."""
    copy = _mutated(
        tmp_path, _MODELS, "class SamplingRunItem(Base):", "class SamplingRunItemRemoved(Base):")
    r = a_sampling_run_freezes_its_identifiers(copy)
    assert not r.ok and "a seed alone is insufficient" in r.detail


def test_it_fires_when_the_run_declares_no_scope(tmp_path: Path) -> None:
    copy = _mutated(
        tmp_path, _MODELS,
        "    scope: Mapped[str] = mapped_column(String, nullable=False)\n"
        "    seed: Mapped[int] = mapped_column(Integer, nullable=False)",
        "    seed: Mapped[int] = mapped_column(Integer, nullable=False)")
    r = a_sampling_run_freezes_its_identifiers(copy)
    assert not r.ok and "scope" in r.detail


def test_the_freeze_check_fails_closed_on_an_unparseable_module(tmp_path: Path) -> None:
    r = a_sampling_run_freezes_its_identifiers(_module(tmp_path, "broken", "class (:\n"))
    assert not r.ok and "cannot parse" in r.detail


# ── the legacy bound writer cannot come back (AD-7 — superseded, not deleted) ────────────────────

def test_the_legacy_bound_check_passes_the_real_tree() -> None:
    assert no_new_legacy_bound_is_written().ok


def test_it_fires_on_a_new_recall_review_construction(tmp_path: Path) -> None:
    src = (
        "from apx.adapters.store_postgres.models import RecallReview\n"
        "def revive(session):\n"
        "    session.add(RecallReview(id='x', tenant='t', matter='m'))\n")
    r = no_new_legacy_bound_is_written([_module(tmp_path, "revived", src)])
    assert not r.ok and "RecallReview" in r.detail and "ambiguous referent" in r.detail


def test_reading_the_legacy_table_stays_allowed(tmp_path: Path) -> None:
    """AD-7 — the rows are readable history. Only a WRITER is forbidden, so ``read_current_bound``
    can still fall back to them for a matter that has no sampling run."""
    src = (
        "from apx.adapters.store_postgres.models import RecallReview\n"
        "def read(session):\n"
        "    return session.query(RecallReview).order_by(RecallReview.reviewed_at).first()\n")
    assert no_new_legacy_bound_is_written([_module(tmp_path, "reader", src)]).ok


def test_the_legacy_bound_check_fails_closed_on_an_unparseable_module(tmp_path: Path) -> None:
    r = no_new_legacy_bound_is_written([_module(tmp_path, "broken", "def (:\n")])
    assert not r.ok and "cannot parse" in r.detail


# ── the review's strengthenings: a gate defeated by a rename is a habit, not a property ──────────

def test_the_legacy_bound_check_also_catches_a_qualified_construction(tmp_path: Path) -> None:
    """CONFIRMED [MEDIUM]. It matched only the bare name, so the writer was one import style away
    from coming back."""
    src = (
        "from apx.adapters.store_postgres import models\n"
        "def revive(session):\n"
        "    session.add(models.RecallReview(id='x'))\n")
    r = no_new_legacy_bound_is_written([_module(tmp_path, "qualified", src)])
    assert not r.ok and "RecallReview" in r.detail


def test_the_population_check_catches_an_aliased_label_pile(tmp_path: Path) -> None:
    """CONFIRMED [MEDIUM]. `LR = LabelRecord` at module level defeated the name match, so the draw
    could be re-pointed at population #1 with the gate still green."""
    copy = _mutated(
        tmp_path, _STORE,
        "class ScopeDenied(",
        "_LR_ALIAS = LabelRecord\n\n\nclass ScopeDenied(", name="aliased.py")
    text = copy.read_text(encoding="utf-8").replace(
        "        derived = self._derived_discarded(session, tenant, matter, version_no)",
        "        _ = _LR_ALIAS.label\n"
        "        derived = self._derived_discarded(session, tenant, matter, version_no)", 1)
    copy.write_text(text, encoding="utf-8")
    r = sampling_population_is_the_derived_view(copy)
    assert not r.ok and "_LR_ALIAS" in r.detail


def test_the_population_check_catches_a_raw_discard_predicate(tmp_path: Path) -> None:
    """The ORM is not the only way back to the wrong population: a raw string predicate reads the
    Story-2.x pile just as wrongly."""
    copy = _mutated(
        tmp_path, _STORE,
        "        derived = self._derived_discarded(session, tenant, matter, version_no)",
        "        _ = \"discard\"\n"
        "        derived = self._derived_discarded(session, tenant, matter, version_no)")
    r = sampling_population_is_the_derived_view(copy)
    assert not r.ok and "discard" in r.detail
