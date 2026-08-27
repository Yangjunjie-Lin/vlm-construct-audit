"""Direction P preregistered known-DGP power and minimum-potential screen."""

from __future__ import annotations

import math
from pathlib import Path
from statistics import mean
from typing import Any

import numpy as np
from scipy.stats import beta, norm

from ..triage.audit_v2 import audit_claim_v2
from .common import ROOT, canonical_hash, dump_yaml, load_yaml, utc_now, write_jsonl

Z_95_ONE = 1.6448536269514722
Z_95_TWO = 1.959963984540054
POSITIVE = "EFFECT_ABOVE_CERTIFICATION_THRESHOLD"


def _analytic_probabilities(n: int, effect: float, config: dict[str, Any]) -> dict[str, float]:
    delta0 = float(config["scientific_sesoi_delta0"])
    variance = float(config["delta1_selection"]["paired_scene_variance"])
    certification_z = float(config["methods"]["P3"]["certification_critical_z"])
    below_z = float(config["methods"]["P3"]["below_critical_z"])
    se = math.sqrt(variance / n)
    p_certify = float(norm.cdf((effect - delta0) / se - certification_z))
    p_below = float(norm.cdf((delta0 - effect) / se - below_z))
    p_gray = max(0.0, 1.0 - p_certify - p_below)
    return {
        "sample_size": n,
        "effect": effect,
        "standard_error": se,
        "probability_of_certification": p_certify,
        "probability_of_gray_zone_output": p_gray,
        "probability_of_below_SESOI_output": p_below,
        "probability_of_false_positive": p_certify if effect <= delta0 else 0.0,
        "probability_of_false_negative": 1.0 - p_certify if effect >= config["certification_alternative_delta1"] else 0.0,
    }


def write_analytic_power_documents() -> dict[str, Any]:
    config = load_yaml("research/post_stop/direction_p/preregistration.yaml")
    rows = [
        _analytic_probabilities(n, effect, config)
        for n in config["analytic_power_grid"]["sample_sizes"]
        for effect in config["analytic_power_grid"]["effects"]
    ]
    target = next(
        row for row in rows
        if row["sample_size"] == config["delta1_selection"]["feasible_maximum_sample_size"]
        and row["effect"] == config["certification_alternative_delta1"]
    )
    feasible = target["probability_of_certification"] >= config["delta1_selection"]["target_power"]
    table = {
        "schema_version": 1,
        "generated_before_any_direction_p_DGP_outcome": True,
        "config_hash": canonical_hash(config),
        "delta0": config["scientific_sesoi_delta0"],
        "delta1": config["certification_alternative_delta1"],
        "paired_scene_variance": config["delta1_selection"]["paired_scene_variance"],
        "one_sided_alpha": config["delta1_selection"]["primary_one_sided_alpha"],
        "critical_z": config["delta1_selection"]["primary_critical_z"],
        "target_power": config["delta1_selection"]["target_power"],
        "feasible_maximum_sample_size": config["delta1_selection"]["feasible_maximum_sample_size"],
        "power_at_delta1_and_feasible_maximum": target["probability_of_certification"],
        "feasible": feasible,
        "rows": rows,
    }
    dump_yaml("research/post_stop/direction_p/power_table.yaml", table)
    lines = [
        "# Direction P Analytic Power",
        "",
        "Frozen before any Direction P simulated DGP outcome. The scientific SESOI is δ0=0.10; it",
        "is unchanged. Under paired scene-level variance 0.16 and a one-sided certification alpha",
        "of 0.025, the smallest two-decimal certification alternative reaching at least 80% power",
        "at the feasible maximum N=768 is δ1=0.15.",
        "",
        f"Analytic power at δ1 and N=768 is {target['probability_of_certification']:.4f}.",
        "The indifference zone is a non-claim region, not a success or failure. P3 uses the",
        "predeclared normal approximation only within the registered paired-DGP model; no guarantee",
        "is transported across families, generator changes, non-exchangeable shifts, or real VLMs.",
        "",
        "| N | effect | certify | gray | below | false positive | false negative |",
        "|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['sample_size']} | {row['effect']:.2f} | "
            f"{row['probability_of_certification']:.4f} | "
            f"{row['probability_of_gray_zone_output']:.4f} | "
            f"{row['probability_of_below_SESOI_output']:.4f} | "
            f"{row['probability_of_false_positive']:.4f} | "
            f"{row['probability_of_false_negative']:.4f} |"
        )
    path = ROOT / "research/post_stop/direction_p/analytic_power.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"feasible": feasible, "delta1": table["delta1"], "power": table["power_at_delta1_and_feasible_maximum"]}


