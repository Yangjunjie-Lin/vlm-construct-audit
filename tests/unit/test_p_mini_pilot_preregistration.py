from __future__ import annotations

import json
from pathlib import Path

import yaml

from vlm_construct_audit.preregistration import verify_no_p_mini_pilot_inference

ROOT = Path(__file__).resolve().parents[2]


def _jsonl(path: str) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in (ROOT / path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_formal_scene_inventory_is_frozen_and_disjoint() -> None:
    scenes = _jsonl("data/p_mini_pilot/scenes.jsonl")
    uptake = _jsonl("data/p_mini_pilot/uptake_validation.jsonl")
    reasoning = _jsonl("data/p_mini_pilot/reasoning_test.jsonl")
    smoke = _jsonl("data/p_mini_pilot/engineering_smoke.jsonl")
    assert (len(scenes), len(uptake), len(reasoning), len(smoke)) == (960, 192, 768, 12)
    assert {row["scene_id"] for row in uptake}.isdisjoint(
        {row["scene_id"] for row in reasoning}
    )
    formal_seeds = {value for row in scenes for value in row["seeds"].values()}
    smoke_seeds = {value for row in smoke for value in row["seeds"].values()}
    assert formal_seeds.isdisjoint(smoke_seeds)


def test_interventions_and_serializations_are_balanced() -> None:
    token = yaml.safe_load(
        (ROOT / "artifacts/preregistration/p_mini_pilot_token_balance.yaml").read_text(
            encoding="utf-8"
        )
    )
    equivalence = yaml.safe_load(
        (
            ROOT
            / "artifacts/preregistration/p_mini_pilot_serialization_equivalence.yaml"
        ).read_text(encoding="utf-8")
    )
    assert token["status"] == "PASS"
    assert len(token["summaries"]) == 6
    assert all(row["maximum_absolute_token_difference"] <= 1 for row in token["summaries"])
    assert equivalence["canonical_fact_equality"] == 1.0


def test_paired_power_retains_n_768_without_changing_deltas() -> None:
    power = yaml.safe_load(
        (
            ROOT / "research/preregistration/p_mini_pilot_power_analysis.yaml"
        ).read_text(encoding="utf-8")
    )
    assert power["delta0"] == 0.10
    assert power["delta1"] == 0.15
    assert power["sample_size_decision"] == "RETAIN_N_768"
    assert power["minimum_analytic_power_at_delta1_n768_in_plausible_region"] >= 0.80


def test_no_inference_artifacts_exist() -> None:
    result = verify_no_p_mini_pilot_inference()
    assert result["status"] == "PASS"
    assert result["scientific_prediction_count"] == 0
    assert result["reasoning_test_model_output_files"] == 0
    assert result["scientific_metrics_files"] == 0
    assert result["run_command_remains_blocked"] is True
