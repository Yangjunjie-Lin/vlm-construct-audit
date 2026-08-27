"""Unseen-DGP calibration generalization without modifying frozen A0."""

from __future__ import annotations

import hashlib
import math
import subprocess
from copy import deepcopy
from pathlib import Path
from statistics import mean
from typing import Any

import numpy as np

from ..audit.engine import audit_claim
from ..statistics.core import clopper_pearson_lower
from ..utils import canonical_hash, dump_yaml, load_yaml, write_jsonl

VALID_CLASS = "VALID_BEHAVIORAL_EFFECT"
INVALID_FAMILIES = {
    "CorrelatedFormatShortcut",
    "PartialUptakeNoComposition",
    "ContractDependentPseudoEffect",
    "EntityMappingLeakage",
    "StochasticParserFailure",
    "MixedValidInvalidPopulation",
}


def _git_head() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()


def reproduce_a0_baseline() -> dict[str, Any]:
    frozen = load_yaml("research/preregistration/tier0_5_a0_baseline.yaml")
    audit = load_yaml("artifacts/metrics/audit_decisions.yaml")
    repeated = load_yaml("artifacts/metrics/statistical_calibration.yaml")
    observed = {
        "fixed_inventory_fmcr": audit["baseline_metrics"]["B1_standard_single_contract_accuracy"]["false_mechanistic_claim_rate"],
        "full_audit_fixed_inventory_fmcr": audit["baseline_metrics"]["B5_full_validity_aware_audit"]["false_mechanistic_claim_rate"],
        "repeated_dgp_baseline_fmcr": repeated["baseline_false_mechanistic_claim_rate"]["B1"],
        "repeated_dgp_full_audit_fmcr": repeated["baseline_false_mechanistic_claim_rate"]["B5"],
        "sensitivity": repeated["sensitivity_to_known_valid_effects"],
        "coverage": repeated["empirical_ci_coverage"],
        "type_s": repeated["type_s_error"],
        "type_m_ratio": repeated["type_m_error_ratio"],
        "abstention": repeated["abstention_rate"],
    }
    expected = frozen["reproduced_metrics_required"]
    mismatches = {
        key: {"expected": expected[key], "observed": value}
        for key, value in observed.items()
        if not math.isclose(float(value), float(expected[key]), rel_tol=0, abs_tol=1e-12)
    }
    result = {
        "schema_version": 1,
        "baseline_id": "A0",
        "source_commit": frozen["source_commit"],
        "observed": observed,
        "mismatches": mismatches,
        "status": "PASS" if not mismatches else "FAIL",
    }
    dump_yaml("artifacts/loop_a/a0_baseline_reproduction.yaml", result)
    if mismatches:
        raise RuntimeError(f"A0 baseline reproduction failed: {mismatches}")
    return result


def _uniform(rng: np.random.Generator, value: Any) -> float:
    if isinstance(value, list):
        return float(rng.uniform(float(value[0]), float(value[1])))
    return float(value)


def _derive_seed(split: str, root_seed: int, family: str, stream: str) -> int:
    message = f"tier0_5_three_loop_triage_v1|{split}|{root_seed}|{family}|{stream}"
    return int.from_bytes(hashlib.sha256(message.encode("utf-8")).digest()[:8], "big")


def _effect_range(family: dict[str, Any], rng: np.random.Generator) -> float:
    truth = family["true_effect"]
    if "range" in truth:
        return _uniform(rng, truth["range"])
    if "weighted_ITT" in truth:
        return float(truth["weighted_ITT"])
    if "overall_ITT_range" in truth:
        return _uniform(rng, truth["overall_ITT_range"])
    if "compositional_effect" in truth:
        return _uniform(rng, truth["compositional_effect"])
    if "target_reasoning_effect" in truth:
        return float(truth["target_reasoning_effect"])
    if "target_effect" in truth:
        return float(truth["target_effect"])
    if "pre_mapping_effect" in truth:
        return _uniform(rng, truth["pre_mapping_effect"])
    raise KeyError(f"No overall effect in {family['family']}")


def _bootstrap_binary_ci(successes: int, total: int, rng: np.random.Generator) -> list[float]:
    estimate = successes / total
    bootstrap = rng.binomial(total, estimate, size=500) / total
    return [float(np.quantile(bootstrap, 0.025)), float(np.quantile(bootstrap, 0.975))]


