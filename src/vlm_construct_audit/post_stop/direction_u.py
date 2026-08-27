"""Direction U known-DGP uptake identification calibration."""

from __future__ import annotations

import math
from pathlib import Path
from statistics import mean, median
from typing import Any

import numpy as np

from .common import ROOT, canonical_hash, dump_yaml, load_yaml, utc_now, write_jsonl

Z95 = 1.959963984540054
STRATA = ["always", "complier", "defier", "never"]


def _diff_mean(y: np.ndarray, group: np.ndarray) -> tuple[float, float, list[float]]:
    one = y[group == 1]
    zero = y[group == 0]
    estimate = float(one.mean() - zero.mean())
    se = math.sqrt(float(one.var(ddof=1) / len(one) + zero.var(ddof=1) / len(zero)))
    return estimate, se, [estimate - Z95 * se, estimate + Z95 * se]


def _wald(y: np.ndarray, u: np.ndarray, z: np.ndarray) -> tuple[float | None, float | None, list[float | None]]:
    dy = float(y[z == 1].mean() - y[z == 0].mean())
    du = float(u[z == 1].mean() - u[z == 0].mean())
    if abs(du) < 1e-8:
        return None, None, [None, None]
    estimate = dy / du
    p = float(z.mean())
    weight = z / p - (1 - z) / (1 - p)
    influence = weight * (y - estimate * u) / du
    se = float(influence.std(ddof=1) / math.sqrt(len(y)))
    return estimate, se, [estimate - Z95 * se, estimate + Z95 * se]


def _regression(y: np.ndarray, u: np.ndarray, z: np.ndarray) -> tuple[float, float, list[float]]:
    x = np.column_stack([np.ones(len(y)), z, u])
    inv = np.linalg.pinv(x.T @ x)
    coef = inv @ x.T @ y
    residual = y - x @ coef
    meat = x.T @ (x * residual[:, None] ** 2)
    covariance = inv @ meat @ inv
    estimate = float(coef[2])
    se = math.sqrt(max(0.0, float(covariance[2, 2])))
    return estimate, se, [estimate - Z95 * se, estimate + Z95 * se]


def _principal_mixture(y: np.ndarray, u: np.ndarray, z: np.ndarray) -> tuple[float | None, float | None, list[float | None]]:
    p0 = float(u[z == 0].mean())
    p1 = float(u[z == 1].mean())
    pc = p1 - p0
    pa = p0
    pn = 1 - p1
    if pc <= 1e-8 or min(pa + pc, pn + pc) <= 0:
        return None, None, [None, None]
    mu_a1 = float(y[(z == 0) & (u == 1)].mean()) if np.any((z == 0) & (u == 1)) else 0.0
    mu_n0 = float(y[(z == 1) & (u == 0)].mean()) if np.any((z == 1) & (u == 0)) else 0.0
    mix1 = float(y[(z == 1) & (u == 1)].mean())
    mix0 = float(y[(z == 0) & (u == 0)].mean())
    mu_c1 = ((pa + pc) * mix1 - pa * mu_a1) / pc
    mu_c0 = ((pn + pc) * mix0 - pn * mu_n0) / pc
    estimate = mu_c1 - mu_c0
    _, se, _ = _wald(y, u, z)
    ci = [estimate - Z95 * se, estimate + Z95 * se]
    return estimate, se, ci


def _bounds(dgp: dict[str, Any], y: np.ndarray, u: np.ndarray, z: np.ndarray) -> tuple[float, float] | None:
    dy = float(y[z == 1].mean() - y[z == 0].mean())
    du = float(u[z == 1].mean() - u[z == 0].mean())
    if abs(du) < 0.10 or "violation_budget" not in dgp:
        return None
    epsilon = float(dgp["violation_budget"])
    measurement = dgp["measurement_error"]
    if isinstance(measurement, dict):
        reliability = measurement["registered_reliability_range"]
        values = [(dy + sign * epsilon) * value / du for sign in [-1, 1] for value in reliability]
    else:
        values = [(dy - epsilon) / du, (dy + epsilon) / du]
    return max(-1.0, min(values)), min(1.0, max(values))


