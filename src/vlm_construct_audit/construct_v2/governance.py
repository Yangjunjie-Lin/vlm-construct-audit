"""Fail-closed governance for the construct-invalid v1 protocol."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[3]
RETIREMENT_PATH = ROOT / "research/construct_restart/v1_retirement.yaml"


def retire_v1() -> dict[str, Any]:
    """Verify and report the immutable v1 retirement declaration.

    The command is intentionally non-mutating. The declaration is versioned in
    Git, and this function refuses to reinterpret a missing or altered record.
    """

    record = yaml.safe_load(RETIREMENT_PATH.read_text(encoding="utf-8"))
    required = {
        "audit_decision": "AUDIT_FAIL_CONSTRUCT_VALIDITY",
        "scientific_inference_executed": False,
        "runner_authorized": False,
        "v1_scientific_execution_permanently_forbidden": True,
        "ordinary_amendment_allowed": False,
        "required_restart": "NEW_CONSTRUCT_NEW_DATA_NEW_PREREGISTRATION",
    }
    mismatches = {
        key: {"expected": expected, "observed": record.get(key)}
        for key, expected in required.items()
        if record.get(key) != expected
    }
    return {
        "status": "V1_RETIRED" if not mismatches else "INVALID_RETIREMENT_RECORD",
        "protocol": record.get("protocol"),
        "runner_forbidden": record.get("v1_scientific_execution_permanently_forbidden"),
        "scientific_inference_executed": record.get("scientific_inference_executed"),
        "ordinary_amendment_allowed": record.get("ordinary_amendment_allowed"),
        "mismatches": mismatches,
    }

