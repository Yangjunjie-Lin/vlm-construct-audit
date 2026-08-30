"""Build and verify the post-human-review v2 preregistration candidate."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

import yaml

from .adjudication import (
    DECISION_PATH,
    METRICS_PATH,
    READY,
    REPORT_PATH,
    RESULTS_DIR,
    _no_inference_state,
    adjudicate_construct_v2_human_review,
)
from .external_review import (
    PROTOCOL_ID,
    PUBLIC_COMMITMENT,
    ReviewInfrastructureError,
    verify_external_review_packages,
)
from .generator import ROOT

SCHEMA_PATH = Path("research/construct_restart/v2_preregistration_candidate_schema.yaml")
TEMPLATES_PATH = Path(
    "research/construct_restart/v2_preregistration_candidate_templates.yaml"
)
PACKAGE_ROOT = Path("research/preregistration/construct_v2")
ARTIFACT_ROOT = Path("artifacts/construct_v2_preregistration_candidate")

AUTOMATED_FREEZE_TAG = "construct-v2-automated-preaudit-freeze"
AUTOMATED_FREEZE_COMMIT = "1552a3c77e0bdd6bf0fdb0bf49447c19df4af6f2"
EXTERNAL_REVIEW_GATE_COMMIT = "fc6ca1aa4a6f931b624fbc7e414b9fb0bfcd34a6"
POLICY_FREEZE_TAG = "construct-v2-human-gate-policy-freeze"
HISTORICAL_TAGS = {
    AUTOMATED_FREEZE_TAG: AUTOMATED_FREEZE_COMMIT,
    "p-mini-pilot-preregistered": "9de60b87ec54bc852a7bb2e9cff87d9c23638042",
    "p-mini-pilot-preregistration-audit-no-pass": (
        "97c64947a0e6b30b0c9a0654519bbd93ae37d846"
    ),
    "vlm-construct-audit-post-stop-final": (
        "f993282e0a27b8da0ba1c239fb96715c9fc5b79a"
    ),
    "vlm-construct-audit-tier0-5-stop": (
        "ce0e797a4926ab5d2309915c2eef14fd9c5be44d"
    ),
}

PACKAGE_NAMES = (
    "master_protocol.yaml",
    "identity.md",
    "construct_definition.yaml",
    "causal_scope.md",
    "estimands.yaml",
    "hypothesis_registry.yaml",
    "model_registry.yaml",
    "uptake_policy.yaml",
    "measurement_policy.yaml",
    "p3_method_lock.yaml",
    "power_and_multiplicity.yaml",
    "go_no_go.yaml",
    "deviation_policy.yaml",
    "novelty_boundary.md",
    "human_review_lock.yaml",
    "execution_boundary.yaml",
)
REPORT_PATHS = (
    REPORT_PATH,
    DECISION_PATH,
    Path("reports/construct_v2_preregistration_candidate_readiness.md"),
    Path("reports/construct_v2_preregistration_candidate_decision.yaml"),
    Path("reports/construct_v2_candidate_evidence_map.yaml"),
    Path("reports/construct_v2_open_audit_issues.yaml"),
)
ARTIFACT_PATHS = (
    ARTIFACT_ROOT / "manifest.yaml",
    ARTIFACT_ROOT / "protected_files.yaml",
    ARTIFACT_ROOT / "verification_report.yaml",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _yaml_bytes(value: Any) -> bytes:
    return yaml.safe_dump(value, sort_keys=False, allow_unicode=True).encode("utf-8")


def _load_yaml(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"YAML is not a mapping: {path}")
    return value


def _tag_target(root: Path, tag: str) -> str | None:
    result = subprocess.run(
        ["git", "rev-parse", "--verify", f"{tag}^{{commit}}"],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def _normalized_text_sha256(path: Path) -> str:
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _candidate_paths() -> tuple[Path, ...]:
    return tuple(PACKAGE_ROOT / name for name in PACKAGE_NAMES) + REPORT_PATHS + ARTIFACT_PATHS


def _validate_schema(root: Path) -> dict[str, Any]:
    schema = _load_yaml(root / SCHEMA_PATH)
    templates = _load_yaml(root / TEMPLATES_PATH)
    expected_package = list(PACKAGE_NAMES)
    expected_reports = [path.as_posix() for path in REPORT_PATHS]
    expected_artifacts = [path.as_posix() for path in ARTIFACT_PATHS]
    failures: list[str] = []
    if schema.get("schema_version") != 1 or schema.get("protocol_id") != PROTOCOL_ID:
        failures.append("candidate schema or protocol mismatch")
    if schema.get("generation_gate") != READY or schema.get("candidate_decision") != READY:
        failures.append("candidate generation gate changed")
    if schema.get("package_files") != expected_package:
        failures.append("candidate package file schema changed")
    if schema.get("report_files") != expected_reports:
        failures.append("candidate report file schema changed")
    if schema.get("artifact_files") != expected_artifacts:
        failures.append("candidate artifact file schema changed")
    locks = schema.get("required_locks", {})
    expected_locks = {
        "automated_freeze_commit": AUTOMATED_FREEZE_COMMIT,
        "automated_freeze_tag": AUTOMATED_FREEZE_TAG,
        "external_review_gate_commit": EXTERNAL_REVIEW_GATE_COMMIT,
        "policy_freeze_tag": POLICY_FREEZE_TAG,
        "reasoning_n": 1280,
        "uptake_n": 256,
        "delta0": 0.10,
        "delta1": 0.15,
        "primary_serialization": "natural_language",
        "triples_role": "robustness_only",
        "path_b_go_authority": False,
    }
    if locks != expected_locks:
        failures.append("candidate required locks changed")
    if schema.get("candidate_tag_created_by_builder") is not False:
        failures.append("candidate schema authorizes builder to create tag")
    if schema.get("scientific_inference_authorized") is not False:
        failures.append("candidate schema authorizes scientific inference")
    if schema.get("runner_authorized") is not False:
        failures.append("candidate schema authorizes runner")
    if templates.get("templates_frozen_before_human_returns") is not True:
        failures.append("candidate templates were not frozen before human returns")
    power_language = templates.get("power_language", {})
    if (
        power_language.get("range_at_n_1280") != [0.8700, 0.8862]
        or power_language.get("end_to_end_pilot_power_claim") != "forbidden"
        or power_language.get("real_model_uptake_gate_probability_estimated") is not False
        or power_language.get("uptake_failure_is_independent_preceding_stop") is not True
        or power_language.get("end_to_end_success_probability_may_be_below_0_8700")
        is not True
    ):
        failures.append("candidate conditional-power language changed")
    return {"schema": schema, "failures": failures}


def _open_audit_issues() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "protocol_id": PROTOCOL_ID,
        "issues": [
            {
                "id": "LEAKAGE_CP_CONDITION_EXPANDED_ROWS",
                "status": "OPEN",
                "issue": "Leakage shortcut Clopper-Pearson upper bounds use condition-expanded rows.",
            },
            {
                "id": "SCENE_CLUSTER_BOOTSTRAP_REQUIRED",
                "status": "REQUIRED_FOR_NEW_INDEPENDENT_AUDIT",
                "issue": "The new independent audit must add a scene-cluster bootstrap upper bound.",
            },
            {
                "id": "POWER_CONDITIONAL_ON_UPTAKE",
                "status": "OPEN",
                "issue": "Stable Path power is conditional on uptake eligibility.",
            },
            {
                "id": "REAL_MODEL_UPTAKE_PASS_PROBABILITY_UNKNOWN",
                "status": "OPEN",
                "issue": "The probability that real models pass all task-specific uptake gates is unknown.",
            },
            {
                "id": "HUMAN_INDEPENDENCE_ATTESTATION_BOUNDARY",
                "status": "OPEN",
                "issue": "External-review independence relies on reviewer attestation, not technically absolute inability to access the public repository.",
            },
            {
                "id": "P3_BEHAVIORAL_NOT_MECHANISTIC",
                "status": "OPEN",
                "issue": "P3 is known-DGP-calibrated behavioral certification, not an internal-mechanism guarantee.",
            },
            {
                "id": "SYNTHETIC_EXTERNAL_VALIDITY_UNKNOWN",
                "status": "OPEN",
                "issue": "External validity of the synthetic bridge composition is not established.",
            },
            {
                "id": "RUNNER_AND_CLL_EXECUTION_AUDIT_PENDING",
                "status": "OPEN",
                "issue": "The runner and real conditional-likelihood scoring path have not received an execution-readiness audit.",
            },
        ],
        "deletion_before_independent_audit": "forbidden",
    }


def _candidate_payloads(root: Path, policy_freeze_commit: str) -> dict[Path, bytes]:
    commitment = _load_yaml(root / PUBLIC_COMMITMENT)
    metrics = _load_yaml(root / METRICS_PATH)
    human_decision = _load_yaml(root / DECISION_PATH)
    import_manifest = _load_yaml(root / RESULTS_DIR / "import_manifest.yaml")
    power = _load_yaml(root / "artifacts/construct_v2/multiplicity_power.yaml")
    p3_hashes = power["p3_method_hashes"]
    evidence = metrics["evidence_hashes"]
    human_metrics_hash = _sha256(root / METRICS_PATH)
    human_decision_hash = _sha256(root / DECISION_PATH)
    policy_hash = human_decision["decision_policy_sha256"]
    bundle_hashes = {
        label: spec["sha256"] for label, spec in commitment["bundles"].items()
    }
    mapping_commitments = {
        label: spec["mapping_sha256_commitment"]
        for label, spec in commitment["bundles"].items()
    }
    master = {
        "schema_version": 1,
        "protocol_id": PROTOCOL_ID,
        "candidate_status": READY,
        "automated_freeze": {
            "commit": AUTOMATED_FREEZE_COMMIT,
            "annotated_tag": AUTOMATED_FREEZE_TAG,
        },
        "external_review_gate_commit": EXTERNAL_REVIEW_GATE_COMMIT,
        "human_gate_policy_freeze": {
            "commit": policy_freeze_commit,
            "annotated_tag": POLICY_FREEZE_TAG,
            "policy_sha256": policy_hash,
        },
        "external_review": {
            "bundle_sha256": bundle_hashes,
            "mapping_commitments": mapping_commitments,
            "original_packet_sha256": evidence["original_packet_sha256"],
            "hidden_key_sha256": evidence["hidden_key_sha256"],
            "human_metrics_sha256": human_metrics_hash,
            "reviewer_attestations_sha256": evidence["reviewer_attestations"],
            "aligned_review_sha256": evidence["aligned_reviews_sha256"],
            "disagreement_file_sha256": evidence["disagreements_sha256"],
        },
        "design_locks": {
            "p3_method_hashes": p3_hashes,
            "delta0": 0.10,
            "delta1": 0.15,
            "reasoning_n": 1280,
            "uptake_n": 256,
            "primary_serialization": "natural_language",
            "triples_role": "robustness_only",
            "path_b_go_authority": False,
            "uptake_tasks": [
                "visual_hop_relation",
                "textual_bridge_relation",
                "direction_reversal",
                "cross_modal_bridge_binding",
            ],
        },
        "human_review_decision_sha256": human_decision_hash,
        "human_pass_authorizes_candidate_only": True,
        "scientific_inference_authorized": False,
        "runner_authorized": False,
        "execution_authorization_created": False,
        "candidate_tag_created_by_builder": False,
        "next_gate": "NEW_INDEPENDENT_PREREGISTRATION_AUDIT",
    }
    measurement = {
        "schema_version": 1,
        "protocol_id": PROTOCOL_ID,
        "primary_score": "length_normalized_candidate_conditional_likelihood",
        "candidate_target": "semantic_answer_text",
        "independent_scorer_verification_required": True,
        "real_cll_path_execution_readiness_audit": "PENDING",
        "measurement_failure_is_preceding_stop": True,
        "scientific_inference_authorized": False,
    }
    p3_lock = {
        "schema_version": 1,
        "method": "P3",
        "delta0": 0.10,
        "delta1": 0.15,
        "source_hash_policy": "sha256_utf8_text_after_crlf_and_cr_normalization_to_lf",
        "source_file_hashes": {
            path: record["expected"] for path, record in p3_hashes["files"].items()
        },
        "all_hashes_unchanged_at_candidate_build": p3_hashes["unchanged"],
        "known_dgp_calibrated_behavioral_certification": True,
        "internal_mechanism_guarantee": False,
        "modification_after_candidate": "forbidden",
    }
    power_lock = {
        "schema_version": 1,
        "protocol_id": PROTOCOL_ID,
        "reasoning_n": 1280,
        "uptake_n": 256,
        "delta0": 0.10,
        "delta1": 0.15,
        "primary_serialization": "natural_language",
        "triples_role": "robustness_only",
        "path_b_go_authority": False,
        "stable_path_downstream_certification_power": {
            "range": [0.8700333333333333, 0.8861666666666667],
            "conditional_on": [
                "construct validity",
                "human construct validity",
                "measurement integrity",
                "uptake eligibility",
            ],
            "is_complete_end_to_end_pilot_power": False,
            "real_model_four_uptake_gate_pass_probability_estimated": False,
            "uptake_failure_is_independent_preceding_stopping_event": True,
            "complete_end_to_end_success_probability_may_be_below_0_8700": True,
            "existing_simulation_results_changed": False,
        },
    }
    human_lock = {
        "schema_version": 1,
        "protocol_id": PROTOCOL_ID,
        "decision": READY,
        "human_metrics_sha256": human_metrics_hash,
        "human_decision_sha256": human_decision_hash,
        "original_return_sha256": evidence["original_returns"],
        "reviewer_attestations_sha256": evidence["reviewer_attestations"],
        "aligned_review_sha256": evidence["aligned_reviews_sha256"],
        "disagreement_file_sha256": evidence["disagreements_sha256"],
        "import_manifest_sha256": _sha256(root / RESULTS_DIR / "import_manifest.yaml"),
        "imported_file_hashes": import_manifest["files"],
        "uncertain_retained": True,
        "disagreements_preserved": True,
        "replacement_reviewers_forbidden": True,
        "third_reviewer_rescue_forbidden": True,
    }
    execution = {
        "schema_version": 1,
        "protocol_id": PROTOCOL_ID,
        "candidate_scope": "INDEPENDENT_PREREGISTRATION_AUDIT_ONLY",
        "runner_implementation_authorized": False,
        "formal_uptake_inference_authorized": False,
        "formal_reasoning_inference_authorized": False,
        "scientific_claim_authorized": False,
        "execution_authorization_created": False,
        "required_future_gates": [
            "new independent preregistration audit",
            "runner and CLL execution-readiness audit",
            "two separate execution authorization files",
        ],
    }
    candidate_decision = {
        "schema_version": 1,
        "protocol_id": PROTOCOL_ID,
        "decision": READY,
        "human_construct_review_decision": READY,
        "candidate_complete": True,
        "candidate_tag_created": False,
        "runner_authorized": False,
        "scientific_inference_authorized": False,
        "exact_next_action": (
            "SUBMIT_CONSTRUCT_V2_CANDIDATE_TO_NEW_INDEPENDENT_PREREGISTRATION_AUDIT"
        ),
    }
    evidence_map = {
        "schema_version": 1,
        "protocol_id": PROTOCOL_ID,
        "claims": {
            "automated_construct_gate": {
                "source": "reports/construct_v2_automated_gate.yaml",
                "freeze_commit": AUTOMATED_FREEZE_COMMIT,
            },
            "human_construct_gate": {
                "decision": DECISION_PATH.as_posix(),
                "metrics": METRICS_PATH.as_posix(),
                "metrics_sha256": human_metrics_hash,
            },
            "power_boundary": {
                "source": "artifacts/construct_v2/multiplicity_power.yaml",
                "interpretation": "conditional downstream certification power only",
            },
            "open_audit_issues": {
                "source": "reports/construct_v2_open_audit_issues.yaml",
                "must_remain_public": True,
            },
        },
    }
    readiness = """# Direction P v2 preregistration candidate readiness

