"""Primary Tier-0 statistics with scene as the resampling unit."""

from __future__ import annotations

import math
import random
from collections import Counter, defaultdict
from statistics import mean
from typing import Any

from scipy.stats import beta

from ..utils import dump_yaml, load_yaml, read_jsonl


PRIMARY_CORRUPTIONS = ("relation_flip", "entity_swap", "attribute_swap")


def percentile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("No values")
    position = (len(ordered) - 1) * q
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (position - lower) * (ordered[upper] - ordered[lower])


def cluster_paired_effect(
    rows: list[dict[str, Any]],
    corruptions: tuple[str, ...] = PRIMARY_CORRUPTIONS,
    bootstrap_replicates: int = 2000,
    seed: int = 20260826,
) -> dict[str, Any]:
    by_scene: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for row in rows:
        by_scene[row["scene_id"]][row["condition"]].append(float(row["score"]))
    differences = []
    for scene_id, conditions in sorted(by_scene.items()):
        if "correct_evidence" not in conditions or any(c not in conditions for c in corruptions):
            continue
        correct = mean(conditions["correct_evidence"])
        corrupted = mean(mean(conditions[c]) for c in corruptions)
        differences.append((scene_id, correct - corrupted))
    if not differences:
        return {"estimate": None, "ci95": [None, None], "scene_clusters": 0}
    estimate = mean(value for _, value in differences)
    rng = random.Random(seed)
    values = [value for _, value in differences]
    boot = [mean(rng.choices(values, k=len(values))) for _ in range(bootstrap_replicates)]
    return {
        "estimate": estimate,
        "ci95": [percentile(boot, 0.025), percentile(boot, 0.975)],
        "scene_clusters": len(values),
        "bootstrap_replicates": bootstrap_replicates,
        "resampling_unit": "scene_id",
    }


def clopper_pearson_lower(successes: int, total: int, alpha: float = 0.05) -> float:
    if total <= 0:
        return 0.0
    if successes == 0:
        return 0.0
    return float(beta.ppf(alpha, successes, total - successes + 1))


def cohens_kappa(left: list[str], right: list[str]) -> float | None:
    if len(left) != len(right) or not left:
        return None
    observed = sum(a == b for a, b in zip(left, right, strict=True)) / len(left)
    left_counts, right_counts = Counter(left), Counter(right)
    labels = set(left_counts) | set(right_counts)
    expected = sum((left_counts[label] / len(left)) * (right_counts[label] / len(right)) for label in labels)
    if math.isclose(expected, 1.0):
        return 1.0 if math.isclose(observed, 1.0) else None
    return (observed - expected) / (1 - expected)


def contract_agreement(rows: list[dict[str, Any]], bootstrap_replicates: int = 1000) -> dict[str, Any]:
    pairs: dict[tuple[str, str, str], dict[str, str]] = defaultdict(dict)
    for row in rows:
        value = row["parsed_response"] if row["parsed_response"] is not None else "__PARSER_FAILURE__"
        pairs[(row["scene_id"], row["condition"], row["serialization"])][row["contract"]] = value
    complete = [(key, pair) for key, pair in pairs.items() if len(pair) == 2]
    left = [pair["conditional_likelihood"] for _, pair in complete]
    right = [pair["constrained_generation"] for _, pair in complete]
    estimate = cohens_kappa(left, right)
    scenes = sorted({key[0] for key, _ in complete})
    rng = random.Random(20260826)
    boot = []
    by_scene = defaultdict(list)
    for key, pair in complete:
        by_scene[key[0]].append(pair)
    for _ in range(bootstrap_replicates):
        sampled = rng.choices(scenes, k=len(scenes))
        sample_pairs = [pair for scene in sampled for pair in by_scene[scene]]
        value = cohens_kappa(
            [pair["conditional_likelihood"] for pair in sample_pairs],
            [pair["constrained_generation"] for pair in sample_pairs],
        )
        if value is not None:
            boot.append(value)
    return {
        "kappa": estimate,
        "ci95": [percentile(boot, 0.025), percentile(boot, 0.975)] if boot else [None, None],
        "pair_count": len(complete),
        "basis": "semantic_answer_parser_failures_as_disagreement",
        "interpretation": "elicitation_plus_measurement_response_contract_robustness",
    }


def _effect_grid(rows: list[dict[str, Any]], split: str, corruptions: tuple[str, ...]) -> dict[str, Any]:
    grid = {}
    for serialization in ("natural_language", "triples"):
        for contract in ("conditional_likelihood", "constrained_generation"):
            subset = [
                row for row in rows
                if row["split"] == split and row["serialization"] == serialization and row["contract"] == contract
            ]
            grid[f"{serialization}__{contract}"] = cluster_paired_effect(subset, corruptions)
    return grid


def analyze_predictions() -> dict[str, Any]:
    predictions = read_jsonl("artifacts/predictions/calibration_predictions.jsonl")
    probes = read_jsonl("artifacts/metrics/measurement_probes.jsonl")
    policy = load_yaml("configs/audit_policy.yaml")
    systems = sorted({row["model_id"] for row in predictions})
    analysis: dict[str, Any] = {"schema_version": 1, "systems": {}}
    for system in systems:
        rows = [row for row in predictions if row["model_id"] == system]
        system_probes = [row for row in probes if row["system"] == system]
        successes = sum(bool(row["mapping_probe_pass"]) for row in system_probes)
        agreement = contract_agreement(rows)
        uptake_grid = _effect_grid(rows, "uptake_validation", ("attribute_swap",))
        downstream_grid = _effect_grid(rows, "reasoning_test", PRIMARY_CORRUPTIONS)
        aggregate_uptake = cluster_paired_effect(
            [row for row in rows if row["split"] == "uptake_validation"], ("attribute_swap",)
        )
        aggregate_downstream = cluster_paired_effect(
            [row for row in rows if row["split"] == "reasoning_test"], PRIMARY_CORRUPTIONS
        )
        format_interactions = {}
        for contract in ("conditional_likelihood", "constrained_generation"):
            nl = downstream_grid[f"natural_language__{contract}"]["estimate"]
            triples = downstream_grid[f"triples__{contract}"]["estimate"]
            format_interactions[contract] = None if nl is None or triples is None else nl - triples
        parser_valid = sum(row["parser_status"] in {"ok", "not_applicable_likelihood"} for row in rows) / len(rows)
        subtypes = Counter(row["diagnostic_subtype"] for row in rows)
        analysis["systems"][system] = {
            "measurement": {
                "probe_successes": successes,
                "probe_total": len(system_probes),
                "probe_rate": successes / len(system_probes),
                "one_sided_95_lower": clopper_pearson_lower(successes, len(system_probes)),
                "independence_assumption": "unique probe cases treated as Bernoulli units; deterministic dependence remains a limitation",
                "parser_valid_rate": parser_valid,
                "contract_agreement": agreement,
            },
            "uptake": {"aggregate": aggregate_uptake, "cells": uptake_grid},
            "downstream": {"aggregate": aggregate_downstream, "cells": downstream_grid},
            "format_interaction": format_interactions,
            "diagnostic_subtype": subtypes.most_common(1)[0][0],
            "policy_snapshot": policy,
        }
    dump_yaml("artifacts/metrics/analysis_results.yaml", analysis)
    return analysis
