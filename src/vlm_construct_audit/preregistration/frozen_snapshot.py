"""Read-only integrity verification for the frozen Direction P v1 tag."""

from __future__ import annotations

import hashlib
import json
import subprocess
from typing import Any

import yaml

from .p_mini_pilot import ROOT

FROZEN_PREREGISTRATION_TAG = "p-mini-pilot-preregistered"
FROZEN_PREREGISTRATION_COMMIT = "9de60b87ec54bc852a7bb2e9cff87d9c23638042"
MANIFEST_PATH = "artifacts/preregistration/p_mini_pilot_preregistration_manifest.yaml"
EXPECTED_FILE_COUNT = 45
EXPECTED_AGGREGATE_SHA256 = (
    "20906cff6cbddcc18a491c562dea83bcc201bd76f5905d27c2e58bc8db32f9d2"
)
EXPECTED_METHOD_LOCK_SHA256 = (
    "c252336a8e14e37f0fce14329a845c042a5ff0037aa5692544f6aab14f62f978"
)
EXPECTED_MODEL_REGISTRY_SHA256 = (
    "738bef0cce88957e81b670665289d830c7d451d6774f75d9164327d88585c2d6"
)
EXPECTED_DATA_MANIFEST_SHA256 = (
    "1eef8c25123326549c345b91dcec861941b45001edd19414884339bce0c1d534"
)

METHOD_LOCK_PATH = "research/preregistration/p_mini_pilot_method_lock.yaml"
MODEL_REGISTRY_PATH = "configs/p_mini_pilot_models.yaml"
DATA_MANIFEST_PATH = "data/p_mini_pilot/data_manifest.yaml"
PREREGISTRATION_DECISION_PATH = "reports/p_mini_pilot_preregistration_decision.yaml"
HISTORICAL_DECISION_PATH = "reports/post_stop_final_decision.yaml"
P3_DECISION_PATH = "reports/post_stop_direction_p_decision.yaml"
MASTER_PROTOCOL_PATH = "research/preregistration/power_calibrated_mini_pilot.yaml"

FORBIDDEN_SNAPSHOT_PATHS = (
    "artifacts/p_mini_pilot/predictions",
    "artifacts/p_mini_pilot/model_outputs",
    "artifacts/p_mini_pilot/reasoning_results",
    "artifacts/p_mini_pilot/scientific_metrics.yaml",
    "research/authorization/p_mini_pilot_independent_audit.yaml",
)


def _git_bytes(*args: str, check: bool = True) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=check, capture_output=True
    )


def _snapshot_bytes(path: str) -> bytes:
    return _git_bytes("show", f"{FROZEN_PREREGISTRATION_TAG}:{path}").stdout


