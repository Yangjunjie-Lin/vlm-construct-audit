from __future__ import annotations

from vlm_construct_audit.reporting import builder


def test_tier0_manifest_excludes_tier0_5_self_referential_manifests(monkeypatch) -> None:
    monkeypatch.setattr(builder, "dump_yaml", lambda *_args, **_kwargs: None)
    manifest = builder.build_artifact_manifest()
    paths = {item["path"] for item in manifest["artifacts"]}
    assert "artifacts/manifests/tier0_5_artifact_manifest.yaml" not in paths
    assert "artifacts/manifests/tier0_5_verification_report.yaml" not in paths
    assert "reports/tier0_5_three_loop_report.md" not in paths
    assert "reports/loop_a_decision.yaml" not in paths
