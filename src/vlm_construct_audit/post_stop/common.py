"""Shared immutable-boundary and artifact helpers for post-STOP work."""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[3]
STOP_COMMIT = "ce0e797a4926ab5d2309915c2eef14fd9c5be44d"
STOP_TAG = "vlm-construct-audit-tier0-5-stop"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_yaml(path: str | Path) -> dict[str, Any]:
    return yaml.safe_load((ROOT / path).read_text(encoding="utf-8"))


def dump_yaml(path: str | Path, value: Any) -> None:
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(yaml.safe_dump(value, sort_keys=False, allow_unicode=True), encoding="utf-8")


def write_jsonl(path: str | Path, rows: list[dict[str, Any]]) -> None:
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")


def canonical_hash(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(raw).hexdigest()


def sha256_file(path: str | Path) -> str:
    target = ROOT / path
    digest = hashlib.sha256()
    with target.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def assert_historical_freeze() -> dict[str, Any]:
    tag_target = git("rev-parse", f"{STOP_TAG}^{{commit}}")
    if tag_target != STOP_COMMIT:
        raise RuntimeError(f"immutable tag mismatch: {tag_target}")
    decision = load_yaml("reports/tier0_5_final_decision.yaml")
    expected = {
        "decision": "STOP_FOR_METHOD_FAILURE",
        "loop_a": "LOOP_A_NO_GO",
        "loop_b_automated": "GO",
        "loop_b_human": "PENDING",
        "loop_c": "LOOP_C_NO_GO",
        "three_model_scientific_pilot": "NOT_AUTHORIZED",
        "exact_next_action": "STOP_FOR_METHOD_FAILURE",
    }
    mismatches = {key: decision.get(key) for key, value in expected.items() if decision.get(key) != value}
    holdout = load_yaml("artifacts/loop_a/holdout/summary.yaml")
    if holdout.get("holdout_execution_count") != 1 or not holdout.get("holdout_rerun_forbidden"):
        mismatches["old_loop_a_holdout"] = "not irreversibly closed"
    if mismatches:
        raise RuntimeError(f"historical state mismatch: {mismatches}")
    protected = [
        "reports/tier0_5_three_loop_report.md",
        "reports/tier0_5_final_decision.yaml",
        "artifacts/loop_a/holdout/summary.yaml",
        "artifacts/loop_b/measurement_metrics.yaml",
        "artifacts/loop_c/decision.yaml",
        "src/vlm_construct_audit/triage/audit_v2.py",
    ]
    return {
        "schema_version": 1,
        "verified_at": utc_now(),
        "status": "PASS",
        "stop_tag": STOP_TAG,
        "stop_tag_target": tag_target,
        "historical_state": expected,
        "old_holdout_rerun": "FORBIDDEN",
        "protected_sha256": {path: sha256_file(path) for path in protected},
        "recoalign_write_performed": False,
    }


def freeze_post_stop() -> dict[str, Any]:
    result = assert_historical_freeze()
    dump_yaml("artifacts/post_stop/freeze_verification.yaml", result)
    from .direction_p import write_analytic_power_documents

    power = write_analytic_power_documents()
    return {"status": "POST_STOP_FREEZE_VERIFIED", "historical": result, "direction_p_power": power}
