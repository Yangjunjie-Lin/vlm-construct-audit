from __future__ import annotations

import subprocess

import pytest

from vlm_construct_audit.construct_v2.generator import build_reasoning_rows
from vlm_construct_audit.construct_v2.runner_guard import (
    BLOCKED_STATUS,
    ConstructV2Runner,
    verify_no_construct_v2_inference,
)


def test_v1_and_audit_tags_remain_at_frozen_commits() -> None:
    v1 = subprocess.run(
        ["git", "rev-parse", "p-mini-pilot-preregistered^{}"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    audit = subprocess.run(
        ["git", "rev-parse", "p-mini-pilot-preregistration-audit-no-pass^{}"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert v1 == "9de60b87ec54bc852a7bb2e9cff87d9c23638042"
    assert audit == "97c64947a0e6b30b0c9a0654519bbd93ae37d846"


def test_prompt_excludes_all_internal_identifiers() -> None:
    scene = build_reasoning_rows(24, split="engineering_smoke")[0]
    prompt = ConstructV2Runner().build_prompt(
        scene, condition="correct", serialization="natural_language"
    )
    visible = str(prompt)
    assert scene["scene_uuid"] not in visible
    assert scene["internal_scene_id"] not in visible
    assert all(entity["entity_uuid"] not in visible for entity in scene["entities"])


def test_formal_runner_fails_closed_without_both_authorizations() -> None:
    runner = ConstructV2Runner()
    assert runner.validate_authorization()["status"] == BLOCKED_STATUS
    with pytest.raises(PermissionError):
        runner.run_formal_uptake()
    with pytest.raises(PermissionError):
        runner.run_formal_reasoning()


def test_no_v2_scientific_outputs_exist() -> None:
    result = verify_no_construct_v2_inference()
    assert result["status"] == "PASS"
    assert result["formal_prediction_files"] == 0
    assert result["uptake_model_outputs"] == 0
    assert result["reasoning_model_outputs"] == 0
    assert result["scientific_metrics"] == 0
    assert result["runner_blocked"] is True

