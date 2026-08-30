"""Validation and no-inference guards for the Direction P preregistration."""

from __future__ import annotations

import hashlib
import json
import subprocess
from typing import Any

import yaml

from .p_mini_pilot import ROOT, _sha256, _validate_scenes

BASE_COMMIT = "f993282e0a27b8da0ba1c239fb96715c9fc5b79a"
STOP_COMMIT = "ce0e797a4926ab5d2309915c2eef14fd9c5be44d"
POST_STOP_TAG = "vlm-construct-audit-post-stop-final"
PREREGISTRATION_TAG = "p-mini-pilot-preregistered"
AUTHORIZATION_PATH = "research/authorization/p_mini_pilot_independent_audit.yaml"

REQUIRED_PACKAGE_FILES = [
    "research/preregistration/p_mini_pilot_identity.md",
    "research/preregistration/p_mini_pilot_literature_matrix.yaml",
    "research/preregistration/p_mini_pilot_novelty_boundary.md",
    "research/preregistration/p_mini_pilot_model_selection_policy.yaml",
    "research/preregistration/p_mini_pilot_power_analysis.yaml",
    "research/preregistration/p_mini_pilot_estimands.yaml",
    "research/preregistration/p_mini_pilot_hypothesis_registry.yaml",
    "research/preregistration/p_mini_pilot_method_lock.yaml",
    "research/preregistration/p_mini_pilot_multiplicity_policy.yaml",
    "research/preregistration/p_mini_pilot_go_no_go.yaml",
    "research/preregistration/p_mini_pilot_deviation_policy.yaml",
    "research/preregistration/power_calibrated_mini_pilot.yaml",
    "configs/p_mini_pilot.yaml",
    "configs/p_mini_pilot_models.yaml",
    "configs/p_mini_pilot_serializations.yaml",
    "configs/p_mini_pilot_interventions.yaml",
    "configs/p_mini_pilot_statistics.yaml",
    "data/p_mini_pilot/scenes.jsonl",
    "data/p_mini_pilot/uptake_validation.jsonl",
    "data/p_mini_pilot/reasoning_test.jsonl",
    "data/p_mini_pilot/engineering_smoke.jsonl",
    "data/p_mini_pilot/data_manifest.yaml",
    "docs/p_mini_pilot_causal_scope.md",
    "docs/p_mini_pilot_claim_boundary.md",
    "docs/p_mini_pilot_measurement_contract.md",
    "docs/p_mini_pilot_execution_boundary.md",
    "reports/p_mini_pilot_preregistration_readiness.md",
    "reports/p_mini_pilot_power_analysis.md",
    "reports/p_mini_pilot_intervention_balance.md",
    "reports/p_mini_pilot_evidence_map.yaml",
    "reports/p_mini_pilot_preregistration_decision.yaml",
    "artifacts/preregistration/p_mini_pilot_token_balance.yaml",
    "artifacts/preregistration/p_mini_pilot_serialization_equivalence.yaml",
]

IMPLEMENTATION_FILES = [
    ".github/workflows/ci.yml",
    "src/vlm_construct_audit/preregistration/__init__.py",
    "src/vlm_construct_audit/preregistration/p_mini_pilot.py",
    "src/vlm_construct_audit/preregistration/validation.py",
    "src/vlm_construct_audit/post_stop/__init__.py",
    "src/vlm_construct_audit/cli.py",
    "tests/integration/test_closed_loop_components.py",
    "tests/integration/test_model_smoke.py",
    "tests/unit/test_p_mini_pilot_preregistration.py",
    "tests/unit/test_post_stop_m.py",
    "tests/unit/test_tier0_5_manifest_isolation.py",
    "tests/regression/test_cli_contract.py",
]

HISTORICAL_FILES = [
    "reports/post_stop_three_direction_report.md",
    "reports/post_stop_final_decision.yaml",
    "reports/post_stop_evidence_map.yaml",
    "reports/post_stop_claim_boundary.md",
    "data/annotations/human_review_metrics.yaml",
    "data/annotations/adjudication.csv",
    "reports/post_stop_direction_p.md",
    "reports/post_stop_direction_p_decision.yaml",
    "reports/post_stop_direction_m.md",
    "reports/post_stop_direction_m_decision.yaml",
    "reports/post_stop_direction_u.md",
    "reports/post_stop_direction_u_decision.yaml",
    "artifacts/post_stop/verification_report.yaml",
    "research/post_stop/global_stop_rules.yaml",
    "research/post_stop/novelty_boundary.md",
    "configs/model_smoke_registry.yaml",
    "src/vlm_construct_audit/triage/audit_v2.py",
    "src/vlm_construct_audit/post_stop/direction_p.py",
    "research/post_stop/direction_p/preregistration.yaml",
    "research/post_stop/direction_p/power_table.yaml",
    "research/post_stop/direction_p/method_freeze.yaml",
]

