"""Independent standard-library verification of the frozen preregistration package."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
FROZEN_TAG = "p-mini-pilot-preregistered"
FROZEN_COMMIT = "9de60b87ec54bc852a7bb2e9cff87d9c23638042"
MANIFEST_PATH = ROOT / "artifacts/preregistration/p_mini_pilot_preregistration_manifest.yaml"
OUTPUT_PATH = ROOT / "artifacts/independent_audit/independent_hash_manifest.yaml"


def sha256_bytes(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_normalized_text(path: Path) -> str:
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def git(*args: str, cwd: Path = ROOT, check: bool = True) -> str:
    result = subprocess.run(["git", *args], cwd=cwd, check=check, capture_output=True, text=True)
    return result.stdout.strip()


def parse_top_level_hashes(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for key in (
        "aggregate_sha256",
        "method_lock_sha256",
        "model_registry_sha256",
        "data_manifest_sha256",
    ):
        match = re.search(rf"(?m)^{re.escape(key)}: ([0-9a-f]{{64}})$", text)
        if match is None:
            raise ValueError(f"missing {key}")
        result[key] = match.group(1)
    return result


def parse_indented_hash_map(text: str, section: str, end_key: str) -> dict[str, str]:
    match = re.search(rf"(?ms)^{re.escape(section)}:\r?\n(?P<body>.*?)^{re.escape(end_key)}:", text)
    if match is None:
        raise ValueError(f"missing section {section}")
    result: dict[str, str] = {}
    for line in match.group("body").splitlines():
        item = re.fullmatch(r"  (.+): ([0-9a-f]{64})", line)
        if item:
            result[item.group(1)] = item.group(2)
    return result


def parse_data_file_hashes(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    current: str | None = None
    in_files = False
    for line in text.splitlines():
        if line == "files:":
            in_files = True
            continue
        if in_files and line and not line.startswith(" "):
            break
        path_match = re.fullmatch(r"  (.+):", line)
        if in_files and path_match:
            current = path_match.group(1)
            continue
        hash_match = re.fullmatch(r"    sha256: ([0-9a-f]{64})", line)
        if in_files and current and hash_match:
            result[current] = hash_match.group(1)
    return result


def count_files(path: Path) -> int:
    return sum(1 for item in path.rglob("*") if item.is_file()) if path.exists() else 0


def main() -> int:
    manifest_text = MANIFEST_PATH.read_text(encoding="utf-8")
    expected_files = parse_indented_hash_map(manifest_text, "files", "aggregate_sha256")
    expected_summary = parse_top_level_hashes(manifest_text)
    actual_files = {path: sha256_bytes(ROOT / path) for path in sorted(expected_files)}
    aggregate_raw = json.dumps(actual_files, sort_keys=True, separators=(",", ":")).encode()
    aggregate = hashlib.sha256(aggregate_raw).hexdigest()

    method_text = (ROOT / "research/preregistration/p_mini_pilot_method_lock.yaml").read_text(
        encoding="utf-8"
    )
    method_sources = parse_indented_hash_map(method_text, "source_file_hashes", "delta0")
    method_source_actual = {
        path: sha256_normalized_text(ROOT / path) for path in sorted(method_sources)
    }

    data_manifest = (ROOT / "data/p_mini_pilot/data_manifest.yaml").read_text(encoding="utf-8")
    scene_expected = parse_data_file_hashes(data_manifest)
    scene_actual = {path: sha256_bytes(ROOT / path) for path in sorted(scene_expected)}

    prereg_tag_object = git("rev-parse", FROZEN_TAG)
    prereg_tag_type = git("cat-file", "-t", FROZEN_TAG)
    prereg_target = git("rev-parse", f"{FROZEN_TAG}^{{}}")
    historical_tags = {
        "vlm-construct-audit-tier0-5-stop": {
            "expected": "ce0e797a4926ab5d2309915c2eef14fd9c5be44d",
            "actual": git("rev-parse", "vlm-construct-audit-tier0-5-stop^{}"),
        },
        "vlm-construct-audit-post-stop-final": {
            "expected": "f993282e0a27b8da0ba1c239fb96715c9fc5b79a",
            "actual": git("rev-parse", "vlm-construct-audit-post-stop-final^{}"),
        },
    }
    protected_diff = git("diff", "--name-only", FROZEN_TAG, "--", *sorted(expected_files))

    result_paths = {
        "predictions": ROOT / "artifacts/p_mini_pilot/predictions",
        "model_outputs": ROOT / "artifacts/p_mini_pilot/model_outputs",
        "reasoning_results": ROOT / "artifacts/p_mini_pilot/reasoning_results",
        "scientific_metrics": ROOT / "artifacts/p_mini_pilot/scientific_metrics.yaml",
        "authorization": ROOT / "research/authorization/p_mini_pilot_independent_audit.yaml",
    }
    scientific_counts = {name: count_files(path) for name, path in result_paths.items()}
    scientific_counts["scientific_metrics"] = int(result_paths["scientific_metrics"].is_file())
    scientific_counts["authorization"] = int(result_paths["authorization"].is_file())

    recoalign = ROOT.parent / "recoalign"
    recoalign_state: dict[str, Any] = {"path": str(recoalign), "exists": recoalign.is_dir()}
    if recoalign_state["exists"]:
        recoalign_state.update(
            {
                "head": git("rev-parse", "HEAD", cwd=recoalign),
                "branch": git("branch", "--show-current", cwd=recoalign),
                "working_tree_clean": git("status", "--porcelain=v1", cwd=recoalign) == "",
            }
        )

    checks = {
        "manifest_file_count_45": len(expected_files) == 45,
        "manifest_file_hashes_match": expected_files == actual_files,
        "aggregate_sha256_match": aggregate == expected_summary["aggregate_sha256"],
        "method_lock_file_hash_match": sha256_bytes(
            ROOT / "research/preregistration/p_mini_pilot_method_lock.yaml"
        )
        == expected_summary["method_lock_sha256"],
        "model_registry_hash_match": sha256_bytes(ROOT / "configs/p_mini_pilot_models.yaml")
        == expected_summary["model_registry_sha256"],
        "data_manifest_hash_match": sha256_bytes(ROOT / "data/p_mini_pilot/data_manifest.yaml")
        == expected_summary["data_manifest_sha256"],
        "method_source_hashes_match": method_sources == method_source_actual,
        "scene_file_hashes_match": scene_expected == scene_actual,
        "preregistration_tag_annotated": prereg_tag_type == "tag",
        "preregistration_tag_target_exact": prereg_target == FROZEN_COMMIT,
        "historical_tag_targets_match": all(
            item["actual"] == item["expected"] for item in historical_tags.values()
        ),
        "frozen_manifest_files_unchanged_on_audit_branch": protected_diff == "",
        "no_scientific_outputs": not any(scientific_counts.values()),
        "recoalign_working_tree_clean": bool(recoalign_state.get("working_tree_clean")),
    }
    output = {
        "schema_version": 1,
        "audited_tag": FROZEN_TAG,
        "audited_commit": FROZEN_COMMIT,
        "tag_object": prereg_tag_object,
        "tag_type": prereg_tag_type,
        "tag_target": prereg_target,
        "manifest_file_count": len(expected_files),
        "aggregate_sha256": {"expected": expected_summary["aggregate_sha256"], "actual": aggregate},
        "method_lock_sha256": {
            "expected": expected_summary["method_lock_sha256"],
            "actual": sha256_bytes(ROOT / "research/preregistration/p_mini_pilot_method_lock.yaml"),
        },
        "model_registry_sha256": {
            "expected": expected_summary["model_registry_sha256"],
            "actual": sha256_bytes(ROOT / "configs/p_mini_pilot_models.yaml"),
        },
        "data_manifest_sha256": {
            "expected": expected_summary["data_manifest_sha256"],
            "actual": sha256_bytes(ROOT / "data/p_mini_pilot/data_manifest.yaml"),
        },
        "manifest_mismatches": [
            path for path in sorted(expected_files) if expected_files[path] != actual_files[path]
        ],
        "method_source_mismatches": [
            path
            for path in sorted(method_sources)
            if method_sources[path] != method_source_actual[path]
        ],
        "scene_file_hashes": {
            path: {"expected": scene_expected[path], "actual": scene_actual[path]}
            for path in sorted(scene_expected)
        },
        "historical_tags": historical_tags,
        "protected_diff": protected_diff.splitlines(),
        "scientific_output_counts": scientific_counts,
        "recoalign": recoalign_state,
        "checks": checks,
        "status": "PASS" if all(checks.values()) else "FAIL",
    }
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0 if output["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
