"""Independent exact-binomial audit of the frozen uptake gate."""

from __future__ import annotations

import json
from pathlib import Path

from scipy.stats import beta

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "artifacts/independent_audit/uptake_worst_case_analysis.yaml"


def lower_cp(successes: int, n: int, alpha: float = 0.05) -> float:
    return 0.0 if successes == 0 else float(beta.ppf(alpha, successes, n - successes + 1))


def upper_cp(successes: int, n: int, alpha: float = 0.05) -> float:
    return 1.0 if successes == n else float(beta.ppf(1 - alpha, successes + 1, n - successes))


def minimum_successes_for_lower(n: int, cutoff: float) -> int:
    return next(successes for successes in range(n + 1) if lower_cp(successes, n) >= cutoff)


def maximum_successes_for_upper(n: int, cutoff: float) -> int:
    return max(successes for successes in range(n + 1) if upper_cp(successes, n) <= cutoff)


def main() -> int:
    overall_n = 192
    task_n = 48
    overall_required = minimum_successes_for_lower(overall_n, 0.80)
    task_required = minimum_successes_for_lower(task_n, 0.80)
    other_three_perfect = 3 * task_n
    worst_relation_successes = max(0, overall_required - other_three_perfect)
    negative_overall_max = maximum_successes_for_upper(overall_n, 0.60)
    negative_task_max = maximum_successes_for_upper(task_n, 0.60)

    output = {
        "schema_version": 1,
        "gate_definition": {
            "overall_scene_count": overall_n,
            "tasks": 4,
            "scenes_per_task": task_n,
            "direct_lower_bound_cutoff": 0.80,
            "negative_control_upper_bound_cutoff": 0.60,
            "bound": "one_sided_95_percent_clopper_pearson",
        },
        "direct_gate": {
            "overall_minimum_successes": overall_required,
            "overall_minimum_observed_accuracy": overall_required / overall_n,
            "overall_lower_bound_at_minimum": lower_cp(overall_required, overall_n),
            "per_task_minimum_successes_for_same_cutoff": task_required,
            "per_task_minimum_observed_accuracy": task_required / task_n,
            "per_task_lower_bound_at_minimum": lower_cp(task_required, task_n),
        },
        "worst_case_masking": {
            "assumption": "three non-relation-direction tasks score 48/48",
            "relation_direction_minimum_successes_while_overall_gate_passes": worst_relation_successes,
            "relation_direction_observed_accuracy": worst_relation_successes / task_n,
            "relation_direction_lower_bound": lower_cp(worst_relation_successes, task_n),
            "overall_successes": overall_required,
            "overall_lower_bound": lower_cp(overall_required, overall_n),
            "aggregate_gate_can_mask_primary_relation_failure": True,
        },
        "negative_control": {
            "overall_maximum_successes_that_still_pass": negative_overall_max,
            "overall_observed_accuracy_at_maximum": negative_overall_max / overall_n,
            "overall_upper_bound_at_maximum": upper_cp(negative_overall_max, overall_n),
            "per_task_maximum_successes_that_still_pass": negative_task_max,
            "per_task_observed_accuracy_at_maximum": negative_task_max / task_n,
            "per_task_upper_bound_at_maximum": upper_cp(negative_task_max, task_n),
            "four_choice_chance": 0.25,
            "cutoff_assessment": "too_permissive_for_a_chance_0.25_negative_control",
            "required_diagnostics": [
                "absolute_accuracy",
                "correct_vs_irrelevant_contrast",
                "answer_prior",
                "option_position_dependence",
            ],
        },
        "measurement_theory": {
            "aggregate_classification": "unjustified_reflective_aggregate",
            "reason": "The four probes are distinct prerequisite skills; high object, attribute, or ID mapping cannot compensate for failed directed-relation uptake.",
            "primary_task_specific_minima_required": [
                "entity_to_direct_relation",
                "relation_direction",
            ],
        },
        "reporting_boundary": {
            "failed_cell_itt_reporting_required": True,
            "failed_cell_claim_eligibility_forbidden": True,
            "separation_in_frozen_estimand_text": True,
        },
        "audit_status": "CONDITIONAL_PREINFERENCE_AMENDMENT_REQUIRED",
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
