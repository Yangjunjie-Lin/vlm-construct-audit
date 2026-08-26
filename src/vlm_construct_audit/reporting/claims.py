"""Claim-language checks and typed conclusion changes."""

from __future__ import annotations

import re

ASSERTIVE_FORBIDDEN = (
    r"\b(valid behavioral effect|accuracy) (proves|identifies|establishes) (an )?internal mechanism\b",
    r"\bmeasurement validity (proves|establishes|is) semantic validity\b",
    r"\b(tier 0|calibration systems?) (proves|establishes) (a )?real[- ]vlm\b",
    r"\bstructured (graph|interface) (is|was) superior\b",
)


def lint_claim_language(text: str) -> list[str]:
    return [pattern for pattern in ASSERTIVE_FORBIDDEN if re.search(pattern, text, re.IGNORECASE)]


def classify_conclusion_change(
    *,
    old_effect: float,
    new_effect: float,
    old_significant: bool,
    new_significant: bool,
    old_scope: str,
    new_scope: str,
    old_decision: str,
    new_decision: str,
    sesoi: float,
) -> str:
    if old_effect * new_effect < 0:
        return "sign_reversal"
    if abs(old_effect) >= sesoi and abs(new_effect) < sesoi:
        return "magnitude_reversal"
    if old_significant and not new_significant:
        return "significance_downgrade"
    if old_scope != new_scope:
        return "scope_downgrade"
    if old_decision != "INCONCLUSIVE" and new_decision == "INCONCLUSIVE":
        return "inconclusive_conversion"
    return "no_material_change"

