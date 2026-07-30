"""The deterministic exhaustive engine (Story 3.2, AD-20/AD-21) — the second reader through the one
read entry point (AD-14). It proves an **absence**: over the scoped *corpus*, in one snapshot, it
returns the **complete** normalised match set as an ``ExhaustiveResultSet`` whose
``truth_status`` is
the constant ``EXHAUSTIVE`` — never a top-k, never truncated (AD-20).

Its honesty is the *denominator* and the qualifications the set carries (AD-42, as data). Two AD-20
rules hold here: it takes **no** limit (a truncation would downgrade an exhaustive set — enforced as
a structural property), and it **refuses** over a *matter* with an open *import job* (a moving
population would split the absence claim across snapshots), naming the job. The *register* is
searched **separately** (AD-21): a register name-match is a distinct hit, never inside the results.
Scope is a query **pre-filter** (AD-13); an empty scope reads nothing (fail-closed, AD-12).
"""

from __future__ import annotations

from apx.core.domain.inventory import Inventory
from apx.core.domain.normalization import NORMALIZATION, normalize
from apx.core.domain.retrieval import ExhaustiveResultSet
from apx.core.ports.read import ExactSearchReader

_EMPTY_DENOMINATOR = Inventory(submitted_pieces=0, in_corpus=0, open_register_entries=0)


class MovingPopulation(Exception):
    """The deterministic engine refused: an *import job* is open over an in-scope *matter*, so the
    *corpus* is moving and an absence claim cannot be made honestly over it (AD-20). Names the
    job(s); it never silently downgrades to a suggestive/partial set."""

    def __init__(self, jobs: list[str]) -> None:
        self.jobs = jobs
        super().__init__(
            f"the corpus is moving — an import job is open ({', '.join(jobs)}); "
            "finish or cancel it before an exhaustive search, or open the worklist")


def search_exhaustive(
    *, tenant: str, scopes: set[str], query: str, reader: ExactSearchReader
) -> ExhaustiveResultSet:
    """Prove an absence (or find every match) over the scoped *corpus*. Normalises the query
    (``fr-fold-v1``), refuses over a moving population, and returns the COMPLETE match set as an
    ``ExhaustiveResultSet`` with its denominator + qualifications. An empty scope yields an empty
    exhaustive set (fail-closed). Takes **no** limit — an exhaustive set is never truncated."""
    if not scopes:
        return ExhaustiveResultSet(
            results=(), denominator=_EMPTY_DENOMINATOR, ocr_share=0.0, below_quality_share=0.0,
            register_hits=(), normalization=NORMALIZATION,
        )
    open_jobs = reader.open_import_jobs(tenant=tenant, scopes=scopes)
    if open_jobs:
        raise MovingPopulation(open_jobs)
    found = reader.exact_search(tenant=tenant, scopes=scopes, normalized_query=normalize(query))
    return ExhaustiveResultSet(
        results=tuple(found.results),
        denominator=found.denominator,
        ocr_share=found.ocr_share,
        below_quality_share=found.below_quality_share,
        register_hits=tuple(found.register_hits),
        normalization=NORMALIZATION,
    )
