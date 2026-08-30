"""Leakage-resistant data generation for cross-modal bridge composition."""

from __future__ import annotations

import hashlib
import json
import random
import uuid
from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[3]
PROTOCOL_ID = "direction_p_construct_valid_mini_pilot_v2"
NAMESPACE = uuid.UUID("927c4ec0-9e7c-4e3f-aa88-10901ecb9193")
ANSWERS = ("northeast", "northwest", "southeast", "southwest")
CARDINALS = ("north", "south", "east", "west")
INVERSE = {"north": "south", "south": "north", "east": "west", "west": "east"}
VECTORS = {
    "north": (0, -1),
    "south": (0, 1),
    "east": (1, 0),
    "west": (-1, 0),
}
COMPOSE = {
    ("north", "east"): "northeast",
    ("east", "north"): "northeast",
    ("north", "west"): "northwest",
    ("west", "north"): "northwest",
    ("south", "east"): "southeast",
    ("east", "south"): "southeast",
    ("south", "west"): "southwest",
    ("west", "south"): "southwest",
}
DECOMPOSITIONS = tuple((first, second, answer) for (first, second), answer in COMPOSE.items())
COLORS = (
    "red", "blue", "green", "amber", "violet", "coral",
    "teal", "indigo", "gold", "pink", "brown", "gray",
)
SHAPES = (
    "circle", "square", "triangle", "hexagon", "diamond", "star",
    "pentagon", "cross", "oval", "trapezoid", "crescent", "octagon",
)
QUESTION_TEMPLATES = {
    "where": "Where is the {source} relative to the {target}?",
    "locate": "Locate the {source} in relation to the {target}.",
    "directional": "What is the direction of the {source} from the {target}?",
    "relation": "Which relation describes the {source} relative to the {target}?",
}
UPTAKE_TASKS = (
    "visual_hop_relation",
    "textual_bridge_relation",
    "direction_reversal",
    "cross_modal_bridge_binding",
)


def _load_yaml(path: str) -> dict[str, Any]:
    return yaml.safe_load((ROOT / path).read_text(encoding="utf-8"))


def _dump_yaml(path: str, value: Any) -> None:
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(yaml.safe_dump(value, sort_keys=False, allow_unicode=True), encoding="utf-8")


def _write_jsonl(path: str, rows: Iterable[dict[str, Any]]) -> None:
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _relation_fact(head_role: str, relation: str, tail_role: str) -> dict[str, str]:
    return {"head_role": head_role, "relation": f"{relation}_of", "tail_role": tail_role}


def _serialize(head: str, relation: str, tail: str, serialization: str) -> str:
    if serialization == "natural_language":
        return f"The {head} is {relation} of the {tail}."
    if serialization == "triples":
        return f"({head}, {relation}_of, {tail})"
    raise ValueError(serialization)


def _descriptor_sets(count: int, seed: int) -> list[list[dict[str, str]]]:
    """Return independent, within-scene unique color/shape descriptors.

    The same descriptor set is deliberately reused across every relation in one
    nuisance group, so question text and entity labels are conditionally balanced
    over all four final answers.
    """

    rng = random.Random(seed)
    pairs = [(color, shape) for color in COLORS for shape in SHAPES]
    result = []
    for _ in range(count):
        selected = rng.sample(pairs, 5)
        result.append(
            [
                {"color": color, "shape": shape, "descriptor": f"{color} {shape}"}
                for color, shape in selected
            ]
        )
    return result


def _internal_uuid(split: str, nonce: int) -> str:
    return str(uuid.uuid5(NAMESPACE, f"{split}:{nonce:032x}"))


def _seed_bundle(rng: random.Random) -> dict[str, int]:
    return {
        "scene_seed": rng.randrange(1, 2**63),
        "option_permutation_seed": rng.randrange(1, 2**63),
        "corruption_seed": rng.randrange(1, 2**63),
        "rendering_seed": rng.randrange(1, 2**63),
    }


def _roles(descriptors: list[dict[str, str]], entity_count: int) -> list[dict[str, Any]]:
    role_names = ("A", "B", "C", "D", "E")[:entity_count]
    rows = []
    for role, descriptor in zip(role_names, descriptors[:entity_count], strict=True):
        rows.append(
            {
                "entity_uuid": str(uuid.uuid5(NAMESPACE, f"entity:{role}:{descriptor['descriptor']}")),
                "role": role,
                **descriptor,
                "visible_in_image": role != "C",
                "model_visible_identifier": descriptor["descriptor"],
            }
        )
    return rows


