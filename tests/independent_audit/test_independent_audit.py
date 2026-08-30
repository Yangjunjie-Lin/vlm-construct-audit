"""Regression checks for the independent audit computations."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[2]


def load_script(name: str) -> ModuleType:
    path = ROOT / "scripts/independent_audit" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_manifest_independent_parser_finds_45_files() -> None:
    module = load_script("verify_frozen_package")
    text = (
        ROOT / "artifacts/preregistration/p_mini_pilot_preregistration_manifest.yaml"
    ).read_text(encoding="utf-8")
    assert len(module.parse_indented_hash_map(text, "files", "aggregate_sha256")) == 45


def test_uptake_exact_thresholds_and_masking() -> None:
    module = load_script("audit_uptake_gate")
    assert module.minimum_successes_for_lower(192, 0.80) == 164
    assert module.minimum_successes_for_lower(48, 0.80) == 44
    assert module.maximum_successes_for_upper(192, 0.60) == 103
    assert 164 - 3 * 48 == 20


def test_formal_scene_index_deterministically_decodes_answer_and_position() -> None:
    rows = [
        json.loads(line)
        for line in (ROOT / "data/p_mini_pilot/scenes.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    decoder = {
        0: "ANS_REL_NE",
        1: "ANS_REL_SE",
        2: "ANS_REL_NW",
        3: "ANS_REL_SW",
    }
    for row in rows:
        index = int(row["scene_id"].rsplit("_", 1)[1])
        assert row["question"]["answer_id"] == decoder[index % 4]
        assert row["question"]["correct_option_position"] == index % 4


def test_cell_power_analytic_target() -> None:
    module = load_script("recompute_cell_power")
    result = module.analytic(768, 0.15, 0.25)
    assert abs(result["certification_probability"] - 0.8277032779664638) < 1e-12


def test_holm_stepdown_stops_after_first_failure() -> None:
    module = load_script("simulate_holm_replication_power")
    import numpy as np

    p_values = np.asarray([[0.001, 0.005, 0.006, 0.02, 0.021, 0.022]])
    rejected = module.holm_rejections(p_values)
    assert rejected.tolist() == [[True, True, True, False, False, False]]