def _sample_effect(probability: float, n: int, outcome_seed: int, bootstrap_seed: int) -> dict[str, Any]:
    outcome_rng = np.random.default_rng(outcome_seed)
    nested_outcomes = outcome_rng.random(384) < min(1.0, max(0.0, probability))
    successes = int(nested_outcomes[:n].sum())
    estimate = successes / n
    bootstrap_rng = np.random.default_rng(bootstrap_seed)
    return {
        "estimate": estimate,
        "ci95": _bootstrap_binary_ci(successes, n, bootstrap_rng),
        "scene_clusters": n,
        "successes": successes,
        "true_effect": probability,
    }


def _kappa_record(kappa: float, n: int) -> dict[str, Any]:
    standard_error = math.sqrt(max(1e-9, (1 - kappa * kappa) / max(n, 2)))
    lower = max(-1.0, kappa - 1.96 * standard_error)
    upper = min(1.0, kappa + 1.96 * standard_error)
    return {
        "kappa": kappa,
        "ci95": [lower, upper],
        "pair_count": n,
        "basis": "simulated_semantic_answer_agreement",
        "interpretation": "elicitation_plus_measurement_response_contract_robustness",
    }


def _family_parameters(family: dict[str, Any], rng: np.random.Generator) -> dict[str, float]:
    ranges = family["parameter_range"]
    params: dict[str, float] = {"true_effect": _effect_range(family, rng)}
    for key, value in ranges.items():
        if isinstance(value, list) and len(value) == 2 and all(isinstance(x, (int, float)) for x in value):
            params[key] = _uniform(rng, value)
    params.setdefault("measurement_validity", 1.0)
    params.setdefault("parser_validity", params["measurement_validity"])
    params.setdefault("contract_agreement", params.get("semantic_answer_kappa", 0.98))
    params.setdefault("uptake_probability", 0.96)
    params.setdefault("format_interaction", 0.0)
    return params


