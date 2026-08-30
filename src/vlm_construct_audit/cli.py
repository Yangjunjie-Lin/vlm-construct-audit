"""Command-line orchestration for the minimum validity loop."""

from __future__ import annotations

import argparse
from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml

from .audit import build_audit_decisions
from .calibration.runner import run_calibration, run_smoke
from .construct_v2 import (
    analyze_construct_v2_power,
    audit_construct_v2_leakage,
    build_construct_v2_report,
    build_construct_v2_review_packet,
    build_external_review_packages,
    generate_construct_v2,
    import_external_review_returns,
    retire_v1,
    run_construct_v2_oracles,
    validate_construct_v2,
    verify_external_review_packages,
    verify_no_construct_v2_inference,
)
from .data import generate_dataset
from .interventions import build_interventions
from .post_stop import (
    adjudicate_post_stop,
    freeze_post_stop,
    import_human_review,
    run_direction_m,
    run_direction_p,
    run_direction_u,
    seal_direction,
)
from .preregistration import (
    validate_p_mini_pilot_preregistration,
    verify_frozen_post_stop_artifacts_read_only,
    verify_no_p_mini_pilot_inference,
    verify_p_mini_pilot_preregistration,
)
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


def _run_p_mini_pilot() -> int:
    _show(
        {
            "status": "V1_SCIENTIFIC_EXECUTION_PERMANENTLY_FORBIDDEN",
            "audit_decision": "AUDIT_FAIL_CONSTRUCT_VALIDITY",
            "no_inference_started": True,
        }
    )
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
    frozen_reports = [
        Path("artifacts/manifests/verification_report.yaml"),
        Path("artifacts/manifests/tier0_5_verification_report.yaml"),
    ]
    snapshots = {
        path: path.read_bytes() for path in frozen_reports if path.exists()
    }
    try:
        base = verify_artifacts()
        tier = None
        if Path("artifacts/manifests/tier0_5_artifact_manifest.yaml").exists():
            tier = verify_tier0_5_artifacts()
    finally:
        for path, content in snapshots.items():
            path.write_bytes(content)
    return {"status": "PASS", "tier0": base, "tier0_5": tier}


def _analyze_construct_v2_power_cli() -> dict[str, Any]:
    result = analyze_construct_v2_power()
    return {
        "status": result["status"],
        "chosen_reasoning_n": result["chosen_reasoning_n"],
        "primary_sample_size_evaluation": result["primary_sample_size_evaluation"],
        "p3_method_hashes_unchanged": result["p3_method_hashes"]["unchanged"],
    }


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
        "run-direction-m-development": lambda: run_direction_m("development"),
        "run-direction-m-holdout": lambda: run_direction_m("holdout"),
        "run-direction-u-development": lambda: run_direction_u("development"),
        "run-direction-u-holdout": lambda: run_direction_u("holdout"),
        "seal-direction-p": lambda: seal_direction("p"),
        "seal-direction-m": lambda: seal_direction("m"),
        "seal-direction-u": lambda: seal_direction("u"),
        "import-human-review": import_human_review,
        "adjudicate-post-stop": adjudicate_post_stop,
        "verify-post-stop-artifacts": verify_frozen_post_stop_artifacts_read_only,
        "validate-p-mini-pilot-preregistration": validate_p_mini_pilot_preregistration,
        "verify-p-mini-pilot-preregistration": verify_p_mini_pilot_preregistration,
        "verify-no-p-mini-pilot-inference": verify_no_p_mini_pilot_inference,
        "retire-p-mini-pilot-v1": retire_v1,
        "generate-construct-v2": generate_construct_v2,
        "validate-construct-v2": validate_construct_v2,
        "audit-construct-v2-leakage": audit_construct_v2_leakage,
        "run-construct-v2-oracles": run_construct_v2_oracles,
        "analyze-construct-v2-power": _analyze_construct_v2_power_cli,
        "build-construct-v2-review-packet": build_construct_v2_review_packet,
        "build-construct-v2-external-review-packages": build_external_review_packages,
        "verify-construct-v2-external-review-packages": verify_external_review_packages,
        "import-construct-v2-external-review": import_external_review_returns,
        "verify-no-construct-v2-inference": verify_no_construct_v2_inference,
        "build-construct-v2-report": build_construct_v2_report,
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
            "run-direction-m-development", "run-direction-m-holdout",
            "run-direction-u-development", "run-direction-u-holdout",
            "seal-direction-p", "seal-direction-m", "seal-direction-u",
            "import-human-review", "adjudicate-post-stop", "verify-post-stop-artifacts",
            "validate-p-mini-pilot-preregistration", "verify-p-mini-pilot-preregistration",
            "verify-no-p-mini-pilot-inference", "run-p-mini-pilot",
            "retire-p-mini-pilot-v1",
            "generate-construct-v2", "validate-construct-v2",
            "audit-construct-v2-leakage", "run-construct-v2-oracles",
            "analyze-construct-v2-power", "build-construct-v2-review-packet",
            "build-construct-v2-external-review-packages",
            "verify-construct-v2-external-review-packages",
            "import-construct-v2-external-review",
            "verify-no-construct-v2-inference", "build-construct-v2-report",
        ],
    )
    parser.add_argument("--config", default="configs/pilot.yaml")
    args = parser.parse_args(argv)
    if not Path(args.config).exists():
        parser.error(f"Config not found: {args.config}")
    if args.command == "run-pilot":
        return _run_pilot()
    if args.command == "run-p-mini-pilot":
        return _run_p_mini_pilot()
    result = _command_table(args.config)[args.command]()
    _show(result)
    if args.command in {
        "validate-p-mini-pilot-preregistration",
        "verify-p-mini-pilot-preregistration",
        "verify-no-p-mini-pilot-inference",
        "validate-construct-v2",
        "audit-construct-v2-leakage",
        "run-construct-v2-oracles",
        "analyze-construct-v2-power",
        "verify-no-construct-v2-inference",
    } and result.get("status") != "PASS":
        return 1
    return 0
