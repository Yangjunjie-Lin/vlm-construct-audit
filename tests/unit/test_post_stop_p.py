from __future__ import annotations

from vlm_construct_audit.post_stop.common import load_yaml
from vlm_construct_audit.post_stop.direction_p import (
    POSITIVE,
    _analytic_probabilities,
    _decide,
)


def test_direction_p_power_is_feasible_at_frozen_alternative() -> None:
    config = load_yaml("research/post_stop/direction_p/preregistration.yaml")
    row = _analytic_probabilities(768, 0.15, config)
    assert row["probability_of_certification"] >= 0.80
    assert row["probability_of_false_negative"] <= 0.20


def test_direction_p_gray_zone_is_not_positive_without_evidence() -> None:
    config = load_yaml("research/post_stop/direction_p/preregistration.yaml")
    row = {
        "measurement_lower": 0.99,
        "parser_valid_rate": 1.0,
        "contract_kappa": 0.98,
        "contract_kappa_lower": 0.95,
        "format_interactions": [0.0, 0.0],
        "partial_identification": False,
        "uptake_lower": 0.90,
        "estimate": 0.11,
        "standard_error": 0.02,
    }
    assert _decide(row, "P3", config) != POSITIVE


def test_direction_p_invalid_measurement_precedes_effect() -> None:
    config = load_yaml("research/post_stop/direction_p/preregistration.yaml")
    row = {
        "measurement_lower": 0.90,
        "parser_valid_rate": 0.92,
        "contract_kappa": 0.98,
        "contract_kappa_lower": 0.95,
        "format_interactions": [0.0, 0.0],
        "partial_identification": False,
        "uptake_lower": 0.90,
        "estimate": 0.40,
        "standard_error": 0.01,
    }
    assert _decide(row, "P3", config) == "INVALID_MEASUREMENT"
