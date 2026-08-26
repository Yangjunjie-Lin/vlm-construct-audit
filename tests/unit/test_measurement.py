from __future__ import annotations

import math

import pytest

from vlm_construct_audit.measurement.contracts import (
    generate_constrained_raw,
    option_map,
    parse_constrained,
    recompute_candidate_scores,
    score_conditional_likelihood,
)


def test_multi_token_likelihood_is_length_normalized() -> None:
    result = score_conditional_likelihood("deep blue", ["red", "deep blue", "bright yellow"])
    selected = result["candidate_scores"]["deep blue"]
    assert selected["tokens"] == ["deep", "blue"]
    assert math.isclose(selected["raw_log_likelihood"], -0.2)
    assert math.isclose(selected["length_normalized_score"], -0.1)
    assert result["parsed_response"] == "deep blue"


def test_option_ids_are_separate_from_semantic_answers() -> None:
    candidates = ["red", "blue", "green"]
    mapping = option_map(candidates)
    result = score_conditional_likelihood("blue", candidates)
    assert mapping == {"A": "red", "B": "blue", "C": "green"}
    assert set(result["candidate_scores"]) == set(candidates)
    assert not set(result["candidate_scores"]) & set(mapping)


@pytest.mark.parametrize(
    "raw,status",
    [
        ('{"answer":"red"}', "ok"),
        ('{"option_id":"A"}', "failed_schema"),
        ('{"answer":" red "}', "failed_disallowed_answer"),
        ("red", "failed_invalid_json"),
        ('{"answer":"red","repair":"blue"}', "failed_schema"),
    ],
)
def test_constrained_parser_fails_closed(raw: str, status: str) -> None:
    assert parse_constrained(raw, ["red", "blue"])["parser_status"] == status


def test_frozen_candidate_record_has_two_equal_scorers() -> None:
    result = score_conditional_likelihood("green", ["red", "deep blue", "green"])
    independent = recompute_candidate_scores(result["candidate_scores"])
    for answer, score in independent.items():
        stored = result["candidate_scores"][answer]["length_normalized_score"]
        assert score == stored


def test_invalid_schema_is_not_silently_repaired() -> None:
    raw = generate_constrained_raw("red", schema_valid=False)
    parsed = parse_constrained(raw, ["red", "blue"])
    assert parsed == {"parsed_response": None, "parser_status": "failed_schema"}
