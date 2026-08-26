from __future__ import annotations

from vlm_construct_audit.statistics.calibration import holm_adjust
from vlm_construct_audit.statistics.core import clopper_pearson_lower, cluster_paired_effect


def test_scene_cluster_effect_and_ci() -> None:
    rows = []
    for scene in range(12):
        rows.append({"scene_id": str(scene), "condition": "correct_evidence", "score": 1})
        for condition in ("relation_flip", "entity_swap", "attribute_swap"):
            rows.append({"scene_id": str(scene), "condition": condition, "score": 0})
    result = cluster_paired_effect(rows, bootstrap_replicates=100)
    assert result["estimate"] == 1.0
    assert result["ci95"] == [1.0, 1.0]
    assert result["resampling_unit"] == "scene_id"


def test_300_success_probe_lower_bound_exceeds_point_98() -> None:
    assert clopper_pearson_lower(300, 300) > 0.98
    assert clopper_pearson_lower(16, 16) < 0.98


def test_holm_adjustment_preserves_ordered_step_down_logic() -> None:
    adjusted = holm_adjust([0.01, 0.04, 0.03])
    assert adjusted == [0.03, 0.06, 0.06]
