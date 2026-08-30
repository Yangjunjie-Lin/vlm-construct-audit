from __future__ import annotations

import csv
import hashlib
import io
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

from vlm_construct_audit.construct_v2 import adjudication, candidate, external_review
from vlm_construct_audit.construct_v2 import validation as construct_validation
from vlm_construct_audit.construct_v2.adjudication import INVALID, NO_GO, READY
from vlm_construct_audit.construct_v2.external_review import (
    JUDGMENTS,
    RESPONSE_FIELDS,
)
from vlm_construct_audit.construct_v2.runner_guard import verify_no_construct_v2_inference
from vlm_construct_audit.preregistration.frozen_snapshot import (
    FROZEN_PREREGISTRATION_COMMIT,
    verify_frozen_p_mini_pilot_preregistration_read_only,
)

ROOT = Path(__file__).resolve().parents[2]
BUNDLE_HASHES = {
    "reviewer_1": "c7c1547dfff6baf016d3a9882ce252af196b165c91a0fdf58e89b7025eb3e496",
    "reviewer_2": "f0dd40c5eab48c4f73f6bbddde33800165c18a4792389c7ea43c223529716697",
}
MAPPING_COMMITMENTS = {
    "reviewer_1": "71a48a2eae3ba87ec97a7e98ffbff3c749fbcf8cf62a886ea259e75595cdb96f",
    "reviewer_2": "442dd8a1e45ffd03ad7e7752a8499f8957f5885799320277b2bcf77ee450f79d",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_yaml(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(value, sort_keys=False), encoding="utf-8")


def _attestation(code: str, bundle_hash: str) -> dict[str, Any]:
    return {
        "reviewer_code": code,
        "is_real_human": True,
        "independent_of_dataset_authorship": True,
        "independent_of_generator_implementation": True,
        "did_not_consult_other_reviewer": True,
        "did_not_use_ai_or_automated_model": True,
        "did_not_access_repository": True,
        "did_not_access_hidden_key": True,
        "did_not_access_generator_code": True,
        "review_started_at": "2026-09-01T09:00:00+00:00",
        "review_completed_at": "2026-09-01T10:00:00+00:00",
        "bundle_sha256": bundle_hash,
        "signed_statement": f"Signed under code {code}",
    }


def _csv_bytes(rows: list[dict[str, Any]], fields: list[str]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\r\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8-sig")


def _make_import_fixture(
    root: Path,
    *,
    human_pass: bool = True,
    same_codes: bool = False,
    disagreement_count: int = 0,
) -> None:
    shutil.copytree(ROOT / "research", root / "research")
    commitment = {
        "schema_version": 1,
        "protocol_id": external_review.PROTOCOL_ID,
        "original_packet": {"sha256": "a" * 64},
        "frozen_hidden_key_sha256": "b" * 64,
        "bundles": {
            label: {
                "sha256": BUNDLE_HASHES[label],
                "mapping_sha256_commitment": MAPPING_COMMITMENTS[label],
            }
            for label in BUNDLE_HASHES
        },
    }
    _write_yaml(root / external_review.PUBLIC_COMMITMENT, commitment)
    results = root / external_review.RESULTS_DIR
    results.mkdir(parents=True)
    codes = {"reviewer_1": "HUMAN-A", "reviewer_2": "HUMAN-A" if same_codes else "HUMAN-B"}
    for label in ("reviewer_1", "reviewer_2"):
        (results / f"{label}_original.csv").write_bytes(b"review_id\r\nTEST\r\n")
        _write_yaml(results / f"{label}_attestation.yaml", _attestation(codes[label], BUNDLE_HASHES[label]))
        (results / f"revealed_mapping_{label}.json").write_text("{}\n", encoding="utf-8")
    aligned = [{"source_review_id": f"CVR-{index:03d}"} for index in range(80)]
    (results / "aligned_reviews.csv").write_bytes(_csv_bytes(aligned, ["source_review_id"]))
    disagreements = [
        {"source_review_id": f"CVR-{index:03d}", "field": JUDGMENTS[0]}
        for index in range(disagreement_count)
    ]
    (results / "disagreements.csv").write_bytes(
        _csv_bytes(disagreements, ["source_review_id", "field"])
    )
    _write_yaml(
        results / "field_metrics.yaml",
        {
            "schema_version": 1,
            "nominal_categories": ["yes", "no", "uncertain"],
            "uncertain_retained": True,
        },
    )
    gates = {
        "reviewer_count_2": True,
        "response_completeness_1_00": True,
        "attestation_validation_pass": not same_codes,
        "overall_agreement_ge_0_95": human_pass,
        "overall_nominal_cohen_kappa_ge_0_80": human_pass,
        "genuine_required_field_no_count_0": True,
        "genuine_required_field_uncertain_count_0": True,
        "genuine_critical_error_yes_or_uncertain_count_0": True,
        "minimum_reviewer_decoy_detection_ge_0_90": True,
        "deleted_disagreements_0": True,
        "model_or_agent_review_used_false": True,
    }
    evidence = {
        "original_packet_sha256": "a" * 64,
        "hidden_key_sha256": "b" * 64,
        "original_returns": {
            label: _sha256(results / f"{label}_original.csv")
            for label in ("reviewer_1", "reviewer_2")
        },
        "reviewer_attestations": {
            label: _sha256(results / f"{label}_attestation.yaml")
            for label in ("reviewer_1", "reviewer_2")
        },
        "aligned_reviews_sha256": _sha256(results / "aligned_reviews.csv"),
        "disagreements_sha256": _sha256(results / "disagreements.csv"),
    }
    metrics = {
        "schema_version": 1,
        "protocol_id": external_review.PROTOCOL_ID,
        "status": "HUMAN_CONSTRUCT_REVIEW_PASS" if human_pass and not same_codes else "HUMAN_CONSTRUCT_REVIEW_FAIL",
        "reviewer_count": 2,
        "reviewer_codes": codes,
        "bundle_hashes": BUNDLE_HASHES,
        "mapping_commitments": MAPPING_COMMITMENTS,
        "mapping_commitment_verified": True,
        "packet_hash_verified": True,
        "response_completeness": 1.0,
        "evidence_hashes": evidence,
        "overall_agreement": 0.99 if human_pass else 0.90,
        "overall_cohen_kappa": 0.90 if human_pass else 0.70,
        "per_field_agreement": {field: 1.0 for field in JUDGMENTS},
        "per_field_kappa": {field: 0.90 for field in JUDGMENTS},
        "uncertain_count": {
            "reviewer_1": 0,
            "reviewer_2": 0,
            "total": 0,
            "per_field": {field: 0 for field in JUDGMENTS},
        },
        "genuine_required_field_failures": {
            "no_count": 0,
            "uncertain_count": 0,
            "total": 0,
            "affected_item_count": 0,
        },
        "genuine_critical_errors": {
            "yes_count": 0,
            "uncertain_count": 0,
            "total": 0,
            "affected_item_count": 0,
        },
        "reviewer_decoy_detection": {
            label: {
                "reviewer_code": codes[label],
                "detected": 16,
                "total": 16,
                "rate": 1.0,
            }
            for label in ("reviewer_1", "reviewer_2")
        },
        "minimum_decoy_detection": 1.0,
        "disagreement_count": disagreement_count,
        "deleted_disagreements": 0,
        "agent_or_model_review_used": False,
        "reviewer_independence_attested": True,
        "gates": gates,
    }
    _write_yaml(results / "human_construct_review_metrics.yaml", metrics)
    imported_names = (
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
    import_manifest = {
        "schema_version": 1,
        "protocol_id": external_review.PROTOCOL_ID,
        "mode": "IMMUTABLE_IMPORT_EVIDENCE",
        "files": {
            (external_review.RESULTS_DIR / name).as_posix(): _sha256(results / name)
            for name in imported_names
        },
        "candidate_created": False,
        "execution_authorization_created": False,
    }
    _write_yaml(results / "import_manifest.yaml", import_manifest)


def _copy_candidate_sources(root: Path) -> None:
    paths = (
        "configs/construct_v2/models.yaml",
        "configs/construct_v2/uptake.yaml",
        "artifacts/construct_v2/multiplicity_power.yaml",
        "src/vlm_construct_audit/post_stop/direction_p.py",
    )
    for relative in paths:
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)


def _patch_package_verifiers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(adjudication, "verify_external_review_packages", lambda _root: {})
    monkeypatch.setattr(candidate, "verify_external_review_packages", lambda _root: {})


def _patch_tags(monkeypatch: pytest.MonkeyPatch) -> None:
    def target(_root: Path, tag: str) -> str | None:
        if tag == candidate.POLICY_FREEZE_TAG:
            return "f" * 40
        return candidate.HISTORICAL_TAGS.get(tag)

    monkeypatch.setattr(candidate, "_tag_target", target)


def test_one_return_never_deblinds(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(external_review, "verify_external_review_packages", lambda _root: {})
    monkeypatch.setattr(
        external_review,
        "pending_external_review_status",
        lambda _root: {"status": external_review.PENDING_STATUS, "mapping_revealed": False},
    )
    returns = tmp_path / external_review.PRIVATE_RETURN_DIR
    returns.mkdir(parents=True)
    (returns / "reviewer_1_responses.csv").write_text("review_id\n", encoding="utf-8")
    result = external_review.import_external_review_returns(tmp_path)
    assert result["status"] == external_review.PENDING_STATUS
    assert result["mapping_revealed"] is False
    assert len(result["missing_return_files"]) == 3


def test_attestation_missing_field_and_bundle_mismatch_fail() -> None:
    value = _attestation("HUMAN-A", BUNDLE_HASHES["reviewer_1"])
    value.pop("did_not_access_hidden_key")
    content = yaml.safe_dump(value).encode()
    _, failures = external_review._validate_attestation(content, BUNDLE_HASHES["reviewer_1"])
    assert "attestation fields do not exactly match frozen schema" in failures
    assert "did_not_access_hidden_key is not true" in failures
    value = _attestation("HUMAN-A", "0" * 64)
    _, failures = external_review._validate_attestation(
        yaml.safe_dump(value).encode(), BUNDLE_HASHES["reviewer_1"]
    )
    assert "bundle_sha256 mismatch" in failures


def test_unknown_and_duplicate_opaque_ids_fail() -> None:
    ids = {f"R1-{index:06d}" for index in range(80)}
    rows = []
    for review_id in sorted(ids):
        row = {field: "yes" for field in JUDGMENTS}
        row.update({"review_id": review_id, "reviewer_notes": "none"})
        rows.append(row)
    rows[0]["review_id"] = "R1-UNKNOWN"
    rows[1]["review_id"] = rows[2]["review_id"]
    _, failures = external_review._validate_responses(
        _csv_bytes(rows, list(RESPONSE_FIELDS)), ids
    )
    assert "unknown opaque review ID" in failures
    assert "duplicate opaque review ID" in failures


def test_uncertain_remains_third_category_and_disagreement_is_preserved(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert external_review._cohen_kappa(
        ["yes", "no", "uncertain"], ["yes", "uncertain", "uncertain"]
    ) == pytest.approx(0.5)
    _make_import_fixture(tmp_path, disagreement_count=1)
    _patch_package_verifiers(monkeypatch)
    decision = adjudication.adjudicate_construct_v2_human_review(tmp_path)
    assert decision["decision"] == READY
    metrics = yaml.safe_load((tmp_path / adjudication.METRICS_PATH).read_text())
    assert metrics["deleted_disagreements"] == 0
    assert metrics["disagreement_count"] == 1
    assert (tmp_path / external_review.RESULTS_DIR / "disagreements.csv").is_file()


def test_same_reviewer_codes_and_mapping_commitment_mismatch_are_invalid(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _make_import_fixture(tmp_path, same_codes=True)
    _patch_package_verifiers(monkeypatch)
    result = adjudication.adjudicate_construct_v2_human_review(tmp_path)
    assert result["decision"] == INVALID

    other = tmp_path / "mapping-mismatch"
    _make_import_fixture(other)
    metrics_path = other / adjudication.METRICS_PATH
    metrics = yaml.safe_load(metrics_path.read_text())
    metrics["mapping_commitments"]["reviewer_1"] = "0" * 64
    _write_yaml(metrics_path, metrics)
    manifest_path = other / adjudication.IMPORT_MANIFEST_PATH
    manifest = yaml.safe_load(manifest_path.read_text())
    manifest["files"][adjudication.METRICS_PATH.as_posix()] = _sha256(metrics_path)
    _write_yaml(manifest_path, manifest)
    result = adjudication.adjudicate_construct_v2_human_review(other)
    assert result["decision"] == INVALID
    assert any("mapping commitments mismatch" in item for item in result["validation_failures"])


def test_manual_metrics_modification_is_invalid(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _make_import_fixture(tmp_path)
    _patch_package_verifiers(monkeypatch)
    metrics_path = tmp_path / adjudication.METRICS_PATH
    metrics_path.write_bytes(metrics_path.read_bytes() + b"\n# manual modification\n")
    result = adjudication.adjudicate_construct_v2_human_review(tmp_path)
    assert result["decision"] == INVALID
    assert any("hash mismatch" in item for item in result["validation_failures"])


def test_human_no_go_is_terminal_and_candidate_is_not_created(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _make_import_fixture(tmp_path, human_pass=False)
    _patch_package_verifiers(monkeypatch)
    result = adjudication.adjudicate_construct_v2_human_review(tmp_path)
    assert result["decision"] == NO_GO
    assert result["exact_next_action"] == "TERMINATE_DIRECTION_P"
    built = candidate.build_construct_v2_preregistration_candidate(tmp_path)
    assert built["candidate_created"] is False
    assert not (tmp_path / candidate.PACKAGE_ROOT).exists()
    assert not (tmp_path / candidate.ARTIFACT_ROOT).exists()


def test_human_pass_builds_candidate_but_keeps_runner_and_authorizations_blocked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _make_import_fixture(tmp_path, disagreement_count=1)
    _copy_candidate_sources(tmp_path)
    _patch_package_verifiers(monkeypatch)
    _patch_tags(monkeypatch)
    adjudicated = adjudication.adjudicate_construct_v2_human_review(tmp_path)
    assert adjudicated["decision"] == READY
    built = candidate.build_construct_v2_preregistration_candidate(tmp_path)
    assert built["status"] == "CANDIDATE_CREATED"
    verified = candidate.verify_construct_v2_preregistration_candidate(tmp_path)
    assert verified["status"] == "PASS"
    assert verified["decision"] == READY
    assert verified["no_inference"]["runner_blocked"] is True
    assert verified["no_inference"]["authorization_files"] == 0
    assert verified["no_inference"]["formal_predictions"] == 0
    assert verified["no_inference"]["uptake_outputs"] == 0
    assert verified["no_inference"]["reasoning_outputs"] == 0
    assert verified["no_inference"]["scientific_metrics"] == 0
    human_lock = yaml.safe_load(
        (tmp_path / candidate.PACKAGE_ROOT / "human_review_lock.yaml").read_text()
    )
    assert human_lock["disagreements_preserved"] is True
    assert human_lock["uncertain_retained"] is True
    assert not any((tmp_path / path).exists() for path in adjudication.AUTHORIZATION_PATHS)


def test_frozen_bundles_tags_recoalign_boundary_and_no_inference() -> None:
    commitment = yaml.safe_load((ROOT / external_review.PUBLIC_COMMITMENT).read_text())
    for label, expected in BUNDLE_HASHES.items():
        assert _sha256(ROOT / "external_review_packages" / f"{label}_bundle.zip") == expected
        assert commitment["bundles"][label]["sha256"] == expected
    for tag, expected in candidate.HISTORICAL_TAGS.items():
        target = subprocess.run(
            ["git", "rev-parse", "--verify", f"{tag}^{{commit}}"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        assert target == expected
    frozen = verify_frozen_p_mini_pilot_preregistration_read_only()
    assert frozen["status"] == "PASS"
    assert frozen["peeled_commit"] == FROZEN_PREREGISTRATION_COMMIT
    historical = yaml.safe_load(
        subprocess.run(
            ["git", "show", "p-mini-pilot-preregistered:reports/post_stop_final_decision.yaml"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    )
    assert historical["recoalign_modified"] is False
    no_inference = verify_no_construct_v2_inference()
    assert no_inference["status"] == "PASS"
    assert no_inference["formal_prediction_files"] == 0


def test_construct_validator_declares_frozen_tokenizer_runtime() -> None:
    project = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert '"transformers==4.49.0"' in project
    registry = yaml.safe_load((ROOT / "configs/p_mini_pilot_models.yaml").read_text())
    assert registry["transformers_version"] == "4.49.0"
    assert {model["transformers_version"] for model in registry["models"]} == {"4.49.0"}


def test_clean_ci_tokenizer_fallback_is_tag_scoped_and_read_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = construct_validation._read_jsonl("data/construct_v2/reasoning_test.jsonl")
    result = construct_validation._verify_frozen_token_balance_read_only(
        rows, fallback_reason="test clean CI cache miss"
    )
    assert result["status"] == "PASS"
    assert result["verification_mode"] == "READ_ONLY_AUTOMATED_FREEZE_TAG_SNAPSHOT"
    assert result["tracked_artifact_modified"] is False
    monkeypatch.setattr(construct_validation, "AUTOMATED_FREEZE_COMMIT", "0" * 40)
    result = construct_validation._verify_frozen_token_balance_read_only(
        rows, fallback_reason="test moved tag"
    )
    assert result["status"] == "FAIL"
    assert "automated preaudit freeze tag target mismatch" in result["failures"]
