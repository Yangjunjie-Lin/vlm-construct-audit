from __future__ import annotations

from vlm_construct_audit.calibration.systems import get_system
from vlm_construct_audit.data import generate_dataset
from vlm_construct_audit.interventions.operators import intervene
from vlm_construct_audit.utils import read_jsonl


def _scene(split: str, depth: int | None = None):
    generate_dataset()
    return next(
        scene
        for scene in read_jsonl("data/generated/scenes.jsonl")
        if scene["split"] == split and (depth is None or scene["reasoning_depth"] == depth)
    )


def test_oracle_uses_supplied_evidence_and_composes() -> None:
    scene = _scene("reasoning_test", 2)
    system = get_system("OracleEvidenceReasoner")
    correct = system.infer(scene, intervene(scene, "correct_evidence"), "correct_evidence", "natural_language", "conditional_likelihood")
    corrupt = system.infer(scene, intervene(scene, "attribute_swap"), "attribute_swap", "natural_language", "conditional_likelihood")
    assert correct.selected_answer == scene["answer"]
    assert corrupt.selected_answer != scene["answer"]
    assert correct.canonical_trace != corrupt.canonical_trace


def test_evidence_blind_is_condition_invariant() -> None:
    scene = _scene("reasoning_test")
    system = get_system("EvidenceBlindSystem")
    answers = {
        system.infer(scene, intervene(scene, condition), condition, "natural_language", "conditional_likelihood").selected_answer
        for condition in ("correct_evidence", "relation_flip", "attribute_swap")
    }
    assert len(answers) == 1


def test_parser_corruption_preserves_pre_mapping_reasoning() -> None:
    scene = _scene("reasoning_test", 2)
    facts = intervene(scene, "correct_evidence")
    oracle = get_system("OracleEvidenceReasoner").infer(scene, facts, "correct_evidence", "natural_language", "conditional_likelihood")
    corrupt = get_system("ParserCorruptedSystem").infer(scene, facts, "correct_evidence", "natural_language", "conditional_likelihood")
    assert corrupt.pre_mapping_answer == oracle.pre_mapping_answer
    assert corrupt.selected_answer != oracle.selected_answer
    assert corrupt.measurement_probe_pass is False


def test_format_shortcut_changes_with_format_not_facts() -> None:
    scene = _scene("reasoning_test")
    facts = intervene(scene, "correct_evidence")
    system = get_system("FormatShortcutSystem")
    nl = system.infer(scene, facts, "correct_evidence", "natural_language", "conditional_likelihood")
    triples = system.infer(scene, facts, "correct_evidence", "triples", "conditional_likelihood")
    assert nl.selected_answer == scene["answer"]
    assert triples.selected_answer != scene["answer"]
    assert nl.pre_mapping_answer is None


def test_uptake_only_passes_direct_and_fails_composition() -> None:
    uptake = _scene("uptake_validation")
    reasoning = _scene("reasoning_test", 2)
    system = get_system("UptakeOnlySystem")
    direct = system.infer(uptake, intervene(uptake, "correct_evidence"), "correct_evidence", "triples", "conditional_likelihood")
    composed = system.infer(reasoning, intervene(reasoning, "correct_evidence"), "correct_evidence", "triples", "conditional_likelihood")
    assert direct.selected_answer == uptake["answer"]
    assert composed.selected_answer != reasoning["answer"]


def test_output_corruption_localizes_after_reasoning() -> None:
    scene = _scene("reasoning_test", 2)
    facts = intervene(scene, "correct_evidence")
    oracle = get_system("OracleEvidenceReasoner").infer(scene, facts, "correct_evidence", "natural_language", "constrained_generation")
    corrupt = get_system("ReasonerWithOutputCorruption").infer(scene, facts, "correct_evidence", "natural_language", "constrained_generation")
    assert corrupt.pre_mapping_answer == oracle.pre_mapping_answer == scene["answer"]
    assert corrupt.selected_answer != scene["answer"]
    assert corrupt.diagnostic_subtype == "final_output_mapping"
    assert corrupt.constrained_schema_valid is True
