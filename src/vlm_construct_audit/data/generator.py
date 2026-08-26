"""Generate small controlled worlds with isolated templates and scene IDs."""

from __future__ import annotations

import random
from collections import Counter
from pathlib import Path
from typing import Any

from ..utils import canonical_hash, dump_yaml, load_yaml, sha256_file, write_jsonl

INVERSE = {
    "left_of": "right_of",
    "right_of": "left_of",
    "above": "below",
    "below": "above",
    "in_front_of": "behind",
    "behind": "in_front_of",
}


def _relation_fact(subject: str, predicate: str, obj: str) -> dict[str, str]:
    return {"kind": "relation", "subject": subject, "predicate": predicate, "object": obj}


def _attribute_fact(subject: str, value: str) -> dict[str, str]:
    return {"kind": "attribute", "subject": subject, "predicate": "color", "object": value}


def _make_scene(
    rng: random.Random,
    index: int,
    split: str,
    shapes: list[str],
    colors: list[str],
    relations: list[str],
    min_entities: int,
    max_entities: int,
) -> dict[str, Any]:
    n_entities = rng.randint(min_entities, max_entities)
    entity_ids = [f"e{index:03d}_{j}" for j in range(n_entities)]
    entity_colors = rng.sample(colors, k=n_entities)
    entities = [
        {
            "entity_id": entity_id,
            "shape": shapes[(index + j) % len(shapes)],
            "color": entity_colors[j],
            "x": j,
            "y": (index + 2 * j) % n_entities,
            "z": (2 * index + j) % n_entities,
        }
        for j, entity_id in enumerate(entity_ids)
    ]
    predicate = relations[index % len(relations)]
    requested_depth = 1 + (index % 2)
    purpose = "uptake" if split == "uptake_validation" else "reasoning"

    if purpose == "uptake":
        target = entity_ids[0]
        required = [_attribute_fact(target, entity_colors[0])]
        question = {
            "question_type": "direct_uptake",
            "text": f"According to the supplied facts, what color is entity {target}?",
            "target_entity": target,
            "anchor_entity": None,
            "predicate": None,
            "options": list(colors),
            "answer": entity_colors[0],
            "reasoning_depth": 1,
            "required_facts": required,
        }
        relations_in_scene = [
            _relation_fact(entity_ids[0], predicate, entity_ids[1]),
            _relation_fact(entity_ids[1], INVERSE[predicate], entity_ids[0]),
        ]
    else:
        target = entity_ids[0]
        if requested_depth == 1:
            anchor = entity_ids[1]
            required = [
                _relation_fact(target, predicate, anchor),
                _attribute_fact(target, entity_colors[0]),
            ]
        else:
            middle, anchor = entity_ids[1], entity_ids[2]
            required = [
                _relation_fact(target, predicate, middle),
                _relation_fact(middle, predicate, anchor),
                _attribute_fact(target, entity_colors[0]),
            ]
        question = {
            "question_type": "relational_attribute_binding",
            "text": (
                f"What color is the entity that is {predicate} "
                f"{'twice from ' if requested_depth == 2 else ''}entity {anchor}?"
            ),
            "target_entity": target,
            "anchor_entity": anchor,
            "predicate": predicate,
            "options": list(colors),
            "answer": entity_colors[0],
            "reasoning_depth": requested_depth,
            "required_facts": required,
        }
        relations_in_scene = [fact for fact in required if fact["kind"] == "relation"]
        relations_in_scene += [
            _relation_fact(fact["object"], INVERSE[fact["predicate"]], fact["subject"])
            for fact in required
            if fact["kind"] == "relation"
        ]

    return {
        "scene_id": f"{split[:3]}_{index:04d}",
        "split": split,
        "template_id": f"{split}_template_{index % 4}",
        "entities": entities,
        "relations": relations_in_scene,
        "question": question,
        "answer": question["answer"],
        "reasoning_depth": question["reasoning_depth"],
        "required_facts": required,
    }


def generate_dataset(config_path: str | Path = "configs/pilot.yaml") -> dict[str, Any]:
    config = load_yaml(config_path)
    rng = random.Random(int(config["seed"]))
    scenes: list[dict[str, Any]] = []
    index = 0
    for split, count in config["splits"].items():
        for _ in range(int(count)):
            scenes.append(
                _make_scene(
                    rng,
                    index,
                    split,
                    list(config["shapes"]),
                    list(config["colors"]),
                    list(config["relations"]),
                    int(config["entities"]["min"]),
                    int(config["entities"]["max"]),
                )
            )
            index += 1

    output = Path("data/generated/scenes.jsonl")
    write_jsonl(output, scenes)
    summary = {
        "schema_version": 1,
        "seed": config["seed"],
        "scene_count": len(scenes),
        "split_counts": dict(Counter(scene["split"] for scene in scenes)),
        "depth_counts": dict(Counter(str(scene["reasoning_depth"]) for scene in scenes)),
        "relation_types_present": sorted(
            {fact["predicate"] for scene in scenes for fact in scene["relations"]}
        ),
        "scene_hash": sha256_file(output),
        "config_hash": canonical_hash(config),
    }
    dump_yaml("data/manifests/scene_manifest.yaml", summary)
    return summary

