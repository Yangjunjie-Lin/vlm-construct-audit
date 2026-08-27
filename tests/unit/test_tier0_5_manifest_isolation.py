from __future__ import annotations

from vlm_construct_audit.reporting.builder import build_artifact_manifest


def test_tier0_manifest_excludes_tier0_5_self_referential_manifests() -> None:
    manifest = build_artifact_manifest()
    paths = {item["path"] for item in manifest["artifacts"]}
    assert "artifacts/manifests/tier0_5_artifact_manifest.yaml" not in paths
    assert "artifacts/manifests/tier0_5_verification_report.yaml" not in paths
    assert "reports/tier0_5_three_loop_report.md" not in paths
    assert "reports/loop_a_decision.yaml" not in paths