def _render_entities(entities: list[dict[str, Any]], first_relation: str) -> list[dict[str, Any]]:
    by_role = {entity["role"]: entity for entity in entities}
    dx, dy = VECTORS[first_relation]
    positions = {"B": (128, 128), "A": (128 + 64 * dx, 128 + 64 * dy)}
    distractor_positions = {"D": (42, 214), "E": (214, 42)}
    result = []
    for role in ("A", "B", "D", "E"):
        if role not in by_role:
            continue
        x, y = positions[role] if role in positions else distractor_positions[role]
        result.append(
            {
                "role": role,
                "descriptor": by_role[role]["descriptor"],
                "color": by_role[role]["color"],
                "shape": by_role[role]["shape"],
                "x": x,
                "y": y,
            }
        )
    return result


def _option_mapping(order: tuple[str, ...]) -> dict[str, str]:
    return dict(zip(("A", "B", "C", "D"), order, strict=True))


def _reasoning_row(
    *, split: str, index: int, group: int, first: str, second: str, answer: str,
    template_id: str, entity_count: int, descriptors: list[dict[str, str]],
    option_order: tuple[str, ...], seeds: dict[str, int], nonce: int,
) -> dict[str, Any]:
    entities = _roles(descriptors, entity_count)
    by_role = {entity["role"]: entity for entity in entities}
    corrupted_second = INVERSE[second]
    corrupted_answer = COMPOSE[(first, corrupted_second)]
    scene_uuid = _internal_uuid(split, nonce)
    question_text = QUESTION_TEMPLATES[template_id].format(
        source=by_role["A"]["descriptor"], target=by_role["C"]["descriptor"]
    )
    correct_fact = _relation_fact("B", second, "C")
    corrupted_fact = _relation_fact("B", corrupted_second, "C")
    return {
        "schema_version": 1,
        "protocol_id": PROTOCOL_ID,
        "protocol_revision": 1,
        "scene_uuid": scene_uuid,
        "internal_scene_id": f"cv2:{scene_uuid}",
        "scene_index": index,
        "nuisance_group": group,
        "split": split,
        "template_id": template_id,
        "entity_count": entity_count,
        "seeds": seeds,
        "entities": entities,
        "modality_allocation": {
            "image_entity_roles": [entity["role"] for entity in entities if entity["visible_in_image"]],
            "text_only_entity_roles": ["C"],
            "c_spatially_rendered": False,
        },
        "image": {
            "path": f"data/construct_v2/images/{scene_uuid}.png",
            "canonical_facts": [_relation_fact("A", first, "B")],
            "render_entities": _render_entities(entities, first),
            "canvas": [256, 256],
            "contains_model_visible_id": False,
        },
        "evidence": {
            "correct": {
                "canonical_facts": [correct_fact],
                "natural_language": _serialize(
                    by_role["B"]["descriptor"], second, by_role["C"]["descriptor"],
                    "natural_language",
                ),
                "triples": _serialize(
                    by_role["B"]["descriptor"], second, by_role["C"]["descriptor"],
                    "triples",
                ),
            },
            "corrupted": {
                "canonical_facts": [corrupted_fact],
                "natural_language": _serialize(
                    by_role["B"]["descriptor"], corrupted_second,
                    by_role["C"]["descriptor"], "natural_language",
                ),
                "triples": _serialize(
                    by_role["B"]["descriptor"], corrupted_second,
                    by_role["C"]["descriptor"], "triples",
                ),
            },
            "changed_fact_count": 1,
            "changed_field": "relation",
            "direct_image_text_conflict": False,
        },
        "question": {
            "text": question_text,
            "source_role": "A",
            "bridge_role": "B",
            "target_role": "C",
            "requires_image_entity": by_role["A"]["descriptor"],
            "requires_text_entity": by_role["C"]["descriptor"],
            "requires_shared_bridge": by_role["B"]["descriptor"],
        },
        "answer": {
            "semantic": answer,
            "corrupted_semantic": corrupted_answer,
            "semantic_candidates": list(option_order),
            "option_mapping": _option_mapping(option_order),
            "correct_option_position": option_order.index(answer),
            "primary_score_target": "semantic_candidate_text",
        },
        "model_visible": {
            "scene_id_included": False,
            "entity_uuid_included": False,
            "relation_coded_candidate_id_included": False,
        },
    }


