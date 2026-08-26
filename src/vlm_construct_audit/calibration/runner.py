"""Execute all known-state systems through both primary response contracts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..measurement.contracts import option_map, parse_constrained
from ..measurement.probes import run_measurement_probes
from ..models.adapters import CalibrationVLMAdapter, FakeSmokeAdapter
from ..models.tiny_blip_smoke import run_tiny_random_blip_forward
from ..utils import (
    canonical_hash,
    dump_yaml,
    load_yaml,
    read_jsonl,
    sha256_file,
    utc_timestamp,
    write_jsonl,
)


def _config_hash() -> str:
    return canonical_hash(
        {
            "pilot": load_yaml("configs/pilot.yaml"),
            "policy": load_yaml("configs/audit_policy.yaml"),
            "preregistration": load_yaml("research/preregistration/minimum_pilot.yaml"),
        }
    )


def run_calibration() -> dict[str, Any]:
    config = load_yaml("configs/pilot.yaml")
    scenes = {row["scene_id"]: row for row in read_jsonl("data/generated/scenes.jsonl")}
    serialized = read_jsonl("data/generated/serialized.jsonl")
    timestamp = utc_timestamp()
    config_hash = _config_hash()
    predictions: list[dict[str, Any]] = []
    probe_rows: list[dict[str, Any]] = []

    for system_name in config["calibration_systems"]:
        adapter = CalibrationVLMAdapter(system_name)
        metadata = adapter.get_revision_metadata()
        probes = run_measurement_probes(system_name, 300)
        probe_rows.extend({"system": system_name, **case} for case in probes["cases"])
        for evidence in serialized:
            scene = scenes[evidence["scene_id"]]
            prepared = adapter.prepare_input(scene, evidence)
            candidates = list(scene["question"]["options"])
            mapping = option_map(candidates)
            for contract in config["contracts"]:
                if contract == "conditional_likelihood":
                    result = adapter.score_candidates(prepared, candidates)
                    system_output = result.pop("system_output")
                    parsed = result["parsed_response"]
                    raw_response = json.dumps(result["candidate_scores"], sort_keys=True, separators=(",", ":"))
                    candidate_scores = result["candidate_scores"]
                    candidate_margin = result["candidate_margin"]
                    parser_status = result["parser_status"]
                elif contract == "constrained_generation":
                    system_output = adapter.constrained_decision(prepared)
                    raw_response = adapter.generate_constrained(prepared, candidates)
                    parsed_result = parse_constrained(raw_response, candidates)
                    parsed = parsed_result["parsed_response"]
                    candidate_scores = None
                    candidate_margin = None
                    parser_status = parsed_result["parser_status"]
                else:
                    raise KeyError(contract)
                predictions.append(
                    {
                        "scene_id": scene["scene_id"],
                        "split": scene["split"],
                        "model_id": system_name,
                        "model_revision": metadata["model_revision"],
                        "condition": evidence["condition"],
                        "serialization": evidence["serialization"],
                        "contract": contract,
                        "elicitation_contract": contract,
                        "scoring_contract": "length_normalized_semantic_candidate" if contract == "conditional_likelihood" else "strict_json_semantic_answer_parser",
                        "raw_response": raw_response,
                        "parsed_response": parsed,
                        "candidate_scores": candidate_scores,
                        "candidate_margin": candidate_margin,
                        "option_id_to_semantic_answer": mapping,
                        "parser_status": parser_status,
                        "timestamp": timestamp,
                        "config_hash": config_hash,
                        "gold_answer": scene["answer"],
                        "score": int(parsed == scene["answer"]),
                        "measurement_probe_pass": system_output.measurement_probe_pass,
                        "pre_mapping_answer": system_output.pre_mapping_answer,
                        "canonical_trace": system_output.canonical_trace,
                        "diagnostic_subtype": system_output.diagnostic_subtype,
                    }
                )

    prediction_path = Path("artifacts/predictions/calibration_predictions.jsonl")
    probe_path = Path("artifacts/metrics/measurement_probes.jsonl")
    write_jsonl(prediction_path, predictions)
    write_jsonl(probe_path, probe_rows)
    manifest = {
        "schema_version": 1,
        "prediction_count": len(predictions),
        "expected_prediction_count": len(scenes) * 6 * 2 * 2 * 6,
        "measurement_probe_count": len(probe_rows),
        "systems": list(config["calibration_systems"]),
        "serializations": list(config["serializations"]),
        "contracts": list(config["contracts"]),
        "config_hash": config_hash,
        "predictions_sha256": sha256_file(prediction_path),
        "measurement_probes_sha256": sha256_file(probe_path),
        "timestamp": timestamp,
    }
    dump_yaml("artifacts/manifests/prediction_manifest.yaml", manifest)
    return manifest


def run_smoke() -> dict[str, Any]:
    scenes = read_jsonl("data/generated/scenes.jsonl")
    serialized = read_jsonl("data/generated/serialized.jsonl")
    scene = scenes[0]
    evidence = next(row for row in serialized if row["scene_id"] == scene["scene_id"] and row["condition"] == "correct_evidence")
    adapter = FakeSmokeAdapter()
    prepared = adapter.prepare_input(scene, evidence)
    likelihood = adapter.score_candidates(prepared, scene["question"]["options"])
    likelihood.pop("system_output")
    raw = adapter.generate_constrained(prepared, scene["question"]["options"])
    strict = parse_constrained(raw, scene["question"]["options"])
    tiny_blip = run_tiny_random_blip_forward()
    result = {
        "schema_version": 1,
        "fake_adapter_status": "PASS",
        "fake_adapter_metadata": adapter.get_revision_metadata(),
        "conditional_likelihood_parsed": likelihood["parsed_response"],
        "constrained_generation": strict,
        "offline_tiny_random_vlm_forward": tiny_blip,
        "open_weight_checkpoint_smoke": "NOT_EXECUTED",
        "scientific_evidence": False,
    }
    dump_yaml("artifacts/metrics/smoke_report.yaml", result)
    return result
