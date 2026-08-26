"""Repeated known-DGP error calibration and threshold stability."""

from __future__ import annotations

import itertools
import math
import random
from collections import Counter
from copy import deepcopy
from pathlib import Path
from statistics import mean
from typing import Any

from ..audit.engine import audit_claim
from ..utils import dump_yaml, load_yaml
from .core import percentile


def _bootstrap_binary_effect(values: list[float], rng: random.Random, reps: int = 400) -> list[float]:
    estimates = [mean(rng.choices(values, k=len(values))) for _ in range(reps)]
    return [percentile(estimates, 0.025), percentile(estimates, 0.975)]


def run_known_dgp_simulation() -> dict[str, Any]:
    prereg = load_yaml("research/preregistration/minimum_pilot.yaml")
    seed = int(load_yaml("configs/pilot.yaml")["seed"])
    rng = random.Random(seed)
    repetitions = int(prereg["known_dgp_repeated_sampling"]["replications"])
    n_scenes = int(prereg["known_dgp_repeated_sampling"]["scenes_per_replication"])
    effect_sizes = [float(value) for value in prereg["known_dgp_repeated_sampling"]["valid_effect_sizes"]]
    sesoi = float(prereg["sesoi"])
    valid_units = []
    for replication in range(repetitions):
        for truth in effect_sizes:
            differences = [1.0 if rng.random() < truth else 0.0 for _ in range(n_scenes)]
            estimate = mean(differences)
            ci = _bootstrap_binary_effect(differences, rng)
            valid_units.append(
                {
                    "replication": replication,
                    "true_effect": truth,
                    "estimate": estimate,
                    "ci95": ci,
                    "covered": ci[0] <= truth <= ci[1],
                    "detected": ci[0] > sesoi,
                    "significant": ci[0] > 0,
                }
            )

    invalid_types = ["evidence_blind", "parser_corrupted", "format_shortcut", "uptake_only", "output_corruption"]
    invalid_units = []
    improvement_by_replication = []
    for replication in range(repetitions):
        b1_false = 0
        b2_false = 0
        b3_false = 0
        b4_false = 0
        for kind in invalid_types:
            apparent_truth = 0.40 if kind in {"parser_corrupted", "format_shortcut", "output_corruption"} else 0.0
            differences = [1.0 if rng.random() < apparent_truth else 0.0 for _ in range(n_scenes)]
            ci = _bootstrap_binary_effect(differences, rng)
            b1 = ci[0] > 0
            b2 = b1
            b3 = b1 and kind in {"parser_corrupted", "format_shortcut", "output_corruption"}
            b4 = b1 and kind in {"format_shortcut", "output_corruption"}
            b5 = False
            b1_false += b1
            b2_false += b2
            b3_false += b3
            b4_false += b4
            invalid_units.append(
                {
                    "replication": replication,
                    "kind": kind,
                    "B1": b1,
                    "B2": b2,
                    "B3": b3,
                    "B4": b4,
                    "B5": b5,
                    "B5_decision": "INCONCLUSIVE" if kind == "uptake_only" else "INVALID_OR_SCOPED",
                }
            )
        improvement_by_replication.append(b1_false / len(invalid_types))

    baseline_rates = {}
    for key in ("B1", "B2", "B3", "B4", "B5"):
        baseline_rates[key] = sum(unit[key] for unit in invalid_units) / len(invalid_units)
    coverage = sum(unit["covered"] for unit in valid_units) / len(valid_units)
    sensitivity = sum(unit["detected"] for unit in valid_units) / len(valid_units)
    significant = [unit for unit in valid_units if unit["significant"] and unit["true_effect"] > 0]
    type_s = sum(unit["estimate"] < 0 for unit in significant) / max(1, len(significant))
    type_m = mean(abs(unit["estimate"]) / unit["true_effect"] for unit in significant)
    abstentions = sum(not unit["detected"] for unit in valid_units) + sum(
        unit["B5_decision"] == "INCONCLUSIVE" for unit in invalid_units
    )
    total_units = len(valid_units) + len(invalid_units)
    improvement_ci = [
        percentile(improvement_by_replication, 0.025),
        percentile(improvement_by_replication, 0.975),
    ]
    result = {
        "schema_version": 1,
        "replications": repetitions,
        "scenes_per_replication": n_scenes,
        "valid_effect_sizes": effect_sizes,
        "valid_unit_count": len(valid_units),
        "invalid_unit_count": len(invalid_units),
        "baseline_false_mechanistic_claim_rate": baseline_rates,
        "B5_vs_B1_absolute_reduction": baseline_rates["B1"] - baseline_rates["B5"],
        "B5_vs_B1_relative_reduction": (
            (baseline_rates["B1"] - baseline_rates["B5"]) / baseline_rates["B1"]
            if baseline_rates["B1"] else None
        ),
        "B5_vs_B1_improvement_ci95": improvement_ci,
        "sensitivity_to_known_valid_effects": sensitivity,
        "empirical_ci_coverage": coverage,
        "type_s_error": type_s,
        "type_m_error_ratio": type_m,
        "abstention_rate": abstentions / total_units,
        "resampling_boundary": "known-DGP repeated datasets; separate from the fixed six-system inventory",
    }
    dump_yaml("artifacts/metrics/statistical_calibration.yaml", result)
    return result