def _simulate_a0_inputs(
    family: dict[str, Any],
    n: int,
    root_seed: int,
    split_spec: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    family_name = family["family"]
    parameter_seed = _derive_seed(split_spec["template_namespace"], root_seed, family_name, "parameters")
    rng = np.random.default_rng(parameter_seed)
    params = _family_parameters(family, rng)
    name = family_name
    templates = split_spec["actual_templates"]
    template = templates[
        _derive_seed(split_spec["template_namespace"], root_seed, name, "template") % len(templates)
    ]

    measurement_trials = 500
    measurement_rng = np.random.default_rng(
        _derive_seed(split_spec["template_namespace"], root_seed, name, "measurement")
    )
    measurement_successes = int(measurement_rng.binomial(measurement_trials, params["measurement_validity"]))
    parser_successes = int(measurement_rng.binomial(measurement_trials, params["parser_validity"]))
    measurement = {
        "probe_successes": measurement_successes,
        "probe_total": measurement_trials,
        "probe_rate": measurement_successes / measurement_trials,
        "one_sided_95_lower": clopper_pearson_lower(measurement_successes, measurement_trials),
        "parser_valid_rate": parser_successes / measurement_trials,
        "contract_agreement": _kappa_record(params["contract_agreement"], n),
    }

    uptake_probability = params["uptake_probability"]
    true_effect = params["true_effect"]
    cell_effects: dict[str, float] = {
        "natural_language__conditional_likelihood": true_effect,
        "natural_language__constrained_generation": true_effect,
        "triples__conditional_likelihood": true_effect,
        "triples__constrained_generation": true_effect,
    }
    if name == "CorrelatedFormatShortcut":
        apparent = _uniform(rng, family["true_effect"]["apparent_effect_range"])
        cell_effects = {
            "natural_language__conditional_likelihood": apparent,
            "natural_language__constrained_generation": apparent,
            "triples__conditional_likelihood": 0.0,
            "triples__constrained_generation": 0.0,
        }
        uptake_probability = 0.05
        params["format_interaction"] = cell_effects["natural_language__conditional_likelihood"]
    elif name == "PartialUptakeNoComposition":
        uptake_probability = _uniform(rng, family["true_effect"]["direct_uptake_effect"])
    elif name == "ContractDependentPseudoEffect":
        cll = _uniform(rng, family["true_effect"]["one_contract_apparent_effect"])
        generation = _uniform(rng, family["true_effect"]["other_contract_effect"])
        cell_effects = {
            "natural_language__conditional_likelihood": cll,
            "triples__conditional_likelihood": cll,
            "natural_language__constrained_generation": generation,
            "triples__constrained_generation": generation,
        }
        uptake_probability = 0.92
    elif name == "EntityMappingLeakage":
        apparent = _uniform(rng, family["true_effect"]["apparent_effect_range"])
        cell_effects = {key: apparent for key in cell_effects}
        uptake_probability = _uniform(rng, family["parameter_range"]["counterbalanced_uptake_effect"])
    elif name == "StochasticParserFailure":
        failure = _uniform(rng, family["parameter_range"]["parser_failure_probability"])
        measurement_successes = int(measurement_rng.binomial(measurement_trials, 1 - failure))
        parser_successes = measurement_successes
        measurement["probe_successes"] = measurement_successes
        measurement["probe_rate"] = measurement_successes / measurement_trials
        measurement["one_sided_95_lower"] = clopper_pearson_lower(measurement_successes, measurement_trials)
        measurement["parser_valid_rate"] = parser_successes / measurement_trials
        uptake_probability = 0.95
    elif name == "MixedValidInvalidPopulation":
        uptake_probability = _uniform(rng, [0.55, 0.78])

    uptake_effect = _sample_effect(
        uptake_probability,
        n,
        _derive_seed(split_spec["template_namespace"], root_seed, name, "uptake"),
        _derive_seed(split_spec["template_namespace"], root_seed, name, "bootstrap_uptake"),
    )
    uptake = {
        "aggregate": uptake_effect,
        "cells": {"pooled_independent_uptake_cell": deepcopy(uptake_effect)},
    }

    cells: dict[str, dict[str, Any]] = {}
    for cell, probability in cell_effects.items():
        if name in {"CorrelatedFormatShortcut", "ContractDependentPseudoEffect"}:
            outcome_stream = f"potential_outcomes:{cell}"
        else:
            outcome_stream = "potential_outcomes:common_mode"
        cells[cell] = _sample_effect(
            probability,
            n,
            _derive_seed(split_spec["template_namespace"], root_seed, name, outcome_stream),
            _derive_seed(split_spec["template_namespace"], root_seed, name, f"bootstrap:{cell}"),
        )
    aggregate_estimate = mean(value["estimate"] for value in cells.values())
    aggregate_lower = mean(value["ci95"][0] for value in cells.values())
    aggregate_upper = mean(value["ci95"][1] for value in cells.values())
    downstream = {
        "aggregate": {
            "estimate": aggregate_estimate,
            "ci95": [aggregate_lower, aggregate_upper],
            "scene_clusters": n,
        },
        "cells": cells,
    }

    interaction = (
        mean(cells[key]["estimate"] for key in cells if key.startswith("natural_language"))
        - mean(cells[key]["estimate"] for key in cells if key.startswith("triples"))
    )
    if name not in {"CorrelatedFormatShortcut"}:
        interaction += params.get("format_interaction", 0.0)
    interaction_se = math.sqrt(max(1e-9, 2 * abs(aggregate_estimate) * (1 - abs(aggregate_estimate)) / max(n, 2)))
    interaction_ci90 = [interaction - 1.645 * interaction_se, interaction + 1.645 * interaction_se]
    tost = interaction_ci90[0] > -0.05 and interaction_ci90[1] < 0.05
    if name != "CorrelatedFormatShortcut":
        # These DGPs use common-mode format outcomes by construction.
        tost = abs(params.get("format_interaction", 0.0)) < 0.05
        interaction = params.get("format_interaction", 0.0)
        interaction_ci90 = [interaction, interaction]
    replication = {
        "equivalence": {"programmatic_fact_equivalence": True},
        "format_interactions": {
            "conditional_likelihood": interaction,
            "constrained_generation": interaction,
        },
        "format_tost": {
            "conditional_likelihood": {"tost_equivalent": tost},
            "constrained_generation": {"tost_equivalent": tost},
        },
        "format_interaction_ci90": {
            "conditional_likelihood": interaction_ci90,
            "constrained_generation": interaction_ci90,
        },
        "diagnostic_subtype": f"unseen_dgp:{name}",
    }
    metadata = {
        "family_parameters": params,
        "scene_seed": root_seed,
        "parameter_seed": parameter_seed,
        "template_namespace": split_spec["template_namespace"],
        "template_id": template["template_id"],
        "template_sha256": hashlib.sha256(template["text"].encode("utf-8")).hexdigest(),
        "shortcut_marker": split_spec["shortcut_markers"][_derive_seed(split_spec["template_namespace"], root_seed, name, "shortcut") % len(split_spec["shortcut_markers"])],
        "parser_corruption_pattern": split_spec["parser_corruption_patterns"][_derive_seed(split_spec["template_namespace"], root_seed, name, "parser_corruption") % len(split_spec["parser_corruption_patterns"])],
        "entity_id_permutation_seed": _derive_seed(split_spec["template_namespace"], root_seed, name, "entity_permutation"),
        "true_effect": true_effect,
    }
    return {
        "measurement": measurement,
        "uptake": uptake,
        "downstream": downstream,
        "replication": replication,
    }, metadata


def _policy_from_registry(registry: dict[str, Any], overrides: dict[str, float] | None = None) -> dict[str, Any]:
    thresholds = registry["primary_thresholds"]
    policy = load_yaml("configs/audit_policy.yaml")
    policy.update(
        {
            "measurement_validity_cutoff": thresholds["measurement_lower"],
            "gate_cutoff": thresholds["uptake_lower"],
            "sesoi": thresholds["effect_SESOI"],
            "contract_kappa_cutoff": thresholds["contract_kappa"],
            "contract_kappa_lower_bound_cutoff": thresholds["contract_kappa_lower"],
            "equivalence_margin": thresholds["format_equivalence_margin"],
        }
    )
    if overrides:
        policy.update(overrides)
    return policy


def _summarize(rows: list[dict[str, Any]], n: int) -> dict[str, Any]:
    subset = [row for row in rows if row["sample_size"] == n]
    valid = [row for row in subset if row["expected_claim_class"] == VALID_CLASS]
    invalid = [row for row in subset if row["family"] in INVALID_FAMILIES]
    significant = [row for row in valid if row["effect_ci95"][0] > 0]
    mixed = [row for row in subset if row["family"] == "MixedValidInvalidPopulation"]
    by_family = {}
    for family in sorted({row["family"] for row in subset}):
        family_rows = [row for row in subset if row["family"] == family]
        by_family[family] = {
            "count": len(family_rows),
            "expected_claim_class": family_rows[0]["expected_claim_class"],
            "exact_class_accuracy": sum(row["decision"] == row["expected_claim_class"] for row in family_rows) / len(family_rows),
            "valid_behavioral_effect_rate": sum(row["decision"] == VALID_CLASS for row in family_rows) / len(family_rows),
            "inconclusive_rate": sum(row["decision"] == "INCONCLUSIVE" for row in family_rows) / len(family_rows),
        }
    fmcr = sum(row["decision"] == VALID_CLASS for row in invalid) / len(invalid)
    valid_family_rates = [
        metrics["valid_behavioral_effect_rate"]
        for metrics in by_family.values()
        if metrics["expected_claim_class"] == VALID_CLASS
    ]
    non_strong_names = {
        "ValidModerateEffect",
        "ValidBoundaryEffect",
        "ValidStochasticUptake",
        "ValidNoisyButMeasured",
        "ValidHeterogeneousScenes",
    }
    non_strong_rates = [by_family[name]["valid_behavioral_effect_rate"] for name in non_strong_names]
    return {
        "sample_size": n,
        "dataset_count": len(subset),
        "known_valid_sensitivity": mean(valid_family_rates),
        "non_strong_macro_sensitivity": mean(non_strong_rates),
        "non_strong_families_at_or_above_0_80": sum(rate >= 0.80 for rate in non_strong_rates),
        "valid_boundary_effect_sensitivity": by_family["ValidBoundaryEffect"]["valid_behavioral_effect_rate"],
        "known_invalid_specificity": 1 - fmcr,
        "fmcr": fmcr,
        "coverage": sum(row["effect_ci95"][0] <= row["true_effect"] <= row["effect_ci95"][1] for row in valid) / len(valid),
        "type_s": sum(row["effect_estimate"] < 0 for row in significant) / max(1, len(significant)),
        "type_m": mean(abs(row["effect_estimate"]) / row["true_effect"] for row in significant),
        "abstention": sum(row["decision"] == "INCONCLUSIVE" for row in subset) / len(subset),
        "partial_identification_accuracy": sum(row["decision"] == "PARTIALLY_IDENTIFIED" for row in mixed) / len(mixed),
        "exact_expected_class_accuracy": sum(row["decision"] == row["expected_claim_class"] for row in subset) / len(subset),
        "by_family": by_family,
    }


def _passes_loop_a(metrics: dict[str, Any]) -> bool:
    return (
        metrics["known_valid_sensitivity"] >= 0.80
        and metrics["known_invalid_specificity"] >= 0.95
        and metrics["fmcr"] <= 0.05
        and metrics["coverage"] >= 0.90
        and metrics["type_s"] <= 0.05
        and metrics["abstention"] <= 0.40
    )


def _threshold_stability(
    observable_rows: list[dict[str, Any]],
    registry: dict[str, Any],
    sample_size: int,
) -> dict[str, Any]:
    grid = registry["diagnostic_threshold_grid"]
    summaries = []
    for uptake in grid["uptake_lower"]:
        for measurement in grid["measurement_lower"]:
            for kappa in grid["contract_kappa"]:
                for margin in grid["format_equivalence_margin"]:
                    decisions = []
                    policy = _policy_from_registry(
                        registry,
                        {
                            "gate_cutoff": float(uptake),
                            "measurement_validity_cutoff": float(measurement),
                            "contract_kappa_cutoff": float(kappa),
                            "format_materiality": float(margin),
                        },
                    )
                    for row in observable_rows:
                        if row["sample_size"] != sample_size:
                            continue
                        inputs = deepcopy(row["a0_inputs"])
                        for contract, ci90 in inputs["replication"]["format_interaction_ci90"].items():
                            inputs["replication"]["format_tost"][contract]["tost_equivalent"] = (
                                ci90[0] > -float(margin) and ci90[1] < float(margin)
                            )
                        decision = audit_claim(
                            inputs["measurement"], inputs["uptake"], inputs["downstream"], inputs["replication"], policy
                        )
                        decisions.append(
                            {
                                "family": row["family"],
                                "sample_size": row["sample_size"],
                                "expected_claim_class": row["expected_claim_class"],
                                "decision": decision.decision,
                                "true_effect": row["true_effect"],
                                "effect_estimate": decision.effect_size,
                                "effect_ci95": decision.confidence_interval,
                            }
                        )
                    summary = _summarize(decisions, sample_size)
                    summaries.append(
                        {
                            "uptake_lower": uptake,
                            "measurement_lower": measurement,
                            "contract_kappa": kappa,
                            "format_margin": margin,
                            "passes_loop_a": _passes_loop_a(summary),
                            "sensitivity": summary["known_valid_sensitivity"],
                            "specificity": summary["known_invalid_specificity"],
                            "fmcr": summary["fmcr"],
                            "abstention": summary["abstention"],
                        }
                    )
    return {
        "grid_count": len(summaries),
        "all_grid_cells_retain_go": all(row["passes_loop_a"] for row in summaries),
        "go_fraction": sum(row["passes_loop_a"] for row in summaries) / len(summaries),
        "minimum_sensitivity": min(row["sensitivity"] for row in summaries),
        "minimum_specificity": min(row["specificity"] for row in summaries),
        "maximum_fmcr": max(row["fmcr"] for row in summaries),
        "maximum_abstention": max(row["abstention"] for row in summaries),
        "rows": summaries,
    }


def _run_split(split: str, method_name: str = "A0") -> dict[str, Any]:
    registry = load_yaml("research/preregistration/loop_a_dgp_registry.yaml")
    protocol = load_yaml("research/preregistration/tier0_5_three_loop.yaml")
    if method_name != "A0":
        raise NotImplementedError("AuditV2 is not frozen")
    split_spec = registry[split]
    templates = load_yaml("research/preregistration/loop_a_templates.yaml")
    split_spec = {**split_spec, "actual_templates": templates[split]}
    repetitions = int(registry["repetitions_per_family_size_split"])
    policy = _policy_from_registry(registry)
    config_hash = canonical_hash({"registry": registry, "protocol": protocol, "method": method_name})
    rows: list[dict[str, Any]] = []
    observable_rows: list[dict[str, Any]] = []
    seed_base = 51000 if split == "development" else 91000
    for n in registry["sample_sizes"]:
        for family in registry["families"]:
            for repetition in range(repetitions):
                root_seed = seed_base + repetition
                inputs, metadata = _simulate_a0_inputs(family, int(n), root_seed, split_spec)
                decision = audit_claim(
                    inputs["measurement"], inputs["uptake"], inputs["downstream"], inputs["replication"], policy
                )
                row = {
                    "split": f"tier0_5_{split}",
                    "method": method_name,
                    "family": family["family"],
                    "family_index": family["family_index"],
                    "sample_size": int(n),
                    "repetition": repetition,
                    "scene_seed": root_seed,
                    "system_parameter_seed": split_spec["parameter_seed_range"][0] + repetition,
                    "template_namespace": metadata["template_namespace"],
                    "template_id": metadata["template_id"],
                    "template_sha256": metadata["template_sha256"],
                    "shortcut_marker": metadata["shortcut_marker"],
                    "parser_corruption_pattern": metadata["parser_corruption_pattern"],
                    "entity_id_permutation_seed": metadata["entity_id_permutation_seed"],
                    "expected_claim_class": family["expected_claim_class"],
                    "allowed_identification_status": family["allowed_identification_status"],
                    "decision": decision.decision,
                    "identification_status": decision.identification_status,
                    "scope_flags": decision.scope_flags,
                    "true_effect": metadata["true_effect"],
                    "effect_estimate": decision.effect_size,
                    "effect_ci95": decision.confidence_interval,
                    "passed_gates": decision.passed_gates,
                    "failed_gates": decision.failed_gates,
                    "config_hash": config_hash,
                }
                rows.append(row)
                observable_rows.append({**row, "a0_inputs": inputs})

    curve = [_summarize(rows, int(n)) for n in registry["sample_sizes"]]
    resolved = next((row for row in curve if row["sample_size"] <= 192 and _passes_loop_a(row)), None)
    sensitivity_at_384 = next(row["known_valid_sensitivity"] for row in curve if row["sample_size"] == 384)
    if resolved:
        diagnostic = "LOOP_A_POWER_RESOLVED"
        selected_n = resolved["sample_size"]
        repair_eligible = False
    elif sensitivity_at_384 < 0.80:
        diagnostic = "LOOP_A_POWER_ONLY_FAIL_REPAIR_ELIGIBLE"
        selected_n = 384
        repair_eligible = True
    else:
        diagnostic = "LOOP_A_POWER_INCONCLUSIVE_AT_N384"
        selected_n = 384
        repair_eligible = False
    threshold = _threshold_stability(observable_rows, registry, int(selected_n))
    output_dir = Path(f"artifacts/loop_a/{split}")
    output_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(output_dir / "dataset_results.jsonl", rows)
    report = {
        "schema_version": 1,
        "split": f"tier0_5_{split}",
        "method": method_name,
        "method_source_commit": "aad52b0b8d714a03056a8f1ff561606519a765d3",
        "execution_head": _git_head(),
        "config_hash": config_hash,
        "family_count": len(registry["families"]),
        "repetitions_per_family_size": repetitions,
        "sample_size_curve": curve,
        "power_diagnostic": diagnostic,
        "selected_sample_size_for_holdout": selected_n,
        "repair_eligible": repair_eligible,
        "threshold_stability": threshold,
        "holdout_execution_count": 1 if split == "holdout" else 0,
    }
    dump_yaml(output_dir / "summary.yaml", report)
    return report


def run_loop_a_development() -> dict[str, Any]:
    if Path("artifacts/loop_a/holdout/summary.yaml").exists():
        raise RuntimeError("Holdout already exists; development may not be rerun")
    reproduce_a0_baseline()
    return _run_split("development", "A0")


def run_loop_a_holdout() -> dict[str, Any]:
    holdout_path = Path("artifacts/loop_a/holdout/summary.yaml")
    if holdout_path.exists():
        raise RuntimeError("Loop A holdout execution limit is one; result already exists")
    freeze = load_yaml("research/preregistration/loop_a_method_freeze.yaml")
    if freeze["holdout_authorized"] is not True:
        raise RuntimeError("Method freeze does not authorize holdout")
    if freeze["method"] != "A0":
        raise NotImplementedError("AuditV2 holdout runner is not implemented")
    return _run_split("holdout", freeze["method"])
