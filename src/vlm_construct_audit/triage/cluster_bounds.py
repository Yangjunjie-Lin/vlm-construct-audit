"""Boundary-safe clustered lower bounds and dependence sensitivity."""

from __future__ import annotations

import math
from typing import Any

from scipy.optimize import brentq, minimize_scalar
from scipy.special import betaln

from ..statistics.core import clopper_pearson_lower


def exact_complete_cluster_lower(successes: int, clusters: int, alpha: float) -> float:
    return clopper_pearson_lower(successes, clusters, alpha=alpha)


def simultaneous_scene_template_lower(
    scene_successes: int,
    scene_clusters: int,
    template_successes: int,
    template_clusters: int,
) -> dict[str, Any]:
    scene_lower = exact_complete_cluster_lower(scene_successes, scene_clusters, alpha=0.025)
    template_lower = exact_complete_cluster_lower(template_successes, template_clusters, alpha=0.025)
    return {
        "method": "Bonferroni_two_marginal_exact_complete_cluster_bounds",
        "scene_lower": scene_lower,
        "template_lower": template_lower,
        "two_way_lower": min(scene_lower, template_lower),
        "simultaneous_confidence": 0.95,
    }


def beta_binomial_profile_lower(
    successes_by_cluster: list[int],
    trials_by_cluster: list[int],
    rho: float,
) -> float:
    if len(successes_by_cluster) != len(trials_by_cluster) or not successes_by_cluster:
        raise ValueError("Cluster vectors must be non-empty and aligned")
    if rho == 0:
        return clopper_pearson_lower(sum(successes_by_cluster), sum(trials_by_cluster), alpha=0.05)

    concentration = (1 - rho) / rho

    def log_likelihood(probability: float) -> float:
        alpha = probability * concentration
        beta = (1 - probability) * concentration
        return sum(
            betaln(successes + alpha, trials - successes + beta) - betaln(alpha, beta)
            for successes, trials in zip(successes_by_cluster, trials_by_cluster, strict=True)
        )

    epsilon = 1e-9
    fit = minimize_scalar(
        lambda probability: -log_likelihood(float(probability)),
        bounds=(epsilon, 1 - epsilon),
        method="bounded",
        options={"xatol": 1e-12},
    )
    if not fit.success:
        raise RuntimeError("Beta-binomial profile maximum could not be located")
    maximum_likelihood_probability = float(fit.x)
    max_log_likelihood = log_likelihood(maximum_likelihood_probability)

    def root(probability: float) -> float:
        return 2 * (max_log_likelihood - log_likelihood(probability)) - 2.7055

    if root(epsilon) <= 0:
        return 0.0
    return float(brentq(root, epsilon, maximum_likelihood_probability))


def icc_design_effect_lower(total_successes: int, total_probes: int, cluster_sizes: list[int], rho: float) -> dict[str, float]:
    m_star = sum(size * size for size in cluster_sizes) / sum(cluster_sizes)
    design_effect = 1 + rho * (m_star - 1)
    effective_n = total_probes / design_effect
    if total_successes == total_probes:
        lower = math.pow(0.05, 1 / effective_n)
    else:
        rate = total_successes / total_probes
        standard_error = math.sqrt(max(1e-12, rate * (1 - rate) / effective_n))
        lower = max(0.0, rate - 1.6448536269514722 * standard_error)
    return {"rho": rho, "m_star": m_star, "design_effect": design_effect, "effective_n": effective_n, "lower": lower}
