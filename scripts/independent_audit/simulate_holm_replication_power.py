"""Multiplicity-aware normal-approximation simulation of the frozen six-cell success gate."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
from scipy.stats import norm

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "artifacts/independent_audit/stable_path_power_simulation.yaml"

N = 768
DELTA0 = 0.10
ALPHA = 0.025
Z_CERT = float(norm.ppf(1 - ALPHA))
Z_REVERSE = float(norm.ppf(0.975))
REPETITIONS = 50_000
GLOBAL_NULL_REPETITIONS = 200_000
DISCORDANCES = [0.15, 0.25, 0.35, 0.50]
WITHIN = [0.00, 0.25, 0.50, 0.75, 0.90]
BETWEEN = [0.00, 0.25, 0.50]
SCENARIOS = {
    "all_six_0.15": [0.15] * 6,
    "two_families_0.15_third_0.00": [0.15, 0.15, 0.15, 0.15, 0.00, 0.00],
    "two_families_0.18_third_0.00": [0.18, 0.18, 0.18, 0.18, 0.00, 0.00],
    "heterogeneous_families_0.15_0.18_0.25": [0.15, 0.15, 0.18, 0.18, 0.25, 0.25],
}


def correlation_matrix(within: float, between: float) -> np.ndarray:
    matrix = np.full((6, 6), between, dtype=float)
    np.fill_diagonal(matrix, 1.0)
    for family in range(3):
        left = 2 * family
        matrix[left, left + 1] = within
        matrix[left + 1, left] = within
    eigenvalues = np.linalg.eigvalsh(matrix)
    if eigenvalues.min() < -1e-10:
        raise ValueError((within, between, eigenvalues))
    return matrix


def holm_rejections(p_values: np.ndarray, alpha: float = ALPHA) -> np.ndarray:
    order = np.argsort(p_values, axis=1, kind="stable")
    ordered = np.take_along_axis(p_values, order, axis=1)
    thresholds = alpha / np.arange(6, 0, -1)
    step_pass = ordered <= thresholds
    ordered_reject = np.logical_and.accumulate(step_pass, axis=1)
    rejected = np.zeros_like(ordered_reject)
    rows = np.arange(p_values.shape[0])[:, None]
    rejected[rows, order] = ordered_reject
    return rejected


def family_pass_matrix(rejected: np.ndarray) -> np.ndarray:
    return np.column_stack(
        [
            rejected[:, 0] & rejected[:, 1],
            rejected[:, 2] & rejected[:, 3],
            rejected[:, 4] & rejected[:, 5],
        ]
    )


def simulate_scenario(
    name: str,
    effects_list: list[float],
    discordance: float,
    within: float,
    between: float,
    seed: int,
) -> dict[str, Any]:
    effects = np.asarray(effects_list, dtype=float)
    if np.any(np.abs(effects) > discordance):
        return {
            "scenario": name,
            "discordance": discordance,
            "within_model_cross_serialization_correlation": within,
            "between_model_correlation": between,
            "status": "INFEASIBLE_DISCORDANCE_BELOW_ABSOLUTE_EFFECT",
        }
    variances = discordance - effects**2
    standard_errors = np.sqrt(variances / N)
    corr = correlation_matrix(within, between)
    rng = np.random.default_rng(seed)
    normal_draws = rng.multivariate_normal(np.zeros(6), corr, size=REPETITIONS)
    estimates = effects + normal_draws * standard_errors
    z_minimum = (estimates - DELTA0) / standard_errors
    p_values = norm.sf(z_minimum)
    unadjusted = p_values < ALPHA
    holm = holm_rejections(p_values)
    family_pass = family_pass_matrix(holm)
    at_least_two = family_pass.sum(axis=1) >= 2
    reverse = estimates + Z_REVERSE * standard_errors < -DELTA0
    no_certified_reverse = ~reverse.any(axis=1)

    equal_leave_one_positive = np.ones(REPETITIONS, dtype=bool)
    inverse_leave_one_positive = np.ones(REPETITIONS, dtype=bool)
    weights = 1 / variances
    for omitted_family in range(3):
        kept = [cell for cell in range(6) if cell // 2 != omitted_family]
        equal_leave_one_positive &= estimates[:, kept].mean(axis=1) > 0
        inverse_leave_one_positive &= (
            np.average(estimates[:, kept], axis=1, weights=weights[kept]) > 0
        )
    stable_equal = at_least_two & no_certified_reverse & equal_leave_one_positive
    stable_inverse = at_least_two & no_certified_reverse & inverse_leave_one_positive

    return {
        "scenario": name,
        "effects": effects.tolist(),
        "discordance": discordance,
        "within_model_cross_serialization_correlation": within,
        "between_model_correlation": between,
        "status": "FEASIBLE",
        "simulation_repetitions": REPETITIONS,
        "seed": seed,
        "unadjusted_cell_power": unadjusted.mean(axis=0).tolist(),
        "unadjusted_cell_power_mean": float(unadjusted.mean()),
        "holm_supported_cell_power": holm.mean(axis=0).tolist(),
        "holm_supported_cell_power_mean": float(holm.mean()),
        "probability_both_formats_pass_within_family": family_pass.mean(axis=0).tolist(),
        "family_replication_power": family_pass.mean(axis=0).tolist(),
        "probability_at_least_two_families_pass": float(at_least_two.mean()),
        "probability_no_certified_reverse": float(no_certified_reverse.mean()),
        "leave_one_family_out_positive_equal_weight": float(equal_leave_one_positive.mean()),
        "leave_one_family_out_positive_inverse_variance_weight": float(
            inverse_leave_one_positive.mean()
        ),
        "stable_path_total_power_equal_weight": float(stable_equal.mean()),
        "stable_path_total_power_inverse_variance_weight": float(stable_inverse.mean()),
        "uptake_assumption": "all_six_cells_pass",
        "inconclusive_rule_assumption": "valid P3 implementation emits positive, below-SESOI, or explicit gray; no valid cell is labelled INCONCLUSIVE",
    }


def global_null_path_b(within: float, between: float, seed: int) -> dict[str, Any]:
    corr = correlation_matrix(within, between)
    rng = np.random.default_rng(seed)
    draws = rng.multivariate_normal(np.zeros(6), corr, size=GLOBAL_NULL_REPETITIONS)
    naive = draws > norm.ppf(0.975)
    any_two = naive.sum(axis=1) >= 2
    families_with_positive = np.column_stack(
        [naive[:, 0] | naive[:, 1], naive[:, 2] | naive[:, 3], naive[:, 4] | naive[:, 5]]
    )
    different_families = families_with_positive.sum(axis=1) >= 2
    same_family_pair = (
        (naive[:, 0] & naive[:, 1]) | (naive[:, 2] & naive[:, 3]) | (naive[:, 4] & naive[:, 5])
    )
    both_serializations_represented = naive[:, [0, 2, 4]].any(axis=1) & naive[:, [1, 3, 5]].any(
        axis=1
    )
    return {
        "within_model_cross_serialization_correlation": within,
        "between_model_correlation": between,
        "repetitions": GLOBAL_NULL_REPETITIONS,
        "seed": seed,
        "probability_at_least_two_naive_positive_cells": float(any_two.mean()),
        "probability_naive_positives_span_two_families": float(different_families.mean()),
        "probability_a_same_family_two_serialization_pair_is_naive_positive": float(
            same_family_pair.mean()
        ),
        "probability_naive_positives_include_both_serializations": float(
            both_serializations_represented.mean()
        ),
    }


def analytic_independent_global_null() -> float:
    probability = 0.025
    return 1 - (1 - probability) ** 6 - 6 * probability * (1 - probability) ** 5


def main() -> int:
    rows = []
    counter = 0
    for name, effects in SCENARIOS.items():
        for discordance in DISCORDANCES:
            for within in WITHIN:
                for between in BETWEEN:
                    rows.append(
                        simulate_scenario(
                            name,
                            effects,
                            discordance,
                            within,
                            between,
                            950_000_000 + counter,
                        )
                    )
                    counter += 1
    global_null = []
    for within_index, within in enumerate(WITHIN):
        for between_index, between in enumerate(BETWEEN):
            global_null.append(
                global_null_path_b(
                    within,
                    between,
                    970_000_000 + within_index * 100 + between_index,
                )
            )

    feasible = [row for row in rows if row["status"] == "FEASIBLE"]
    key_summaries = []
    for scenario in SCENARIOS:
        for discordance in DISCORDANCES:
            selected = [
                row
                for row in feasible
                if row["scenario"] == scenario and row["discordance"] == discordance
            ]
            if not selected:
                key_summaries.append(
                    {
                        "scenario": scenario,
                        "discordance": discordance,
                        "status": "INFEASIBLE",
                    }
                )
                continue
            key_summaries.append(
                {
                    "scenario": scenario,
                    "discordance": discordance,
                    "status": "FEASIBLE",
                    "stable_path_power_range_over_dependence": [
                        min(row["stable_path_total_power_equal_weight"] for row in selected),
                        max(row["stable_path_total_power_equal_weight"] for row in selected),
                    ],
                    "holm_supported_cell_power_mean_range": [
                        min(row["holm_supported_cell_power_mean"] for row in selected),
                        max(row["holm_supported_cell_power_mean"] for row in selected),
                    ],
                    "probability_at_least_two_families_range": [
                        min(row["probability_at_least_two_families_pass"] for row in selected),
                        max(row["probability_at_least_two_families_pass"] for row in selected),
                    ],
                }
            )
    output = {
        "schema_version": 1,
        "method": "multivariate_normal_approximation_to_six_correlated_paired_estimators",
        "sample_size_per_cell": N,
        "delta0": DELTA0,
        "family_wise_alpha": ALPHA,
        "holm_hypotheses": 6,
        "dependence_definition": "specified correlations are correlations of the six asymptotic cell estimators; within-model entries couple the two serializations and between-model entries couple cells from different families",
        "simulation_repetitions_per_scenario": REPETITIONS,
        "key_summaries": key_summaries,
        "global_null_path_b": {
            "analytic_independent_probability_at_least_two_naive_positive_cells": analytic_independent_global_null(),
            "simulation": global_null,
        },
        "stable_path_interpretation": {
            "cell_level_power_is_not_overall_power": True,
            "n768_adequately_powered_for_all_frozen_stable_scenarios": False,
            "pooling_weight_not_frozen": True,
            "reported_weight_sensitivity": ["equal_cell", "inverse_paired_variance"],
            "audit_status": "CONDITIONAL_PREINFERENCE_AMENDMENT_REQUIRED",
        },
        "rows": rows,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {"key_summaries": key_summaries, "global_null_path_b": output["global_null_path_b"]},
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
