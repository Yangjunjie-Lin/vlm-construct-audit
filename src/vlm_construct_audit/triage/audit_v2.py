"""Single development-only sensitivity repair frozen before Loop A holdout."""

from __future__ import annotations

import math
from statistics import mean
from typing import Any

from ..audit.engine import ClaimDecision

ONE_SIDED_95_Z = 1.6448536269514722


def pooled_scene_lower_bound(downstream_results: dict[str, Any]) -> dict[str, Any]:
    """Pool cell point estimates while retaining one scene as the effective unit.

    The four cell estimates may be repeated observations of the same scene. AuditV2 therefore
    uses the minimum scene-cluster count rather than multiplying it by the number of cells and
    uses the largest Bernoulli variance among cells for a conservative one-sided lower bound.
    """
    cells = list(downstream_results["cells"].values())
    estimates = [float(cell["estimate"]) for cell in cells]
    effective_n = min(int(cell["scene_clusters"]) for cell in cells)
    pooled = mean(estimates)
    worst_variance = max(max(1e-12, estimate * (1 - estimate)) for estimate in estimates)
    standard_error = math.sqrt(worst_variance / effective_n)
    return {
        "estimate": pooled,
        "one_sided_95_lower": max(-1.0, pooled - ONE_SIDED_95_Z * standard_error),
        "effective_scene_clusters": effective_n,
        "cell_estimates": estimates,
        "cell_count": len(cells),
        "pseudoreplicated_cell_multiplier": False,
    }


def audit_claim_v2(
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
    equivalence_pass = bool(replication_results["equivalence"]["programmatic_fact_equivalence"])
    interactions = [
        float(value) for value in replication_results["format_interactions"].values() if value is not None
    ]
    format_dependent = equivalence_pass and any(
        abs(value) > policy["format_materiality"] for value in interactions
    )
    format_tost_pass = all(
        bool(result["tost_equivalent"])
        for result in replication_results["format_tost"].values()
    )
    format_stable = equivalence_pass and not format_dependent and format_tost_pass
    uptake_lower = uptake_results["aggregate"]["ci95"][0]
    uptake_pass = uptake_lower is not None and uptake_lower >= policy["gate_cutoff"]
    pooled = pooled_scene_lower_bound(downstream_results)
    cell_replication_pass = all(
        float(cell["estimate"]) > policy["sesoi"] for cell in downstream_results["cells"].values()
    )
    pooled_effect_pass = pooled["one_sided_95_lower"] > policy["sesoi"]

    gates = {
        "measurement_mapping": mapping_pass,
        "deterministic_parser": parser_pass,
        "response_contract_robustness": agreement_pass,
        "programmatic_fact_equivalence": equivalence_pass,
        "format_stability": format_stable,
        "independent_uptake": uptake_pass,
        "all_cell_point_estimates_above_SESOI": cell_replication_pass,
        "pooled_scene_one_sided_effect": pooled_effect_pass,
    }
    for gate, value in gates.items():
        (passed if value else failed).append(gate)

    partial = replication_results.get("partial_identification", {})
    partial_eligible = (
        bool(partial.get("eligible"))
        and partial.get("observed_uptake_filtering") is False
        and partial.get("bounds") == [-1.0, 1.0]
    )
    scope_flags: list[str] = []
    if format_dependent:
        scope_flags.append("FORMAT_DEPENDENT")
    if not agreement_pass:
        scope_flags.append("RESPONSE_CONTRACT_UNSTABLE")

    if not mapping_pass or not parser_pass:
        decision = "INVALID_MEASUREMENT"
        identification_status = "OBSERVED_MEASUREMENT_INVALID"
    elif not equivalence_pass:
        decision = "INCONCLUSIVE"
        identification_status = "SERIALIZATION_EQUIVALENCE_FAILED"
    elif format_dependent:
        decision = "FORMAT_DEPENDENT"
        identification_status = "TARGET_MECHANISM_INVALID"
    elif partial_eligible:
        decision = "PARTIALLY_IDENTIFIED"
        identification_status = "PARTIALLY_IDENTIFIED"
    elif not uptake_pass:
        decision = "INVALID_INTERVENTION"
        identification_status = "TARGET_MECHANISM_INVALID"
    elif not agreement_pass or not format_stable:
        decision = "INCONCLUSIVE"
        identification_status = "CONTRACT_OR_FORMAT_UNSTABLE"
    elif cell_replication_pass and pooled_effect_pass:
        decision = "VALID_BEHAVIORAL_EFFECT"
        identification_status = "BEHAVIORAL_ONLY_INTERNAL_MECHANISM_NOT_IDENTIFIED"
    else:
        decision = "INCONCLUSIVE"
        identification_status = "BEHAVIORAL_ONLY_INTERNAL_MECHANISM_NOT_IDENTIFIED"

    return ClaimDecision(
        decision=decision,
        estimand="E1_scene_paired_behavioral_ITT_AuditV2_one_sided_pooled_scene_estimator",
        eligible_population="registered_unseen_DGP_family_x_scene_generator_x_four_frozen_cells",
        passed_gates=passed,
        failed_gates=failed,
        effect_size=pooled["estimate"],
        confidence_interval=[pooled["one_sided_95_lower"], 1.0],
        equivalence_result=replication_results["equivalence"],
        replication_status=(
            "ALL_CELL_POINT_ESTIMATES_ABOVE_SESOI"
            if cell_replication_pass
            else "CELL_REPLICATION_FAILED"
        ),
        identification_status=identification_status,
        claim_boundary="Known-DGP behavioral-method calibration only; no real-VLM or internal-mechanism inference.",
        supporting_artifacts=[
            "research/preregistration/audit_v2.yaml",
            "artifacts/loop_a/development_audit_v2/summary.yaml",
        ],
        scope_flags=scope_flags,
        diagnostic_subtype="audit_v2_scene_pooled_one_sided_with_partial_identification",
    )