def build_reasoning_rows(n: int, *, split: str = "reasoning_test", seed: int = 862001) -> list[dict[str, Any]]:
    if n % len(DECOMPOSITIONS):
        raise ValueError("reasoning scene count must be divisible by 8")
    group_count = n // len(DECOMPOSITIONS)
    descriptor_sets = _descriptor_sets(group_count, seed + 11)
    rng = random.Random(seed + {"reasoning_test": 1000, "engineering_smoke": 2000}.get(split, 3000))
    candidate_base = list(ANSWERS)
    rng.shuffle(candidate_base)
    template_ids = tuple(QUESTION_TEMPLATES)
    rows = []
    for group in range(group_count):
        template_id = template_ids[group % len(template_ids)]
        entity_count = 3 + (group % 3)
        offset = group % len(candidate_base)
        option_order = tuple(candidate_base[offset:] + candidate_base[:offset])
        group_nonce = rng.randrange(1, 2**127)
        group_seeds = [_seed_bundle(rng) for _ in DECOMPOSITIONS]
        relation_rows = []
        for relation_index, (first, second, answer) in enumerate(DECOMPOSITIONS):
            relation_rows.append(
                _reasoning_row(
                    split=split,
                    index=-1,
                    group=group,
                    first=first,
                    second=second,
                    answer=answer,
                    template_id=template_id,
                    entity_count=entity_count,
                    descriptors=descriptor_sets[group],
                    option_order=option_order,
                    seeds=group_seeds[relation_index],
                    nonce=group_nonce + relation_index,
                )
            )
        rows.extend(relation_rows)
    rng.shuffle(rows)
    for index, row in enumerate(rows):
        row["scene_index"] = index
    return rows


def _uptake_question(task: str, by_role: dict[str, dict[str, Any]]) -> str:
    if task == "visual_hop_relation":
        return f"Where is the {by_role['A']['descriptor']} relative to the {by_role['B']['descriptor']}?"
    if task == "textual_bridge_relation":
        return f"According to the evidence, where is the {by_role['B']['descriptor']} relative to the {by_role['C']['descriptor']}?"
    if task == "direction_reversal":
        return f"According to the evidence, where is the {by_role['C']['descriptor']} relative to the {by_role['B']['descriptor']}?"
    return f"Where is the object identified by the evidence relative to the {by_role['A']['descriptor']}?"


def build_uptake_rows(n: int = 256, *, seed: int = 862701) -> list[dict[str, Any]]:
    if n != 256:
        raise ValueError("formal uptake validation is frozen at 256 scenes")
    rng = random.Random(seed)
    descriptor_sets = _descriptor_sets(64, seed + 17)
    candidate_base = list(CARDINALS)
    rng.shuffle(candidate_base)
    rows = []
    for task_index, task in enumerate(UPTAKE_TASKS):
        for group in range(16):
            descriptors = descriptor_sets[task_index * 16 + group]
            entities = _roles(descriptors, 5)
            by_role = {entity["role"]: entity for entity in entities}
            offset = group % len(candidate_base)
            option_order = tuple(candidate_base[offset:] + candidate_base[:offset])
            for relation_index, relation in enumerate(CARDINALS):
                answer = INVERSE[relation] if task == "direction_reversal" else relation
                scene_uuid = _internal_uuid(
                    "uptake_validation", rng.randrange(1, 2**127)
                )
                render_relation = relation
                relevant_text = _serialize(
                    by_role["B"]["descriptor"], relation, by_role["C"]["descriptor"],
                    "natural_language",
                )
                irrelevant_text = _serialize(
                    by_role["D"]["descriptor"], relation, by_role["E"]["descriptor"],
                    "natural_language",
                )
                if task == "cross_modal_bridge_binding":
                    # B is the text-identified object; B relative to A is the answer.
                    relevant_text = f"The bridge object is the {by_role['B']['descriptor']}."
                    irrelevant_text = f"The bridge object is the {by_role['C']['descriptor']}."
                    render_relation = INVERSE[relation]
                rows.append(
                    {
                        "schema_version": 1,
                        "protocol_id": PROTOCOL_ID,
                        "protocol_revision": 1,
                        "scene_uuid": scene_uuid,
                        "internal_scene_id": f"cv2u:{scene_uuid}",
                        "scene_index": -1,
                        "split": "uptake_validation",
                        "uptake_task": task,
                        "template_id": f"uptake_{task}_v1",
                        "entity_count": 5,
                        "seeds": _seed_bundle(rng),
                        "entities": entities,
                        "image": {
                            "path": f"data/construct_v2/images/{scene_uuid}.png",
                            "irrelevant_control_path": (
                                f"data/construct_v2/images/{scene_uuid}_irrelevant.png"
                            ),
                            "canonical_facts": [_relation_fact("A", render_relation, "B")],
                            "render_entities": _render_entities(entities, render_relation),
                            "irrelevant_render_entities": [
                                {**entity, "x": 128, "y": 128}
                                for entity in _render_entities(entities, render_relation)
                                if entity["role"] in {"A", "B"}
                            ],
                            "contains_model_visible_id": False,
                        },
                        "evidence": {
                            "relevant": relevant_text,
                            "matched_irrelevant": irrelevant_text,
                        },
                        "question": {"text": _uptake_question(task, by_role)},
                        "answer": {
                            "semantic": answer,
                            "semantic_candidates": list(option_order),
                            "option_mapping": _option_mapping(option_order),
                            "correct_option_position": option_order.index(answer),
                        },
                        "negative_control": {
                            "matched": True,
                            "target_accuracy_upper_bound": 0.40,
                            "paired_utility_minimum": 0.20,
                        },
                        "model_visible": {
                            "scene_id_included": False,
                            "entity_uuid_included": False,
                            "relation_coded_candidate_id_included": False,
                        },
                    }
                )
    rng.shuffle(rows)
    for index, row in enumerate(rows):
        row["scene_index"] = index
    return rows


