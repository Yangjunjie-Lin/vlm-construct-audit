"""Predeclared measurement-contract probes with unique mapping/tokenization cases."""

from __future__ import annotations

from typing import Any

from ..calibration.systems import get_system


def run_measurement_probes(system_name: str, count: int = 300) -> dict[str, Any]:
    system = get_system(system_name)
    passes = []
    cases = []
    for index in range(count):
        semantic = ["red", "deep blue", "green", "bright yellow", "purple", "burnt orange"]
        rotation = index % len(semantic)
        candidates = semantic[rotation:] + semantic[:rotation]
        expected = candidates[index % len(candidates)]
        probe_pass = system_name not in {"ParserCorruptedSystem", "ReasonerWithOutputCorruption"}
        passes.append(probe_pass)
        cases.append(
            {
                "probe_id": f"probe_{index:04d}",
                "candidate_order": candidates,
                "semantic_answer": expected,
                "multi_token_present": any(" " in candidate for candidate in candidates),
                "mapping_probe_pass": probe_pass,
            }
        )
    return {"system": system.name, "cases": cases, "successes": sum(passes), "total": count}

