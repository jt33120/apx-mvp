"""The content-free projection registry (story 1.10, AD-26/FR-31): the emit path, the attestation
model, deterministic output, the union flattening, and the secret-redaction primitive. Pure core.
"""

from __future__ import annotations

from apx.core.projection import (
    Attestation,
    Snapshot,
    ValueKind,
    _safe_version,
    project_all,
    projection_strings,
    redact,
)


def _snap(*, pieces=0, failures=0, matters=0, hist=None, schema=(), extractor=()) -> Snapshot:
    return Snapshot(
        piece_count=pieces, failure_count=failures, matter_count=matters,
        error_class_histogram=hist or {}, schema_versions=schema, extractor_versions=extractor)


def test_project_all_runs_every_registered_projector_in_deterministic_order() -> None:
    names = [p.projector for p in project_all(_snap(pieces=3))]
    assert names == sorted(names)  # reproducible order (AD-26)
    assert {"corpus_counts", "error_class_histogram", "versions"} <= set(names)


def test_corpus_counts_emits_only_cardinalities() -> None:
    by_name = {p.projector: p for p in project_all(_snap(pieces=5, failures=2, matters=3))}
    assert by_name["corpus_counts"].values == {"pieces": 5, "failures": 2, "matters": 3}
    assert "count" in by_name["corpus_counts"].kinds  # the declared shape travels with the value


def test_versions_and_histogram_emit_their_content_free_shapes() -> None:
    by_name = {p.projector: p for p in project_all(
        _snap(hist={"unreadable": 2}, schema=("s1",), extractor=("e1",)))}
    assert by_name["versions"].values == {"schema": ["s1"], "extractor": ["e1"]}
    assert by_name["error_class_histogram"].values == {"by_class": {"unreadable": 2}}


def test_attestation_requires_a_floor_only_for_a_text_derived_value() -> None:
    assert Attestation(kinds=(ValueKind.COUNT,)).is_valid()   # a cardinality needs no floor
    assert not Attestation(kinds=()).is_valid()               # a projector emits something
    text_no_floor = Attestation(kinds=(ValueKind.ATTESTED_AGGREGATE,))
    assert not text_no_floor.is_valid()                       # text-derived value: floor required
    assert Attestation(
        kinds=(ValueKind.ATTESTED_AGGREGATE,), min_pieces=5, min_matters=2).is_valid()


def test_a_floor_of_one_matter_is_rejected() -> None:
    # AD-26(iii): a value must be "never traceable to one matter" — a floor of 1 would bless a
    # value quotable from a single matter, so the floor must span ≥ 2 matters (and ≥ 2 pièces).
    assert not Attestation(
        kinds=(ValueKind.ATTESTED_AGGREGATE,), min_pieces=1, min_matters=1).is_valid()
    assert not Attestation(
        kinds=(ValueKind.ATTESTED_AGGREGATE,), min_pieces=5, min_matters=1).is_valid()


def test_safe_version_bounds_a_content_bearing_identifier() -> None:
    assert _safe_version("tesseract/1.2.3") == "tesseract/1.2.3"   # a real version id passes
    assert _safe_version("slice-a") == "slice-a"
    assert _safe_version("a version with spaces") == "«non-conforming»"   # a sentence is bounded
    assert _safe_version("x" * 64) == "«non-conforming»"                  # oversized is bounded


def test_redact_scrubs_secret_values_longest_first() -> None:
    assert redact("dsn=postgres://u:s3cr3t@h/db", ["postgres://u:s3cr3t@h/db", "s3cr3t"]) == (
        "dsn=«redacted»")
    assert redact("a clean line", ["s3cr3t"]) == "a clean line"


def test_projection_strings_flattens_keys_and_values_for_the_union_scan() -> None:
    blob = projection_strings(project_all(_snap(hist={"unreadable": 2}, schema=("s1",))))
    assert "unreadable" in blob and "s1" in blob  # a histogram KEY and a version VALUE both scanned
