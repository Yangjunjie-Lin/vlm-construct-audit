"""Intersection-union audit engine with parallel scope and identification fields."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from ..effects import effect_gate, latent_uptake_bounds
from ..uptake import uptake_gate
from ..utils import dump_yaml, load_yaml


@dataclass
class ClaimDecision:
    decision: str
    estimand: str
    eligible_population: str
    passed_gates: list[str]
    failed_gates: list[str]
    effect_size: float | None
    confidence_interval: list[float | None]
    equivalence_result: dict[str, Any]
    replication_status: str
    identification_status: str
    claim_boundary: str
    supporting_artifacts: list[str]
    scope_flags: list[str]
    diagnostic_subtype: str | None = None


def audit_claim(
    measurement_results: dict[str, Any],
    uptake_results: dict[str, Any],
    downstream_results: dict[str, Any],
    replication_results: dict[str, Any],
    policy: dict[str, Any],
) -> ClaimDecision:
    passed: list[str] = []
    failed: list[str] = []
    mapping_pass = measurement_results["one_sided_95_lower"] >= policy["measurement_validity_cutoff"]
    parser_pass = measurement_results["parser_valid_rate"] >= policy["measurement_validity_cutoff"]
    agreement = measurement_results["contract_agreement"]
    agreement_pass = (
        agreement["kappa"] is not None
        and agreement["kappa"] >= policy["contract_kappa_cutoff"]
        and agreement["ci95"][0] is not None
        and agreement["ci95"][0] >= policy["contract_kappa_lower_bound_cutoff"]
    )
    for label, value in (
        ("measurement_mapping", mapping_pass),
        ("deterministic_parser", parser_pass),
        ("response_contract_robustness", agreement_pass),
    ):
        (passed if value else failed).append(label)

    equivalence_pass = bool(replication_results["equivalence"]["programmatic_fact_equivalence"])
    (passed if equivalence_pass else failed).append("programmatic_fact_equivalence")
    uptake = uptake_gate(uptake_results, policy["gate_cutoff"])
    (passed if uptake["passed"] else failed).append("independent_uptake")
    effect = effect_gate(downstream_results, policy["sesoi"])
    (passed if effect["passed"] else failed).append("intersection_downstream_effect")

    interactions = [value for value in replication_results["format_interactions"].values() if value is not None]
    format_dependent = equivalence_pass and any(abs(value) > policy["format_materiality"] for value in interactions)
    format_stable = equivalence_pass and not format_dependent
    (passed if format_stable else failed).append("format_stability")

    scope_flags = []
    if format_dependent:
        scope_flags.append("FORMAT_DEPENDENT")
    if not agreement_pass:
        scope_flags.append("RESPONSE_CONTRACT_UNSTABLE")
    identification_status = "BEHAVIORAL_ONLY_INTERNAL_MECHANISM_NOT_IDENTIFIED"

    if not mapping_pass or not parser_pass:
        decision = "INVALID_MEASUREMENT"
    elif not equivalence_pass:
        decision = "INCONCLUSIVE"
    elif format_dependent:
        decision = "FORMAT_DEPENDENT"
    elif not uptake["passed"]:
        decision = "INVALID_INTERVENTION"
    elif not agreement_pass:
        decision = "INCONCLUSIVE"
    elif effect["passed"]:
        decision = "VALID_BEHAVIORAL_EFFECT"
    else:
        decision = "INCONCLUSIVE"

    return ClaimDecision(
        decision=decision,
        estimand="E1_scene_paired_behavioral_ITT_standardized_over_target_corruptions",
        eligible_population="frozen_Tier0_system_x_scene_generator_x_NL_triples_x_two_response_contracts",
        passed_gates=passed,
        failed_gates=failed,
        effect_size=effect["aggregate_effect"],
        confidence_interval=effect["aggregate_ci95"],
        equivalence_result=replication_results["equivalence"],
        replication_status="ALL_FOUR_CELLS_PASS" if effect["passed"] and agreement_pass else "FAILED_OR_INCOMPLETE",
        identification_status=identification_status,
        claim_boundary="Known-system behavioral calibration only; no real-VLM or internal-mechanism inference.",
        supporting_artifacts=[
            "artifacts/metrics/analysis_results.yaml",
            "artifacts/metrics/equivalence_report.yaml",
            "artifacts/predictions/calibration_predictions.jsonl",
        ],
        scope_flags=scope_flags,
        diagnostic_subtype=replication_results.get("diagnostic_subtype"),
    )


def _baseline_claims(system_result: dict[str, Any], decision: ClaimDecision) -> dict[str, bool]:
    cell = system_result["downstream"]["cells"]["natural_language__conditional_likelihood"]
    b1 = cell["ci95"][0] is not None and cell["ci95"][0] > 0
    uptake_cell = system_result["uptake"]["cells"]["natural_language__conditional_likelihood"]
    b3 = b1 and uptake_cell["ci95"][0] is not None and uptake_cell["ci95"][0] > 0
    agreement = system_result["measurement"]["contract_agreement"]
    b4 = b1 and agreement["kappa"] is not None and agreement["kappa"] >= 0.90
    return {
        "B1_standard_single_contract_accuracy": b1,
        "B2_prompt_format_sensitivity_reporting": b1,
        "B3_simple_manipulation_check_filtering": b3,
        "B4_contract_agreement_filtering": b4,
        "B5_full_validity_aware_audit": decision.decision == "VALID_BEHAVIORAL_EFFECT",
    }


def build_audit_decisions() -> dict[str, Any]:
    analysis = load_yaml("artifacts/metrics/analysis_results.yaml")
    equivalence = load_yaml("artifacts/metrics/equivalence_report.yaml")
    policy = load_yaml("configs/audit_policy.yaml")
    expected = {
        path.parent.name: load_yaml(path)["expected_claim_class"]
        for path in Path("src/vlm_construct_audit/calibration/states").glob("*/expected_claim_class.yaml")
    }
    decisions = {}
    baselines = {}
    confusion: dict[str, dict[str, int]] = {}
    for system, result in analysis["systems"].items():
        decision = audit_claim(
            result["measurement"],
            result["uptake"],
            result["downstream"],
            {
                "equivalence": equivalence,
                "format_interactions": result["format_interaction"],
                "diagnostic_subtype": result["diagnostic_subtype"],
            },
            policy,
        )
        decisions[system] = asdict(decision)
        baselines[system] = _baseline_claims(result, decision)
        truth = expected[system]
        confusion.setdefault(truth, {})[decision.decision] = confusion.setdefault(truth, {}).get(decision.decision, 0) + 1

    invalid_systems = [system for system in decisions if expected[system] != "VALID_BEHAVIORAL_EFFECT"]
    baseline_metrics = {}
    for baseline in next(iter(baselines.values())):
        false_claims = sum(baselines[system][baseline] for system in invalid_systems)
        valid_detected = int(baselines["OracleEvidenceReasoner"][baseline])
        baseline_metrics[baseline] = {
            "false_mechanistic_claim_rate": false_claims / len(invalid_systems),
            "false_claims": false_claims,
            "known_invalid_denominator": len(invalid_systems),
            "sensitivity": valid_detected,
            "known_valid_denominator": 1,
            "sensitivity_precision_warning": "one archetype is not a population estimate",
        }

    matches = sum(decisions[system]["decision"] == expected[system] for system in decisions)
    output = {
        "schema_version": 1,
        "decisions": decisions,
        "expected_claim_classes": expected,
        "calibration_confusion_matrix": confusion,
        "expected_class_matches": matches,
        "system_count": len(decisions),
        "baselines": baselines,
        "baseline_metrics": baseline_metrics,
        "E5": latent_uptake_bounds(),
        "claim_boundary": "Calibration classifications do not identify real VLM internal mechanisms.",
    }
    dump_yaml("artifacts/metrics/audit_decisions.yaml", output)
    return output
