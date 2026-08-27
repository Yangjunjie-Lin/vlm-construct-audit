from __future__ import annotations

from vlm_construct_audit.triage.loop_a import (
    _passes_loop_a,
    _simulate_a0_inputs,
    reproduce_a0_baseline,
)
from vlm_construct_audit.utils import load_yaml


def test_a0_baseline_reproduces_frozen_metrics() -> None:
    assert reproduce_a0_baseline()["status"] == "PASS"


def test_unseen_split_nuisance_namespaces_are_disjoint() -> None:
    registry = load_yaml("research/preregistration/loop_a_dgp_registry.yaml")
    assert registry["development"]["template_namespace"] != registry["holdout"]["template_namespace"]
    assert set(registry["development"]["shortcut_markers"]).isdisjoint(registry["holdout"]["shortcut_markers"])
    assert set(registry["development"]["parser_corruption_patterns"]).isdisjoint(registry["holdout"]["parser_corruption_patterns"])
    assert registry["development"]["entity_id_permutation_seed"] != registry["holdout"]["entity_id_permutation_seed"]


def test_simulator_feeds_frozen_a0_contract_shape() -> None:
    registry = load_yaml("research/preregistration/loop_a_dgp_registry.yaml")
    family = registry["families"][0]
    inputs, metadata = _simulate_a0_inputs(family, 48, 51000, registry["development"])
    assert set(inputs) == {"measurement", "uptake", "downstream", "replication"}
    assert len(inputs["downstream"]["cells"]) == 4
    assert metadata["template_namespace"].startswith("loop_a_dev")


def test_loop_a_gate_does_not_trade_specificity_for_sensitivity() -> None:
    passing = {
        "known_valid_sensitivity": 0.80,
        "known_invalid_specificity": 0.95,
        "fmcr": 0.05,
        "coverage": 0.90,
        "type_s": 0.05,
        "abstention": 0.40,
    }
    assert _passes_loop_a(passing)
    for key in passing:
        failed = dict(passing)
        failed[key] = passing[key] - 0.01 if key not in {"fmcr", "type_s", "abstention"} else passing[key] + 0.01
        assert not _passes_loop_a(failed)
