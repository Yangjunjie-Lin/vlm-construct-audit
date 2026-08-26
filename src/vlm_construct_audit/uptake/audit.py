"""Evaluate cell-level uptake without sample-level filtering."""

from __future__ import annotations

from typing import Any


def uptake_gate(uptake_results: dict[str, Any], cutoff: float) -> dict[str, Any]:
    aggregate = uptake_results["aggregate"]
    lower = aggregate["ci95"][0]
    passed = lower is not None and lower >= cutoff
    return {
        "passed": passed,
        "rule": "one_sided_lower_bound_at_or_above_cutoff",
        "cutoff": cutoff,
        "effect": aggregate["estimate"],
        "lower_bound": lower,
        "sample_level_filtering_used": False,
    }

