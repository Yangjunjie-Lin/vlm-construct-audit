from __future__ import annotations

from vlm_construct_audit.construct_v2.generator import build_reasoning_rows
from vlm_construct_audit.construct_v2.leakage import audit_leakage


def test_all_registered_shortcut_classifiers_remain_below_gates() -> None:
    result = audit_leakage(build_reasoning_rows(768), folds=4)
    assert result["status"] == "PASS"
    shortcut = result["cross_validated_shortcuts"]
    assert shortcut["maximum_accuracy"] <= 0.30
    assert shortcut["maximum_one_sided_95_exact_upper"] <= 0.35
    assert shortcut["views"]["option_position_only"]
    assert result["deterministic_contingency"]["status"] == "PASS"
