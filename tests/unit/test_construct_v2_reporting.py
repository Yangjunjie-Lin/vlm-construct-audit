from __future__ import annotations

from pathlib import Path

import yaml

from vlm_construct_audit.construct_v2.reporting import build_construct_v2_report

ROOT = Path(__file__).resolve().parents[2]


def test_all_construct_restart_yaml_is_machine_readable() -> None:
    files = list((ROOT / "research/construct_restart").glob("*.yaml"))
    assert files
    for path in files:
        assert yaml.safe_load(path.read_text(encoding="utf-8")) is not None


def test_automated_report_passes_but_stops_at_external_review() -> None:
    result = build_construct_v2_report()
    assert result["status"] == "PENDING_EXTERNAL_CONSTRUCT_REVIEW"
    assert result["automated_gate"] == "PASS"
    assert result["chosen_reasoning_n"] == 1280
    assert result["human_reviewers_completed"] == 0
    assert result["scientific_model_output_count"] == 0
    automated = yaml.safe_load(
        (ROOT / "reports/construct_v2_automated_gate.yaml").read_text(encoding="utf-8")
    )
    assert all(automated["gates"].values())
    assert automated["formal_vlm_inference_run"] is False
