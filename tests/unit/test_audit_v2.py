from __future__ import annotations

from vlm_construct_audit.triage.audit_v2 import audit_claim_v2, pooled_scene_lower_bound


def _fixtures() -> tuple[dict, dict, dict, dict, dict]:
    cells = {
        f"cell_{index}": {"estimate": 0.20, "ci95": [0.12, 0.28], "scene_clusters": 192}
        for index in range(4)
    }
    measurement = {
        "one_sided_95_lower": 0.99,
        "parser_valid_rate": 1.0,
        "contract_agreement": {"kappa": 0.98, "ci95": [0.95, 1.0]},
    }
    uptake = {"aggregate": {"estimate": 0.95, "ci95": [0.90, 0.98]}}
    downstream = {"aggregate": {"estimate": 0.20, "ci95": [0.12, 0.28]}, "cells": cells}
    replication = {
        "equivalence": {"programmatic_fact_equivalence": True},
        "format_interactions": {"conditional_likelihood": 0.0, "constrained_generation": 0.0},
        "format_tost": {
            "conditional_likelihood": {"tost_equivalent": True},
            "constrained_generation": {"tost_equivalent": True},
        },
        "partial_identification": {"eligible": False},
    }
    policy = {
        "measurement_validity_cutoff": 0.98,
        "contract_kappa_cutoff": 0.90,
        "contract_kappa_lower_bound_cutoff": 0.85,
        "format_materiality": 0.10,
        "gate_cutoff": 0.80,
        "sesoi": 0.10,
    }
    return measurement, uptake, downstream, replication, policy


def test_audit_v2_does_not_multiply_scene_count_by_cells() -> None:
    _, _, downstream, _, _ = _fixtures()
    pooled = pooled_scene_lower_bound(downstream)
    assert pooled["effective_scene_clusters"] == 192
    assert pooled["pseudoreplicated_cell_multiplier"] is False


def test_audit_v2_valid_effect_requires_all_cell_point_estimates() -> None:
    args = list(_fixtures())
    assert audit_claim_v2(*args).decision == "VALID_BEHAVIORAL_EFFECT"
    args[2]["cells"]["cell_0"]["estimate"] = 0.05
    assert audit_claim_v2(*args).decision == "INCONCLUSIVE"


def test_audit_v2_partial_identification_prevents_false_valid_claim() -> None:
    args = list(_fixtures())
    args[3]["partial_identification"] = {
        "eligible": True,
        "bounds": [-1.0, 1.0],
        "observed_uptake_filtering": False,
    }
    decision = audit_claim_v2(*args)
    assert decision.decision == "PARTIALLY_IDENTIFIED"
    assert decision.identification_status == "PARTIALLY_IDENTIFIED"


def test_audit_v2_keeps_measurement_and_contract_thresholds() -> None:
    args = list(_fixtures())
    args[0]["one_sided_95_lower"] = 0.979
    assert audit_claim_v2(*args).decision == "INVALID_MEASUREMENT"
    args = list(_fixtures())
    args[0]["contract_agreement"]["ci95"][0] = 0.849
    assert audit_claim_v2(*args).decision == "INCONCLUSIVE"
