from __future__ import annotations

from vlm_construct_audit.construct_v2.generator import build_reasoning_rows, build_uptake_rows
from vlm_construct_audit.construct_v2.validation import (
    write_balance_artifacts,
    write_serialization_equivalence,
)


def test_balance_artifacts_pass_for_registered_factorial_design() -> None:
    result = write_balance_artifacts(build_reasoning_rows(768), build_uptake_rows())
    assert result == {
        "answer_balance": "PASS",
        "relation_balance": "PASS",
        "template_balance": "PASS",
        "uptake_balance": "PASS",
    }


def test_natural_language_and_triples_are_canonically_equal() -> None:
    result = write_serialization_equivalence(build_reasoning_rows(768))
    assert result["status"] == "PASS"
    assert result["canonical_nl_triples_equality"] == 1.0
    assert result["changed_fact_count_exactly_one_rate"] == 1.0
    assert result["direct_image_text_conflict_count"] == 0

