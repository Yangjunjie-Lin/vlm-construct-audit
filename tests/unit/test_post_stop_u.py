from __future__ import annotations

import numpy as np

from vlm_construct_audit.post_stop.direction_u import _bounds, _wald


def test_wald_recovers_simple_complier_effect() -> None:
    z = np.tile([0, 1], 500)
    u = z.copy()
    rng = np.random.default_rng(7)
    y = (rng.random(1000) < (0.2 + 0.3 * u)).astype(int)
    estimate, _, ci = _wald(y, u, z)
    assert estimate is not None
    assert abs(estimate - 0.3) < 0.08
    assert ci[0] < 0.3 < ci[1]


def test_bounds_require_registered_sensitivity_budget() -> None:
    z = np.tile([0, 1], 100)
    u = z.copy()
    y = u.copy()
    dgp = {"measurement_error": "none"}
    assert _bounds(dgp, y, u, z) is None


def test_bounds_are_ordered_and_bounded() -> None:
    z = np.tile([0, 1], 100)
    u = z.copy()
    y = u.copy()
    dgp = {"measurement_error": "none", "violation_budget": 0.02}
    lower, upper = _bounds(dgp, y, u, z)
    assert -1 <= lower <= upper <= 1
