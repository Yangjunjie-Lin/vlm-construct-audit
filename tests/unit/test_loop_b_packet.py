from __future__ import annotations

from vlm_construct_audit.triage.loop_b import _canonical, _mutate, _template_inventory


def test_template_inventory_has_200_actual_unique_strings() -> None:
    templates = _template_inventory()
    assert len(templates) == 200
    assert len({item["text"] for item in templates}) == 200
    assert len({item["sha256"] for item in templates}) == 200


def test_canonical_checker_detects_every_frozen_mutation() -> None:
    facts = [
        {"kind": "relation", "subject": "a", "predicate": "left_of", "object": "b"},
        {"kind": "attribute", "subject": "a", "predicate": "color", "object": "red"},
        {"kind": "attribute", "subject": "b", "predicate": "shape", "object": "square"},
    ]
    source = _canonical(facts)
    for mutation in ("omission", "subject_object_swap", "inverse_relation", "attribute_change", "duplicate_fact"):
        assert _canonical(_mutate(facts, mutation)) != source