def _lower_exact(successes: int, n: int, alpha: float = 0.05) -> float:
    return 0.0 if successes == 0 else float(beta.ppf(alpha, successes, n - successes + 1))


def _draw_effect(rng: np.random.Generator, family: dict[str, Any], config: dict[str, Any]) -> float:
    low, high = map(float, family["truth_effect"])
    if family["family"] == "StochasticUptakeITT":
        ranges = config["new_parameter_ranges"]
        uptake = rng.uniform(*ranges["stochastic_uptake_probability"])
        complier = rng.uniform(*ranges["stochastic_complier_effect"])
        return float(uptake * complier)
    return low if low == high else float(rng.uniform(low, high))


def _paired_cell(rng: np.random.Generator, effect: float, n: int) -> dict[str, float]:
    effect = float(np.clip(effect, -0.85, 0.85))
    discordance = max(abs(effect) + 0.02, 0.16 + effect * effect)
    discordance = min(discordance, 0.98)
    p01 = (discordance + effect) / 2
    p10 = (discordance - effect) / 2
    counts = rng.multinomial(n, [p01, p10, 1 - discordance])
    estimate = float((counts[0] - counts[1]) / n)
    variance = float(max(1e-12, (counts[0] + counts[1]) / n - estimate * estimate))
    return {"estimate": estimate, "paired_variance": variance, "discordant": int(counts[0] + counts[1])}


def _simulate_dataset(config: dict[str, Any], family: dict[str, Any], n: int, repetition: int, split: str) -> dict[str, Any]:
    base = 171000000 if split == "development" else 271000000
    seed = base + n * 10000 + int(family["family_index"]) * 100 + repetition
    rng = np.random.default_rng(seed)
    name = family["family"]
    true_effect = _draw_effect(rng, family, config)
    offsets = list(map(float, family.get("cell_effect_offsets", [0.0, 0.003, -0.003, 0.0])))
    observed_effects = [true_effect + value for value in offsets]
    if name == "ContractPseudoEffect":
        observed_effects = [0.24, 0.22, 0.01, -0.01]
    elif name == "FormatShortcut":
        observed_effects = [0.28, 0.25, -0.02, 0.00]
    elif name == "InvalidUptake":
        observed_effects = [0.19, 0.18, 0.17, 0.20]
    cells = [_paired_cell(rng, value, n) for value in observed_effects]
    estimate = mean(cell["estimate"] for cell in cells)
    se = math.sqrt(max(cell["paired_variance"] for cell in cells) / n)
    ranges = config["new_parameter_ranges"]
    measurement_p = rng.uniform(*ranges["valid_measurement_probability"])
    parser_p = rng.uniform(*ranges["valid_measurement_probability"])
    if name == "MeasurementCorruption":
        measurement_p = rng.uniform(*ranges["corrupt_measurement_probability"])
        parser_p = rng.uniform(0.88, 0.95)
    probes = int(config["measurement_validation"]["probes_per_dataset"])
    measurement_success = int(rng.binomial(probes, measurement_p))
    parser_success = int(rng.binomial(probes, parser_p))
    measurement_lower = _lower_exact(measurement_success, probes)
    parser_rate = parser_success / probes
    uptake_p = rng.uniform(*ranges["valid_uptake_probability"])
    if name == "InvalidUptake":
        uptake_p = rng.uniform(*ranges["invalid_uptake_probability"])
    uptake_success = int(rng.binomial(probes, uptake_p))
    uptake_lower = _lower_exact(uptake_success, probes)
    kappa = float(rng.uniform(*ranges["valid_contract_kappa"]))
    if name == "ContractPseudoEffect":
        kappa = float(rng.uniform(*ranges["invalid_contract_kappa"]))
    kappa_lower = max(-1.0, kappa - 0.025)
    format_interactions = [float(rng.normal(0, 0.008)), float(rng.normal(0, 0.008))]
    if name == "FormatShortcut":
        format_interactions = [0.22, 0.25]
    partial = name == "MixedPrincipalStrata"
    record = {
        "split": split,
        "family": name,
        "family_index": family["family_index"],
        "sample_size": n,
        "repetition": repetition,
        "seed": seed,
        "truth_effect": true_effect,
        "expected_decision": family["expected_decision"],
        "eligibility": family["eligibility"],
        "cell_estimates": [cell["estimate"] for cell in cells],
        "estimate": estimate,
        "standard_error": se,
        "ci95": [max(-1.0, estimate - Z_95_TWO * se), min(1.0, estimate + Z_95_TWO * se)],
        "measurement_lower": measurement_lower,
        "parser_valid_rate": parser_rate,
        "uptake_lower": uptake_lower,
        "contract_kappa": kappa,
        "contract_kappa_lower": kappa_lower,
        "format_interactions": format_interactions,
        "partial_identification": partial,
    }
    for method in ["P0", "P1", "P2", "P3"]:
        record[f"decision_{method}"] = _decide(record, method, config)
    return record


