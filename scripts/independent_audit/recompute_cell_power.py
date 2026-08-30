"""Independent paired-binary power recomputation for the frozen cell-level rule."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import yaml
from scipy.stats import binom, norm

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "artifacts/independent_audit/power_recalculation.yaml"
ALIAS_OUTPUT = ROOT / "artifacts/independent_audit/cell_level_power_recalculation.yaml"
REPO_POWER = ROOT / "research/preregistration/p_mini_pilot_power_analysis.yaml"

EFFECTS = [0.00, 0.05, 0.10, 0.12, 0.15, 0.18, 0.25]
DISCORDANCES = [0.15, 0.25, 0.35, 0.50, 1.00]
SAMPLE_SIZES = [384, 512, 768, 1024, 1536]
DELTA0 = 0.10
DELTA1 = 0.15
ALPHA = 0.025
Z_CERT = float(norm.ppf(1 - ALPHA))
Z_BELOW = float(norm.ppf(0.95))
Z_CI = float(norm.ppf(0.975))
MC_REPETITIONS = 100_000


def analytic(n: int, effect: float, discordance: float) -> dict[str, float]:
    variance = discordance - effect**2
    se = math.sqrt(variance / n)
    certify = float(norm.cdf((effect - DELTA0) / se - Z_CERT))
    below = float(norm.cdf((DELTA0 - effect) / se - Z_BELOW))
    minimum = float(norm.cdf((effect - DELTA0) / se - Z_BELOW))
    return {
        "variance": variance,
        "standard_error": se,
        "certification_probability": certify,
        "below_probability": below,
        "gray_probability": max(0.0, 1.0 - certify - below),
        "minimum_effect_rejection_probability": minimum,
    }


def monte_carlo(n: int, effect: float, discordance: float, seed: int) -> dict[str, float | int]:
    p10 = (discordance + effect) / 2
    p01 = (discordance - effect) / 2
    rng = np.random.default_rng(seed)
    counts = rng.multinomial(n, [p10, p01, 1 - discordance], size=MC_REPETITIONS)
    estimates = (counts[:, 0] - counts[:, 1]) / n
    sample_variances = (counts[:, 0] + counts[:, 1] - n * estimates**2) / (n - 1)
    standard_errors = np.sqrt(np.maximum(sample_variances, 0) / n)
    certify = estimates - Z_CERT * standard_errors > DELTA0
    below = estimates + Z_BELOW * standard_errors <= DELTA0
    gray = ~(certify | below)
    minimum = estimates - Z_BELOW * standard_errors > DELTA0
    ci_lower = estimates - Z_CI * standard_errors
    ci_upper = estimates + Z_CI * standard_errors
    return {
        "repetitions": MC_REPETITIONS,
        "seed": seed,
        "certification_probability": float(certify.mean()),
        "below_probability": float(below.mean()),
        "gray_probability": float(gray.mean()),
        "minimum_effect_rejection_probability": float(minimum.mean()),
        "wald_ci_coverage": float(((ci_lower <= effect) & (effect <= ci_upper)).mean()),
    }


def exact_frozen_wald_probability(n: int, effect: float, discordance: float) -> float:
    """Sum the multinomial law exactly for the frozen plug-in-Wald certification rule."""
    q_plus = (discordance + effect) / (2 * discordance)
    total = 0.0
    for discordant in range(n + 1):
        probability_m = float(binom.pmf(discordant, n, discordance))
        if probability_m < 1e-18:
            continue
        plus = np.arange(discordant + 1)
        estimates = (2 * plus - discordant) / n
        sample_variance = (discordant - n * estimates**2) / (n - 1)
        standard_error = np.sqrt(np.maximum(sample_variance, 0) / n)
        rejects = estimates - Z_CERT * standard_error > DELTA0
        conditional = binom.pmf(plus, discordant, q_plus)
        total += probability_m * float(conditional[rejects].sum())
    return total


def bootstrap_behavior(
    n: int, effect: float, discordance: float, seed: int, datasets: int = 300, resamples: int = 999
) -> dict[str, Any]:
    rng = np.random.default_rng(seed)
    p10 = (discordance + effect) / 2
    p01 = (discordance - effect) / 2
    observed = rng.multinomial(n, [p10, p01, 1 - discordance], size=datasets)
    certifications = []
    coverages = []
    gray = []
    for counts in observed:
        empirical = counts / n
        draws = rng.multinomial(n, empirical, size=resamples)
        boot = (draws[:, 0] - draws[:, 1]) / n
        lower, upper = np.quantile(boot, [0.025, 0.975])
        certifications.append(lower > DELTA0)
        coverages.append(lower <= effect <= upper)
        below = upper <= DELTA0
        gray.append(not certifications[-1] and not below)
    return {
        "datasets": datasets,
        "resamples_per_dataset": resamples,
        "seed": seed,
        "percentile_ci_certification_probability": float(np.mean(certifications)),
        "percentile_ci_coverage": float(np.mean(coverages)),
        "gray_probability": float(np.mean(gray)),
    }


def repository_rows() -> dict[tuple[float, float, int], dict[str, Any]]:
    artifact = yaml.safe_load(REPO_POWER.read_text(encoding="utf-8"))
    return {
        (float(row["effect"]), float(row["paired_discordance"]), int(row["sample_size"])): row
        for row in artifact["rows"]
    }


def main() -> int:
    repo = repository_rows()
    rows: list[dict[str, Any]] = []
    comparison_failures: list[dict[str, Any]] = []
    for effect_index, effect in enumerate(EFFECTS):
        for discordance_index, discordance in enumerate(DISCORDANCES):
            p10 = (discordance + effect) / 2
            p01 = (discordance - effect) / 2
            for n_index, n in enumerate(SAMPLE_SIZES):
                key = (effect, discordance, n)
                if p01 < 0 or p10 + p01 > 1:
                    rows.append(
                        {
                            "effect": effect,
                            "discordance": discordance,
                            "sample_size": n,
                            "status": "INFEASIBLE_PAIRED_PROBABILITIES",
                        }
                    )
                    continue
                seed = 910_000_000 + effect_index * 1_000_000 + discordance_index * 10_000 + n_index
                analytic_result = analytic(n, effect, discordance)
                mc_result = monte_carlo(n, effect, discordance, seed)
                repo_row = repo[key]
                comparison = {
                    "analytic_absolute_difference": abs(
                        analytic_result["certification_probability"]
                        - float(repo_row["analytic_certification_power"])
                    ),
                    "monte_carlo_absolute_difference": abs(
                        float(mc_result["certification_probability"])
                        - float(repo_row["certification_power"])
                    ),
                    "gray_absolute_difference": abs(
                        float(mc_result["gray_probability"])
                        - float(repo_row["gray_zone_probability"])
                    ),
                    "coverage_absolute_difference": abs(
                        float(mc_result["wald_ci_coverage"]) - float(repo_row["ci_coverage"])
                    ),
                }
                comparison["within_tolerance"] = (
                    comparison["analytic_absolute_difference"] < 1e-12
                    and comparison["monte_carlo_absolute_difference"] <= 0.02
                    and comparison["gray_absolute_difference"] <= 0.02
                    and comparison["coverage_absolute_difference"] <= 0.02
                )
                if not comparison["within_tolerance"]:
                    comparison_failures.append(
                        {
                            "effect": effect,
                            "discordance": discordance,
                            "sample_size": n,
                            **comparison,
                        }
                    )
                rows.append(
                    {
                        "effect": effect,
                        "discordance": discordance,
                        "sample_size": n,
                        "status": "FEASIBLE",
                        "p10": p10,
                        "p01": p01,
                        "analytic": analytic_result,
                        "monte_carlo": mc_result,
                        "repository_comparison": comparison,
                    }
                )

    exact = []
    for effect in (DELTA0, DELTA1):
        for discordance in DISCORDANCES:
            if discordance < abs(effect):
                continue
            probability = exact_frozen_wald_probability(768, effect, discordance)
            exact.append(
                {
                    "effect": effect,
                    "discordance": discordance,
                    "sample_size": 768,
                    "exact_finite_sample_frozen_wald_certification_probability": probability,
                    "analytic_normal_probability": analytic(768, effect, discordance)[
                        "certification_probability"
                    ],
                }
            )

    bootstrap = [
        {
            "effect": DELTA1,
            "discordance": discordance,
            "sample_size": 768,
            **bootstrap_behavior(768, DELTA1, discordance, 930_000_000 + index),
        }
        for index, discordance in enumerate(DISCORDANCES)
        if discordance >= DELTA1
    ]
    target = [
        row
        for row in rows
        if row.get("status") == "FEASIBLE" and row["effect"] == DELTA1 and row["sample_size"] == 768
    ]
    boundary = [
        row
        for row in rows
        if row.get("status") == "FEASIBLE" and row["effect"] == DELTA0 and row["sample_size"] == 768
    ]
    output = {
        "schema_version": 1,
        "independent_implementation": True,
        "formula": {
            "effect": "theta = p10 - p01",
            "discordance": "d = p10 + p01",
            "paired_variance": "d - theta^2",
        },
        "delta0": DELTA0,
        "delta1": DELTA1,
        "one_sided_alpha": ALPHA,
        "normal_critical_z": Z_CERT,
        "grid": {
            "effects": EFFECTS,
            "discordances": DISCORDANCES,
            "sample_sizes": SAMPLE_SIZES,
        },
        "methods": [
            "analytic_normal_known_joint_variance",
            "independent_multinomial_monte_carlo_with_plugin_paired_variance",
            "exact_finite_sample_multinomial_sum_for_frozen_wald_rule_at_n768",
            "paired_percentile_bootstrap_behavior_at_delta1_n768",
        ],
        "target_n768_delta1": [
            {
                "discordance": row["discordance"],
                "analytic_power": row["analytic"]["certification_probability"],
                "monte_carlo_power": row["monte_carlo"]["certification_probability"],
                "gray_probability": row["monte_carlo"]["gray_probability"],
                "wald_ci_coverage": row["monte_carlo"]["wald_ci_coverage"],
            }
            for row in target
        ],
        "boundary_type_i_n768": [
            {
                "discordance": row["discordance"],
                "analytic": row["analytic"]["certification_probability"],
                "monte_carlo": row["monte_carlo"]["certification_probability"],
            }
            for row in boundary
        ],
        "exact_selected": exact,
        "bootstrap_selected": bootstrap,
        "repository_comparison_failures": comparison_failures,
        "repository_match": not comparison_failures,
        "cell_level_conclusion": "PASS" if not comparison_failures else "FAIL_POWER_IMPLEMENTATION",
        "scope_warning": "These are marginal cell-level operating characteristics and are not Stable Path power.",
        "rows": rows,
    }
    rendered = json.dumps(output, indent=2, sort_keys=True) + "\n"
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(rendered)
    with ALIAS_OUTPUT.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(rendered)
    print(
        json.dumps(
            {
                key: output[key]
                for key in (
                    "target_n768_delta1",
                    "boundary_type_i_n768",
                    "exact_selected",
                    "bootstrap_selected",
                    "repository_match",
                    "cell_level_conclusion",
                )
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if output["repository_match"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
