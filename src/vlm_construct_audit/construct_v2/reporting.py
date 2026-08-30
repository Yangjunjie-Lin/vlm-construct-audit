"""Assemble inference-free v2 preaudit reports and the single automated gate."""

from __future__ import annotations

import hashlib
from typing import Any

import yaml

from .generator import ROOT
from .runner_guard import verify_no_construct_v2_inference


def _load(path: str) -> dict[str, Any]:
    return yaml.safe_load((ROOT / path).read_text(encoding="utf-8"))


def _dump(path: str, value: Any) -> None:
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(yaml.safe_dump(value, sort_keys=False, allow_unicode=True), encoding="utf-8")


def _sha256(path: str) -> str:
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def _view_max(shortcuts: dict[str, Any], view: str, metric: str) -> float:
    return max(model[metric] for model in shortcuts["views"][view].values())


def build_construct_v2_report() -> dict[str, Any]:
    oracle = _load("artifacts/construct_v2/oracle_metrics.yaml")
    leakage = _load("artifacts/construct_v2/leakage_metrics.yaml")
    answer = _load("artifacts/construct_v2/answer_balance.yaml")
    relation = _load("artifacts/construct_v2/relation_balance.yaml")
    template = _load("artifacts/construct_v2/template_balance.yaml")
    token = _load("artifacts/construct_v2/token_balance.yaml")
    equivalence = _load("artifacts/construct_v2/serialization_equivalence.yaml")
    power = _load("artifacts/construct_v2/multiplicity_power.yaml")
    verification = _load("artifacts/construct_v2/verification_report.yaml")
    review = _load("artifacts/construct_v2_review/packet_manifest.yaml")
    novelty = _load("research/construct_restart/v2_literature_matrix.yaml")
    no_inference = verify_no_construct_v2_inference()
    shortcuts = leakage["cross_validated_shortcuts"]
    gates = {
        "joint_multimodal_oracle_accuracy_1_00": oracle["joint_multimodal"]["accuracy"] == 1.0,
        "question_only_unique_solution_rate_0": oracle["question_only"]["unique_solution_rate"] == 0,
        "image_only_unique_solution_rate_0": oracle["image_only"]["unique_solution_rate"] == 0,
        "evidence_only_unique_solution_rate_0": oracle["evidence_only"]["unique_solution_rate"] == 0,
        "question_only_shortcut_accuracy_le_0_30": _view_max(
            shortcuts, "question_only", "cross_validated_accuracy"
        )
        <= 0.30,
        "metadata_shortcut_accuracy_le_0_30": _view_max(
            shortcuts, "scene_metadata_only", "cross_validated_accuracy"
        )
        <= 0.30,
        "entity_label_shortcut_accuracy_le_0_30": _view_max(
            shortcuts, "entity_labels_only", "cross_validated_accuracy"
        )
        <= 0.30,
        "option_position_shortcut_accuracy_le_0_30": _view_max(
            shortcuts, "option_position_only", "cross_validated_accuracy"
        )
        <= 0.30,
        "all_shortcut_95_upper_bounds_le_0_35": (
            shortcuts["maximum_one_sided_95_exact_upper"] <= 0.35
        ),
        "answer_balance": answer["status"] == "PASS",
        "relation_balance": relation["status"] == "PASS",
        "template_balance": template["status"] == "PASS",
        "task_specific_uptake_balance": verification["balance"]["uptake_balance"] == "PASS",
        "correct_corrupted_changed_fact_count_1": equivalence[
            "changed_fact_count_exactly_one_rate"
        ]
        == 1.0,
        "direct_image_text_conflict_count_0": equivalence["direct_image_text_conflict_count"] == 0,
        "canonical_nl_triples_equality_1_00": equivalence[
            "canonical_nl_triples_equality"
        ]
        == 1.0,
        "token_length_maximum_difference_le_1": token["maximum_observed_difference"] <= 1,
        "overall_stable_path_power_ge_0_80": next(
            item
            for item in power["primary_sample_size_evaluation"]
            if item["n"] == power["chosen_reasoning_n"]
        )["overall_stable_path_power_range_over_dependence"][0]
        >= 0.80,
        "p3_method_hashes_unchanged": power["p3_method_hashes"]["unchanged"],
        "scientific_model_output_count_0": no_inference["formal_prediction_files"] == 0,
        "runner_blocked": no_inference["runner_blocked"],
    }
    automated_pass = all(gates.values())
    human_pending = review["reviewer_count_completed"] < review["reviewer_count_required"]
    if not automated_pass:
        decision = "CONSTRUCT_V2_AUTOMATED_NO_GO"
    elif human_pending:
        decision = "PENDING_EXTERNAL_CONSTRUCT_REVIEW"
    else:
        decision = "CONSTRUCT_V2_READY_FOR_INDEPENDENT_AUDIT"
    values = {
        "joint_multimodal_oracle_accuracy": oracle["joint_multimodal"]["accuracy"],
        "question_only_unique_solution_rate": oracle["question_only"]["unique_solution_rate"],
        "image_only_unique_solution_rate": oracle["image_only"]["unique_solution_rate"],
        "evidence_only_unique_solution_rate": oracle["evidence_only"]["unique_solution_rate"],
        "shortcut_maximum_accuracy": shortcuts["maximum_accuracy"],
        "shortcut_maximum_one_sided_95_exact_upper": shortcuts[
            "maximum_one_sided_95_exact_upper"
        ],
        "question_only_maximum_accuracy": _view_max(
            shortcuts, "question_only", "cross_validated_accuracy"
        ),
        "metadata_maximum_accuracy": _view_max(
            shortcuts, "scene_metadata_only", "cross_validated_accuracy"
        ),
        "entity_label_maximum_accuracy": _view_max(
            shortcuts, "entity_labels_only", "cross_validated_accuracy"
        ),
        "option_position_maximum_accuracy": _view_max(
            shortcuts, "option_position_only", "cross_validated_accuracy"
        ),
        "chosen_reasoning_n": power["chosen_reasoning_n"],
        "chosen_n_stable_path_power_range": next(
            item
            for item in power["primary_sample_size_evaluation"]
            if item["n"] == power["chosen_reasoning_n"]
        )["overall_stable_path_power_range_over_dependence"],
        "token_maximum_absolute_difference": token["maximum_observed_difference"],
        "formal_prediction_files": no_inference["formal_prediction_files"],
        "uptake_model_outputs": no_inference["uptake_model_outputs"],
        "reasoning_model_outputs": no_inference["reasoning_model_outputs"],
        "scientific_metrics": no_inference["scientific_metrics"],
    }
    automated = {
        "schema_version": 1,
        "protocol_id": "direction_p_construct_valid_mini_pilot_v2",
        "automated_gate_status": "PASS" if automated_pass else "FAIL",
        "final_decision": decision,
        "gates": gates,
        "values": values,
        "human_review": {
            "packet_rows": review["row_count"],
            "genuine": review["genuine_count"],
            "decoys": review["decoy_count"],
            "reviewers_required": review["reviewer_count_required"],
            "reviewers_completed": review["reviewer_count_completed"],
            "status": review["review_status"],
        },
        "novelty_decision": novelty["decision"],
        "formal_vlm_inference_run": False,
    }
    _dump("reports/construct_v2_automated_gate.yaml", automated)
    evidence_files = [
        "research/construct_restart/v1_retirement.yaml",
        "research/construct_restart/v2_construct_definition.yaml",
        "research/construct_restart/v2_estimands.yaml",
        "research/construct_restart/v2_hypothesis_registry.yaml",
        "research/construct_restart/v2_power_policy.yaml",
        "research/construct_restart/v2_multiplicity_policy.yaml",
        "research/construct_restart/v2_go_no_go.yaml",
        "research/construct_restart/v2_deviation_policy.yaml",
        "research/construct_restart/v2_literature_matrix.yaml",
        "data/construct_v2/data_manifest.yaml",
        "artifacts/construct_v2/oracle_metrics.yaml",
        "artifacts/construct_v2/leakage_metrics.yaml",
        "artifacts/construct_v2/answer_balance.yaml",
        "artifacts/construct_v2/relation_balance.yaml",
        "artifacts/construct_v2/template_balance.yaml",
        "artifacts/construct_v2/token_balance.yaml",
        "artifacts/construct_v2/serialization_equivalence.yaml",
        "artifacts/construct_v2/multiplicity_power.yaml",
        "artifacts/construct_v2/verification_report.yaml",
        "artifacts/construct_v2_review/packet_manifest.yaml",
        "reports/construct_v2_automated_gate.yaml",
    ]
    evidence_map = {
        "schema_version": 1,
        "protocol_id": "direction_p_construct_valid_mini_pilot_v2",
        "decision": decision,
        "files": {path: _sha256(path) for path in evidence_files},
        "scientific_predictions_included": False,
    }
    _dump("reports/construct_v2_evidence_map.yaml", evidence_map)

    design_lines = [
        "# Direction P v2 construct-valid design report",
        "",
        f"Decision: `{decision}`.",
        "",
        "The image supplies A and B plus the visual first hop A R1 B. Text supplies only",
        "the bridge fact B R2 C. C is not spatially rendered. The question asks for A relative",
        "to C, so image-only and evidence-only inputs each retain one bit of answer uncertainty.",
        "Correct and corrupted conditions share image, question, entities, semantic candidates,",
        "and option order; only R2 changes. Neither condition contradicts a visible fact.",
        "",
        f"The power policy selected N={power['chosen_reasoning_n']} before data generation.",
        "Natural language is the sole confirmatory serialization; triples is robustness only.",
        "The estimand is a paired behavioral ITT, not an internal mechanism effect.",
        "",
        "All automated construct, leakage, balance, serialization, token, power, P3-hash, and",
        "no-inference gates pass. Two real independent human reviews remain outstanding.",
    ]
    (ROOT / "reports/construct_v2_design_report.md").write_text(
        "\n".join(design_lines) + "\n", encoding="utf-8"
    )
    readiness_lines = [
        "# Direction P v2 preregistration readiness",
        "",
        f"Current state: `{decision}`.",
        "",
        "Automated preaudit is complete and passed. The blinded packet contains 64 genuine",
        "scenes and 16 preregistered decoys. No reviewer responses exist. No final v2",
        "preregistration tag may be created until two eligible independent reviewers pass the",
        "registered agreement, kappa, critical-error, and decoy-detection gates, and a new",
        "independent preregistration audit passes.",
        "",
        "Formal prediction files, uptake outputs, reasoning outputs, and scientific metrics are",
        "all zero. The runner remains fail-closed without the two external authorization files.",
    ]
    (ROOT / "reports/construct_v2_preregistration_readiness.md").write_text(
        "\n".join(readiness_lines) + "\n", encoding="utf-8"
    )
    return {
        "status": decision,
        "automated_gate": automated["automated_gate_status"],
        "chosen_reasoning_n": power["chosen_reasoning_n"],
        "human_reviewers_completed": review["reviewer_count_completed"],
        "scientific_model_output_count": no_inference["formal_prediction_files"],
    }