def _invalidity_decision(row: dict[str, Any], config: dict[str, Any]) -> str | None:
    if row["measurement_lower"] < config["measurement_validation"]["cutoff"] or row["parser_valid_rate"] < config["measurement_validation"]["parser_valid_cutoff"]:
        return "INVALID_MEASUREMENT"
    if row["contract_kappa"] < config["contract_validation"]["kappa_cutoff"] or row["contract_kappa_lower"] < config["contract_validation"]["kappa_lower_cutoff"]:
        return "FORMAT_OR_CONTRACT_DEPENDENT"
    if max(abs(value) for value in row["format_interactions"]) > config["contract_validation"]["format_materiality"]:
        return "FORMAT_OR_CONTRACT_DEPENDENT"
    if row["partial_identification"]:
        return "PARTIALLY_IDENTIFIED"
    if row["uptake_lower"] < config["intervention_validation"]["cutoff"]:
        return "INVALID_INTERVENTION"
    return None


def _decide(row: dict[str, Any], method: str, config: dict[str, Any], critical_z: float | None = None) -> str:
    if method == "P0":
        measurement = {
            "one_sided_95_lower": row["measurement_lower"],
            "parser_valid_rate": row["parser_valid_rate"],
            "contract_agreement": {"kappa": row["contract_kappa"], "ci95": [row["contract_kappa_lower"], 1.0]},
        }
        uptake = {"aggregate": {"ci95": [row["uptake_lower"], 1.0]}}
        downstream = {"cells": {f"cell_{i}": {"estimate": value, "scene_clusters": row["sample_size"]} for i, value in enumerate(row["cell_estimates"])}}
        partial = {"eligible": row["partial_identification"], "observed_uptake_filtering": False, "bounds": [-1.0, 1.0]}
        replication = {
            "equivalence": {"programmatic_fact_equivalence": True},
            "format_interactions": {f"format_{i}": value for i, value in enumerate(row["format_interactions"])},
            "format_tost": {"nl": {"tost_equivalent": True}, "triples": {"tost_equivalent": True}},
            "partial_identification": partial,
        }
        policy = {
            "measurement_validity_cutoff": config["measurement_validation"]["cutoff"],
            "contract_kappa_cutoff": config["contract_validation"]["kappa_cutoff"],
            "contract_kappa_lower_bound_cutoff": config["contract_validation"]["kappa_lower_cutoff"],
            "format_materiality": config["contract_validation"]["format_materiality"],
            "gate_cutoff": config["intervention_validation"]["cutoff"],
            "sesoi": config["scientific_sesoi_delta0"],
        }
        old = audit_claim_v2(measurement, uptake, downstream, replication, policy).decision
        return {
            "VALID_BEHAVIORAL_EFFECT": POSITIVE,
            "FORMAT_DEPENDENT": "FORMAT_OR_CONTRACT_DEPENDENT",
            "INVALID_MEASUREMENT": "INVALID_MEASUREMENT",
            "INVALID_INTERVENTION": "INVALID_INTERVENTION",
            "PARTIALLY_IDENTIFIED": "PARTIALLY_IDENTIFIED",
        }.get(old, "INCONCLUSIVE")
    invalid = _invalidity_decision(row, config)
    if invalid:
        return invalid
    delta0 = float(config["scientific_sesoi_delta0"])
    if method == "P1":
        return POSITIVE if row["estimate"] - Z_95_ONE * row["standard_error"] > delta0 else "INCONCLUSIVE"
    if method == "P2":
        critical_z = Z_95_ONE
    elif method == "P3" and critical_z is None:
        critical_z = float(config["methods"]["P3"]["certification_critical_z"])
    if row["estimate"] - float(critical_z) * row["standard_error"] > delta0:
        return POSITIVE
    if row["estimate"] + Z_95_ONE * row["standard_error"] <= delta0:
        return "EFFECT_BELOW_SESOI"
    return "EFFECT_IN_INDIFFERENCE_ZONE"


