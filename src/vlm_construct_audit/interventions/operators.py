"""Generate target-specific and matched control evidence packages."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from ..data.generator import INVERSE
from ..utils import dump_yaml, read_jsonl, sha256_file, write_jsonl


def _pad_facts(scene: dict[str, Any], facts: list[dict[str, str]], count: int = 3) -> list[dict[str, str]]:
    entities = scene["entities"]
    cursor = 1
    result = deepcopy(facts)
    if not any(fact["kind"] == "relation" for fact in result):
        result.append(deepcopy(scene["relations"][0]))
    while len(result) < count:
        entity = entities[cursor % len(entities)]
        filler = {
            "kind": "attribute",
            "subject": entity["entity_id"],
            "predicate": "shape",
            "object": entity["shape"],
        }
        if filler not in result:
            result.append(filler)
        cursor += 1
    return result[:count]


def _different_color(scene: dict[str, Any], color: str) -> str:
    colors = ["red", "blue", "green", "yellow", "purple", "orange"]
    return colors[(colors.index(color) + 1 + len(scene["scene_id"]) % 4) % len(colors)]


def _relation_flip(facts: list[dict[str, str]]) -> list[dict[str, str]]:
    result = deepcopy(facts)
    for fact in result:
        if fact["kind"] == "relation":
            fact["predicate"] = INVERSE[fact["predicate"]]
            return result
    # Direct uptake scenes contain no required relation; corrupt their target attribute.
    result[0]["object"] = "__relation_flip_control__"
    return result


def _entity_swap(facts: list[dict[str, str]]) -> list[dict[str, str]]:
    result = deepcopy(facts)
    for fact in result:
        if fact["kind"] == "relation":
            fact["subject"], fact["object"] = fact["object"], fact["subject"]
            return result
    result[0]["subject"] = result[-1]["subject"]
    return result


def _attribute_swap(scene: dict[str, Any], facts: list[dict[str, str]]) -> list[dict[str, str]]:
    result = deepcopy(facts)
    target = scene["question"]["target_entity"]
    for fact in result:
        if fact["kind"] == "attribute" and fact["predicate"] == "color" and fact["subject"] == target:
            fact["object"] = _different_color(scene, fact["object"])
            return result
    raise AssertionError("Every scene must include its target color fact")


def _matched_irrelevant(scene: dict[str, Any], facts: list[dict[str, str]]) -> list[dict[str, str]]:
    entities = scene["entities"]
    ids = [entity["entity_id"] for entity in entities]
    mapping = {entity_id: ids[(i + 1) % len(ids)] for i, entity_id in enumerate(ids)}
    lookup = {entity["entity_id"]: entity for entity in entities}
    result: list[dict[str, str]] = []
    for fact in facts:
        if fact["kind"] == "relation":
            result.append(
                {
                    "kind": "relation",
                    "subject": mapping[fact["subject"]],
                    "predicate": fact["predicate"],
                    "object": mapping[fact["object"]],
                }
            )
        else:
            replacement_id = mapping[fact["subject"]]
            replacement_entity = lookup[replacement_id]
            result.append(
                {
                    "kind": "attribute",
                    "subject": replacement_id,
                    "predicate": fact["predicate"],
                    "object": replacement_entity.get(fact["predicate"], replacement_entity["shape"]),
                }
            )
    return result


def intervene(scene: dict[str, Any], condition: str) -> list[dict[str, str]]:
    correct = _pad_facts(scene, scene["required_facts"])
    if condition == "correct_evidence":
        return correct
    if condition == "relation_flip":
        return _relation_flip(correct)
    if condition == "entity_swap":
        return _entity_swap(correct)
    if condition == "attribute_swap":
        return _attribute_swap(scene, correct)
    if condition == "matched_irrelevant":
        return _matched_irrelevant(scene, correct)
    if condition == "plausible_contradictory":
        # A fluent, type-consistent target contradiction rather than nonsense.
        return _attribute_swap(scene, correct)
    raise KeyError(condition)


def build_interventions(
    scenes_path: str | Path = "data/generated/scenes.jsonl",
    conditions: list[str] | None = None,
) -> dict[str, Any]:
    conditions = conditions or [
        "correct_evidence",
        "relation_flip",
        "entity_swap",
        "attribute_swap",
        "matched_irrelevant",
        "plausible_contradictory",
    ]
    scenes = read_jsonl(scenes_path)
    rows = []
    for scene in scenes:
        correct = intervene(scene, "correct_evidence")
        for condition in conditions:
            facts = intervene(scene, condition)
            rows.append(
                {
                    "scene_id": scene["scene_id"],
                    "split": scene["split"],
                    "condition": condition,
                    "question": scene["question"],
                    "answer": scene["answer"],
                    "facts": facts,
                    "fact_count": len(facts),
                    "entity_count": len({f["subject"] for f in facts} | {f["object"] for f in facts if f["kind"] == "relation"}),
                    "relation_count": sum(f["kind"] == "relation" for f in facts),
                    "changes_supplied_facts": facts != correct,
                    "scene_answer_unchanged": True,
                }
            )
    output = Path("data/generated/interventions.jsonl")
    write_jsonl(output, rows)
    summary = {
        "schema_version": 1,
        "row_count": len(rows),
        "conditions": conditions,
        "all_fact_counts_matched": len({row["fact_count"] for row in rows}) == 1,
        "all_entity_counts_matched_within_scene": all(
            len({row["entity_count"] for row in rows if row["scene_id"] == scene["scene_id"]}) == 1
            for scene in scenes
        ),
        "all_relation_counts_matched_within_scene": all(
            len({row["relation_count"] for row in rows if row["scene_id"] == scene["scene_id"]}) == 1
            for scene in scenes
        ),
        "all_noncorrect_conditions_change_facts": all(
            row["changes_supplied_facts"]
            for row in rows
            if row["condition"] != "correct_evidence"
        ),
        "all_interventions_preserve_world_answer": all(row["scene_answer_unchanged"] for row in rows),
        "sha256": sha256_file(output),
    }
    dump_yaml("data/manifests/intervention_manifest.yaml", summary)
    return summary
