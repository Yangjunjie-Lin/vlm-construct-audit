from __future__ import annotations

import subprocess
import sys


def test_required_cli_commands_are_exposed() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "vlm_construct_audit", "--help"],
        check=True,
        capture_output=True,
        text=True,
    )
    for command in (
        "validate-config", "generate-data", "validate-equivalence", "run-calibration",
        "run-smoke", "run-pilot", "analyze", "audit-claims", "build-evidence-map",
        "build-report", "verify-artifacts",
        "run-loop-a", "run-loop-b", "run-loop-c", "adjudicate-tier0-5",
        "validate-p-mini-pilot-preregistration", "verify-p-mini-pilot-preregistration",
        "verify-no-p-mini-pilot-inference", "run-p-mini-pilot",
        "retire-p-mini-pilot-v1",
        "generate-construct-v2", "validate-construct-v2",
        "audit-construct-v2-leakage", "run-construct-v2-oracles",
        "analyze-construct-v2-power", "build-construct-v2-review-packet",
        "verify-no-construct-v2-inference", "build-construct-v2-report",
    ):
        assert command in result.stdout


def test_scientific_pilot_fails_closed() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "vlm_construct_audit", "run-pilot"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "NOT_AUTHORIZED" in result.stdout
    assert "no_inference_started: true" in result.stdout


def test_p_mini_pilot_is_permanently_retired() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "vlm_construct_audit", "run-p-mini-pilot"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "V1_SCIENTIFIC_EXECUTION_PERMANENTLY_FORBIDDEN" in result.stdout
    assert "no_inference_started: true" in result.stdout
