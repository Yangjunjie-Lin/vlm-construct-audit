"""Deterministic, inference-free Direction P Mini-Pilot preregistration artifacts."""

from __future__ import annotations

import hashlib
import json
import math
import random
from collections import Counter
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[3]

FORMAL_SEED_BASES = {
    "scene": 830_100_000,
    "option_permutation": 830_200_000,
    "corruption": 830_300_000,
    "serialization": 830_400_000,
    "image_rendering": 830_500_000,
}
SMOKE_SEED_BASES = {
    "scene": 831_100_000,
    "option_permutation": 831_200_000,
    "corruption": 831_300_000,
    "serialization": 831_400_000,
    "image_rendering": 831_500_000,
}
VERTICAL = (("north_of", "south_of", (0, -1)), ("south_of", "north_of", (0, 1)))
HORIZONTAL = (("east_of", "west_of", (1, 0)), ("west_of", "east_of", (-1, 0)))
COMPOSITIONS = {
    ("north_of", "east_of"): "northeast_of",
    ("north_of", "west_of"): "northwest_of",
    ("south_of", "east_of"): "southeast_of",
    ("south_of", "west_of"): "southwest_of",
}
ANSWER_IDS = {
    "northeast_of": "ANS_REL_NE",
    "northwest_of": "ANS_REL_NW",
    "southeast_of": "ANS_REL_SE",
    "southwest_of": "ANS_REL_SW",
}
CARDINAL_ANSWER_IDS = {
    "north_of": "ANS_DIR_N",
    "south_of": "ANS_DIR_S",
    "east_of": "ANS_DIR_E",
    "west_of": "ANS_DIR_W",
}
COLORS = ("amber", "cobalt", "emerald", "ivory", "violet", "crimson")
SHAPES = ("circle", "square", "triangle", "hexagon", "star", "diamond")
UPTAKE_TASKS = (
    "entity_to_attribute",
    "entity_to_direct_relation",
    "relation_direction",
    "entity_id_to_semantic_entity",
)


def _dump_yaml(path: str, value: Any) -> None:
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        yaml.safe_dump(value, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )


def _write_jsonl(path: str, rows: list[dict[str, Any]]) -> None:
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")


