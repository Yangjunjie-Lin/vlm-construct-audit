from __future__ import annotations

from vlm_construct_audit.reporting.claims import classify_conclusion_change, lint_claim_language


def test_claim_linter_rejects_construct_overreach() -> None:
    assert lint_claim_language("Accuracy proves an internal mechanism.")
    assert lint_claim_language("Measurement validity is semantic validity.")
    assert not lint_claim_language("Accuracy does not identify an internal mechanism.")


def test_p_value_loss_is_not_sign_reversal() -> None:
    change = classify_conclusion_change(
        old_effect=0.3,
        new_effect=0.3,
        old_significant=True,
        new_significant=False,
        old_scope="same",
        new_scope="same",
        old_decision="VALID_BEHAVIORAL_EFFECT",
        new_decision="VALID_BEHAVIORAL_EFFECT",
        sesoi=0.1,
    )
    assert change == "significance_downgrade"


def test_change_taxonomy_distinguishes_sign_scope_and_inconclusive() -> None:
    base = {
        "old_effect": 0.3,
        "new_effect": 0.2,
        "old_significant": True,
        "new_significant": True,
        "old_scope": "all_models",
        "new_scope": "all_models",
        "old_decision": "VALID_BEHAVIORAL_EFFECT",
        "new_decision": "VALID_BEHAVIORAL_EFFECT",
        "sesoi": 0.1,
    }
    assert classify_conclusion_change(**(base | {"new_effect": -0.2})) == "sign_reversal"
    assert classify_conclusion_change(**(base | {"new_effect": 0.05})) == "magnitude_reversal"
    assert classify_conclusion_change(**(base | {"new_scope": "validated_cells"})) == "scope_downgrade"
    assert classify_conclusion_change(**(base | {"new_decision": "INCONCLUSIVE"})) == "inconclusive_conversion"
