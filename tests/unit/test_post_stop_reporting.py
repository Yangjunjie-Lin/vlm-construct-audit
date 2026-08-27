from __future__ import annotations

import pytest

from vlm_construct_audit.post_stop.human_review import _bool, _cohen_kappa
from vlm_construct_audit.post_stop.reporting import _select_final


def test_human_boolean_parser_is_strict() -> None:
    assert _bool("true") is True
    assert _bool("No") is False
    with pytest.raises(ValueError):
        _bool("probably")


def test_kappa_perfect_agreement() -> None:
    assert _cohen_kappa([True, False, True], [True, False, True]) == 1.0


def test_priority_selects_p_only_after_human_go() -> None:
    assert _select_final("DIRECTION_P_GO", "DIRECTION_U_GO", "DIRECTION_M_SCIENTIFIC_GO", "HUMAN_REVIEW_GO") == "PREREGISTER_POWER_CALIBRATED_MINI_PILOT"
    assert _select_final("DIRECTION_P_GO", "DIRECTION_U_GO", "DIRECTION_M_SCIENTIFIC_GO", "MEASUREMENT_FOUNDATION_NO_GO") == "MEASUREMENT_FOUNDATION_NO_GO"


def test_priority_falls_through_without_combining_directions() -> None:
    assert _select_final("DIRECTION_P_NO_GO", "DIRECTION_U_GO", "DIRECTION_M_SCIENTIFIC_GO", "HUMAN_REVIEW_GO") == "PREREGISTER_UPTAKE_IDENTIFICATION_MINI_PILOT"
    assert _select_final("DIRECTION_P_NO_GO", "DIRECTION_U_NO_GO", "DIRECTION_M_NO_GO", "HUMAN_REVIEW_GO") == "TERMINATE_SUCCESSOR_PROGRAM"
