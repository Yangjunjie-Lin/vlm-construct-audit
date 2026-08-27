"""Command-line orchestration for the minimum validity loop."""

from __future__ import annotations

import argparse
from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml

from .audit import build_audit_decisions
from .calibration.runner import run_calibration, run_smoke
from .data import generate_dataset
from .interventions import build_interventions
from .post_stop import freeze_post_stop, run_direction_p
from .reporting import build_artifact_manifest, build_evidence_map, build_report, verify_artifacts
from .serialization import build_serializations, validate_equivalence
from .statistics import analyze_predictions, run_known_dgp_simulation, run_threshold_sensitivity
from .triage.loop_b import run_loop_b
from .triage.loop_c import run_loop_c
from .triage.reporting import adjudicate_tier0_5, verify_tier0_5_artifacts
from .utils import load_yaml


def _show(value: Any) -> None:
    print(yaml.safe_dump(value, sort_keys=False, allow_unicode=True).rstrip())


def validate_config() -> dict[str, Any]:
    pilot = load_yaml("configs/pilot.yaml")
    policy = load_yaml("configs/audit_policy.yaml")
    prereg = load_yaml("research/preregistration/minimum_pilot.yaml")
    failures = []
    if sum(int(value) for value in pilot["splits"].values()) != int(pilot["scene_count"]):
        failures.append("split counts do not sum to scene_count")
    if set(pilot["serializations"]) != {"natural_language", "triples"}:
        failures.append("primary serializers must be NL and triples")
    if set(pilot["contracts"]) != {"conditional_likelihood", "constrained_generation"}:
        failures.append("two primary response contracts are required")
    if len(pilot["calibration_systems"]) != 6:
        failures.append("six calibration systems are required")
    if policy.get("allow_sample_uptake_filtering") is not False:
        failures.append("sample-level uptake filtering must be forbidden")
    if prereg["status"]["tier1"] != "not_authorized_until_tier0_go":
        failures.append("Tier 1 authorization boundary missing")
    amendment = load_yaml("research/preregistration/amendment_001.yaml")
    if amendment.get("before_any_calibration_predictions") is not True:
        failures.append("pre-result amendment record invalid")
    result = {"status": "PASS" if not failures else "FAIL", "failures": failures, "files_validated": 5}
    if failures:
        raise ValueError(result)
    return result


def generate_all(config: str) -> dict[str, Any]:
    scenes = generate_dataset(config)
    interventions = build_interventions(conditions=load_yaml(config)["interventions"])
    serializations = build_serializations()
    return {"scenes": scenes, "interventions": interventions, "serializations": serializations}


def analyze_all() -> dict[str, Any]:
    return {
        "effects": analyze_predictions(),
        "known_dgp": run_known_dgp_simulation(),
        "threshold_sensitivity": run_threshold_sensitivity(),
    }


def minimum_loop(config: str = "configs/pilot.yaml") -> dict[str, Any]:
    validate_config()
    generate_all(config)
    equivalence = validate_equivalence()
    calibration = run_calibration()
    smoke = run_smoke()
    analyze_all()
    audit = build_audit_decisions()
    evidence = build_evidence_map()
    decision = build_report()
    manifest = build_artifact_manifest()
    verification = verify_artifacts()
    return {
        "status": "CLOSED_LOOP_COMPLETE",
        "tier0_decision": decision["tier0_decision"],
        "scientific_pilot_status": decision["scientific_pilot_status"],
        "scenes": 48,
        "systems": 6,
        "predictions": calibration["prediction_count"],
        "expected_class_matches": audit["expected_class_matches"],
        "programmatic_equivalence": equivalence["programmatic_fact_equivalence"],
        "manual_equivalence_review": equivalence["manual_sample_review"]["status"],
        "tiny_random_vlm_smoke": smoke["offline_tiny_random_vlm_forward"]["status"],
        "artifact_count": manifest["artifact_count"],
        "verification": verification["status"],
        "evidence_claims": len(evidence["claims"]),
    }


def _run_pilot() -> int:
    models = load_yaml("configs/models.yaml")
    message = {
        "status": "NOT_AUTHORIZED",
        "reason": "Tier-0 sensitivity gate is inconclusive; model revisions and real-image license are not frozen.",
        "configured_models": len(models["models"]),
        "no_inference_started": True,
    }
    _show(message)
    return 2


def _read_loop_a() -> dict[str, Any]:
    result = load_yaml("artifacts/loop_a/holdout/summary.yaml")
    return {
        "decision": result["decision"],
        "holdout_execution_count": result["holdout_execution_count"],
        "holdout_rerun_forbidden": result["holdout_rerun_forbidden"],
        "config_hash": result["config_hash"],
    }


def _verify_all() -> dict[str, Any]:
    base = verify_artifacts()
    tier = None
    if Path("artifacts/manifests/tier0_5_artifact_manifest.yaml").exists():
        tier = verify_tier0_5_artifacts()
    return {"status": "PASS", "tier0": base, "tier0_5": tier}


def _command_table(config: str) -> dict[str, Callable[[], Any]]:
    return {
        "validate-config": validate_config,
        "generate-data": lambda: generate_all(config),
        "validate-equivalence": validate_equivalence,
        "run-calibration": run_calibration,
        "run-smoke": run_smoke,
        "analyze": analyze_all,
        "audit-claims": build_audit_decisions,
        "build-evidence-map": build_evidence_map,
        "build-report": build_report,
        "verify-artifacts": _verify_all,
        "minimum-loop": lambda: minimum_loop(config),
        "run-loop-a": _read_loop_a,
        "run-loop-b": run_loop_b,
        "run-loop-c": run_loop_c,
        "adjudicate-tier0-5": adjudicate_tier0_5,
        "post-stop-freeze": freeze_post_stop,
        "run-direction-p-development": lambda: run_direction_p("development"),
        "run-direction-p-holdout": lambda: run_direction_p("holdout"),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="vlm-construct-audit")
    parser.add_argument(
        "command",
        choices=[
            "validate-config", "generate-data", "validate-equivalence", "run-calibration",
            "run-smoke", "run-pilot", "analyze", "audit-claims", "build-evidence-map",
            "build-report", "verify-artifacts", "minimum-loop",
            "run-loop-a", "run-loop-b", "run-loop-c", "adjudicate-tier0-5",
            "post-stop-freeze", "run-direction-p-development", "run-direction-p-holdout",
        ],
    )
    parser.add_argument("--config", default="configs/pilot.yaml")
    args = parser.parse_args(argv)
    if not Path(args.config).exists():
        parser.error(f"Config not found: {args.config}")
    if args.command == "run-pilot":
        return _run_pilot()
    result = _command_table(args.config)[args.command]()
    _show(result)
    return 0
