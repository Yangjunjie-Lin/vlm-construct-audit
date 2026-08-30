import hashlib
from pathlib import Path

from vlm_construct_audit.final_closeout import (
    RELEASE_ROOT,
    audit_final_review_integrity,
    build_final_negative_evidence_release,
)


def test_final_review_integrity_audit_is_non_rescue_and_reproducible() -> None:
    result = audit_final_review_integrity()
    independence = result["reviewer_independence"]
    assert result["review_integrity_classification"] == "REVIEW_INTEGRITY_INCONCLUSIVE"
    assert result["scientific_action"] == "TERMINATE_DIRECTION_P"
    assert result["attestations"]["reviewer_1"][
        "attestation_internal_identity_consistency"
    ] == "FAIL"
    assert independence["identical_classification_judgments"] == 880
    assert independence["reviewer_notes_verbatim_matches"] == 80
    assert {row["decoy_type"] for row in independence["shared_missed_decoys"]} == {
        "second_hop_visually_represented"
    }
    assert result["decoy_construction"]["overall_classification"] == "DECOY_VALID"
    assert result["rescue_authority"] is False


def test_negative_evidence_release_checksums_match() -> None:
    result = build_final_negative_evidence_release()
    assert result["decision"] == "TERMINATE_SUCCESSOR_PROGRAM"
    release = Path(__file__).resolve().parents[2] / RELEASE_ROOT
    lines = (release / "checksums.sha256").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 10
    for line in lines:
        expected, name = line.split("  ", 1)
        assert hashlib.sha256((release / name).read_bytes()).hexdigest() == expected
