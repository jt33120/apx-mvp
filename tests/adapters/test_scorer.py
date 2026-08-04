"""The Postgres SemanticScorer adapter (Story 4.2): the statement pre-filters scope and takes the
max cosine per pièce (shape asserted by compiling to PG SQL, no DB), and the scorer short-circuits
when there is nothing to score."""

from __future__ import annotations

from sqlalchemy.dialects import postgresql

from apx.adapters.store_postgres.scorer import PgSemanticScorer, piece_scores_stmt


def _pg(stmt) -> str:  # noqa: ANN001
    return str(stmt.compile(dialect=postgresql.dialect())).lower()


def test_the_statement_scope_pre_filters_and_takes_the_max_cosine_per_piece() -> None:
    sql = _pg(piece_scores_stmt(
        tenant="t", matter="m", scopes={"w"}, query_vector=[0.1] * 4, piece_ids=["a", "b"]))
    assert "<=>" in sql and "min(" in sql and "group by" in sql        # max cosine per pièce
    assert "matter_scope.scope in" in sql                              # the AD-13 scope pre-filter
    assert "chunk.tenant =" in sql and "chunk.matter =" in sql         # tenant + matter pinned
    assert "chunk.piece_id in" in sql                                  # bounded to the given set


def test_the_scorer_scores_nothing_for_an_empty_set_or_empty_scope() -> None:
    class _NoEmbed:
        dimensions = 1024
        model_id = "x"
        model_version = "v"

        def embed(self, texts: list[str]) -> list[list[float]]:
            raise AssertionError("must not embed when there is nothing to score")

    scorer = PgSemanticScorer(session_factory=lambda: None, embedder=_NoEmbed())
    assert scorer.score(tenant="t", matter="m", scopes={"w"}, query_text="q", piece_ids=[]) == {}
    assert scorer.score(tenant="t", matter="m", scopes=set(), query_text="q", piece_ids=["a"]) == {}
