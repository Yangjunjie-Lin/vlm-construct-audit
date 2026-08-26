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