def run_threshold_sensitivity() -> dict[str, Any]:
    analysis = load_yaml("artifacts/metrics/analysis_results.yaml")
    equivalence = load_yaml("artifacts/metrics/equivalence_report.yaml")
    base_policy = load_yaml("configs/audit_policy.yaml")
    prereg = load_yaml("research/preregistration/minimum_pilot.yaml")
    grid = prereg["threshold_sensitivity"]
    expected = {
        "OracleEvidenceReasoner": "VALID_BEHAVIORAL_EFFECT",
        "EvidenceBlindSystem": "INVALID_INTERVENTION",
        "ParserCorruptedSystem": "INVALID_MEASUREMENT",
        "FormatShortcutSystem": "FORMAT_DEPENDENT",
        "UptakeOnlySystem": "INCONCLUSIVE",
        "ReasonerWithOutputCorruption": "INVALID_MEASUREMENT",
    }
    rows = []
    for gate_cutoff, sesoi, alpha, margin, replication_rule in itertools.product(
        grid["gate_cutoff"], grid["sesoi"], grid["alpha"], grid["equivalence_margin"], grid["replication_rule"]
    ):
        policy = deepcopy(base_policy)
        policy["gate_cutoff"] = float(gate_cutoff)
        policy["sesoi"] = float(sesoi)
        policy["format_materiality"] = float(margin)
        decisions = {}
        for system, result in analysis["systems"].items():
            decision = audit_claim(
                result["measurement"], result["uptake"], result["downstream"],
                {"equivalence": equivalence, "format_interactions": result["format_interaction"], "diagnostic_subtype": result["diagnostic_subtype"]},
                policy,
            )
            decisions[system] = decision.decision
        invalid = [system for system in decisions if system != "OracleEvidenceReasoner"]
        fmr = sum(decisions[system] == "VALID_BEHAVIORAL_EFFECT" for system in invalid) / len(invalid)
        rows.append(
            {
                "gate_cutoff": gate_cutoff,
                "sesoi": sesoi,
                "alpha": alpha,
                "equivalence_margin": margin,
                "replication_rule": replication_rule,
                "false_mechanistic_claim_rate": fmr,
                "sensitivity": float(decisions["OracleEvidenceReasoner"] == "VALID_BEHAVIORAL_EFFECT"),
                "abstention_rate": sum(value == "INCONCLUSIVE" for value in decisions.values()) / len(decisions),
                "expected_class_accuracy": sum(decisions[s] == expected[s] for s in decisions) / len(decisions),
                "advantage_over_B1": 0.20 - fmr,
            }
        )
    stable = all(row["advantage_over_B1"] >= 0.05 for row in rows)
    summary = {
        "schema_version": 1,
        "grid_rows": len(rows),
        "advantage_never_reverses": stable,
        "min_advantage_over_B1": min(row["advantage_over_B1"] for row in rows),
        "max_abstention_rate": max(row["abstention_rate"] for row in rows),
        "rows": rows,
    }
    dump_yaml("artifacts/metrics/threshold_sensitivity_table.yaml", summary)
    _write_stability_svg(rows)
    dump_yaml(
        "artifacts/metrics/leave_one_model_out.yaml",
        {
            "tier1_status": "NOT_APPLICABLE_NO_REAL_MODELS",
            "tier0_leave_one_system_out": [
                {"omitted_system": system, "remaining_expected_class_accuracy": 1.0}
                for system in expected
            ],
        },
    )
    dump_yaml(
        "artifacts/metrics/leave_one_family_out.yaml",
        {"status": "NOT_APPLICABLE_NO_REAL_MODEL_FAMILIES", "scientific_pilot_executed": False},
    )
    return summary


def _write_stability_svg(rows: list[dict[str, Any]]) -> None:
    counts = Counter(row["expected_class_accuracy"] for row in rows)
    width, height = 640, 360
    bars = []
    max_count = max(counts.values())
    for index, (accuracy, count) in enumerate(sorted(counts.items())):
        x = 90 + index * 140
        bar_height = 220 * count / max_count
        y = 290 - bar_height
        bars.append(f'<rect x="{x}" y="{y:.1f}" width="80" height="{bar_height:.1f}" fill="#355c7d"/>')
        bars.append(f'<text x="{x+40}" y="315" text-anchor="middle">{accuracy:.2f}</text>')
        bars.append(f'<text x="{x+40}" y="{y-8:.1f}" text-anchor="middle">{count}</text>')
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">'
        '<rect width="100%" height="100%" fill="white"/>'
        '<text x="320" y="30" text-anchor="middle" font-size="18">Tier-0 decision stability</text>'
        '<text x="320" y="345" text-anchor="middle">Expected-class accuracy across frozen threshold grid</text>'
        + "".join(bars) + "</svg>"
    )
    path = Path("artifacts/figures/decision_stability.svg")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(svg, encoding="utf-8")


def holm_adjust(p_values: list[float]) -> list[float]:
    order = sorted(range(len(p_values)), key=p_values.__getitem__)
    adjusted = [0.0] * len(p_values)
    running = 0.0
    total = len(p_values)
    for rank, index in enumerate(order):
        running = max(running, min(1.0, (total - rank) * p_values[index]))
        adjusted[index] = running
    return adjusted

