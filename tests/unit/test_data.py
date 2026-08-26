from __future__ import annotations

from vlm_construct_audit.data.generator import generate_dataset
from vlm_construct_audit.interventions.operators import build_interventions
from vlm_construct_audit.serialization.formats import (
    build_serializations,
    parse_facts,
    validate_equivalence,
)
from vlm_construct_audit.utils import read_jsonl, sha256_file


def _prepare() -> None:
    generate_dataset()
    build_interventions()
    build_serializations()


def test_answers_are_unique_and_relation_directions_are_paired() -> None:
    generate_dataset()
    scenes = read_jsonl("data/generated/scenes.jsonl")
    assert all(scene["answer"] in scene["question"]["options"] for scene in scenes)
    assert all(scene["question"]["options"].count(scene["answer"]) == 1 for scene in scenes)
    for scene in scenes:
        relations = {(f["subject"], f["predicate"], f["object"]) for f in scene["relations"]}
        for subject, predicate, obj in list(relations):
            inverse = {
                "left_of": "right_of", "right_of": "left_of", "above": "below",
                "below": "above", "in_front_of": "behind", "behind": "in_front_of",
            }[predicate]
            assert (obj, inverse, subject) in relations


def test_corruptions_change_facts_and_preserve_world_answer() -> None:
    _prepare()
    rows = read_jsonl("data/generated/interventions.jsonl")
    correct = {row["scene_id"]: row["facts"] for row in rows if row["condition"] == "correct_evidence"}
    for row in rows:
        if row["condition"] != "correct_evidence":
            assert row["facts"] != correct[row["scene_id"]]
        assert row["scene_answer_unchanged"] is True
    assert all(row["fact_count"] == 3 for row in rows)


def test_serialization_round_trip_equivalence() -> None:
    _prepare()
    rows = read_jsonl("data/generated/serialized.jsonl")
    for row in rows:
        assert parse_facts(row["serialized_evidence"], row["serialization"]) == row["facts"]
    assert validate_equivalence()["programmatic_fact_equivalence"] is True


def test_splits_isolate_scene_ids_and_template_combinations() -> None:
    generate_dataset()
    scenes = read_jsonl("data/generated/scenes.jsonl")
    scene_sets = {}
    template_sets = {}
    for split in {scene["split"] for scene in scenes}:
        scene_sets[split] = {scene["scene_id"] for scene in scenes if scene["split"] == split}
        template_sets[split] = {scene["template_id"] for scene in scenes if scene["split"] == split}
    splits = sorted(scene_sets)
    for i, left in enumerate(splits):
        for right in splits[i + 1 :]:
            assert scene_sets[left].isdisjoint(scene_sets[right])
            assert template_sets[left].isdisjoint(template_sets[right])


def test_fixed_seed_reproduces_scene_hash() -> None:
    generate_dataset()
    first = sha256_file("data/generated/scenes.jsonl")
    generate_dataset()
    assert sha256_file("data/generated/scenes.jsonl") == first
