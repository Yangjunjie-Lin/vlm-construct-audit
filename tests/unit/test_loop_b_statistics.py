from __future__ import annotations

from vlm_construct_audit.triage.cluster_bounds import (
    beta_binomial_profile_lower,
    icc_design_effect_lower,
    simultaneous_scene_template_lower,
)


def test_160_clusters_are_insufficient_but_200_pass_simultaneous_point_98() -> None:
    assert simultaneous_scene_template_lower(160, 160, 160, 160)["two_way_lower"] < 0.98
    assert simultaneous_scene_template_lower(200, 200, 200, 200)["two_way_lower"] >= 0.98


def test_beta_binomial_reports_every_frozen_rho_without_selection() -> None:
    successes = [3] * 200
    trials = [3] * 200
    values = [beta_binomial_profile_lower(successes, trials, rho) for rho in (0.0, 0.05, 0.10, 0.20)]
    assert len(values) == 4
    assert all(0 < value <= 1 for value in values)


def test_icc_sensitivity_uses_design_effect() -> None:
    zero = icc_design_effect_lower(600, 600, [3] * 200, 0.0)
    correlated = icc_design_effect_lower(600, 600, [3] * 200, 0.20)
    assert zero["effective_n"] > correlated["effective_n"]
    assert zero["lower"] > correlated["lower"]
