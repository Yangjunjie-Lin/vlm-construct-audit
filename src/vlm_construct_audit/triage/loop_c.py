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


def run_loop_c() -> dict[str, Any]:
    decision_path = Path("artifacts/loop_c/decision.yaml")
    if decision_path.exists():
        return load_yaml(decision_path)
    registry = load_yaml("configs/model_smoke_registry.yaml")
    config_hash = canonical_hash(registry)
    python = _smoke_python()
    summaries = []
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
            if summary_path.exists():
                summaries.append(load_yaml(summary_path))
            else:
                summaries.append(
                    {
                        "model_id": model_id,
                        "family": model["family"],
                        "status": "FAILED_WITHOUT_SUMMARY",
                        "returncode": process.returncode,
                    }
                )
    loaded = sum(bool(item.get("checkpoint_load_success")) for item in summaries)
    full_gate = sum(item.get("status") == "PASS" for item in summaries)
    if not environment.get("cuda_available") or loaded == 0:
        loop_decision = "LOOP_C_BLOCKED_BY_COMPUTE"
    elif full_gate < 3:
        loop_decision = "LOOP_C_PARTIAL_ENGINEERING"
    else:
        loop_decision = "LOOP_C_GO"
    observed_latencies = [item.get("latency_seconds_mean") for item in summaries if item.get("latency_seconds_mean")]
    runtime_projection = None
    if len(observed_latencies) == 3:
        runtime_projection = {
            "synthetic_evaluations": 28800,
            "seconds": sum(observed_latencies) * 28800,
            "hours": sum(observed_latencies) * 28800 / 3600,
            "basis": "sum_of_three_observed_per-case_family_latencies_times_28800",
        }
    decision = {
        "schema_version": 1,
        "decision": loop_decision,
        "config_hash": config_hash,
        "families_registered": 3,
        "families_attempted": len(summaries),
        "checkpoint_load_successes": loaded,
        "full_engineering_gate_passes": full_gate,
        "environment_cuda_available": bool(environment.get("cuda_available")),
        "full_pilot_runtime_projection": runtime_projection,
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
                "error_type": item.get("error_type"),
                "error": item.get("error"),
            }
            for item in summaries
        ],
    }
    dump_yaml(decision_path, decision)
    return decision