Decision: `CONSTRUCT_V2_READY_FOR_INDEPENDENT_PREREGISTRATION_AUDIT`.

The 0.8700–0.8862 range is Stable Path downstream certification power conditional
on construct validity, human construct validity, measurement integrity, and uptake
eligibility. It is not complete end-to-end Pilot power. The simulation does not
estimate the probability that a real model passes all four task-specific uptake
gates. Uptake failure is an independent preceding stopping event, so complete
end-to-end success probability may be below 0.8700. This limitation changes neither
N=1280, uptake N=256, delta0=0.10, delta1=0.15, nor the existing simulation results.

Natural language remains primary; triples remains robustness only; Path B has no GO
authority. Human PASS authorizes only this candidate and a new independent
preregistration audit. The runner and VLM inference remain blocked.
"""
    source_copies = {
        "identity.md": "research/construct_restart/v2_identity.md",
        "construct_definition.yaml": "research/construct_restart/v2_construct_definition.yaml",
        "causal_scope.md": "research/construct_restart/v2_causal_graph.md",
        "estimands.yaml": "research/construct_restart/v2_estimands.yaml",
        "hypothesis_registry.yaml": "research/construct_restart/v2_hypothesis_registry.yaml",
        "model_registry.yaml": "configs/construct_v2/models.yaml",
        "uptake_policy.yaml": "configs/construct_v2/uptake.yaml",
        "go_no_go.yaml": "research/construct_restart/v2_go_no_go.yaml",
        "deviation_policy.yaml": "research/construct_restart/v2_deviation_policy.yaml",
        "novelty_boundary.md": "research/construct_restart/v2_novelty_boundary.md",
    }
    payloads = {
        PACKAGE_ROOT / name: (root / source).read_bytes()
        for name, source in source_copies.items()
    }
    payloads.update(
        {
            PACKAGE_ROOT / "master_protocol.yaml": _yaml_bytes(master),
            PACKAGE_ROOT / "measurement_policy.yaml": _yaml_bytes(measurement),
            PACKAGE_ROOT / "p3_method_lock.yaml": _yaml_bytes(p3_lock),
            PACKAGE_ROOT / "power_and_multiplicity.yaml": _yaml_bytes(power_lock),
            PACKAGE_ROOT / "human_review_lock.yaml": _yaml_bytes(human_lock),
            PACKAGE_ROOT / "execution_boundary.yaml": _yaml_bytes(execution),
            REPORT_PATHS[2]: readiness.encode("utf-8"),
            REPORT_PATHS[3]: _yaml_bytes(candidate_decision),
            REPORT_PATHS[4]: _yaml_bytes(evidence_map),
            REPORT_PATHS[5]: _yaml_bytes(_open_audit_issues()),
        }
    )
    return payloads


def _write_new(path: Path, content: bytes) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite candidate artifact: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def build_construct_v2_preregistration_candidate(root: Path = ROOT) -> dict[str, Any]:
    """Create the complete candidate only after deterministic HUMAN PASS."""
    root = root.resolve()
    adjudication = adjudicate_construct_v2_human_review(root)
    if adjudication.get("decision") != READY:
        return {
            "status": "BLOCKED_BY_HUMAN_DECISION",
            "human_decision": adjudication.get("decision"),
            "candidate_created": False,
            "runner_authorized": False,
            "scientific_inference_authorized": False,
        }
    schema = _validate_schema(root)
    if schema["failures"]:
        return {
            "status": "BLOCKED_BY_CANDIDATE_SCHEMA_FAILURE",
            "failures": schema["failures"],
            "candidate_created": False,
        }
    verify_external_review_packages(root)
    no_inference = _no_inference_state(root)
    if no_inference["status"] != "PASS":
        return {
            "status": "BLOCKED_BY_NO_INFERENCE_BOUNDARY",
            "no_inference": no_inference,
            "candidate_created": False,
        }
    policy_freeze_commit = _tag_target(root, POLICY_FREEZE_TAG)
    if policy_freeze_commit is None:
        return {
            "status": "BLOCKED_BY_MISSING_POLICY_FREEZE_TAG",
            "candidate_created": False,
        }
    tag_failures = [
        f"{tag} target changed"
        for tag, commit in HISTORICAL_TAGS.items()
        if _tag_target(root, tag) != commit
    ]
    if tag_failures:
        return {
            "status": "BLOCKED_BY_HISTORICAL_TAG_FAILURE",
            "failures": tag_failures,
            "candidate_created": False,
        }
    collisions = [path.as_posix() for path in _candidate_paths() if (root / path).exists()]
    allowed_existing = {REPORT_PATH.as_posix(), DECISION_PATH.as_posix()}
    unexpected = [path for path in collisions if path not in allowed_existing]
    if unexpected:
        return {
            "status": "BLOCKED_BY_EXISTING_CANDIDATE_FILES",
            "files": unexpected,
            "candidate_created": False,
        }

    payloads = _candidate_payloads(root, policy_freeze_commit)
    for relative, content in payloads.items():
        _write_new(root / relative, content)
    protected_paths = tuple(PACKAGE_ROOT / name for name in PACKAGE_NAMES) + REPORT_PATHS
    protected = {
        "schema_version": 1,
        "protocol_id": PROTOCOL_ID,
        "decision": READY,
        "protected_files": [path.as_posix() for path in protected_paths],
        "post_result_deletion_or_replacement": "forbidden",
    }
    protected_bytes = _yaml_bytes(protected)
    _write_new(root / ARTIFACT_PATHS[1], protected_bytes)
    hashes = {path.as_posix(): _sha256(root / path) for path in protected_paths}
    hashes[ARTIFACT_PATHS[1].as_posix()] = _sha256_bytes(protected_bytes)
    manifest = {
        "schema_version": 1,
        "protocol_id": PROTOCOL_ID,
        "decision": READY,
        "file_count": len(hashes),
        "files": hashes,
        "aggregate_sha256": hashlib.sha256(
            json.dumps(hashes, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
        "policy_freeze_tag": POLICY_FREEZE_TAG,
        "policy_freeze_commit": policy_freeze_commit,
        "automated_freeze_tag": AUTOMATED_FREEZE_TAG,
        "automated_freeze_commit": AUTOMATED_FREEZE_COMMIT,
        "candidate_tag_created": False,
        "scientific_inference_authorized": False,
    }
    _write_new(root / ARTIFACT_PATHS[0], _yaml_bytes(manifest))
    pending_verification = {
        "schema_version": 1,
        "protocol_id": PROTOCOL_ID,
        "status": "PENDING_CANDIDATE_VERIFICATION",
        "runner_authorized": False,
        "scientific_inference_authorized": False,
    }
    _write_new(root / ARTIFACT_PATHS[2], _yaml_bytes(pending_verification))
    return {
        "status": "CANDIDATE_CREATED",
        "decision": READY,
        "candidate_created": True,
        "file_count": len(_candidate_paths()),
        "manifest_sha256": _sha256(root / ARTIFACT_PATHS[0]),
        "runner_authorized": False,
        "scientific_inference_authorized": False,
        "candidate_tag_created": False,
    }


def verify_construct_v2_preregistration_candidate(root: Path = ROOT) -> dict[str, Any]:
    """Verify every candidate lock without authorizing execution or inference."""
    root = root.resolve()
    failures: list[str] = []
    adjudication = adjudicate_construct_v2_human_review(root)
    if adjudication.get("decision") != READY:
        failures.append("human decision is not PASS")
    failures.extend(_validate_schema(root)["failures"])
    expected = _candidate_paths()
    missing = [path.as_posix() for path in expected if not (root / path).is_file()]
    failures.extend(f"candidate file missing: {path}" for path in missing)
    if missing:
        return {"status": "FAIL", "failures": failures, "decision": None}
    try:
        verify_external_review_packages(root)
    except (ReviewInfrastructureError, OSError, KeyError, TypeError, yaml.YAMLError) as exc:
        failures.append(f"external review package verification failed: {exc}")
    manifest = _load_yaml(root / ARTIFACT_PATHS[0])
    protected = _load_yaml(root / ARTIFACT_PATHS[1])
    if manifest.get("decision") != READY or protected.get("decision") != READY:
        failures.append("candidate manifest or protected-file decision mismatch")
    files = manifest.get("files", {})
    if manifest.get("file_count") != len(files):
        failures.append("candidate manifest file count mismatch")
    for relative, expected_hash in files.items():
        path = root / relative
        if not path.is_file() or _sha256(path) != expected_hash:
            failures.append(f"candidate hash mismatch: {relative}")
    aggregate = hashlib.sha256(
        json.dumps(files, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    if manifest.get("aggregate_sha256") != aggregate:
        failures.append("candidate aggregate hash mismatch")
    protected_expected = [
        path.as_posix()
        for path in tuple(PACKAGE_ROOT / name for name in PACKAGE_NAMES) + REPORT_PATHS
    ]
    if protected.get("protected_files") != protected_expected:
        failures.append("candidate protected file list mismatch")

    decision = _load_yaml(root / REPORT_PATHS[3])
    master = _load_yaml(root / PACKAGE_ROOT / "master_protocol.yaml")
    p3_lock = _load_yaml(root / PACKAGE_ROOT / "p3_method_lock.yaml")
    power = _load_yaml(root / PACKAGE_ROOT / "power_and_multiplicity.yaml")
    human_lock = _load_yaml(root / PACKAGE_ROOT / "human_review_lock.yaml")
    if decision.get("decision") != READY:
        failures.append("candidate decision is not exactly READY_FOR_INDEPENDENT_AUDIT")
    if master.get("protocol_id") != PROTOCOL_ID or master.get("candidate_status") != READY:
        failures.append("candidate master protocol mismatch")
    if master.get("external_review_gate_commit") != EXTERNAL_REVIEW_GATE_COMMIT:
        failures.append("candidate external review gate commit mismatch")
    if master.get("automated_freeze", {}) != {
        "commit": AUTOMATED_FREEZE_COMMIT,
        "annotated_tag": AUTOMATED_FREEZE_TAG,
    }:
        failures.append("candidate automated freeze lock mismatch")
    for tag, commit in HISTORICAL_TAGS.items():
        if _tag_target(root, tag) != commit:
            failures.append(f"historical tag moved: {tag}")
    policy_freeze_commit = _tag_target(root, POLICY_FREEZE_TAG)
    if policy_freeze_commit is None or master.get("human_gate_policy_freeze", {}).get(
        "commit"
    ) != policy_freeze_commit:
        failures.append("human-gate policy freeze tag mismatch")
    for relative, expected_hash in p3_lock.get("source_file_hashes", {}).items():
        path = root / relative
        if not path.is_file() or _normalized_text_sha256(path) != expected_hash:
            failures.append(f"P3 hash changed: {relative}")
    if p3_lock.get("delta0") != 0.10 or p3_lock.get("delta1") != 0.15:
        failures.append("P3 delta lock changed")
    if (
        power.get("reasoning_n") != 1280
        or power.get("uptake_n") != 256
        or power.get("delta0") != 0.10
        or power.get("delta1") != 0.15
        or power.get("primary_serialization") != "natural_language"
        or power.get("triples_role") != "robustness_only"
        or power.get("path_b_go_authority") is not False
    ):
        failures.append("candidate primary N, delta, serialization, or Path B lock changed")
    expected_uptake_tasks = [
        "visual_hop_relation",
        "textual_bridge_relation",
        "direction_reversal",
        "cross_modal_bridge_binding",
    ]
    if master.get("design_locks", {}).get("uptake_tasks") != expected_uptake_tasks:
        failures.append("candidate four task-specific uptake gates changed")
    conditional = power.get("stable_path_downstream_certification_power", {})
    if (
        conditional.get("is_complete_end_to_end_pilot_power") is not False
        or conditional.get("real_model_four_uptake_gate_pass_probability_estimated") is not False
        or conditional.get("uptake_failure_is_independent_preceding_stopping_event") is not True
        or conditional.get("complete_end_to_end_success_probability_may_be_below_0_8700")
        is not True
    ):
        failures.append("candidate power boundary is not conditional on uptake eligibility")

    commitment = _load_yaml(root / PUBLIC_COMMITMENT)
    metrics = _load_yaml(root / METRICS_PATH)
    evidence = metrics.get("evidence_hashes", {})
    if human_lock.get("human_metrics_sha256") != _sha256(root / METRICS_PATH):
        failures.append("candidate human metrics hash mismatch")
    if human_lock.get("reviewer_attestations_sha256") != evidence.get(
        "reviewer_attestations"
    ):
        failures.append("candidate reviewer attestations hash mismatch")
    if human_lock.get("aligned_review_sha256") != evidence.get("aligned_reviews_sha256"):
        failures.append("candidate aligned review hash mismatch")
    if human_lock.get("disagreement_file_sha256") != evidence.get("disagreements_sha256"):
        failures.append("candidate disagreement hash mismatch")
    for label, spec in commitment.get("bundles", {}).items():
        if master.get("external_review", {}).get("bundle_sha256", {}).get(label) != spec.get(
            "sha256"
        ):
            failures.append(f"candidate bundle commitment mismatch: {label}")
        if master.get("external_review", {}).get("mapping_commitments", {}).get(
            label
        ) != spec.get("mapping_sha256_commitment"):
            failures.append(f"candidate mapping commitment mismatch: {label}")
    issues = _load_yaml(root / REPORT_PATHS[5])
    template = _load_yaml(root / TEMPLATES_PATH)
    if [item.get("id") for item in issues.get("issues", [])] != template.get(
        "open_issue_ids"
    ):
        failures.append("required open audit issues changed or were deleted")

    no_inference = _no_inference_state(root)
    if no_inference["status"] != "PASS":
        failures.append("scientific output, runner authorization, or execution authorization detected")
    if manifest.get("candidate_tag_created") is not False:
        failures.append("candidate builder recorded a candidate tag")
    verification = {
        "schema_version": 1,
        "protocol_id": PROTOCOL_ID,
        "status": "PASS" if not failures else "FAIL",
        "decision": READY if not failures else None,
        "failures": failures,
        "manifest_sha256": _sha256(root / ARTIFACT_PATHS[0]),
        "human_decision": adjudication.get("decision"),
        "historical_tags": {
            tag: _tag_target(root, tag) for tag in (*HISTORICAL_TAGS, POLICY_FREEZE_TAG)
        },
        "no_inference": no_inference,
        "runner_authorized": False,
        "execution_authorization_created": False,
        "candidate_tag_created": False,
    }
    (root / ARTIFACT_PATHS[2]).write_bytes(_yaml_bytes(verification))
    return verification