def _selected_reasoning_n() -> int:
    power_path = ROOT / "artifacts/construct_v2/multiplicity_power.yaml"
    if not power_path.exists():
        raise RuntimeError("run analyze-construct-v2-power before formal data generation")
    power = yaml.safe_load(power_path.read_text(encoding="utf-8"))
    n = power.get("chosen_reasoning_n")
    if n not in {768, 1024, 1280, 1536}:
        raise RuntimeError("power analysis did not select a feasible preregistered N")
    return int(n)


def generate_construct_v2(reasoning_n: int | None = None) -> dict[str, Any]:
    """Generate all v2 data without invoking a model or tokenizer."""

    config = _load_yaml("configs/construct_v2/data.yaml")
    chosen_n = _selected_reasoning_n() if reasoning_n is None else reasoning_n
    uptake = build_uptake_rows(config["splits"]["uptake_validation"])
    reasoning = build_reasoning_rows(chosen_n)
    smoke = build_reasoning_rows(config["splits"]["engineering_smoke"], split="engineering_smoke")
    all_formal = uptake + reasoning
    _write_jsonl("data/construct_v2/uptake_validation.jsonl", uptake)
    _write_jsonl("data/construct_v2/reasoning_test.jsonl", reasoning)
    _write_jsonl("data/construct_v2/engineering_smoke.jsonl", smoke)
    _write_jsonl("data/construct_v2/scenes.jsonl", all_formal)

    from .renderer import render_dataset

    rendered = render_dataset(all_formal + smoke)
    paths = [
        "data/construct_v2/uptake_validation.jsonl",
        "data/construct_v2/reasoning_test.jsonl",
        "data/construct_v2/engineering_smoke.jsonl",
        "data/construct_v2/scenes.jsonl",
    ]
    manifest = {
        "schema_version": 1,
        "protocol_id": PROTOCOL_ID,
        "protocol_revision": config["protocol_revision"],
        "scientific_model_inference_used": False,
        "v1_scene_reuse": False,
        "counts": {
            "uptake_validation": len(uptake),
            "reasoning_test": len(reasoning),
            "engineering_smoke": len(smoke),
            "formal_total": len(all_formal),
        },
        "rendered_images": rendered,
        "files": {path: _sha256(ROOT / path) for path in paths},
        "answer_counts": dict(Counter(row["answer"]["semantic"] for row in reasoning)),
    }
    _dump_yaml("data/construct_v2/data_manifest.yaml", manifest)
    return {"status": "GENERATED", **manifest["counts"], "rendered_images": rendered}