def _simulate(config: dict[str, Any], dgp: dict[str, Any], n: int, repetition: int, split: str) -> dict[str, Any]:
    base = 183000000 if split == "development" else 283000000
    seed = base + n * 10000 + int(dgp["DGP_index"]) * 1000 + repetition
    rng = np.random.default_rng(seed)
    proportions = np.asarray([dgp["principal_stratum"][name] for name in STRATA], dtype=float)
    strata_index = rng.choice(len(STRATA), n, p=proportions)
    strata = np.asarray([STRATA[index] for index in strata_index])
    z = rng.binomial(1, 0.5, n)
    u0 = np.isin(strata, ["always", "defier"]).astype(int)
    u1 = np.isin(strata, ["always", "complier"]).astype(int)
    u_true = np.where(z == 1, u1, u0)
    baseline = np.asarray([dgp["baseline_probabilities"][name] for name in strata])
    effects = np.asarray([dgp["stratum_effects"][name] for name in strata])
    latent = rng.random(n)
    y0 = (latent < baseline).astype(int)
    y1 = (latent < np.clip(baseline + effects, 0, 1)).astype(int)
    outcome_probability = np.where(u_true == 1, np.clip(baseline + effects, 0, 1), baseline)
    outcome_probability = np.clip(outcome_probability + z * float(dgp["direct_Z_effect"]), 0, 1)
    y = (rng.random(n) < outcome_probability).astype(int)
    u_observed = u_true.copy()
    if isinstance(dgp["measurement_error"], dict):
        sensitivity = float(dgp["measurement_error"]["sensitivity"])
        specificity = float(dgp["measurement_error"]["specificity"])
        u_observed = np.where(u_true == 1, rng.binomial(1, sensitivity, n), rng.binomial(1, 1 - specificity, n))
    naive_mask = u_observed == 1
    if len(set(z[naive_mask])) == 2:
        u0_est = _diff_mean(y[naive_mask], z[naive_mask])
    else:
        u0_est = (None, None, [None, None])
    u1_est = _diff_mean(y, z)
    u2_est = _regression(y, u_observed, z)
    u3_est = _principal_mixture(y, u_observed, z)
    u4_est = _wald(y, u_observed, z)
    first_stage = float(u_observed[z == 1].mean() - u_observed[z == 0].mean())
    bounds = _bounds(dgp, y, u_observed, z)
    status = dgp["identification_status"]
    warning = status != "POINT_IDENTIFIED"
    if status == "POINT_IDENTIFIED" and abs(first_stage) >= config["weak_encouragement_cutoff"]:
        policy_status = "POINT_IDENTIFIED"
        policy_estimate, policy_se, policy_ci = u4_est
        policy_bounds = None
    elif status == "PARTIALLY_IDENTIFIED" and bounds is not None:
        policy_status = "PARTIALLY_IDENTIFIED"
        policy_estimate, policy_se, policy_ci = None, None, [None, None]
        policy_bounds = list(bounds)
    else:
        policy_status = "NOT_IDENTIFIED"
        policy_estimate, policy_se, policy_ci = None, None, [None, None]
        policy_bounds = None
    positive = policy_status == "POINT_IDENTIFIED" and policy_ci[0] is not None and policy_ci[0] > 0
    naive_positive = u0_est[2][0] is not None and u0_est[2][0] > 0
    return {
        "split": split, "DGP": dgp["DGP"], "DGP_index": dgp["DGP_index"], "sample_size": n,
        "repetition": repetition, "seed": seed, "config_hash": canonical_hash(config),
        "true_ITT": float(dgp["true_ITT"]),
        "true_CACE": dgp["true_CACE_or_target_stratum_effect"],
        "identification_status": status, "first_stage": first_stage,
        "assumption_warning": warning,
        "U0": {"estimate": u0_est[0], "se": u0_est[1], "ci95": u0_est[2], "positive_claim": naive_positive},
        "U1": {"estimate": u1_est[0], "se": u1_est[1], "ci95": u1_est[2]},
        "U2": {"estimate": u2_est[0], "se": u2_est[1], "ci95": u2_est[2]},
        "U3": {"estimate": u3_est[0], "se": u3_est[1], "ci95": u3_est[2]},
        "U4": {"estimate": u4_est[0], "se": u4_est[1], "ci95": u4_est[2]},
        "U5": {"bounds": list(bounds) if bounds is not None else None},
        "policy": {"status": policy_status, "estimate": policy_estimate, "se": policy_se, "ci95": policy_ci, "bounds": policy_bounds, "positive_claim": positive, "unconditional_valid_behavioral_effect": False if warning else positive},
        "latent_check": {"sample_true_ITT": float(np.mean(np.where(u1 == 1, y1, y0) - np.where(u0 == 1, y1, y0))), "observed_uptake_filtering_used_by_policy": False},
    }


