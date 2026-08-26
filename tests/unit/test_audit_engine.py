from __future__ import annotations

from copy import deepcopy

from vlm_construct_audit.audit.engine import audit_claim


def _fixtures():
    measurement = {
        "one_sided_95_lower": 0.99,
        "parser_valid_rate": 1.0,
        "contract_agreement": {"kappa": 1.0, "ci95": [1.0, 1.0]},
    }
    effect = {"estimate": 0.5, "ci95": [0.4, 0.6], "scene_clusters": 16}
    uptake = {"aggregate": deepcopy(effect), "cells": {"cell": deepcopy(effect)}}
    downstream = {
        "aggregate": deepcopy(effect),
        "cells": {f"cell_{i}": deepcopy(effect) for i in range(4)},
    }
    replication = {
        "equivalence": {"programmatic_fact_equivalence": True},
        "format_interactions": {"conditional_likelihood": 0.0, "constrained_generation": 0.0},
        "format_tost": {
            "conditional_likelihood": {"tost_equivalent": True},
            "constrained_generation": {"tost_equivalent": True},
        },
        "diagnostic_subtype": "fixture",
    }
    policy = {
        "measurement_validity_cutoff": 0.98,
        "contract_kappa_cutoff": 0.90,
        "contract_kappa_lower_bound_cutoff": 0.85,
        "gate_cutoff": 0.80,
        "sesoi": 0.10,
        "format_materiality": 0.10,
    }
    return measurement, uptake, downstream, replication, policy


def test_intersection_union_all_gates_required() -> None:
    args = _fixtures()
    # Uptake must be above the frozen lower-bound gate for the valid fixture.
    args[1]["aggregate"]["ci95"] = [0.9, 1.0]
    decision = audit_claim(*args)
    assert decision.decision == "VALID_BEHAVIORAL_EFFECT"
    assert decision.identification_status == "BEHAVIORAL_ONLY_INTERNAL_MECHANISM_NOT_IDENTIFIED"
    for gate in ("measurement", "uptake", "downstream", "format"):
        measurement, uptake, downstream, replication, policy = _fixtures()
        uptake["aggregate"]["ci95"] = [0.9, 1.0]
        if gate == "measurement":
            measurement["one_sided_95_lower"] = 0.5
            expected = "INVALID_MEASUREMENT"
        elif gate == "uptake":
            uptake["aggregate"]["ci95"] = [0.1, 0.2]
            expected = "INVALID_INTERVENTION"
        elif gate == "downstream":
            downstream["cells"]["cell_0"]["ci95"] = [0.0, 0.2]
            expected = "INCONCLUSIVE"
        else:
            replication["format_interactions"]["conditional_likelihood"] = 0.5
            expected = "FORMAT_DEPENDENT"
        assert audit_claim(measurement, uptake, downstream, replication, policy).decision == expected


def test_non_equivalent_formats_are_inconclusive_not_format_dependent() -> None:
    measurement, uptake, downstream, replication, policy = _fixtures()
    uptake["aggregate"]["ci95"] = [0.9, 1.0]
    replication["equivalence"]["programmatic_fact_equivalence"] = False
    replication["format_interactions"]["conditional_likelihood"] = 1.0
    assert audit_claim(measurement, uptake, downstream, replication, policy).decision == "INCONCLUSIVE"


def test_output_corruption_is_not_called_reasoning_failure() -> None:
    measurement, uptake, downstream, replication, policy = _fixtures()
    measurement["one_sided_95_lower"] = 0.0
    replication["diagnostic_subtype"] = "final_output_mapping"
    decision = audit_claim(measurement, uptake, downstream, replication, policy)
    assert decision.decision == "INVALID_MEASUREMENT"
    assert decision.diagnostic_subtype == "final_output_mapping"
    assert "reasoning failure" not in decision.claim_boundary.lower()


def test_decision_schema_has_required_fields() -> None:
    measurement, uptake, downstream, replication, policy = _fixtures()
    decision = audit_claim(measurement, uptake, downstream, replication, policy)
    for field in (
        "decision", "estimand", "eligible_population", "passed_gates", "failed_gates",
        "effect_size", "confidence_interval", "equivalence_result", "replication_status",
        "identification_status", "claim_boundary", "supporting_artifacts",
    ):
        assert hasattr(decision, field)
