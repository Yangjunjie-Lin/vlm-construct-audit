"""Fail-closed interface boundary for future v2 scientific execution."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml

from .generator import ROOT
from .renderer import render_scene

AUDIT_AUTHORIZATION = ROOT / "research/authorization/construct_v2_independent_audit.yaml"
READINESS_AUTHORIZATION = ROOT / "research/authorization/construct_v2_execution_readiness.yaml"
BLOCKED_STATUS = "V2_NOT_AUTHORIZED_PENDING_HUMAN_AND_INDEPENDENT_AUDIT"


class ConstructV2Runner:
    """Interface-only runner; no model runtime is bundled or invoked."""

    def validate_authorization(self) -> dict[str, Any]:
        missing = [
            str(path.relative_to(ROOT))
            for path in (AUDIT_AUTHORIZATION, READINESS_AUTHORIZATION)
            if not path.exists()
        ]
        if missing:
            return {
                "valid": False,
                "status": BLOCKED_STATUS,
                "missing": missing,
                "no_inference_started": True,
            }
        audit = yaml.safe_load(AUDIT_AUTHORIZATION.read_text(encoding="utf-8"))
        readiness = yaml.safe_load(READINESS_AUTHORIZATION.read_text(encoding="utf-8"))
        valid = (
            audit.get("decision") == "CONSTRUCT_V2_INDEPENDENT_AUDIT_PASS"
            and readiness.get("decision") == "CONSTRUCT_V2_EXECUTION_READY"
            and audit.get("protocol_id") == "direction_p_construct_valid_mini_pilot_v2"
            and readiness.get("protocol_id") == "direction_p_construct_valid_mini_pilot_v2"
        )
        return {
            "valid": valid,
            "status": "AUTHORIZED" if valid else BLOCKED_STATUS,
            "missing": [],
            "no_inference_started": True,
        }

    def _require_authorization(self) -> None:
        authorization = self.validate_authorization()
        if not authorization["valid"]:
            raise PermissionError(json.dumps(authorization, sort_keys=True))

    def render_scene(self, scene: dict[str, Any]) -> Path:
        return render_scene(scene)

    def build_prompt(
        self,
        scene: dict[str, Any],
        *,
        condition: str,
        serialization: str,
    ) -> dict[str, Any]:
        if condition not in {"correct", "corrupted"}:
            raise ValueError(condition)
        if serialization not in {"natural_language", "triples"}:
            raise ValueError(serialization)
        prompt = {
            "evidence": scene["evidence"][condition][serialization],
            "question": scene["question"]["text"],
            "semantic_candidates": scene["answer"]["semantic_candidates"],
            "primary_score_target": "semantic_candidate_text",
        }
        serialized = json.dumps(prompt, sort_keys=True)
        forbidden = (
            scene["scene_uuid"],
            scene["internal_scene_id"],
            *(entity["entity_uuid"] for entity in scene["entities"]),
        )
        if any(value in serialized for value in forbidden):
            raise ValueError("model-visible prompt contains an internal identifier")
        return prompt

    def score_candidates(
        self,
        scene: dict[str, Any],
        scorer: Callable[[dict[str, Any]], dict[str, float]],
        *,
        condition: str,
        serialization: str,
    ) -> dict[str, float]:
        self._require_authorization()
        return scorer(self.build_prompt(scene, condition=condition, serialization=serialization))

    def verify_independent_scorer(
        self, primary_scores: dict[str, float], independent_scores: dict[str, float]
    ) -> dict[str, Any]:
        same_candidates = set(primary_scores) == set(independent_scores)
        primary_order = sorted(primary_scores, key=primary_scores.get, reverse=True)
        independent_order = sorted(independent_scores, key=independent_scores.get, reverse=True)
        return {
            "same_candidates": same_candidates,
            "ranking_agreement": primary_order == independent_order,
            "maximum_absolute_difference": (
                max(abs(primary_scores[key] - independent_scores[key]) for key in primary_scores)
                if same_candidates
                else None
            ),
        }

    def run_formal_uptake(self) -> None:
        self._require_authorization()
        raise RuntimeError("V2_FORMAL_SCIENTIFIC_RUNNER_NOT_BUNDLED")

    def run_formal_reasoning(self) -> None:
        self._require_authorization()
        raise RuntimeError("V2_FORMAL_SCIENTIFIC_RUNNER_NOT_BUNDLED")


def verify_no_construct_v2_inference() -> dict[str, Any]:
    candidate_roots = [
        ROOT / "artifacts/construct_v2/predictions",
        ROOT / "artifacts/construct_v2/model_outputs",
        ROOT / "artifacts/construct_v2/uptake_model_outputs",
        ROOT / "artifacts/construct_v2/reasoning_model_outputs",
    ]
    files_by_root = {
        path.relative_to(ROOT).as_posix(): (
            [str(item.relative_to(ROOT)) for item in path.rglob("*") if item.is_file()]
            if path.exists()
            else []
        )
        for path in candidate_roots
    }
    scientific_metrics = ROOT / "artifacts/construct_v2/scientific_metrics.yaml"
    formal_prediction_files = sum(len(files) for files in files_by_root.values())
    runner = ConstructV2Runner().validate_authorization()
    result = {
        "status": "PASS",
        "formal_prediction_files": formal_prediction_files,
        "uptake_model_outputs": len(files_by_root["artifacts/construct_v2/uptake_model_outputs"]),
        "reasoning_model_outputs": len(
            files_by_root["artifacts/construct_v2/reasoning_model_outputs"]
        ),
        "scientific_metrics": int(scientific_metrics.exists()),
        "runner_blocked": not runner["valid"],
        "runner_status": runner["status"],
        "authorization_files_created_by_preaudit": False,
        "files_by_root": files_by_root,
    }
    if any(
        [
            result["formal_prediction_files"] != 0,
            result["uptake_model_outputs"] != 0,
            result["reasoning_model_outputs"] != 0,
            result["scientific_metrics"] != 0,
            not result["runner_blocked"],
        ]
    ):
        result["status"] = "FAIL_INFERENCE_DETECTED_OR_RUNNER_OPEN"
    return result
