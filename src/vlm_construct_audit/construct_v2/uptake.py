"""Task-specific uptake design and future analysis gates."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

import numpy as np
from scipy.stats import beta

from .generator import CARDINALS, UPTAKE_TASKS


def exact_lower(successes: int, n: int, alpha: float = 0.05) -> float:
    return 0.0 if successes == 0 else float(beta.ppf(alpha, successes, n - successes + 1))


def exact_upper(successes: int, n: int, alpha: float = 0.05) -> float:
    return 1.0 if successes == n else float(beta.ppf(1 - alpha, successes + 1, n - successes))


def validate_uptake_design(rows: list[dict[str, Any]]) -> dict[str, Any]:
    task_counts = Counter(row["uptake_task"] for row in rows)
    answer_counts = Counter((row["uptake_task"], row["answer"]["semantic"]) for row in rows)
    position_counts = Counter(
        (row["uptake_task"], row["answer"]["correct_option_position"]) for row in rows
    )
    task_gates = {}
    for task in UPTAKE_TASKS:
        task_gates[task] = {
            "scene_count_64": task_counts[task] == 64,
            "answer_classes_exact_16_each": all(answer_counts[(task, answer)] == 16 for answer in CARDINALS),
            "option_positions_exact_16_each": all(position_counts[(task, position)] == 16 for position in range(4)),
            "matched_irrelevant_control_present": all(
                row["negative_control"]["matched"]
                and row["evidence"].get("matched_irrelevant")
                and row["image"].get("irrelevant_control_path")
                for row in rows
                if row["uptake_task"] == task
            ),
        }
    passed = len(rows) == 256 and all(
        all(gates.values()) for gates in task_gates.values()
    )
    return {
        "scene_count": len(rows),
        "task_counts": dict(task_counts),
        "answer_counts": {
            task: {answer: answer_counts[(task, answer)] for answer in CARDINALS}
            for task in UPTAKE_TASKS
        },
        "position_counts": {
            task: {position: position_counts[(task, position)] for position in range(4)}
            for task in UPTAKE_TASKS
        },
        "task_gates": task_gates,
        "status": "PASS" if passed else "CONSTRUCT_V2_AUTOMATED_NO_GO",
    }


def _paired_bootstrap_lower(
    relevant: np.ndarray,
    irrelevant: np.ndarray,
    *,
    resamples: int = 10_000,
    seed: int = 862501,
) -> float:
    rng = np.random.default_rng(seed)
    differences = relevant.astype(float) - irrelevant.astype(float)
    indices = rng.integers(0, len(differences), size=(resamples, len(differences)))
    estimates = differences[indices].mean(axis=1)
    return float(np.quantile(estimates, 0.05, method="lower"))


def evaluate_uptake_outputs(predictions: list[dict[str, Any]]) -> dict[str, Any]:
    """Evaluate future outputs; this function does not load or run a model."""

    cells: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in predictions:
        key = (row["model_family"], row["serialization"], row["uptake_task"])
        cells[key].append(row)
    results = {}
    for (model, serialization, task), cell in sorted(cells.items()):
        if len(cell) != 64:
            raise ValueError(f"uptake cell {model}/{serialization}/{task} must contain 64 scenes")
        relevant = np.asarray([bool(row["relevant_correct"]) for row in cell])
        irrelevant = np.asarray([bool(row["irrelevant_correct"]) for row in cell])
        relevant_successes = int(relevant.sum())
        irrelevant_successes = int(irrelevant.sum())
        lower = exact_lower(relevant_successes, len(cell))
        upper = exact_upper(irrelevant_successes, len(cell))
        utility = float((relevant.astype(float) - irrelevant.astype(float)).mean())
        utility_lower = _paired_bootstrap_lower(relevant, irrelevant)
        gates = {
            "direct_accuracy_exact_lower_ge_0_80": lower >= 0.80,
            "irrelevant_accuracy_exact_upper_le_0_40": upper <= 0.40,
            "paired_utility_ge_0_20": utility >= 0.20,
            "paired_utility_lower_ge_0_20": utility_lower >= 0.20,
        }
        key = f"{model}::{serialization}::{task}"
        results[key] = {
            "model_family": model,
            "serialization": serialization,
            "uptake_task": task,
            "n": len(cell),
            "correct_evidence_accuracy": relevant_successes / len(cell),
            "correct_evidence_one_sided_95_exact_lower": lower,
            "irrelevant_evidence_accuracy": irrelevant_successes / len(cell),
            "irrelevant_evidence_one_sided_95_exact_upper": upper,
            "paired_evidence_utility": utility,
            "paired_evidence_utility_one_sided_95_bootstrap_lower": utility_lower,
            "gates": gates,
            "status": "PASS" if all(gates.values()) else "INVALID_INTERVENTION",
        }

    eligibility = {}
    model_serializations = sorted({(row["model_family"], row["serialization"]) for row in predictions})
    for model, serialization in model_serializations:
        required = [results[f"{model}::{serialization}::{task}"]["status"] for task in UPTAKE_TASKS]
        eligibility[f"{model}::{serialization}"] = {
            "required_task_statuses": dict(zip(UPTAKE_TASKS, required, strict=True)),
            "eligible": all(status == "PASS" for status in required),
            "cross_task_averaging_used": False,
        }
    return {
        "unit": "model_x_serialization_x_uptake_task",
        "cells": results,
        "reasoning_eligibility": eligibility,
        "status": (
            "PASS"
            if eligibility and all(item["eligible"] for item in eligibility.values())
            else "INVALID_INTERVENTION"
        ),
    }