def _rate(rows: list[dict[str, Any]], predicate: Any) -> float:
    return 0.0 if not rows else sum(bool(predicate(row)) for row in rows) / len(rows)


def _summarize(rows: list[dict[str, Any]], method: str, config: dict[str, Any], n: int, critical_z: float | None = None) -> dict[str, Any]:
    selected = [row for row in rows if row["sample_size"] == n]
    key = f"decision_{method}"
    decision = (lambda row: _decide(row, method, config, critical_z)) if critical_z is not None else (lambda row: row[key])
    invalid = [row for row in selected if row["eligibility"] not in {"valid"}]
    low = [row for row in selected if row["eligibility"] == "valid" and row["truth_effect"] <= config["scientific_sesoi_delta0"]]
    gray = [row for row in selected if row["eligibility"] == "valid" and config["scientific_sesoi_delta0"] < row["truth_effect"] < config["certification_alternative_delta1"]]
    high = [row for row in selected if row["eligibility"] == "valid" and row["truth_effect"] >= config["certification_alternative_delta1"]]
    eligible = [row for row in selected if row["eligibility"] == "valid"]
    positives = [row for row in high if decision(row) == POSITIVE]
    type_s = _rate(positives, lambda row: row["estimate"] < 0)
    type_m_values = [abs(row["estimate"] / row["truth_effect"]) for row in positives if row["truth_effect"] != 0]
    by_family = {}
    for family in sorted({row["family"] for row in selected}):
        family_rows = [row for row in selected if row["family"] == family]
        by_family[family] = {
            "count": len(family_rows),
            "positive_rate": _rate(family_rows, lambda row: decision(row) == POSITIVE),
            "exact_expected_decision_rate": _rate(family_rows, lambda row: decision(row) == row["expected_decision"]),
        }
    return {
        "method": method,
        "sample_size": n,
        "dataset_count": len(selected),
        "fmcr": _rate(invalid, lambda row: decision(row) == POSITIVE),
        "specificity_effect_le_delta0": _rate(low, lambda row: decision(row) != POSITIVE),
        "sensitivity_effect_ge_delta1": _rate(high, lambda row: decision(row) == POSITIVE),
        "gray_zone_overclaim_rate": _rate(gray, lambda row: decision(row) == POSITIVE),
        "coverage": _rate(eligible, lambda row: row["ci95"][0] <= row["truth_effect"] <= row["ci95"][1]),
        "type_s": type_s,
        "type_m_ratio": mean(type_m_values) if type_m_values else None,
        "abstention_rate": _rate(selected, lambda row: decision(row) == "INCONCLUSIVE"),
        "explicit_gray_zone_rate": _rate(selected, lambda row: decision(row) == "EFFECT_IN_INDIFFERENCE_ZONE"),
        "claim_coverage": _rate(selected, lambda row: decision(row) == POSITIVE),
        "by_family": by_family,
    }


def _paired_improvement_interval(rows: list[dict[str, Any]], n: int) -> dict[str, float]:
    high = [row for row in rows if row["sample_size"] == n and row["eligibility"] == "valid" and row["truth_effect"] >= 0.15]
    differences = np.asarray([(row["decision_P3"] == POSITIVE) - (row["decision_P0"] == POSITIVE) for row in high], dtype=float)
    value = float(differences.mean())
    se = float(differences.std(ddof=1) / math.sqrt(len(differences)))
    return {"mean": value, "ci95": [value - Z_95_TWO * se, value + Z_95_TWO * se], "paired_datasets": len(high)}