def _method_metrics(rows: list[dict[str, Any]], method: str, target: str) -> dict[str, Any]:
    values = []
    covered = []
    signed = []
    for row in rows:
        truth = row[target]
        estimate = row[method]["estimate"]
        ci = row[method]["ci95"]
        if isinstance(truth, (int, float)) and estimate is not None:
            values.append(float(estimate) - float(truth))
            if ci[0] is not None:
                covered.append(ci[0] <= truth <= ci[1])
                if ci[0] > 0 or ci[1] < 0:
                    signed.append(np.sign(estimate) != np.sign(truth) if truth != 0 else False)
    return {
        "count": len(values), "bias": mean(values) if values else None,
        "absolute_bias": abs(mean(values)) if values else None,
        "rmse": math.sqrt(mean(value * value for value in values)) if values else None,
        "coverage": mean(covered) if covered else None,
        "type_s": mean(signed) if signed else 0.0,
    }


def _summarize(rows: list[dict[str, Any]], config: dict[str, Any], split: str) -> dict[str, Any]:
    primary_n = max(config["sample_sizes"])
    primary = [row for row in rows if row["sample_size"] == primary_n]
    point = [row for row in primary if row["identification_status"] == "POINT_IDENTIFIED"]
    partial = [row for row in primary if row["identification_status"] == "PARTIALLY_IDENTIFIED"]
    violations = [row for row in primary if row["identification_status"] != "POINT_IDENTIFIED"]
    policy_values = [row["policy"]["estimate"] - row["true_CACE"] for row in point if row["policy"]["estimate"] is not None]
    policy_coverage = [row["policy"]["ci95"][0] <= row["true_CACE"] <= row["policy"]["ci95"][1] for row in point if row["policy"]["ci95"][0] is not None]
    bound_rows = [row for row in partial if row["policy"]["bounds"] is not None]
    bound_coverage = [row["policy"]["bounds"][0] <= row["true_CACE"] <= row["policy"]["bounds"][1] for row in bound_rows]
    bound_widths = [row["policy"]["bounds"][1] - row["policy"]["bounds"][0] for row in bound_rows]
    by_regime = {}
    dgp_map = {item["DGP"]: item for item in config["DGPs"]}
    for name in sorted({row["DGP"] for row in partial}):
        selected = [row for row in bound_rows if row["DGP"] == name]
        by_regime[name] = {
            "compliance_regime": dgp_map[name].get("compliance_regime"),
            "bound_coverage": mean(row["policy"]["bounds"][0] <= row["true_CACE"] <= row["policy"]["bounds"][1] for row in selected) if selected else None,
            "median_bound_width": median(row["policy"]["bounds"][1] - row["policy"]["bounds"][0] for row in selected) if selected else None,
        }
    naive_fmcr = mean(row["U0"]["positive_claim"] for row in violations)
    policy_fmcr = mean(row["policy"]["unconditional_valid_behavioral_effect"] for row in violations)
    null_point = [row for row in point if row["true_CACE"] == 0]
    false_positive = mean(row["policy"]["positive_claim"] for row in null_point)
    significant_point = [row for row in point if row["policy"]["ci95"][0] > 0 or row["policy"]["ci95"][1] < 0]
    policy_type_s = mean(bool(np.sign(row["policy"]["estimate"]) != np.sign(row["true_CACE"])) for row in significant_point if row["true_CACE"] != 0) if any(row["true_CACE"] != 0 for row in significant_point) else 0.0
    informative = [name for name, value in by_regime.items() if value["bound_coverage"] is not None and value["bound_coverage"] >= 0.90 and value["median_bound_width"] <= 0.20]
    metrics = {
        "primary_sample_size": primary_n,
        "methods": {
            "U0": _method_metrics(point, "U0", "true_CACE"),
            "U1": _method_metrics(primary, "U1", "true_ITT"),
            "U2": _method_metrics(point, "U2", "true_CACE"),
            "U3": _method_metrics(point, "U3", "true_CACE"),
            "U4": _method_metrics(point, "U4", "true_CACE"),
        },
        "policy": {
            "absolute_bias": abs(mean(policy_values)),
            "rmse": math.sqrt(mean(value * value for value in policy_values)),
            "coverage": mean(policy_coverage),
            "false_positive_rate": false_positive,
            "type_s": policy_type_s,
            "fmcr": policy_fmcr,
            "naive_observed_uptake_filtering_fmcr": naive_fmcr,
            "fmcr_absolute_reduction_vs_naive": naive_fmcr - policy_fmcr,
            "assumption_warning_rate_violation_settings": mean(row["assumption_warning"] for row in violations),
            "unconditional_valid_rate_violation_settings": mean(row["policy"]["unconditional_valid_behavioral_effect"] for row in violations),
            "weak_instrument_failure_rate": mean(row["policy"]["status"] == "NOT_IDENTIFIED" for row in primary if row["DGP"] == "WeakEncouragement"),
        },
        "partial_identification": {
            "bound_coverage": mean(bound_coverage),
            "median_bound_width": median(bound_widths),
            "by_regime": by_regime,
            "informative_regimes": informative,
        },
        "status_counts": {status: sum(row["policy"]["status"] == status for row in primary) for status in ["POINT_IDENTIFIED", "PARTIALLY_IDENTIFIED", "NOT_IDENTIFIED"]},
    }
    gates = config["go_gates"]
    gate_table = {
        "absolute_bias": metrics["policy"]["absolute_bias"] <= gates["point_identified_absolute_bias_max"],
        "coverage": metrics["policy"]["coverage"] >= gates["point_identified_coverage_min"],
        "fmcr": metrics["policy"]["fmcr"] <= gates["fmcr_max"],
        "type_s": metrics["policy"]["type_s"] <= gates["type_s_max"],
        "bound_coverage": metrics["partial_identification"]["bound_coverage"] >= gates["partial_bound_coverage_min"],
        "bound_width": metrics["partial_identification"]["median_bound_width"] <= gates["partial_median_bound_width_max"],
        "two_informative_regimes": len(informative) >= gates["informative_realistic_compliance_regimes_min"],
        "warnings": metrics["policy"]["assumption_warning_rate_violation_settings"] >= gates["sensitivity_warning_rate_violation_settings"],
        "no_unconditional_valid": metrics["policy"]["unconditional_valid_rate_violation_settings"] <= gates["unconditional_valid_rate_violation_settings"],
        "fmcr_reduction": metrics["policy"]["fmcr_absolute_reduction_vs_naive"] >= gates["fmcr_absolute_reduction_vs_naive_min"],
    }
    decision = "DEVELOPMENT_COMPLETE_NOT_A_HOLDOUT_DECISION" if split != "holdout" else ("DIRECTION_U_GO" if all(gate_table.values()) else "DIRECTION_U_NO_GO")
    return {"schema_version": 1, "direction": "U", "split": split, "config_hash": canonical_hash(config), "DGP_count": len(config["DGPs"]), "dataset_count": len(rows), "metrics": metrics, "gate_table": gate_table, "decision": decision, "claim_boundary": config["known_DGP_claim_boundary"]}


