from __future__ import annotations

import math

import numpy as np

from vlm_construct_audit.construct_v2.power import (
    analyze_construct_v2_power,
    holm_rejections,
    paired_standard_error,
    simulate_power_row,
)


def test_paired_standard_error_matches_independent_formula() -> None:
    observed = paired_standard_error(0.15, 0.25, 768)
    expected = math.sqrt((0.25 - 0.15**2) / 768)
    assert observed == expected


def test_holm_step_down_is_correct() -> None:
    p_values = np.asarray([[0.001, 0.010, 0.030], [0.009, 0.010, 0.011]])
    observed = holm_rejections(p_values)
    assert observed.tolist() == [[True, True, False], [False, False, False]]


def test_simulation_is_reproducible_and_reports_overall_power() -> None:
    kwargs = {
        "n": 768,
        "effects": (0.15, 0.15, 0.00),
        "discordance": 0.25,
        "cross_model_correlation": 0.25,
        "serialization_correlation": 0.50,
        "repetitions": 1000,
        "seed": 12345,
    }
    first = simulate_power_row(**kwargs)
    second = simulate_power_row(**kwargs)
    assert first == second
    assert 0 <= first["overall_stable_path_power"] <= 1
    assert set(first["holm_supported_family_power"]) == {"SmolVLM", "InternVL", "Qwen-VL"}


def test_path_b_does_not_enter_sample_size_selection() -> None:
    result = analyze_construct_v2_power(repetitions=200, write=False)
    assert result["path_b_used_in_go_decision"] is False
    assert all("path_b" not in row for row in result["rows"])

