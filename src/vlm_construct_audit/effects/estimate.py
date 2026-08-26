"""Intersection effect gate and conservative E5 bounds."""

from __future__ import annotations

from typing import Any


def effect_gate(downstream_results: dict[str, Any], sesoi: float) -> dict[str, Any]:
    cells = downstream_results["cells"]
    passed_cells = {
        name: value["ci95"][0] is not None and value["ci95"][0] > sesoi
        for name, value in cells.items()
    }
    return {
        "passed": all(passed_cells.values()),
        "passed_cells": passed_cells,
        "sesoi": sesoi,
        "aggregate_effect": downstream_results["aggregate"]["estimate"],
        "aggregate_ci95": downstream_results["aggregate"]["ci95"],
    }


def latent_uptake_bounds() -> dict[str, Any]:
    return {
        "estimand": "E5_always_uptake_principal_stratum_effect",
        "principal_stratum": "U_star_1_equals_1_and_U_star_0_equals_1",
        "bounds": [-1.0, 1.0],
        "outcome_support": [0, 1],
        "identification_status": "PARTIALLY_IDENTIFIED",
        "monotonicity": "not_assumed",
        "observed_uptake_filtering": False,
    }