def _build_summary(rows: list[dict[str, Any]], config: dict[str, Any], split: str) -> dict[str, Any]:
    curves = {method: [_summarize(rows, method, config, n) for n in config["simulation"]["sample_sizes"]] for method in ["P0", "P1", "P2", "P3"]}
    primary_n = int(config["simulation"]["primary_sample_size"])
    primary = {method: next(item for item in curve if item["sample_size"] == primary_n) for method, curve in curves.items()}
    risk_curve = []
    for critical_z in config["methods"]["P3"]["threshold_stability_z"]:
        metric = _summarize(rows, "P3", config, primary_n, float(critical_z))
        risk_curve.append({"critical_z": critical_z, **{key: metric[key] for key in ["fmcr", "sensitivity_effect_ge_delta1", "specificity_effect_le_delta0", "gray_zone_overclaim_rate", "abstention_rate", "claim_coverage"]}})
    gates = config["go_gates"]
    p3 = primary["P3"]
    non_strong = [name for name in ["CertificationBoundaryEffect", "ModerateEffect", "HeterogeneousEffect", "StochasticUptakeITT"] if p3["by_family"][name]["positive_rate"] >= 0.80]
    improvement = _paired_improvement_interval(rows, primary_n)
    gate_table = {
        "fmcr": p3["fmcr"] <= gates["fmcr_max"],
        "specificity": p3["specificity_effect_le_delta0"] >= gates["specificity_effect_le_delta0_min"],
        "sensitivity": p3["sensitivity_effect_ge_delta1"] >= gates["sensitivity_effect_ge_delta1_min"],
        "gray_zone_overclaim": p3["gray_zone_overclaim_rate"] <= gates["gray_zone_overclaim_max"],
        "coverage": p3["coverage"] >= gates["coverage_min"],
        "type_s": p3["type_s"] <= gates["type_s_max"],
        "abstention": p3["abstention_rate"] <= gates["abstention_max"],
        "two_non_strong_families": len(non_strong) >= gates["non_strong_families_with_sensitivity_ge_0_80_min"],
        "threshold_stability": all(row["fmcr"] <= 0.05 and row["sensitivity_effect_ge_delta1"] >= 0.80 and row["gray_zone_overclaim_rate"] <= 0.05 for row in risk_curve),
        "sensitivity_improvement_over_frozen_AuditV2": improvement["ci95"][0] > 0,
        "fmcr_not_worse_than_frozen_AuditV2": p3["fmcr"] <= primary["P0"]["fmcr"],
    }
    if all(gate_table.values()):
        decision = "DIRECTION_P_GO"
    elif split == "holdout":
        decision = "DIRECTION_P_NO_GO"
    else:
        decision = "DEVELOPMENT_COMPLETE_NOT_A_HOLDOUT_DECISION"
    return {
        "schema_version": 1,
        "direction": "P",
        "split": split,
        "config_hash": canonical_hash(config),
        "delta0": config["scientific_sesoi_delta0"],
        "delta1": config["certification_alternative_delta1"],
        "primary_sample_size": primary_n,
        "curves": curves,
        "primary_metrics": primary,
        "risk_coverage_curve": risk_curve,
        "threshold_stability": {"stable": gate_table["threshold_stability"], "rows": risk_curve},
        "non_strong_families_at_or_above_0_80": non_strong,
        "paired_sensitivity_improvement_P3_minus_P0": improvement,
        "gate_table": gate_table,
        "decision": decision,
        "claim_boundary": config["claim_boundary"],
    }


def run_direction_p(split: str) -> dict[str, Any]:
    if split not in {"development", "holdout"}:
        raise ValueError(split)
    config = load_yaml("research/post_stop/direction_p/preregistration.yaml")
    power = load_yaml("research/post_stop/direction_p/power_table.yaml")
    if not power.get("feasible"):
        return {"decision": "INFEASIBLE_NO_GO", "no_DGP_generated": True}
    artifact_root = Path("artifacts/post_stop/direction_p") / split
    marker_path = ROOT / artifact_root / "execution_marker.yaml"
    if split == "holdout":
        freeze = ROOT / "research/post_stop/direction_p/method_freeze.yaml"
        authorization = ROOT / "research/post_stop/direction_p/holdout_authorization.yaml"
        if not freeze.exists() or not authorization.exists():
            raise RuntimeError("sealed holdout requires method freeze and authorization records")
        if marker_path.exists():
            raise RuntimeError("Direction P sealed holdout execution limit exhausted")
    started = utc_now()
    marker = {
        "schema_version": 1,
        "direction": "P",
        "split": split,
        "started_at": started,
        "config_hash": canonical_hash(config),
        "execution_count": 1,
        "old_loop_a_holdout_accessed_for_tuning": False,
        "intermediate_results_emitted": False,
        "status": "RUNNING",
    }
    dump_yaml(marker_path.relative_to(ROOT), marker)
    rows = [
        _simulate_dataset(config, family, n, repetition, split)
        for family in config["families"]
        for n in config["simulation"]["sample_sizes"]
        for repetition in range(config["simulation"]["repetitions_per_family_size_split"])
    ]
    summary = _build_summary(rows, config, split)
    write_jsonl(artifact_root / "dataset_results.jsonl", rows)
    dump_yaml(artifact_root / "summary.yaml", summary)
    marker.update({"completed_at": utc_now(), "status": "COMPLETE", "dataset_count": len(rows), "decision": summary["decision"]})
    dump_yaml(marker_path.relative_to(ROOT), marker)
    return summary
