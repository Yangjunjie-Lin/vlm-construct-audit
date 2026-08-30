"""Multiplicity-aware Stable Path power for three primary family hypotheses."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import yaml
from scipy.stats import norm

from .generator import ROOT

ALPHA = 0.025
DELTA0 = 0.10
DELTA1 = 0.15
Z_P3 = 1.959963984540054
MATERIALITY_MARGIN = 0.05
SAMPLE_SIZES = (768, 1024, 1280, 1536)
SCENARIOS = (
    (0.15, 0.15, 0.00),
    (0.15, 0.15, 0.15),
    (0.18, 0.18, 0.00),
    (0.18, 0.18, 0.18),
    (0.15, 0.18, 0.25),
)
DISCORDANCES = (0.15, 0.25, 0.35, 0.50)
CROSS_MODEL_CORRELATIONS = (0.00, 0.25, 0.50)
SERIALIZATION_CORRELATIONS = (0.25, 0.50, 0.75, 0.90)
FAMILIES = ("SmolVLM", "InternVL", "Qwen-VL")


def paired_variance(effect: float, discordance: float) -> float:
    if discordance < abs(effect):
        raise ValueError("discordance must be at least the absolute paired risk difference")
    return discordance - effect**2


def paired_standard_error(effect: float, discordance: float, n: int) -> float:
    return math.sqrt(paired_variance(effect, discordance) / n)


def holm_rejections(p_values: np.ndarray, alpha: float = ALPHA) -> np.ndarray:
    """Vectorized Holm step-down decisions for three hypotheses."""

    if p_values.ndim != 2 or p_values.shape[1] != 3:
        raise ValueError("expected repetitions by three p-values")
    order = np.argsort(p_values, axis=1, kind="stable")
    ordered = np.take_along_axis(p_values, order, axis=1)
    thresholds = alpha / np.arange(3, 0, -1)
    ordered_rejections = np.logical_and.accumulate(ordered <= thresholds, axis=1)
    result = np.zeros_like(ordered_rejections)
    result[np.arange(len(p_values))[:, None], order] = ordered_rejections
    return result


def _normal_draws(
    rng: np.random.Generator,
    repetitions: int,
    cross_model_correlation: float,
    serialization_correlation: float,
) -> tuple[np.ndarray, np.ndarray]:
    common = rng.normal(size=(repetitions, 1))
    family_noise = rng.normal(size=(repetitions, 3))
    natural = (
        math.sqrt(cross_model_correlation) * common
        + math.sqrt(1 - cross_model_correlation) * family_noise
    )
    triples_noise = rng.normal(size=(repetitions, 3))
    triples = (
        serialization_correlation * natural
        + math.sqrt(1 - serialization_correlation**2) * triples_noise
    )
    return natural, triples


def simulate_power_row(
    *,
    n: int,
    effects: tuple[float, float, float],
    discordance: float,
    cross_model_correlation: float,
    serialization_correlation: float,
    repetitions: int,
    seed: int,
) -> dict[str, Any]:
    if any(abs(effect) > discordance for effect in effects):
        return {
            "n": n,
            "effects": list(effects),
            "discordance": discordance,
            "cross_model_correlation": cross_model_correlation,
            "natural_language_triples_correlation": serialization_correlation,
            "status": "INFEASIBLE_DISCORDANCE_BELOW_ABSOLUTE_EFFECT",
        }
    effect_array = np.asarray(effects, dtype=float)
    standard_errors = np.asarray(
        [paired_standard_error(effect, discordance, n) for effect in effects]
    )
    rng = np.random.default_rng(seed)
    natural_z, triples_z = _normal_draws(
        rng, repetitions, cross_model_correlation, serialization_correlation
    )
    natural = effect_array + natural_z * standard_errors
    triples = effect_array + triples_z * standard_errors
    p_values = norm.sf((natural - DELTA0) / standard_errors)
    marginal = p_values <= ALPHA
    holm = holm_rejections(p_values)
    two_of_three = holm.sum(axis=1) >= 2
    natural_reverse = natural + Z_P3 * standard_errors < -DELTA0
    triples_reverse = triples + Z_P3 * standard_errors < -DELTA0
    supported_triples_positive = np.logical_or(~holm, triples > 0).all(axis=1)
    supported_format_margin = np.logical_or(
        ~holm, triples - natural >= -MATERIALITY_MARGIN
    ).all(axis=1)
    triples_robust = (
        ~triples_reverse.any(axis=1)
        & supported_triples_positive
        & supported_format_margin
    )
    stable = two_of_three & ~natural_reverse.any(axis=1) & triples_robust
    return {
        "n": n,
        "effects": list(effects),
        "discordance": discordance,
        "cross_model_correlation": cross_model_correlation,
        "natural_language_triples_correlation": serialization_correlation,
        "status": "FEASIBLE",
        "repetitions": repetitions,
        "seed": seed,
        "paired_standard_errors": standard_errors.tolist(),
        "marginal_cell_power": dict(zip(FAMILIES, marginal.mean(axis=0).tolist(), strict=True)),
        "holm_supported_family_power": dict(
            zip(FAMILIES, holm.mean(axis=0).tolist(), strict=True)
        ),
        "probability_at_least_two_holm_supported": float(two_of_three.mean()),
        "certified_reverse_probability": float(
            (natural_reverse.any(axis=1) | triples_reverse.any(axis=1)).mean()
        ),
        "triples_robustness_probability": float(triples_robust.mean()),
        "overall_stable_path_power": float(stable.mean()),
    }


def _normalized_text_sha256(path: Path) -> str:
    normalized = path.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256(normalized.encode()).hexdigest()


def verify_p3_method_hashes() -> dict[str, Any]:
    lock = yaml.safe_load(
        (ROOT / "research/preregistration/p_mini_pilot_method_lock.yaml").read_text(
            encoding="utf-8"
        )
    )
    files = {}
    for relative, expected in lock["source_file_hashes"].items():
        observed = _normalized_text_sha256(ROOT / relative)
        files[relative] = {
            "expected": expected,
            "observed": observed,
            "unchanged": observed == expected,
        }
    return {
        "delta0_unchanged": float(lock["delta0"]) == DELTA0,
        "delta1_unchanged": float(lock["delta1"]) == DELTA1,
        "files": files,
        "unchanged": all(item["unchanged"] for item in files.values()),
    }


def _scenario_id(effects: tuple[float, float, float]) -> str:
    return "_".join(f"{effect:.2f}" for effect in effects)


def analyze_construct_v2_power(
    *, repetitions: int = 30_000, write: bool = True
) -> dict[str, Any]:
    rows = []
    counter = 0
    for n in SAMPLE_SIZES:
        for effects in SCENARIOS:
            for discordance in DISCORDANCES:
                for cross_correlation in CROSS_MODEL_CORRELATIONS:
                    for serialization_correlation in SERIALIZATION_CORRELATIONS:
                        rows.append(
                            simulate_power_row(
                                n=n,
                                effects=effects,
                                discordance=discordance,
                                cross_model_correlation=cross_correlation,
                                serialization_correlation=serialization_correlation,
                                repetitions=repetitions,
                                seed=864_000_000 + counter,
                            )
                        )
                        counter += 1
    primary_summaries = []
    chosen_n = None
    primary = (0.15, 0.15, 0.00)
    for n in SAMPLE_SIZES:
        selected = [
            row
            for row in rows
            if row["status"] == "FEASIBLE"
            and row["n"] == n
            and row["effects"] == list(primary)
            and row["discordance"] == 0.25
        ]
        minimum = min(row["overall_stable_path_power"] for row in selected)
        maximum = max(row["overall_stable_path_power"] for row in selected)
        summary = {
            "n": n,
            "scenario": list(primary),
            "discordance": 0.25,
            "overall_stable_path_power_range_over_dependence": [minimum, maximum],
            "passes_minimum_0_80": minimum >= 0.80,
        }
        primary_summaries.append(summary)
        if chosen_n is None and summary["passes_minimum_0_80"]:
            chosen_n = n
    hashes = verify_p3_method_hashes()
    status = (
        "PASS"
        if chosen_n is not None and hashes["unchanged"]
        else "V2_MINI_PILOT_INFEASIBLE"
    )
    result = {
        "schema_version": 1,
        "method": "correlated_normal_approximation_to_three_paired_family_estimators",
        "delta0": DELTA0,
        "delta1": DELTA1,
        "p3_certification_critical_z": Z_P3,
        "holm_family_wise_alpha": ALPHA,
        "holm_hypotheses": 3,
        "simulation_repetitions_per_row": repetitions,
        "primary_scenario": list(primary),
        "plausible_discordance_upper_bound": 0.25,
        "primary_sample_size_evaluation": primary_summaries,
        "chosen_reasoning_n": chosen_n,
        "p3_method_hashes": hashes,
        "path_b_used_in_go_decision": False,
        "status": status,
        "rows": rows,
    }
    if write:
        target = ROOT / "artifacts/construct_v2/multiplicity_power.yaml"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(yaml.safe_dump(result, sort_keys=False), encoding="utf-8")
        report = ROOT / "reports/construct_v2_power_report.md"
        report.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            "# Direction P v2 multiplicity-aware power",
            "",
            "The selected N is the smallest registered candidate whose worst dependence-grid",
            "Stable Path power is at least 0.80 for two active families at δ1=0.15 and",
            "discordance 0.25. Natural language forms the three-hypothesis Holm family; triples",
            "enters only the prespecified robustness check.",
            "",
            "| N | Stable Path range | passes 0.80 |",
            "|---:|---:|:---:|",
        ]
        for item in primary_summaries:
            low, high = item["overall_stable_path_power_range_over_dependence"]
            lines.append(f"| {item['n']} | {low:.4f}–{high:.4f} | {item['passes_minimum_0_80']} |")
        lines.extend(
            [
                "",
                f"Chosen reasoning N: **{chosen_n}**.",
                "",
                "P3 numerical rules and hashes are unchanged. The simulation estimates a",
                "behavioral certification gate and does not validate an internal mechanism.",
            ]
        )
        report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return result


def power_summary_json(result: dict[str, Any]) -> str:
    return json.dumps(
        {
            "status": result["status"],
            "chosen_reasoning_n": result["chosen_reasoning_n"],
            "primary_sample_size_evaluation": result["primary_sample_size_evaluation"],
        },
        indent=2,
    )

