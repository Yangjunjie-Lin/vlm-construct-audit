"""Deterministic, fail-closed adjudication of imported Direction P v2 reviews."""

from __future__ import annotations

import csv
import hashlib
from pathlib import Path
from typing import Any

import yaml

from .external_review import (
    JUDGMENTS,
    PROTOCOL_ID,
    PUBLIC_COMMITMENT,
    RESULTS_DIR,
    ReviewInfrastructureError,
    _validate_attestation,
    verify_external_review_packages,
)
from .generator import ROOT

POLICY_PATH = Path("research/construct_restart/v2_post_review_decision_policy.yaml")
METRICS_PATH = RESULTS_DIR / "human_construct_review_metrics.yaml"
IMPORT_MANIFEST_PATH = RESULTS_DIR / "import_manifest.yaml"
DECISION_PATH = Path("reports/construct_v2_human_review_decision.yaml")
REPORT_PATH = Path("reports/construct_v2_human_review_report.md")

PENDING = "PENDING_EXTERNAL_CONSTRUCT_REVIEW"
INVALID = "CONSTRUCT_V2_REVIEW_INVALID"
READY = "CONSTRUCT_V2_READY_FOR_INDEPENDENT_PREREGISTRATION_AUDIT"
NO_GO = "CONSTRUCT_V2_HUMAN_NO_GO"