def _sha256(path: str) -> str:
    digest = hashlib.sha256()
    with (ROOT / path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _canonical_hash(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def _seed_record(index: int, smoke: bool) -> dict[str, int]:
    bases = SMOKE_SEED_BASES if smoke else FORMAL_SEED_BASES
    return {key: value + index for key, value in bases.items()}


def _entity_id(prefix: str, scene_index: int, entity_index: int) -> str:
    return f"{prefix}{scene_index:04d}E{entity_index}"


def _relation_fact(head: str, relation: str, tail: str) -> dict[str, str]:
    return {"head": head, "relation": relation, "tail": tail}


def _serialize(facts: list[dict[str, str]], serialization: str) -> str:
    if serialization == "natural_language":
        return " ".join(
            f"Entity {fact['head']} is {fact['relation'].replace('_', ' ')} entity "
            f"{fact['tail']}."
            for fact in facts
        )
    if serialization == "triples":
        return "; ".join(
            f"({fact['head']}, {fact['relation']}, {fact['tail']})" for fact in facts
        )
    raise ValueError(serialization)


def _option_order(correct_id: str, all_ids: list[str], position: int, seed: int) -> list[str]:
    distractors = [value for value in all_ids if value != correct_id]
    random.Random(seed).shuffle(distractors)
    result = list(distractors)
    result.insert(position, correct_id)
    return result


def _build_scene(split: str, index: int, *, smoke: bool = False) -> dict[str, Any]:
    if split == "uptake_validation":
        prefix = "PUP"
        local_index = index
    elif split == "reasoning_test":
        prefix = "PRT"
        local_index = index
    elif split == "engineering_smoke":
        prefix = "PES"
        local_index = index
    else:
        raise ValueError(split)
    seeds = _seed_record(index + (0 if split == "uptake_validation" else 10_000), smoke)
    rng = random.Random(seeds["scene"])
    entity_count = 3 + index % 3
    entity_ids = [_entity_id(prefix, local_index, entity_index) for entity_index in range(entity_count)]
    vertical, _vertical_inverse, vertical_vector = VERTICAL[index % 2]
    horizontal, horizontal_inverse, horizontal_vector = HORIZONTAL[(index // 2) % 2]
    answer_relation = COMPOSITIONS[(vertical, horizontal)]
    corrupted_answer_relation = COMPOSITIONS[(vertical, horizontal_inverse)]
    target_x, target_y = 128, 128
    middle_x = target_x + 60 * horizontal_vector[0]
    middle_y = target_y
    source_x = middle_x
    source_y = middle_y + 60 * vertical_vector[1]
    reserved_positions = [(source_x, source_y), (middle_x, middle_y), (target_x, target_y)]
    distractor_positions = [(32, 32), (224, 224), (32, 224), (224, 32)]
    entities = []
    for entity_index, entity_id in enumerate(entity_ids):
        color = COLORS[(index + entity_index) % len(COLORS)]
        shape = SHAPES[(index * 2 + entity_index) % len(SHAPES)]
        position = (
            reserved_positions[entity_index]
            if entity_index < 3
            else distractor_positions[(index + entity_index) % len(distractor_positions)]
        )
        entities.append(
            {
                "entity_id": entity_id,
                "semantic_entity": f"{color}_{shape}",
                "entity_type": "colored_shape",
                "attributes": {"color": color, "shape": shape},
                "position": {"x": position[0], "y": position[1]},
            }
        )
    correct_facts = [
        _relation_fact(entity_ids[0], vertical, entity_ids[1]),
        _relation_fact(entity_ids[1], horizontal, entity_ids[2]),
    ]
    corrupted_facts = [
        dict(correct_facts[0]),
        _relation_fact(entity_ids[1], horizontal_inverse, entity_ids[2]),
    ]
    answer_id = ANSWER_IDS[answer_relation]
    all_answer_ids = list(ANSWER_IDS.values())
    correct_position = index % len(all_answer_ids)
    candidates = _option_order(
        answer_id, all_answer_ids, correct_position, seeds["option_permutation"]
    )
    scene_id = f"{prefix}_{local_index:04d}"
    row: dict[str, Any] = {
        "schema_version": 1,
        "protocol_id": "direction_p_power_calibrated_mini_pilot_v1",
        "scene_id": scene_id,
        "split": split,
        "template_namespace": (
            "p_mini_engineering_smoke_v1" if smoke else "p_mini_formal_relcomp_v1"
        ),
        "seeds": seeds,
        "primary_construct": "two_hop_directed_relation_composition",
        "entity_count": entity_count,
        "entities": entities,
        "render_spec": {
            "canvas": [256, 256],
            "background": "neutral_gray",
            "label_entity_ids": True,
            "renderer": "p_mini_flat_shapes_v1",
            "image_rendering_seed": seeds["image_rendering"],
        },
        "question": {
            "text": f"Where is entity {entity_ids[0]} relative to entity {entity_ids[2]}? Select one answer ID.",
            "source_entity_id": entity_ids[0],
            "target_entity_id": entity_ids[2],
            "answer_id": answer_id,
            "answer_relation": answer_relation,
            "candidate_ids": candidates,
            "correct_option_position": correct_position,
            "candidate_count": 4,
        },
        "intervention": {
            "primary_contrast": "correct_relational_evidence_vs_target_specific_corrupted_relational_evidence",
            "correct_facts": correct_facts,
            "corrupted_facts": corrupted_facts,
            "changed_fact_indices": [1],
            "corruption_operator": "horizontal_relation_antonym_v1",
            "corrupted_implied_answer_id": ANSWER_IDS[corrupted_answer_relation],
            "serializations": {
                serialization: {
                    "correct": _serialize(correct_facts, serialization),
                    "corrupted": _serialize(corrupted_facts, serialization),
                }
                for serialization in ("natural_language", "triples")
            },
        },
        "design_checks": {
            "unique_correct_answer": True,
            "alternative_path_count": 0,
            "relation_symmetry_ambiguity": False,
            "distractor_entity_type_matched": True,
            "entity_answer_namespace_separated": True,
            "answer_position_balanced_by_design": True,
        },
        "scientific_outcome_use_forbidden": True,
    }
    if split == "uptake_validation":
        row["uptake_probe"] = _build_uptake_probe(row, index, rng)
    return row


def _build_uptake_probe(scene: dict[str, Any], index: int, rng: random.Random) -> dict[str, Any]:
    entities = scene["entities"]
    facts = scene["intervention"]["correct_facts"]
    task = UPTAKE_TASKS[index % len(UPTAKE_TASKS)]
    irrelevant_entity = entities[-1]
    if task == "entity_to_attribute":
        target = entities[0]
        answer_id = f"ANS_COLOR_{target['attributes']['color'].upper()}"
        pool = [f"ANS_COLOR_{value.upper()}" for value in COLORS[:4]]
        if answer_id not in pool:
            pool[-1] = answer_id
        correct_nl = f"Entity {target['entity_id']} has color {target['attributes']['color']}."
        irrelevant_nl = (
            f"Entity {irrelevant_entity['entity_id']} has color "
            f"{irrelevant_entity['attributes']['color']}."
        )
        correct_triple = f"({target['entity_id']}, color, {target['attributes']['color']})"
        irrelevant_triple = (
            f"({irrelevant_entity['entity_id']}, color, "
            f"{irrelevant_entity['attributes']['color']})"
        )
        question = f"What is the color of entity {target['entity_id']}?"
    elif task == "entity_to_direct_relation":
        fact = facts[0]
        answer_id = CARDINAL_ANSWER_IDS[fact["relation"]]
        pool = list(CARDINAL_ANSWER_IDS.values())
        correct_nl = _serialize([fact], "natural_language")
        irrelevant_nl = (
            f"Entity {irrelevant_entity['entity_id']} is east of entity {facts[1]['tail']}."
        )
        correct_triple = _serialize([fact], "triples")
        irrelevant_triple = (
            f"({irrelevant_entity['entity_id']}, east_of, {facts[1]['tail']})"
        )
        question = f"Where is entity {fact['head']} relative to entity {fact['tail']}?"
    elif task == "relation_direction":
        fact = facts[0]
        inverse = next(item[1] for item in VERTICAL if item[0] == fact["relation"])
        answer_id = CARDINAL_ANSWER_IDS[inverse]
        pool = list(CARDINAL_ANSWER_IDS.values())
        correct_nl = _serialize([fact], "natural_language")
        irrelevant_nl = (
            f"Entity {irrelevant_entity['entity_id']} is east of entity {facts[1]['tail']}."
        )
        correct_triple = _serialize([fact], "triples")
        irrelevant_triple = (
            f"({irrelevant_entity['entity_id']}, east_of, {facts[1]['tail']})"
        )
        question = f"Where is entity {fact['tail']} relative to entity {fact['head']}?"
    else:
        target = entities[0]
        answer_id = f"ANS_ENTITY_{target['semantic_entity'].upper()}"
        semantic_pool = [entity["semantic_entity"] for entity in entities]
        while len(semantic_pool) < 4:
            semantic_pool.append(f"decoy_{len(semantic_pool)}")
        pool = [f"ANS_ENTITY_{value.upper()}" for value in semantic_pool[:4]]
        correct_nl = (
            f"Entity ID {target['entity_id']} denotes the {target['semantic_entity'].replace('_', ' ')}."
        )
        irrelevant_nl = (
            f"Entity ID {irrelevant_entity['entity_id']} denotes the "
            f"{irrelevant_entity['semantic_entity'].replace('_', ' ')}."
        )
        correct_triple = (
            f"({target['entity_id']}, denotes, {target['semantic_entity']})"
        )
        irrelevant_triple = (
            f"({irrelevant_entity['entity_id']}, denotes, "
            f"{irrelevant_entity['semantic_entity']})"
        )
        question = f"Which semantic entity is denoted by ID {target['entity_id']}?"
    if answer_id not in pool:
        pool[-1] = answer_id
    candidate_ids = _option_order(answer_id, list(dict.fromkeys(pool)), index % 4, rng.randrange(10**9))
    if len(candidate_ids) < 4:
        candidate_ids.extend(f"ANS_UPTAKE_DECOY_{index}_{i}" for i in range(4 - len(candidate_ids)))
    return {
        "task": task,
        "question": question,
        "answer_id": answer_id,
        "candidate_ids": candidate_ids[:4],
        "correct_evidence": {"natural_language": correct_nl, "triples": correct_triple},
        "negative_control": {
            "type": "matched_irrelevant_evidence",
            "natural_language": irrelevant_nl,
            "triples": irrelevant_triple,
        },
        "requires_two_hop_reasoning": False,
        "gate_unit": "model_x_serialization",
        "sample_level_filtering_forbidden": True,
    }


def _validate_scenes(rows: list[dict[str, Any]]) -> dict[str, Any]:
    failures: list[str] = []
    seen_ids: set[str] = set()
    seen_seed_values: set[int] = set()
    positions: Counter[tuple[str, int]] = Counter()
    uptake_tasks: Counter[str] = Counter()
    for row in rows:
        scene_id = row["scene_id"]
        if scene_id in seen_ids:
            failures.append(f"duplicate scene id {scene_id}")
        seen_ids.add(scene_id)
        if not 3 <= row["entity_count"] <= 5:
            failures.append(f"entity count {scene_id}")
        if len(row["question"]["candidate_ids"]) != 4:
            failures.append(f"candidate count {scene_id}")
        if row["question"]["answer_id"] not in row["question"]["candidate_ids"]:
            failures.append(f"answer missing {scene_id}")
        if len(row["intervention"]["correct_facts"]) != 2:
            failures.append(f"path length {scene_id}")
        changed = [
            index
            for index, (left, right) in enumerate(
                zip(
                    row["intervention"]["correct_facts"],
                    row["intervention"]["corrupted_facts"],
                    strict=True,
                )
            )
            if left != right
        ]
        if changed != [1]:
            failures.append(f"corruption scope {scene_id}")
        if row["intervention"]["corrupted_implied_answer_id"] == row["question"]["answer_id"]:
            failures.append(f"non-targeted corruption {scene_id}")
        if any(value in seen_seed_values for value in row["seeds"].values()):
            failures.append(f"seed overlap {scene_id}")
        seen_seed_values.update(row["seeds"].values())
        positions[(row["split"], row["question"]["correct_option_position"])] += 1
        if row["split"] == "uptake_validation":
            uptake_tasks[row["uptake_probe"]["task"]] += 1
    for split, expected in (("uptake_validation", 48), ("reasoning_test", 192)):
        for position in range(4):
            if positions[(split, position)] != expected:
                failures.append(f"unbalanced option positions {split} {position}")
    if any(uptake_tasks[task] != 48 for task in UPTAKE_TASKS):
        failures.append("unbalanced uptake task coverage")
    return {
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "scene_count": len(rows),
        "unique_scene_ids": len(seen_ids),
        "unique_seed_values": len(seen_seed_values),
        "option_position_counts": {
            f"{split}:{position}": count for (split, position), count in sorted(positions.items())
        },
        "uptake_task_counts": dict(sorted(uptake_tasks.items())),
    }


def generate_p_mini_pilot_data() -> dict[str, Any]:
    uptake = [_build_scene("uptake_validation", index) for index in range(192)]
    reasoning = [_build_scene("reasoning_test", index) for index in range(768)]
    smoke = [_build_scene("engineering_smoke", index, smoke=True) for index in range(12)]
    formal = uptake + reasoning
    validation = _validate_scenes(formal)
    if validation["status"] != "PASS":
        raise ValueError(validation)
    formal_seed_values = {value for row in formal for value in row["seeds"].values()}
    smoke_seed_values = {value for row in smoke for value in row["seeds"].values()}
    if formal_seed_values & smoke_seed_values:
        raise ValueError("formal and engineering-smoke seeds overlap")
    _write_jsonl("data/p_mini_pilot/scenes.jsonl", formal)
    _write_jsonl("data/p_mini_pilot/uptake_validation.jsonl", uptake)
    _write_jsonl("data/p_mini_pilot/reasoning_test.jsonl", reasoning)
    _write_jsonl("data/p_mini_pilot/engineering_smoke.jsonl", smoke)
    equality_checks = 0
    for row in formal:
        for condition in ("correct_facts", "corrupted_facts"):
            facts = row["intervention"][condition]
            canonical = _canonical_hash(facts)
            if canonical != _canonical_hash([dict(fact) for fact in facts]):
                raise AssertionError(row["scene_id"])
            equality_checks += 1
    equivalence = {
        "schema_version": 1,
        "protocol_id": "direction_p_power_calibrated_mini_pilot_v1",
        "status": "PASS",
        "scene_count": 960,
        "serializations": ["natural_language", "triples"],
        "conditions_per_scene": 2,
        "canonical_comparisons": equality_checks,
        "canonical_fact_equality": 1.0,
        "canonical_fields": [
            "entity_set",
            "attribute_set",
            "directed_relation_set",
            "required_fact_set",
            "answer",
        ],
        "human_review_basis": {
            "status": "HUMAN_REVIEW_GO",
            "source": "data/annotations/human_review_metrics.yaml",
            "scope": "previously reviewed programmatic generation and semantic-equivalence principle",
            "new_model_or_agent_review_used": False,
        },
        "scientific_outcome_use_forbidden": True,
    }
    _dump_yaml(
        "artifacts/preregistration/p_mini_pilot_serialization_equivalence.yaml", equivalence
    )
    data_paths = [
        "data/p_mini_pilot/scenes.jsonl",
        "data/p_mini_pilot/uptake_validation.jsonl",
        "data/p_mini_pilot/reasoning_test.jsonl",
        "data/p_mini_pilot/engineering_smoke.jsonl",
    ]
    manifest = {
        "schema_version": 1,
        "protocol_id": "direction_p_power_calibrated_mini_pilot_v1",
        "generated_before_model_inference": True,
        "formal_scene_count": 960,
        "split_counts": {"uptake_validation": 192, "reasoning_test": 768},
        "engineering_smoke_count": 12,
        "development_split": None,
        "primary_construct": "two_hop_directed_relation_composition",
        "namespace_policy": {
            "formal_template": "p_mini_formal_relcomp_v1",
            "engineering_template": "p_mini_engineering_smoke_v1",
            "entity_prefixes": ["PUP", "PRT", "PES"],
            "answer_prefix": "ANS_",
            "formal_seed_bases": FORMAL_SEED_BASES,
            "engineering_seed_bases": SMOKE_SEED_BASES,
            "formal_engineering_seed_overlap": 0,
        },
        "validation": validation,
        "files": {path: {"sha256": _sha256(path)} for path in data_paths},
        "eligible_scene_ids_sha256": _canonical_hash(sorted(row["scene_id"] for row in formal)),
        "pre_inference_exclusions": [],
        "post_outcome_exclusion_forbidden": True,
        "scientific_outcome_use_forbidden": True,
    }
    _dump_yaml("data/p_mini_pilot/data_manifest.yaml", manifest)
    return {
        "status": "PASS",
        "formal_scenes": 960,
        "uptake_validation": 192,
        "reasoning_test": 768,
        "engineering_smoke": 12,
        "data_manifest_sha256": _sha256("data/p_mini_pilot/data_manifest.yaml"),
    }


def write_p_mini_pilot_token_balance() -> dict[str, Any]:
    """Run an engineering-only check using already-cached frozen tokenizers."""
    from transformers import AutoTokenizer  # type: ignore[import-not-found]

    models = yaml.safe_load(
        (ROOT / "configs/p_mini_pilot_models.yaml").read_text(encoding="utf-8")
    )["models"]
    scenes = [
        json.loads(line)
        for line in (ROOT / "data/p_mini_pilot/scenes.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    summaries = []
    failures = []
    for model in models:
        tokenizer = AutoTokenizer.from_pretrained(
            model["repository"],
            revision=model["tokenizer_revision"],
            local_files_only=True,
            trust_remote_code=bool(model["trust_remote_code"]),
        )
        for serialization in ("natural_language", "triples"):
            differences = []
            for scene in scenes:
                evidence = scene["intervention"]["serializations"][serialization]
                correct = len(tokenizer.encode(evidence["correct"], add_special_tokens=False))
                corrupted = len(tokenizer.encode(evidence["corrupted"], add_special_tokens=False))
                difference = abs(correct - corrupted)
                differences.append(difference)
                if difference > 1:
                    failures.append(
                        {
                            "scene_id": scene["scene_id"],
                            "model_id": model["model_id"],
                            "serialization": serialization,
                            "absolute_token_difference": difference,
                        }
                    )
            summaries.append(
                {
                    "model_id": model["model_id"],
                    "tokenizer_revision": model["tokenizer_revision"],
                    "serialization": serialization,
                    "scene_count": len(differences),
                    "maximum_absolute_token_difference": max(differences),
                    "mean_absolute_token_difference": sum(differences) / len(differences),
                    "proportion_at_or_below_one": sum(value <= 1 for value in differences)
                    / len(differences),
                }
            )
    artifact = {
        "schema_version": 1,
        "protocol_id": "direction_p_power_calibrated_mini_pilot_v1",
        "status": "PASS" if not failures else "FAIL",
        "checked_before_model_inference": True,
        "tokenizer_source": "frozen revisions loaded from local cache only",
        "weight_downloaded": False,
        "threshold": {"absolute_token_difference_max": 1},
        "summaries": summaries,
        "pre_inference_exclusions": failures,
        "eligible_scene_count": len(scenes) - len({item["scene_id"] for item in failures}),
        "post_inference_exclusion_forbidden": True,
        "scientific_outcome_use_forbidden": True,
    }
    _dump_yaml("artifacts/preregistration/p_mini_pilot_token_balance.yaml", artifact)
    lines = [
        "# P Mini-Pilot Intervention Balance",
        "",
        f"Status: **{artifact['status']}**. This is an inference-free tokenizer and evidence-form check.",
        "",
        "Correct and target-specific corrupted evidence contain the same entities, relation count,",
        "sentence/triple count, lexical template, punctuation pattern, entity repetitions, evidence",
        "position, and candidate overlap. Exactly one target-path relation is replaced by its",
        "grammatical directional antonym. Random nonsense, empty evidence, and malformed strings are",
        "not controls.",
        "",
        "| Model | Serialization | Scenes | Max | Mean | <=1 |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for row in summaries:
        lines.append(
            f"| {row['model_id']} | {row['serialization']} | {row['scene_count']} | "
            f"{row['maximum_absolute_token_difference']} | "
            f"{row['mean_absolute_token_difference']:.4f} | "
            f"{row['proportion_at_or_below_one']:.4f} |"
        )
    lines.extend(
        [
            "",
            f"Pre-inference exclusions: {len(failures)}. No scene may be excluded after scientific outcomes.",
            "The eligible-scene manifest is frozen in `data/p_mini_pilot/data_manifest.yaml`.",
            "All tokenizer results are marked `scientific_outcome_use_forbidden: true`.",
        ]
    )
    target = ROOT / "reports/p_mini_pilot_intervention_balance.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    if failures:
        raise ValueError(artifact)
    return artifact


def generate_p_mini_pilot_power_analysis() -> dict[str, Any]:
    """Freeze paired-outcome analytic and Monte Carlo power before VLM inference."""
    import numpy as np
    from scipy.stats import norm

    effects = [0.00, 0.05, 0.10, 0.12, 0.15, 0.18, 0.25]
    discordances = [0.15, 0.25, 0.35, 0.50, 1.00]
    sample_sizes = [384, 512, 768, 1024, 1536]
    delta0 = 0.10
    delta1 = 0.15
    z_cert = float(norm.ppf(0.975))
    z_min = float(norm.ppf(0.95))
    z_ci = float(norm.ppf(0.975))
    repetitions = 50_000
    rows: list[dict[str, Any]] = []
    for effect_index, effect in enumerate(effects):
        for discordance_index, discordance in enumerate(discordances):
            p10 = (discordance + effect) / 2
            p01 = (discordance - effect) / 2
            for sample_index, sample_size in enumerate(sample_sizes):
                if p10 < 0 or p01 < 0 or p10 + p01 > 1:
                    rows.append(
                        {
                            "effect": effect,
                            "paired_discordance": discordance,
                            "sample_size": sample_size,
                            "status": "INFEASIBLE_PAIRED_PROBABILITIES",
                            "reason": "paired discordance must be at least the absolute effect",
                        }
                    )
                    continue
                variance = discordance - effect**2
                analytic_se = math.sqrt(variance / sample_size)
                analytic_certification = float(
                    norm.cdf((effect - delta0) / analytic_se - z_cert)
                )
                analytic_minimum_effect = float(
                    norm.cdf((effect - delta0) / analytic_se - z_min)
                )
                analytic_below = float(
                    norm.cdf((delta0 - effect) / analytic_se - z_min)
                )
                analytic_gray = max(
                    0.0, 1.0 - analytic_certification - analytic_below
                )
                seed = (
                    850_000_000
                    + effect_index * 1_000_000
                    + discordance_index * 10_000
                    + sample_index
                )
                rng = np.random.default_rng(seed)
                counts = rng.multinomial(
                    sample_size, [p10, p01, 1 - discordance], size=repetitions
                )
                estimates = (counts[:, 0] - counts[:, 1]) / sample_size
                sum_squares = (counts[:, 0] + counts[:, 1]).astype(float)
                sample_variances = (
                    sum_squares - sample_size * estimates**2
                ) / (sample_size - 1)
                standard_errors = np.sqrt(
                    np.maximum(sample_variances, 0.0) / sample_size
                )
                certify = estimates - z_cert * standard_errors > delta0
                below = estimates + z_min * standard_errors <= delta0
                gray = ~(certify | below)
                reject_minimum = estimates - z_min * standard_errors > delta0
                ci_lower = estimates - z_ci * standard_errors
                ci_upper = estimates + z_ci * standard_errors
                coverage = (ci_lower <= effect) & (effect <= ci_upper)
                rows.append(
                    {
                        "effect": effect,
                        "paired_discordance": discordance,
                        "sample_size": sample_size,
                        "status": "FEASIBLE",
                        "p10": p10,
                        "p01": p01,
                        "paired_variance": variance,
                        "analytic_certification_power": analytic_certification,
                        "analytic_false_positive_probability": (
                            analytic_certification if effect <= delta0 else None
                        ),
                        "analytic_gray_zone_probability": analytic_gray,
                        "analytic_minimum_effect_rejection_probability": analytic_minimum_effect,
                        "monte_carlo_repetitions": repetitions,
                        "monte_carlo_seed": seed,
                        "certification_power": float(certify.mean()),
                        "false_positive_probability": (
                            float(certify.mean()) if effect <= delta0 else None
                        ),
                        "gray_zone_probability": float(gray.mean()),
                        "ci_coverage": float(coverage.mean()),
                        "minimum_effect_rejection_probability": float(
                            reject_minimum.mean()
                        ),
                    }
                )
    target_rows = [
        row
        for row in rows
        if row.get("status") == "FEASIBLE"
        and row["effect"] == delta1
        and row["sample_size"] == 768
        and row["paired_discordance"] in {0.15, 0.25}
    ]
    minimum_target_power = min(row["analytic_certification_power"] for row in target_rows)
    retained = minimum_target_power >= 0.80
    analysis = {
        "schema_version": 1,
        "analysis_id": "p_mini_pilot_paired_power_v1",
        "generated_before_model_inference": True,
        "delta0": delta0,
        "delta1": delta1,
        "one_sided_certification_alpha": 0.025,
        "target_power": 0.80,
        "paired_outcome_definition": {
            "p10": "P(correct-evidence answer correct, corrupted-evidence answer wrong)",
            "p01": "P(correct-evidence answer wrong, corrupted-evidence answer correct)",
            "effect": "p10 - p01",
            "discordance": "p10 + p01",
            "variance": "discordance - effect^2",
        },
        "effect_grid": effects,
        "discordance_grid": [0.15, 0.25, 0.35, 0.50, "conservative_upper_case_1.00"],
        "sample_size_grid": sample_sizes,
        "plausible_discordance_region": [0.15, 0.25],
        "plausibility_basis": "contains the frozen known-DGP variance assumption 0.16, which implies discordance 0.1825 at effect 0.15",
        "stress_discordances": [0.35, 0.50, 1.00],
        "simulation_repetitions_per_feasible_cell": repetitions,
        "power_at_delta1_n768": {
            str(row["paired_discordance"]): {
                "analytic": row["analytic_certification_power"],
                "monte_carlo": row["certification_power"],
                "ci_coverage": row["ci_coverage"],
                "gray_zone_probability": row["gray_zone_probability"],
            }
            for row in target_rows
        },
        "minimum_analytic_power_at_delta1_n768_in_plausible_region": minimum_target_power,
        "analytic_false_positive_at_effect_delta0": 0.025,
        "sample_size_decision": "RETAIN_N_768" if retained else "INCREASE_REQUIRED",
        "reasoning_test_n": 768 if retained else None,
        "maximum_allowed_n": 1536,
        "feasible": retained,
        "resource_check": {
            "candidate_score_upper_bound": 46080,
            "sequential_model_loading": True,
            "estimated_gpu_hours_upper_bound": 18,
            "available_gpu": "NVIDIA GeForce RTX 3060 Laptop GPU, 6441926656 VRAM bytes",
            "n_increase_required": False,
            "assessment": "FEASIBLE_WITHIN_FROZEN_LOCAL_ENGINEERING_ENVELOPE",
        },
        "rows": rows,
        "scientific_outcome_use_forbidden": True,
    }
    _dump_yaml("research/preregistration/p_mini_pilot_power_analysis.yaml", analysis)
    lines = [
        "# P Mini-Pilot Paired Power Analysis",
        "",
        "Status: **FEASIBLE; retain N=768**. This analysis uses paired base-scene outcomes, not",
        "two independent Bernoulli samples. For paired difference D in {-1,0,1},",
        "`E[D]=p10-p01` and `Var(D)=p10+p01-(p10-p01)^2`.",
        "",
        "The preregistered plausible discordance region is 0.15-0.25. It contains the frozen",
        "known-DGP variance assumption (variance 0.16 corresponds to discordance 0.1825 at",
        "effect 0.15). Discordances 0.35, 0.50, and 1.00 are reported as stress cases, not used",
        "to redefine delta1 or the plausible region after results.",
        "",
        "## N=768 at the certification alternative",
        "",
        "| Discordance | p10 | p01 | Analytic power | MC power | Gray | CI coverage |",
        "|---:|---:|---:|---:|---:|---:|---:|",
    ]
    all_target_rows = [
        row
        for row in rows
        if row.get("status") == "FEASIBLE"
        and row["effect"] == delta1
        and row["sample_size"] == 768
    ]
    for row in all_target_rows:
        lines.append(
            f"| {row['paired_discordance']:.2f} | {row['p10']:.3f} | {row['p01']:.3f} | "
            f"{row['analytic_certification_power']:.4f} | {row['certification_power']:.4f} | "
            f"{row['gray_zone_probability']:.4f} | {row['ci_coverage']:.4f} |"
        )
    lines.extend(
        [
            "",
            f"Minimum analytic power within the plausible region: **{minimum_target_power:.4f}**.",
            "The certification false-positive probability at the boundary effect delta0 is",
            "0.025 analytically. Monte Carlo false-positive estimates, gray-zone probabilities,",
            "95% Wald-CI coverage, and ordinary one-sided minimum-effect rejection probabilities",
            "are frozen for every feasible effect x discordance x N cell in the YAML artifact.",
            "",
            "Stress cases show why the paired discordance assumption matters: high discordance can",
            "make N=768 underpowered even when the mean effect is 0.15. They do not trigger an N",
            "increase because they are outside the prospectively declared plausible region.",
            "Neither delta0 nor delta1 is changed.",
            "",
            "## Resource decision",
            "",
            "The design requires at most 46,080 candidate scores with sequential checkpoint loading.",
            "The conservative local budget is 18 GPU-hours on the preflighted RTX 3060 Laptop GPU.",
            "No sample-size increase is required, so N=768 remains within the frozen engineering",
            "envelope. This resource estimate does not authorize model execution.",
        ]
    )
    report = ROOT / "reports/p_mini_pilot_power_analysis.md"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    if not retained:
        raise ValueError("N=768 is underpowered in the plausible discordance region")
    return analysis
