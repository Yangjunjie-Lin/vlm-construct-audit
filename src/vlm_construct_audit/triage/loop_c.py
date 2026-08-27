"""Orchestrate the isolated three-family non-scientific checkpoint preflight."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

from ..utils import canonical_hash, dump_yaml, load_yaml


def _smoke_python() -> Path:
    return Path(".venv-vlm-smoke/Scripts/python.exe")


def adjudicate_loop_c_from_artifacts() -> dict[str, Any]:
    registry = load_yaml("configs/model_smoke_registry.yaml")
    config_hash = canonical_hash(registry)
    environment = load_yaml("artifacts/loop_c/environment.yaml")
    summaries = []
    for model in registry["models"]:
        path = Path(f"artifacts/loop_c/{model['model_id']}/summary.yaml")
        if path.exists():
            summaries.append(load_yaml(path))
        else:
            summaries.append(
                {
                    "model_id": model["model_id"],
                    "family": model["family"],
                    "status": "NOT_ATTEMPTED",
                }
            )
    loaded = sum(bool(item.get("checkpoint_load_success")) for item in summaries)
    visual = sum(bool(item.get("actual_visual_forward_success")) for item in summaries)
    full_gate = sum(item.get("status") == "PASS" for item in summaries)
    if not environment.get("cuda_available") or loaded == 0:
        loop_decision = "LOOP_C_BLOCKED_BY_COMPUTE"
    elif loaded < 3 or visual < 3:
        loop_decision = "LOOP_C_PARTIAL_ENGINEERING"
    elif full_gate < 3:
        loop_decision = "LOOP_C_NO_GO"
    else:
        loop_decision = "LOOP_C_GO"
    observed_latencies = [item.get("latency_seconds_mean") for item in summaries]
    runtime_projection = None
    if all(value is not None for value in observed_latencies):
        seconds = sum(float(value) for value in observed_latencies) * 9600
        runtime_projection = {
            "synthetic_evaluations_total": 28800,
            "evaluations_per_family": 9600,
            "seconds": seconds,
            "hours": seconds / 3600,
            "basis": "sum_of_three_observed_per-case_family_latencies_times_9600",
            "excludes_transport_set_and_setup_overhead": True,
        }
    prediction_bytes = sum(
        Path(f"artifacts/loop_c/{item['model_id']}/predictions.jsonl").stat().st_size
        for item in summaries
        if Path(f"artifacts/loop_c/{item['model_id']}/predictions.jsonl").exists()
    )
    storage_projection = {
        "observed_prediction_bytes_for_120_primary_cases": prediction_bytes,
        "projected_bytes_for_28800_cases": prediction_bytes * 240,
    }
    decision = {
        "schema_version": 1,
        "decision": loop_decision,
        "config_hash": config_hash,
        "families_registered": 3,
        "families_attempted": sum(item.get("status") != "NOT_ATTEMPTED" for item in summaries),
        "checkpoint_load_successes": loaded,
        "visual_forward_successes": visual,
        "full_engineering_gate_passes": full_gate,
        "environment_cuda_available": bool(environment.get("cuda_available")),
        "full_pilot_runtime_projection": runtime_projection,
        "full_pilot_storage_projection": storage_projection,
        "full_pilot_resource_feasible": loop_decision == "LOOP_C_GO" and runtime_projection is not None,
        "scientific_vlm_result": "NOT_EXECUTED",
        "mock_or_tiny_random_substitution": False,
        "model_summaries": [
            {
                "model_id": item.get("model_id"),
                "family": item.get("family"),
                "status": item.get("status"),
                "checkpoint_load_success": item.get("checkpoint_load_success", False),
                "actual_visual_forward_success": item.get("actual_visual_forward_success", False),
                "artifact_completeness": item.get("artifact_completeness"),
                "parser_valid_rate": item.get("parser_valid_rate"),
                "independent_scorer_ranking_agreement": item.get(
                    "independent_scorer_ranking_agreement"
                ),
                "deterministic_rerun_agreement": item.get("deterministic_rerun_agreement"),
                "peak_vram_bytes": item.get("peak_vram_bytes"),
                "peak_ram_bytes": item.get("peak_ram_bytes"),
                "latency_seconds_mean": item.get("latency_seconds_mean"),
                "error_type": item.get("error_type"),
                "error": item.get("error"),
            }
            for item in summaries
        ],
    }
    dump_yaml("artifacts/loop_c/decision.yaml", decision)
    return decision


def run_loop_c() -> dict[str, Any]:
    decision_path = Path("artifacts/loop_c/decision.yaml")
    if decision_path.exists():
        return load_yaml(decision_path)
    registry = load_yaml("configs/model_smoke_registry.yaml")
    python = _smoke_python()
    environment: dict[str, Any]
    if not python.exists():
        environment = {"cuda_available": False, "error": "isolated smoke environment missing"}
    else:
        env_command = [
            str(python),
            "-m",
            "vlm_construct_audit.triage.vlm_smoke_worker",
            "--environment",
        ]
        environment_process = subprocess.run(
            env_command,
            cwd=Path.cwd(),
            env={**os.environ, "PYTHONPATH": "src"},
            capture_output=True,
            text=True,
            check=False,
        )
        if environment_process.returncode == 0:
            environment = json.loads(environment_process.stdout.strip())
        else:
            environment = {
                "cuda_available": False,
                "returncode": environment_process.returncode,
                "stderr": environment_process.stderr,
            }
    dump_yaml("artifacts/loop_c/environment.yaml", environment)
    if environment.get("cuda_available"):
        for model in registry["models"]:
            model_id = model["model_id"]
            command = [
                str(python),
                "-m",
                "vlm_construct_audit.triage.vlm_smoke_worker",
                "--registry",
                "configs/model_smoke_registry.yaml",
                "--model-id",
                model_id,
            ]
            process = subprocess.run(
                command,
                cwd=Path.cwd(),
                env={**os.environ, "PYTHONPATH": "src", "TOKENIZERS_PARALLELISM": "false"},
                capture_output=True,
                text=True,
                check=False,
            )
            log_path = Path(f"artifacts/loop_c/{model_id}/load_and_run.log")
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_path.write_text(
                f"returncode={process.returncode}\nSTDOUT\n{process.stdout}\nSTDERR\n{process.stderr}",
                encoding="utf-8",
            )
            summary_path = Path(f"artifacts/loop_c/{model_id}/summary.yaml")
            if not summary_path.exists():
                dump_yaml(
                    summary_path,
                    {
                        "model_id": model_id,
                        "family": model["family"],
                        "status": "FAILED_WITHOUT_SUMMARY",
                        "returncode": process.returncode,
                    },
                )
    return adjudicate_loop_c_from_artifacts()