def run_direction_u(split: str) -> dict[str, Any]:
    if split not in {"development", "holdout"}:
        raise ValueError(split)
    config = load_yaml("research/post_stop/direction_u/preregistration.yaml")
    root = Path("artifacts/post_stop/direction_u") / split
    marker = ROOT / root / "execution_marker.yaml"
    if split == "holdout":
        if not (ROOT / "research/post_stop/direction_u/method_freeze.yaml").exists() or not (ROOT / "research/post_stop/direction_u/holdout_authorization.yaml").exists():
            raise RuntimeError("Direction U holdout not frozen and authorized")
        if marker.exists():
            raise RuntimeError("Direction U sealed holdout execution limit exhausted")
    dump_yaml(root / "execution_marker.yaml", {"schema_version": 1, "direction": "U", "split": split, "status": "RUNNING", "started_at": utc_now(), "execution_count": 1, "config_hash": canonical_hash(config), "historical_outcomes_used_for_tuning": False})
    rows = [_simulate(config, dgp, n, repetition, split) for dgp in config["DGPs"] for n in config["sample_sizes"] for repetition in range(config["repetitions_per_DGP_size_split"])]
    summary = _summarize(rows, config, split)
    write_jsonl(root / "dataset_results.jsonl", rows)
    dump_yaml(root / "summary.yaml", summary)
    dump_yaml(root / "execution_marker.yaml", {"schema_version": 1, "direction": "U", "split": split, "status": "COMPLETE", "completed_at": utc_now(), "execution_count": 1, "config_hash": canonical_hash(config), "decision": summary["decision"], "historical_outcomes_used_for_tuning": False})
    return summary