def _snapshot_yaml(path: str) -> dict[str, Any]:
    value = yaml.safe_load(_snapshot_bytes(path))
    if not isinstance(value, dict):
        raise TypeError(f"frozen YAML is not a mapping: {path}")
    return value


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _aggregate_hash(file_hashes: dict[str, str]) -> str:
    raw = json.dumps(file_hashes, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def _normalized_text_sha256(content: bytes) -> str:
    text = content.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _snapshot_path_exists(path: str) -> bool:
    return (
        _git_bytes(
            "cat-file",
            "-e",
            f"{FROZEN_PREREGISTRATION_TAG}:{path}",
            check=False,
        ).returncode
        == 0
    )


def verify_frozen_p_mini_pilot_preregistration_read_only() -> dict[str, Any]:
    """Recompute the v1 freeze solely from its annotated tag snapshot."""
    failures: list[str] = []
    tag_type_result = _git_bytes(
        "cat-file", "-t", f"refs/tags/{FROZEN_PREREGISTRATION_TAG}", check=False
    )
    tag_type = tag_type_result.stdout.decode().strip()
    if tag_type_result.returncode != 0 or tag_type != "tag":
        failures.append("frozen preregistration ref is missing or is not an annotated tag")

    peeled_result = _git_bytes(
        "rev-parse", "--verify", f"{FROZEN_PREREGISTRATION_TAG}^{{commit}}", check=False
    )
    peeled_commit = peeled_result.stdout.decode().strip()
    if peeled_result.returncode != 0:
        failures.append("frozen preregistration tag cannot be peeled to a commit")
    elif peeled_commit != FROZEN_PREREGISTRATION_COMMIT:
        failures.append(
            "frozen preregistration tag target mismatch: "
            f"{peeled_commit} != {FROZEN_PREREGISTRATION_COMMIT}"
        )

    manifest: dict[str, Any] = {}
    file_hashes: dict[str, str] = {}
    try:
        manifest = _snapshot_yaml(MANIFEST_PATH)
        manifest_files = manifest.get("files", {})
        if not isinstance(manifest_files, dict):
            failures.append("frozen manifest files field is not a mapping")
            manifest_files = {}
        if manifest.get("file_count") != EXPECTED_FILE_COUNT:
            failures.append("frozen manifest file_count is not 45")
        if len(manifest_files) != EXPECTED_FILE_COUNT:
            failures.append("frozen manifest does not enumerate exactly 45 files")
        for path, expected_hash in sorted(manifest_files.items()):
            try:
                digest = _sha256(_snapshot_bytes(str(path)))
            except subprocess.CalledProcessError:
                failures.append(f"frozen manifest file missing: {path}")
                continue
            file_hashes[str(path)] = digest
            if digest != expected_hash:
                failures.append(f"frozen manifest hash mismatch: {path}")
        aggregate = _aggregate_hash(file_hashes) if file_hashes else None
        if manifest.get("aggregate_sha256") != aggregate:
            failures.append("frozen aggregate preregistration hash mismatch")
        if aggregate != EXPECTED_AGGREGATE_SHA256:
            failures.append("frozen aggregate differs from the registered commitment")
    except (subprocess.CalledProcessError, TypeError, yaml.YAMLError) as exc:
        failures.append(f"cannot read frozen preregistration manifest: {exc}")

    committed_hashes = {
        "method_lock_sha256": (METHOD_LOCK_PATH, EXPECTED_METHOD_LOCK_SHA256),
        "model_registry_sha256": (MODEL_REGISTRY_PATH, EXPECTED_MODEL_REGISTRY_SHA256),
        "data_manifest_sha256": (DATA_MANIFEST_PATH, EXPECTED_DATA_MANIFEST_SHA256),
    }
    recomputed_hashes: dict[str, str | None] = {}
    for field, (path, registered_hash) in committed_hashes.items():
        try:
            digest = _sha256(_snapshot_bytes(path))
        except subprocess.CalledProcessError:
            failures.append(f"frozen committed file missing: {path}")
            digest = None
        recomputed_hashes[field] = digest
        if digest != manifest.get(field):
            failures.append(f"frozen manifest {field} mismatch")
        if digest != registered_hash:
            failures.append(f"frozen {field} differs from the registered commitment")

    try:
        method_lock = _snapshot_yaml(METHOD_LOCK_PATH)
        for path, expected_hash in method_lock.get("source_file_hashes", {}).items():
            if _normalized_text_sha256(_snapshot_bytes(path)) != expected_hash:
                failures.append(f"frozen P3 source hash mismatch: {path}")
        if method_lock.get("method") != "P3":
            failures.append("frozen method lock is not P3")
        if method_lock.get("delta0") != 0.10 or method_lock.get("delta1") != 0.15:
            failures.append("frozen P3 SESOI bounds changed")
    except (subprocess.CalledProcessError, TypeError, yaml.YAMLError) as exc:
        failures.append(f"cannot verify frozen P3 method lock: {exc}")

    try:
        data_manifest = _snapshot_yaml(DATA_MANIFEST_PATH)
        for path, record in data_manifest.get("files", {}).items():
            if _sha256(_snapshot_bytes(path)) != record.get("sha256"):
                failures.append(f"frozen data-manifest file hash mismatch: {path}")
        if data_manifest.get("scientific_outcome_use_forbidden") is not True:
            failures.append("frozen data manifest does not forbid scientific outcome use")
    except (subprocess.CalledProcessError, TypeError, yaml.YAMLError) as exc:
        failures.append(f"cannot verify frozen data manifest: {exc}")

    try:
        preregistration_decision = _snapshot_yaml(PREREGISTRATION_DECISION_PATH)
        no_inference = preregistration_decision.get("no_inference_verification", {})
        if preregistration_decision.get("decision") != "PREREGISTRATION_COMPLETE_NO_INFERENCE":
            failures.append("frozen preregistration decision changed")
        if preregistration_decision.get("scientific_inference_authorized") is not False:
            failures.append("frozen preregistration decision authorizes inference")
        expected_no_inference = {
            "scientific_prediction_count": 0,
            "reasoning_test_model_output_files": 0,
            "scientific_metrics_files": 0,
            "run_command_remains_blocked": True,
        }
        if no_inference != expected_no_inference:
            failures.append("frozen no-inference decision state changed")

        historical = _snapshot_yaml(HISTORICAL_DECISION_PATH)
        if historical.get("decision") != "PREREGISTER_POWER_CALIBRATED_MINI_PILOT":
            failures.append("frozen historical final decision changed")
        if historical.get("direction_decisions") != {
            "P": "DIRECTION_P_GO",
            "U": "DIRECTION_U_NO_GO",
            "M": "DIRECTION_M_NO_GO",
        }:
            failures.append("frozen historical direction decisions changed")
        if historical.get("recoalign_modified") is not False:
            failures.append("frozen historical decision records ReCoAlign modification")

        p3_decision = _snapshot_yaml(P3_DECISION_PATH)
        if (
            p3_decision.get("decision") != "DIRECTION_P_GO"
            or p3_decision.get("holdout_execution_count") != 1
            or p3_decision.get("delta0") != 0.10
            or p3_decision.get("delta1") != 0.15
        ):
            failures.append("frozen P3 historical decision changed")

        master = _snapshot_yaml(MASTER_PROTOCOL_PATH)
        if master.get("scientific_inference_authorized") is not False:
            failures.append("frozen master protocol authorizes scientific inference")
    except (subprocess.CalledProcessError, TypeError, yaml.YAMLError) as exc:
        failures.append(f"cannot verify frozen decisions: {exc}")

    forbidden_present = [path for path in FORBIDDEN_SNAPSHOT_PATHS if _snapshot_path_exists(path)]
    if forbidden_present:
        failures.append(f"forbidden paths exist in frozen snapshot: {forbidden_present}")

    return {
        "status": "PASS" if not failures else "FAIL",
        "mode": "READ_ONLY_TAG_SNAPSHOT",
        "failures": failures,
        "tag": FROZEN_PREREGISTRATION_TAG,
        "tag_object_type": tag_type or None,
        "peeled_commit": peeled_commit or None,
        "expected_commit": FROZEN_PREREGISTRATION_COMMIT,
        "current_head_compared_to_snapshot": False,
        "current_worktree_compared_to_snapshot": False,
        "manifest_file_count": manifest.get("file_count"),
        "aggregate_sha256": manifest.get("aggregate_sha256"),
        **recomputed_hashes,
        "scientific_prediction_count": 0 if not forbidden_present else None,
        "scientific_inference_authorized": False,
        "tracked_artifacts_modified": False,
    }
