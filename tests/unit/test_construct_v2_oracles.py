from __future__ import annotations

from vlm_construct_audit.construct_v2.generator import build_reasoning_rows
from vlm_construct_audit.construct_v2.oracle import (
    EvidenceOnlyOracle,
    ImageOnlyOracle,
    JointMultimodalOracle,
    QuestionOnlyOracle,
    evaluate_oracles,
)


def test_symbolic_oracle_support_and_joint_solutions() -> None:
    rows = build_reasoning_rows(768)
    for row in rows:
        assert len(QuestionOnlyOracle.support(row)) == 4
        assert len(ImageOnlyOracle.support(row)) == 2
        assert len(EvidenceOnlyOracle.support(row)) == 2
        assert JointMultimodalOracle.solve(row) == row["answer"]["semantic"]
        assert (
            JointMultimodalOracle.solve(row, "corrupted")
            == row["answer"]["corrupted_semantic"]
        )


def test_oracle_construct_gates_pass_exactly() -> None:
    metrics = evaluate_oracles(build_reasoning_rows(768))
    assert metrics["status"] == "PASS"
    assert metrics["question_only"]["bayes_optimal_accuracy"] == 0.25
    assert metrics["question_only"]["unique_solution_rate"] == 0
    assert metrics["image_only"]["bayes_optimal_accuracy"] == 0.5
    assert metrics["image_only"]["conditional_answer_entropy_bits"] == 1.0
    assert metrics["evidence_only"]["bayes_optimal_accuracy"] == 0.5
    assert metrics["evidence_only"]["conditional_answer_entropy_bits"] == 1.0
    assert metrics["joint_multimodal"]["accuracy"] == 1.0
    assert metrics["joint_multimodal"]["unique_solution_rate"] == 1.0

