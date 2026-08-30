from __future__ import annotations

from vlm_construct_audit.construct_v2.generator import UPTAKE_TASKS, build_uptake_rows
from vlm_construct_audit.construct_v2.uptake import evaluate_uptake_outputs, validate_uptake_design


def _predictions(failing_task: str | None = None) -> list[dict]:
    rows = []
    for task in UPTAKE_TASKS:
        for index in range(64):
            rows.append(
                {
                    "model_family": "test_family",
                    "serialization": "natural_language",
                    "uptake_task": task,
                    "relevant_correct": not (task == failing_task and index >= 48),
                    "irrelevant_correct": index < 8,
                }
            )
    return rows


def test_uptake_design_is_balanced_per_task() -> None:
    result = validate_uptake_design(build_uptake_rows())
    assert result["status"] == "PASS"
    assert all(set(counts.values()) == {16} for counts in result["answer_counts"].values())


def test_task_specific_gates_pass_with_strong_paired_utility() -> None:
    result = evaluate_uptake_outputs(_predictions())
    assert result["status"] == "PASS"
    assert result["reasoning_eligibility"]["test_family::natural_language"]["eligible"]


def test_one_failed_task_cannot_be_compensated_by_other_tasks() -> None:
    result = evaluate_uptake_outputs(_predictions("direction_reversal"))
    eligibility = result["reasoning_eligibility"]["test_family::natural_language"]
    assert result["status"] == "INVALID_INTERVENTION"
    assert eligibility["eligible"] is False
    assert eligibility["cross_task_averaging_used"] is False