EXPECTED_MAPPING = {
    "RETURNS_MISSING": PENDING,
    "RETURN_VALIDATION_FAILURE": INVALID,
    "HUMAN_CONSTRUCT_REVIEW_PASS": READY,
    "HUMAN_CONSTRUCT_REVIEW_FAIL": NO_GO,
}
EXPECTED_TERMINAL_ACTIONS = {
    NO_GO: "TERMINATE_DIRECTION_P",
    INVALID: "STOP_AND_PRESERVE_RETURNS",
}
EXPECTED_NON_AUTHORIZATIONS = {
    "runner implementation",
    "formal uptake inference",
    "formal reasoning inference",
    "scientific claim",
    "final preregistration tag",
    "execution authorization",
}
EXPECTED_GATES = {
    "reviewer_count_2",
    "response_completeness_1_00",
    "attestation_validation_pass",
    "overall_agreement_ge_0_95",
    "overall_nominal_cohen_kappa_ge_0_80",
    "genuine_required_field_no_count_0",
    "genuine_required_field_uncertain_count_0",
    "genuine_critical_error_yes_or_uncertain_count_0",
    "minimum_reviewer_decoy_detection_ge_0_90",
    "deleted_disagreements_0",
    "model_or_agent_review_used_false",
}
AUTHORIZATION_PATHS = (
    Path("research/authorization/construct_v2_independent_audit.yaml"),
    Path("research/authorization/construct_v2_execution_readiness.yaml"),
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_yaml(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"YAML is not a mapping: {path}")
    return value


def _policy_failures(policy: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if policy.get("schema_version") != 1:
        failures.append("post-review policy schema_version changed")
    if policy.get("protocol_id") != PROTOCOL_ID:
        failures.append("post-review policy protocol_id changed")
    if policy.get("frozen_before_any_human_return") is not True:
        failures.append("post-review policy was not frozen before human returns")
    if set(policy.get("input_states", [])) != set(EXPECTED_MAPPING):
        failures.append("post-review policy input states changed")
    if policy.get("decision_mapping") != EXPECTED_MAPPING:
        failures.append("post-review decision mapping changed")
    if policy.get("terminal_actions") != EXPECTED_TERMINAL_ACTIONS:
        failures.append("post-review terminal actions changed")
    if set(policy.get("human_pass_does_not_authorize", [])) != EXPECTED_NON_AUTHORIZATIONS:
        failures.append("human PASS non-authorization boundary changed")
    forbidden_controls = (
        "replacement_reviewers_after_valid_failure",
        "third_reviewer_rescue",
        "disagreement_deletion",
        "threshold_change_after_results",
        "packet_regeneration_after_results",
        "bundle_regeneration_after_results",
    )
    for field in forbidden_controls:
        if policy.get(field) != "forbidden":
            failures.append(f"post-review policy no longer forbids {field}")
    return failures


def validate_construct_v2_post_review_policy(root: Path = ROOT) -> dict[str, Any]:
    path = root / POLICY_PATH
    failures: list[str] = []
    if not path.is_file():
        failures.append("post-review decision policy missing")
        policy: dict[str, Any] = {}
    else:
        try:
            policy = _load_yaml(path)
            failures.extend(_policy_failures(policy))
        except (TypeError, yaml.YAMLError) as exc:
            failures.append(str(exc))
    return {
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "policy_path": POLICY_PATH.as_posix(),
        "policy_sha256": _sha256(path) if path.is_file() else None,
    }


def _no_inference_state(root: Path) -> dict[str, Any]:
    roots = {
        "formal_predictions": root / "artifacts/construct_v2/predictions",
        "model_outputs": root / "artifacts/construct_v2/model_outputs",
        "uptake_outputs": root / "artifacts/construct_v2/uptake_model_outputs",
        "reasoning_outputs": root / "artifacts/construct_v2/reasoning_model_outputs",
    }
    counts = {
        label: sum(path.is_file() for path in directory.rglob("*"))
        if directory.exists()
        else 0
        for label, directory in roots.items()
    }
    counts["scientific_metrics"] = int(
        (root / "artifacts/construct_v2/scientific_metrics.yaml").is_file()
    )
    authorization_count = sum((root / path).is_file() for path in AUTHORIZATION_PATHS)
    return {
        **counts,
        "authorization_files": authorization_count,
        "runner_blocked": authorization_count == 0,
        "status": "PASS"
        if not any(counts.values()) and authorization_count == 0
        else "FAIL",
    }


def _csv_row_count(path: Path) -> int:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return sum(1 for _ in csv.DictReader(handle))


def _check_import_evidence(
    root: Path,
    metrics: dict[str, Any],
    commitment: dict[str, Any],
) -> list[str]:
    failures: list[str] = []
    manifest_path = root / IMPORT_MANIFEST_PATH
    if not manifest_path.is_file():
        return ["immutable review import manifest missing"]
    try:
        manifest = _load_yaml(manifest_path)
    except (TypeError, yaml.YAMLError) as exc:
        return [f"invalid review import manifest: {exc}"]
    if manifest.get("protocol_id") != PROTOCOL_ID:
        failures.append("review import manifest protocol_id mismatch")
    if manifest.get("mode") != "IMMUTABLE_IMPORT_EVIDENCE":
        failures.append("review import manifest mode mismatch")
    if manifest.get("candidate_created") is not False:
        failures.append("importer created a preregistration candidate")
    if manifest.get("execution_authorization_created") is not False:
        failures.append("importer created execution authorization")
    expected_import_files = {
        (RESULTS_DIR / name).as_posix()
        for name in (
            "reviewer_1_original.csv",
            "reviewer_2_original.csv",
            "reviewer_1_attestation.yaml",
            "reviewer_2_attestation.yaml",
            "revealed_mapping_reviewer_1.json",
            "revealed_mapping_reviewer_2.json",
            "aligned_reviews.csv",
            "disagreements.csv",
            "field_metrics.yaml",
            "human_construct_review_metrics.yaml",
        )
    }
    files = manifest.get("files", {})
    if set(files) != expected_import_files:
        failures.append("review import manifest file set mismatch")
    for relative, expected_hash in files.items():
        path = root / relative
        if not path.is_file():
            failures.append(f"imported review evidence missing: {relative}")
        elif _sha256(path) != expected_hash:
            failures.append(f"imported review evidence hash mismatch: {relative}")

    evidence = metrics.get("evidence_hashes", {})
    if evidence.get("original_packet_sha256") != commitment.get("original_packet", {}).get(
        "sha256"
    ):
        failures.append("metrics original packet hash mismatch")
    if evidence.get("hidden_key_sha256") != commitment.get("frozen_hidden_key_sha256"):
        failures.append("metrics hidden key hash mismatch")
    file_bindings = {
        "aligned_reviews_sha256": RESULTS_DIR / "aligned_reviews.csv",
        "disagreements_sha256": RESULTS_DIR / "disagreements.csv",
    }
    for field, relative in file_bindings.items():
        path = root / relative
        if not path.is_file() or evidence.get(field) != _sha256(path):
            failures.append(f"metrics {field} mismatch")
    for slot in (1, 2):
        label = f"reviewer_{slot}"
        bindings = (
            ("original_returns", RESULTS_DIR / f"{label}_original.csv"),
            ("reviewer_attestations", RESULTS_DIR / f"{label}_attestation.yaml"),
        )
        for group, relative in bindings:
            path = root / relative
            if not path.is_file() or evidence.get(group, {}).get(label) != _sha256(path):
                failures.append(f"metrics {group} hash mismatch for {label}")
    return failures


def _metrics_failures(
    root: Path,
    metrics: dict[str, Any],
    commitment: dict[str, Any],
) -> list[str]:
    failures: list[str] = []
    if metrics.get("schema_version") != 1 or metrics.get("protocol_id") != PROTOCOL_ID:
        failures.append("human metrics schema or protocol mismatch")
    if metrics.get("reviewer_count") != 2:
        failures.append("human metrics reviewer count is not two")
    expected_bundles = {
        label: spec["sha256"] for label, spec in commitment.get("bundles", {}).items()
    }
    expected_mappings = {
        label: spec["mapping_sha256_commitment"]
        for label, spec in commitment.get("bundles", {}).items()
    }
    if metrics.get("bundle_hashes") != expected_bundles:
        failures.append("human metrics bundle hashes mismatch")
    if metrics.get("mapping_commitments") != expected_mappings:
        failures.append("human metrics mapping commitments mismatch")
    if metrics.get("mapping_commitment_verified") is not True:
        failures.append("mapping commitment was not verified")
    if metrics.get("packet_hash_verified") is not True:
        failures.append("packet hash was not verified")
    if metrics.get("response_completeness") != 1.0:
        failures.append("response completeness is not 1.00")

    reviewer_codes = metrics.get("reviewer_codes", {})
    if set(reviewer_codes) != {"reviewer_1", "reviewer_2"} or len(
        set(reviewer_codes.values())
    ) != 2:
        failures.append("reviewer codes are missing or not distinct")
    for slot in (1, 2):
        label = f"reviewer_{slot}"
        path = root / RESULTS_DIR / f"{label}_attestation.yaml"
        if not path.is_file():
            failures.append(f"{label} attestation missing")
            continue
        attestation, attestation_failures = _validate_attestation(
            path.read_bytes(), expected_bundles.get(label, "")
        )
        failures.extend(f"{label} attestation: {failure}" for failure in attestation_failures)
        if attestation.get("reviewer_code") != reviewer_codes.get(label):
            failures.append(f"{label} code does not match metrics")

    agreement = metrics.get("overall_agreement")
    kappa = metrics.get("overall_cohen_kappa")
    if not isinstance(agreement, (int, float)) or not 0 <= agreement <= 1:
        failures.append("overall agreement invalid")
    if kappa is not None and (not isinstance(kappa, (int, float)) or not -1 <= kappa <= 1):
        failures.append("overall three-category kappa invalid")
    if set(metrics.get("per_field_agreement", {})) != set(JUDGMENTS):
        failures.append("per-field agreement is incomplete")
    if set(metrics.get("per_field_kappa", {})) != set(JUDGMENTS):
        failures.append("per-field kappa is incomplete")

    uncertain = metrics.get("uncertain_count", {})
    if any(
        not isinstance(uncertain.get(label), int) or uncertain.get(label, -1) < 0
        for label in ("reviewer_1", "reviewer_2", "total")
    ):
        failures.append("uncertain counts invalid")
    elif uncertain["total"] != uncertain["reviewer_1"] + uncertain["reviewer_2"]:
        failures.append("uncertain reviewer counts do not sum to total")
    per_field_uncertain = uncertain.get("per_field", {})
    if set(per_field_uncertain) != set(JUDGMENTS):
        failures.append("uncertain per-field counts are incomplete")
    elif uncertain.get("total") != sum(per_field_uncertain.values()):
        failures.append("uncertain per-field counts do not sum to total")

    genuine = metrics.get("genuine_required_field_failures", {})
    if genuine.get("total") != genuine.get("no_count", -1) + genuine.get(
        "uncertain_count", -1
    ):
        failures.append("genuine required-field failure totals mismatch")
    critical = metrics.get("genuine_critical_errors", {})
    if critical.get("total") != critical.get("yes_count", -1) + critical.get(
        "uncertain_count", -1
    ):
        failures.append("genuine critical-error totals mismatch")

    decoy = metrics.get("reviewer_decoy_detection", {})
    rates: list[float] = []
    for label in ("reviewer_1", "reviewer_2"):
        row = decoy.get(label, {})
        total = row.get("total")
        detected = row.get("detected")
        rate = row.get("rate")
        if (
            not isinstance(total, int)
            or total <= 0
            or not isinstance(detected, int)
            or not 0 <= detected <= total
            or rate != detected / total
            or row.get("reviewer_code") != reviewer_codes.get(label)
        ):
            failures.append(f"{label} decoy detection metrics invalid")
        else:
            rates.append(rate)
    if rates and metrics.get("minimum_decoy_detection") != min(rates):
        failures.append("minimum decoy detection mismatch")

    disagreement_path = root / RESULTS_DIR / "disagreements.csv"
    aligned_path = root / RESULTS_DIR / "aligned_reviews.csv"
    if not disagreement_path.is_file() or _csv_row_count(disagreement_path) != metrics.get(
        "disagreement_count"
    ):
        failures.append("disagreement file count mismatch")
    if metrics.get("deleted_disagreements") != 0:
        failures.append("deleted disagreement count is not zero")
    if not aligned_path.is_file() or _csv_row_count(aligned_path) != 80:
        failures.append("aligned review file does not preserve all 80 items")
    if metrics.get("agent_or_model_review_used") is not False:
        failures.append("agent or model reviewer flag is not false")
    if metrics.get("reviewer_independence_attested") is not True:
        failures.append("reviewer independence is not attested")

    gates = metrics.get("gates", {})
    if set(gates) != EXPECTED_GATES:
        failures.append("human gate set changed")
    expected_gate_values = {
        "reviewer_count_2": metrics.get("reviewer_count") == 2,
        "response_completeness_1_00": metrics.get("response_completeness") == 1.0,
        "attestation_validation_pass": not any("attestation" in item for item in failures),
        "overall_agreement_ge_0_95": isinstance(agreement, (int, float))
        and agreement >= 0.95,
        "overall_nominal_cohen_kappa_ge_0_80": isinstance(kappa, (int, float))
        and kappa >= 0.80,
        "genuine_required_field_no_count_0": genuine.get("no_count") == 0,
        "genuine_required_field_uncertain_count_0": genuine.get("uncertain_count") == 0,
        "genuine_critical_error_yes_or_uncertain_count_0": critical.get("total") == 0,
        "minimum_reviewer_decoy_detection_ge_0_90": bool(rates) and min(rates) >= 0.90,
        "deleted_disagreements_0": metrics.get("deleted_disagreements") == 0,
        "model_or_agent_review_used_false": metrics.get("agent_or_model_review_used") is False,
    }
    if gates != expected_gate_values:
        failures.append("stored human gates do not match frozen thresholds")
    expected_status = (
        "HUMAN_CONSTRUCT_REVIEW_PASS"
        if all(expected_gate_values.values())
        else "HUMAN_CONSTRUCT_REVIEW_FAIL"
    )
    if metrics.get("status") != expected_status:
        failures.append("stored human status does not match frozen gates")
    return failures


def _decision_report(decision: dict[str, Any], metrics: dict[str, Any] | None) -> str:
    lines = [
        "# Direction P v2 human construct review decision",
        "",
        f"Decision: `{decision['decision']}`.",
        "",
    ]
    if decision["decision"] == READY:
        lines.extend(
            [
                "Both frozen human-review gates pass. This authorizes only creation of a",
                "preregistration candidate for a new independent audit. It does not authorize",
                "a runner, VLM inference, a scientific claim, or execution authorization.",
            ]
        )
    elif decision["decision"] == NO_GO:
        lines.append("The frozen human gate failed. Direction P terminates without a candidate.")
    else:
        lines.append("Imported review evidence is invalid; preserve returns and stop.")
    if metrics:
        lines.extend(
            [
                "",
                f"Reviewer count: {metrics.get('reviewer_count')}",
                f"Overall agreement: {metrics.get('overall_agreement')}",
                f"Overall three-category Cohen kappa: {metrics.get('overall_cohen_kappa')}",
                f"Uncertain count: {metrics.get('uncertain_count', {}).get('total')}",
                f"Disagreement count: {metrics.get('disagreement_count')}",
            ]
        )
    if decision.get("validation_failures"):
        lines.extend(
            ["", "Validation failures:", *[f"- {item}" for item in decision["validation_failures"]]]
        )
    return "\n".join(lines).rstrip() + "\n"


def _write_once_or_verify(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != content:
            raise RuntimeError(f"refusing to overwrite existing adjudication artifact: {path}")
        return
    path.write_bytes(content)


def adjudicate_construct_v2_human_review(root: Path = ROOT) -> dict[str, Any]:
    """Validate imported metrics and apply only the pre-frozen decision mapping."""
    root = root.resolve()
    policy_validation = validate_construct_v2_post_review_policy(root)
    metrics_path = root / METRICS_PATH
    if not metrics_path.is_file():
        return {
            "status": PENDING,
            "decision": PENDING,
            "reviewer_count_completed": 0,
            "outputs_created": False,
        }

    failures = list(policy_validation["failures"])
    metrics: dict[str, Any] | None = None
    try:
        verify_external_review_packages(root)
    except (ReviewInfrastructureError, OSError, KeyError, TypeError, yaml.YAMLError) as exc:
        failures.append(f"external review package verification failed: {exc}")
    try:
        commitment = _load_yaml(root / PUBLIC_COMMITMENT)
        metrics = _load_yaml(metrics_path)
        failures.extend(_check_import_evidence(root, metrics, commitment))
        failures.extend(_metrics_failures(root, metrics, commitment))
    except (OSError, TypeError, yaml.YAMLError) as exc:
        commitment = {}
        failures.append(f"human metrics could not be validated: {exc}")

    no_inference = _no_inference_state(root)
    if no_inference["status"] != "PASS":
        failures.append("no-inference or runner boundary failed")
    input_state = "RETURN_VALIDATION_FAILURE" if failures else metrics["status"]
    decision_value = EXPECTED_MAPPING[input_state]
    next_action = {
        READY: "BUILD_CONSTRUCT_V2_PREREGISTRATION_CANDIDATE",
        NO_GO: "TERMINATE_DIRECTION_P",
        INVALID: "STOP_AND_PRESERVE_RETURNS",
    }[decision_value]
    decision = {
        "schema_version": 1,
        "protocol_id": PROTOCOL_ID,
        "decision": decision_value,
        "input_state": input_state,
        "decision_policy": POLICY_PATH.as_posix(),
        "decision_policy_sha256": policy_validation["policy_sha256"],
        "human_metrics_sha256": _sha256(metrics_path),
        "validation_failures": failures,
        "reviewer_count": metrics.get("reviewer_count") if metrics else None,
        "human_pass_authorizes_candidate_only": decision_value == READY,
        "runner_authorized": False,
        "formal_vlm_inference_authorized": False,
        "execution_authorization_created": False,
        "no_inference": no_inference,
        "exact_next_action": next_action,
    }
    decision_bytes = yaml.safe_dump(
        decision, sort_keys=False, allow_unicode=True
    ).encode("utf-8")
    report_bytes = _decision_report(decision, metrics).encode("utf-8")
    _write_once_or_verify(root / DECISION_PATH, decision_bytes)
    _write_once_or_verify(root / REPORT_PATH, report_bytes)
    return {"status": decision_value, **decision}