FORBIDDEN_RESULT_PATHS = [
    "artifacts/p_mini_pilot/predictions",
    "artifacts/p_mini_pilot/model_outputs",
    "artifacts/p_mini_pilot/reasoning_results",
    "artifacts/p_mini_pilot/scientific_metrics.yaml",
]


def _load_yaml(path: str) -> dict[str, Any]:
    return yaml.safe_load((ROOT / path).read_text(encoding="utf-8"))


def _git(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=check, capture_output=True, text=True
    )


def _tag_target(tag: str) -> str | None:
    result = _git("rev-parse", "--verify", f"{tag}^{{commit}}", check=False)
    return result.stdout.strip() if result.returncode == 0 else None


def _read_jsonl(path: str) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in (ROOT / path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _aggregate_hash(file_hashes: dict[str, str]) -> str:
    raw = json.dumps(file_hashes, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def _normalized_text_sha256(path: str) -> str:
    text_value = (ROOT / path).read_text(encoding="utf-8")
    normalized = text_value.replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def validate_p_mini_pilot_preregistration() -> dict[str, Any]:
    failures: list[str] = []
    missing = [path for path in REQUIRED_PACKAGE_FILES if not (ROOT / path).is_file()]
    failures.extend(f"missing required file: {path}" for path in missing)
    if missing:
        return {
            "status": "FAIL",
            "decision": "PREREGISTRATION_VALIDATION_FAILURE",
            "failures": failures,
            "files_validated": len(REQUIRED_PACKAGE_FILES) - len(missing),
        }
    if _tag_target("vlm-construct-audit-tier0-5-stop") != STOP_COMMIT:
        failures.append("Tier 0.5 stop tag target mismatch")
    if _tag_target(POST_STOP_TAG) != BASE_COMMIT:
        failures.append("Post-STOP final tag target mismatch")
    historical_diff = _git(
        "diff", "--name-only", BASE_COMMIT, "--", *HISTORICAL_FILES
    ).stdout.splitlines()
    if historical_diff:
        failures.append(f"historical files changed: {historical_diff}")
    final = _load_yaml("reports/post_stop_final_decision.yaml")
    expected_final = {
        "decision": "PREREGISTER_POWER_CALIBRATED_MINI_PILOT",
        "selected_direction": "P",
        "loop_b_human": "HUMAN_REVIEW_GO",
        "audit_v2": "LOOP_A_NO_GO",
        "old_holdout_rerun": False,
        "recoalign_modified": False,
    }
    for key, expected in expected_final.items():
        if final.get(key) != expected:
            failures.append(f"historical decision mismatch {key}")
    if final.get("direction_decisions") != {
        "P": "DIRECTION_P_GO",
        "U": "DIRECTION_U_NO_GO",
        "M": "DIRECTION_M_NO_GO",
    }:
        failures.append("historical direction decisions mismatch")
    verification = _load_yaml("artifacts/post_stop/verification_report.yaml")
    if verification.get("status") != "PASS":
        failures.append("Post-STOP artifact verification is not PASS")
    p_decision = _load_yaml("reports/post_stop_direction_p_decision.yaml")
    if (
        p_decision.get("decision") != "DIRECTION_P_GO"
        or p_decision.get("holdout_execution_count") != 1
    ):
        failures.append("Direction P known-DGP lock mismatch")
    novelty = _load_yaml(
        "research/preregistration/p_mini_pilot_literature_matrix.yaml"
    )
    novelty_decision = novelty.get("collision_assessment", {}).get("decision")
    if novelty_decision not in {"NOVELTY_PASS", "NOVELTY_PASS_WITH_CAUTION"}:
        failures.append(f"novelty decision blocks preregistration: {novelty_decision}")
    models = _load_yaml("configs/p_mini_pilot_models.yaml").get("models", [])
    required_model_fields = {
        "model_id",
        "family",
        "repository",
        "revision",
        "weight_hashes",
        "parameter_count",
        "license",
        "processor_revision",
        "tokenizer_revision",
        "dtype",
        "quantization",
        "device_map",
        "transformers_version",
        "trust_remote_code",
        "selection_reason",
    }
    if len(models) != 3 or len({model.get("family") for model in models}) != 3:
        failures.append("model registry is not three distinct families")
    for model in models:
        absent = sorted(required_model_fields - set(model))
        if absent:
            failures.append(f"model fields missing for {model.get('model_id')}: {absent}")
    scenes = _read_jsonl("data/p_mini_pilot/scenes.jsonl")
    uptake = _read_jsonl("data/p_mini_pilot/uptake_validation.jsonl")
    reasoning = _read_jsonl("data/p_mini_pilot/reasoning_test.jsonl")
    smoke = _read_jsonl("data/p_mini_pilot/engineering_smoke.jsonl")
    if (len(scenes), len(uptake), len(reasoning), len(smoke)) != (960, 192, 768, 12):
        failures.append("scene split counts mismatch")
    if {row["scene_id"] for row in scenes} != {
        row["scene_id"] for row in uptake + reasoning
    }:
        failures.append("combined scene file does not equal split union")
    design_validation = _validate_scenes(scenes)
    if design_validation["status"] != "PASS":
        failures.extend(design_validation["failures"])
    formal_seeds = {value for row in scenes for value in row["seeds"].values()}
    smoke_seeds = {value for row in smoke for value in row["seeds"].values()}
    if formal_seeds & smoke_seeds:
        failures.append("engineering-smoke seeds overlap formal scenes")
    manifest = _load_yaml("data/p_mini_pilot/data_manifest.yaml")
    for path, record in manifest.get("files", {}).items():
        if _sha256(path) != record.get("sha256"):
            failures.append(f"data hash mismatch: {path}")
    token_balance = _load_yaml(
        "artifacts/preregistration/p_mini_pilot_token_balance.yaml"
    )
    if token_balance.get("status") != "PASS" or any(
        row.get("maximum_absolute_token_difference", 2) > 1
        for row in token_balance.get("summaries", [])
    ):
        failures.append("token balance failed")
    equivalence = _load_yaml(
        "artifacts/preregistration/p_mini_pilot_serialization_equivalence.yaml"
    )
    if equivalence.get("canonical_fact_equality") != 1.0:
        failures.append("canonical serialization equality failed")
    power = _load_yaml("research/preregistration/p_mini_pilot_power_analysis.yaml")
    if (
        power.get("sample_size_decision") != "RETAIN_N_768"
        or power.get("minimum_analytic_power_at_delta1_n768_in_plausible_region", 0) < 0.80
        or not power.get("feasible")
    ):
        failures.append("paired power requirement failed")
    method = _load_yaml("research/preregistration/p_mini_pilot_method_lock.yaml")
    for path, expected_hash in method.get("source_file_hashes", {}).items():
        if _normalized_text_sha256(path) != expected_hash:
            failures.append(f"P3 method-lock hash mismatch: {path}")
    master = _load_yaml("research/preregistration/power_calibrated_mini_pilot.yaml")
    if master.get("scientific_inference_authorized") is not False:
        failures.append("master protocol incorrectly authorizes inference")
    decision = _load_yaml("reports/p_mini_pilot_preregistration_decision.yaml")
    if decision.get("decision") != "PREREGISTRATION_COMPLETE_NO_INFERENCE":
        failures.append("preregistration decision is not complete-no-inference")
    if decision.get("scientific_inference_authorized") is not False:
        failures.append("decision report incorrectly authorizes inference")
    no_inference = decision.get("no_inference_verification", {})
    if no_inference != {
        "scientific_prediction_count": 0,
        "reasoning_test_model_output_files": 0,
        "scientific_metrics_files": 0,
        "run_command_remains_blocked": True,
    }:
        failures.append("decision report no-inference counts mismatch")
    return {
        "status": "PASS" if not failures else "FAIL",
        "decision": (
            "PREREGISTRATION_COMPLETE_NO_INFERENCE"
            if not failures
            else "PREREGISTRATION_VALIDATION_FAILURE"
        ),
        "failures": failures,
        "files_validated": len(REQUIRED_PACKAGE_FILES),
        "historical_integrity": "PASS" if not historical_diff else "FAIL",
        "scene_design": design_validation,
        "model_count": len(models),
        "scientific_inference_authorized": False,
    }


def build_p_mini_pilot_preregistration_manifest() -> dict[str, Any]:
    paths = REQUIRED_PACKAGE_FILES + IMPLEMENTATION_FILES
    missing = [path for path in paths if not (ROOT / path).is_file()]
    if missing:
        raise FileNotFoundError(missing)
    hashes = {path: _sha256(path) for path in sorted(paths)}
    manifest = {
        "schema_version": 1,
        "manifest_id": "p_mini_pilot_preregistration_manifest_v1",
        "generated_before_model_inference": True,
        "expected_tag": PREREGISTRATION_TAG,
        "file_count": len(hashes),
        "files": hashes,
        "aggregate_sha256": _aggregate_hash(hashes),
        "method_lock_sha256": _sha256(
            "research/preregistration/p_mini_pilot_method_lock.yaml"
        ),
        "model_registry_sha256": _sha256("configs/p_mini_pilot_models.yaml"),
        "data_manifest_sha256": _sha256("data/p_mini_pilot/data_manifest.yaml"),
        "scientific_outcome_use_forbidden": True,
    }
    target = (
        ROOT
        / "artifacts/preregistration/p_mini_pilot_preregistration_manifest.yaml"
    )
    target.write_text(
        yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
    return manifest


def verify_p_mini_pilot_preregistration() -> dict[str, Any]:
    validation = validate_p_mini_pilot_preregistration()
    manifest_path = (
        ROOT
        / "artifacts/preregistration/p_mini_pilot_preregistration_manifest.yaml"
    )
    failures = list(validation["failures"])
    if not manifest_path.is_file():
        failures.append("preregistration manifest missing")
        manifest: dict[str, Any] = {}
    else:
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        current = {
            path: _sha256(path)
            for path in manifest.get("files", {})
            if (ROOT / path).is_file()
        }
        missing = sorted(set(manifest.get("files", {})) - set(current))
        if missing:
            failures.append(f"manifest files missing: {missing}")
        mismatches = sorted(
            path
            for path, digest in current.items()
            if manifest["files"].get(path) != digest
        )
        if mismatches:
            failures.append(f"manifest hash mismatches: {mismatches}")
        if current and manifest.get("aggregate_sha256") != _aggregate_hash(current):
            failures.append("aggregate preregistration hash mismatch")
    tag_target = _tag_target(PREREGISTRATION_TAG)
    tag_status = "NOT_YET_CREATED"
    if tag_target is not None:
        head = _git("rev-parse", "HEAD").stdout.strip()
        tag_status = "PASS"
        if tag_target != head:
            failures.append(f"preregistration tag target {tag_target} != HEAD {head}")
            tag_status = "FAIL"
        protected = REQUIRED_PACKAGE_FILES + IMPLEMENTATION_FILES + [
            "artifacts/preregistration/p_mini_pilot_preregistration_manifest.yaml"
        ]
        if (
            _git(
                "diff",
                "--quiet",
                PREREGISTRATION_TAG,
                "--",
                *protected,
                check=False,
            ).returncode
            != 0
        ):
            failures.append("PREREGISTRATION_TAG_DIRTY")
            tag_status = "FAIL"
    return {
        "status": "PASS" if not failures else "FAIL",
        "decision": (
            "PREREGISTRATION_COMPLETE_NO_INFERENCE"
            if not failures
            else "PREREGISTRATION_VALIDATION_FAILURE"
        ),
        "failures": failures,
        "manifest_file_count": manifest.get("file_count"),
        "aggregate_sha256": manifest.get("aggregate_sha256"),
        "preregistration_tag": PREREGISTRATION_TAG,
        "tag_target": tag_target,
        "tag_status": tag_status,
    }


def verify_no_p_mini_pilot_inference() -> dict[str, Any]:
    forbidden_existing = [
        path for path in FORBIDDEN_RESULT_PATHS if (ROOT / path).exists()
    ]
    scanned_files = []
    content_hits = []
    forbidden_markers = (
        "reasoning_test_model_response",
        "correct_vs_corrupted_scientific_outcome",
        "real_model_effect_estimate",
        "p3_real_model_certification_result",
    )
    for suffix in ("*.jsonl", "*.yaml", "*.csv", "*.log"):
        for path in ROOT.rglob(suffix):
            if any(part == ".git" or part.startswith(".venv") for part in path.parts):
                continue
            scanned_files.append(path)
            text = path.read_text(encoding="utf-8", errors="ignore").lower()
            for marker in forbidden_markers:
                if marker in text:
                    content_hits.append(
                        {"path": str(path.relative_to(ROOT)), "marker": marker}
                    )
    prediction_files = []
    model_output_files = []
    scientific_metric_files = []
    artifact_root = ROOT / "artifacts/p_mini_pilot"
    if artifact_root.exists():
        for path in artifact_root.rglob("*"):
            if not path.is_file():
                continue
            relative = str(path.relative_to(ROOT)).replace("\\", "/")
            lowered = relative.lower()
            if "prediction" in lowered:
                prediction_files.append(relative)
            if "model_output" in lowered or "reasoning_result" in lowered:
                model_output_files.append(relative)
            if "scientific_metric" in lowered:
                scientific_metric_files.append(relative)
    authorization_present = (ROOT / AUTHORIZATION_PATH).is_file()
    failures = []
    if forbidden_existing:
        failures.append(f"forbidden result paths exist: {forbidden_existing}")
    if content_hits:
        failures.append(f"forbidden scientific outcome markers: {content_hits}")
    if prediction_files or model_output_files or scientific_metric_files:
        failures.append("P Mini-Pilot scientific output files detected")
    return {
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "scientific_prediction_count": len(prediction_files),
        "reasoning_test_model_output_files": len(model_output_files),
        "scientific_metrics_files": len(scientific_metric_files),
        "forbidden_result_paths_present": forbidden_existing,
        "content_marker_hits": content_hits,
        "scanned_structured_or_log_files": len(set(scanned_files)),
        "independent_authorization_present": authorization_present,
        "run_command_remains_blocked": not authorization_present,
    }


def verify_frozen_post_stop_artifacts_read_only() -> dict[str, Any]:
    """Recompute the Post-STOP checks without refreshing a frozen report timestamp."""
    p = _load_yaml("reports/post_stop_direction_p_decision.yaml")
    m = _load_yaml("reports/post_stop_direction_m_decision.yaml")
    u = _load_yaml("reports/post_stop_direction_u_decision.yaml")
    human = _load_yaml("data/annotations/human_review_metrics.yaml")
    checks = {
        "historical_freeze": _tag_target("vlm-construct-audit-tier0-5-stop")
        == STOP_COMMIT,
        "P_holdout_once": p.get("holdout_execution_count") == 1
        and _load_yaml("artifacts/post_stop/direction_p/holdout/execution_marker.yaml").get(
            "execution_count"
        )
        == 1,
        "M_holdout_zero": m.get("sealed_holdout", {}).get("execution_count") == 0
        and not (ROOT / "artifacts/post_stop/direction_m/holdout/execution_marker.yaml").exists(),
        "U_holdout_zero": u.get("sealed_holdout", {}).get("execution_count") == 0
        and not (ROOT / "artifacts/post_stop/direction_u/holdout/execution_marker.yaml").exists(),
        "direction_decisions_present": (
            p.get("decision") == "DIRECTION_P_GO"
            and m.get("decision") == "DIRECTION_M_NO_GO"
            and u.get("decision") == "DIRECTION_U_NO_GO"
        ),
        "human_review_complete": human.get("reviewer_count") == 2
        and human.get("status") == "HUMAN_REVIEW_GO"
        and all(human.get("gates", {}).values()),
        "model_as_human_forbidden": human.get("agent_or_model_review_used") is False,
    }
    return {
        "schema_version": 1,
        "mode": "READ_ONLY_FROZEN_RECOMPUTATION",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "directions": {
            "P": p.get("decision"),
            "M": m.get("decision"),
            "U": u.get("decision"),
        },
        "human_review": human.get("status"),
        "frozen_report_unchanged": True,
    }


def validate_independent_authorization() -> dict[str, Any]:
    path = ROOT / AUTHORIZATION_PATH
    if not path.is_file():
        return {"status": "MISSING", "valid": False}
    authorization = yaml.safe_load(path.read_text(encoding="utf-8"))
    required = {
        "status",
        "audited_preregistration_tag",
        "audited_commit",
        "auditor_identity",
        "audit_date",
        "preregistration_hash",
        "method_lock_hash",
        "model_registry_hash",
        "data_manifest_hash",
        "authorization_scope",
    }
    failures = [f"missing field {key}" for key in sorted(required - set(authorization))]
    manifest = _load_yaml(
        "artifacts/preregistration/p_mini_pilot_preregistration_manifest.yaml"
    )
    expected = {
        "status": "PASS",
        "audited_preregistration_tag": PREREGISTRATION_TAG,
        "audited_commit": _tag_target(PREREGISTRATION_TAG),
        "preregistration_hash": manifest.get("aggregate_sha256"),
        "method_lock_hash": manifest.get("method_lock_sha256"),
        "model_registry_hash": manifest.get("model_registry_sha256"),
        "data_manifest_hash": manifest.get("data_manifest_sha256"),
    }
    for key, value in expected.items():
        if authorization.get(key) != value:
            failures.append(f"authorization mismatch {key}")
    identity = str(authorization.get("auditor_identity", "")).strip().lower()
    if not identity or identity in {"codex", "openai", "authoring_agent", "self"}:
        failures.append("auditor identity is missing or not independent")
    return {
        "status": "PASS" if not failures else "FAIL",
        "valid": not failures,
        "failures": failures,
    }
