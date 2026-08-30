"""Independent programmatic construct and leakage audit for all frozen scenes."""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data/p_mini_pilot"
OUTPUT = ROOT / "artifacts/independent_audit/data_construct_metrics.yaml"
LEAKAGE_OUTPUT = ROOT / "artifacts/independent_audit/data_leakage_checks.yaml"

VECTORS = {
    "north_of": (0, -1),
    "south_of": (0, 1),
    "east_of": (1, 0),
    "west_of": (-1, 0),
}
DIAGONALS = {
    (1, -1): "northeast_of",
    (-1, -1): "northwest_of",
    (1, 1): "southeast_of",
    (-1, 1): "southwest_of",
}
ANSWER_IDS = {
    "northeast_of": "ANS_REL_NE",
    "northwest_of": "ANS_REL_NW",
    "southeast_of": "ANS_REL_SE",
    "southwest_of": "ANS_REL_SW",
}
INVERSES = {
    "north_of": "south_of",
    "south_of": "north_of",
    "east_of": "west_of",
    "west_of": "east_of",
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def fact_tuple(fact: dict[str, str]) -> tuple[str, str, str]:
    return fact["head"], fact["relation"], fact["tail"]


def parse_natural_language(text: str) -> list[tuple[str, str, str]]:
    pattern = re.compile(r"Entity (\S+) is ([a-z ]+) entity (\S+)\.")
    return [
        (head, relation.replace(" ", "_"), tail) for head, relation, tail in pattern.findall(text)
    ]


def parse_triples(text: str) -> list[tuple[str, str, str]]:
    pattern = re.compile(r"\(([^,]+), ([^,]+), ([^)]+)\)")
    return [(head, relation, tail) for head, relation, tail in pattern.findall(text)]


def composed_relation(facts: list[dict[str, str]]) -> str | None:
    if len(facts) != 2 or facts[0]["tail"] != facts[1]["head"]:
        return None
    left = VECTORS.get(facts[0]["relation"])
    right = VECTORS.get(facts[1]["relation"])
    if left is None or right is None:
        return None
    vector = (left[0] + right[0], left[1] + right[1])
    return DIAGONALS.get(vector)


def coordinate_relation(scene: dict[str, Any]) -> str | None:
    positions = {
        entity["entity_id"]: (entity["position"]["x"], entity["position"]["y"])
        for entity in scene["entities"]
    }
    source = positions[scene["question"]["source_entity_id"]]
    target = positions[scene["question"]["target_entity_id"]]
    delta = (
        1 if source[0] > target[0] else -1 if source[0] < target[0] else 0,
        1 if source[1] > target[1] else -1 if source[1] < target[1] else 0,
    )
    return DIAGONALS.get(delta)


def simple_path_count(scene: dict[str, Any]) -> int:
    graph: dict[str, set[str]] = defaultdict(set)
    for fact in scene["intervention"]["correct_facts"]:
        graph[fact["head"]].add(fact["tail"])
        graph[fact["tail"]].add(fact["head"])
    source = scene["question"]["source_entity_id"]
    target = scene["question"]["target_entity_id"]
    count = 0

    def visit(node: str, seen: set[str]) -> None:
        nonlocal count
        if node == target:
            count += 1
            return
        for neighbor in graph[node] - seen:
            visit(neighbor, seen | {neighbor})

    visit(source, {source})
    return count


def rate(values: list[bool]) -> float:
    return sum(values) / len(values) if values else 0.0


def main() -> int:
    scenes = read_jsonl(DATA / "scenes.jsonl")
    uptake = read_jsonl(DATA / "uptake_validation.jsonl")
    reasoning = read_jsonl(DATA / "reasoning_test.jsonl")
    smoke = read_jsonl(DATA / "engineering_smoke.jsonl")

    scene_ids = [row["scene_id"] for row in scenes]
    uptake_ids = {row["scene_id"] for row in uptake}
    reasoning_ids = {row["scene_id"] for row in reasoning}
    smoke_ids = {row["scene_id"] for row in smoke}
    formal_seeds = [seed for row in scenes for seed in row["seeds"].values()]
    smoke_seeds = [seed for row in smoke for seed in row["seeds"].values()]

    unique_answer_checks: list[bool] = []
    path_checks: list[bool] = []
    alternative_path_checks: list[bool] = []
    relation_direction_checks: list[bool] = []
    corruption_count_checks: list[bool] = []
    corruption_equivalence_checks: list[bool] = []
    corrupted_answer_checks: list[bool] = []
    namespace_checks: list[bool] = []
    nl_checks: list[bool] = []
    triple_checks: list[bool] = []
    image_oracle_checks: list[bool] = []
    evidence_oracle_checks: list[bool] = []
    corrupted_evidence_gold_checks: list[bool] = []
    index_answer_checks: list[bool] = []
    index_position_checks: list[bool] = []
    candidate_semantic_checks: list[bool] = []
    entity_index_checks: list[bool] = []
    answer_counts: Counter[str] = Counter()
    answer_relation_counts: Counter[str] = Counter()
    positions: Counter[str] = Counter()
    whitespace_differences: dict[str, list[int]] = defaultdict(list)
    character_differences: dict[str, list[int]] = defaultdict(list)

    mod4_to_answer: dict[int, str] = {
        0: "ANS_REL_NE",
        1: "ANS_REL_SE",
        2: "ANS_REL_NW",
        3: "ANS_REL_SW",
    }
    for scene in scenes:
        question = scene["question"]
        intervention = scene["intervention"]
        correct = intervention["correct_facts"]
        corrupted = intervention["corrupted_facts"]
        candidates = question["candidate_ids"]
        answer = question["answer_id"]
        index = int(re.search(r"_(\d+)$", scene["scene_id"]).group(1))
        entity_ids = {entity["entity_id"] for entity in scene["entities"]}

        unique_answer_checks.append(
            len(candidates) == len(set(candidates)) and candidates.count(answer) == 1
        )
        composed = composed_relation(correct)
        path_checks.append(composed is not None and ANSWER_IDS[composed] == answer)
        paths = simple_path_count(scene)
        alternative_path_checks.append(
            paths == 1 and scene["design_checks"]["alternative_path_count"] == 0
        )

        positions_by_id = {
            entity["entity_id"]: (entity["position"]["x"], entity["position"]["y"])
            for entity in scene["entities"]
        }
        fact_geometry_ok = True
        for fact in correct:
            head = positions_by_id[fact["head"]]
            tail = positions_by_id[fact["tail"]]
            observed = (
                1 if head[0] > tail[0] else -1 if head[0] < tail[0] else 0,
                1 if head[1] > tail[1] else -1 if head[1] < tail[1] else 0,
            )
            fact_geometry_ok &= observed == VECTORS[fact["relation"]]
        relation_direction_checks.append(fact_geometry_ok)

        changed = [
            i for i, pair in enumerate(zip(correct, corrupted, strict=True)) if pair[0] != pair[1]
        ]
        corruption_count_checks.append(changed == [1])
        changed_left, changed_right = correct[1], corrupted[1]
        corruption_equivalence_checks.append(
            changed_left["head"] == changed_right["head"]
            and changed_left["tail"] == changed_right["tail"]
            and INVERSES[changed_left["relation"]] == changed_right["relation"]
        )
        corrupted_relation = composed_relation(corrupted)
        corrupted_answer_checks.append(
            corrupted_relation is not None
            and ANSWER_IDS[corrupted_relation] == intervention["corrupted_implied_answer_id"]
            and intervention["corrupted_implied_answer_id"] != answer
        )
        namespace_checks.append(not (entity_ids & set(candidates)) and answer.startswith("ANS_"))

        expected_correct = [fact_tuple(fact) for fact in correct]
        expected_corrupted = [fact_tuple(fact) for fact in corrupted]
        for serialization, record in intervention["serializations"].items():
            parser = (
                parse_natural_language if serialization == "natural_language" else parse_triples
            )
            nl_or_triple_correct = parser(record["correct"]) == expected_correct
            nl_or_triple_corrupt = parser(record["corrupted"]) == expected_corrupted
            if serialization == "natural_language":
                nl_checks.extend([nl_or_triple_correct, nl_or_triple_corrupt])
            else:
                triple_checks.extend([nl_or_triple_correct, nl_or_triple_corrupt])
            whitespace_differences[serialization].append(
                abs(len(record["correct"].split()) - len(record["corrupted"].split()))
            )
            character_differences[serialization].append(
                abs(len(record["correct"]) - len(record["corrupted"]))
            )

        image_oracle_checks.append(ANSWER_IDS[coordinate_relation(scene)] == answer)
        evidence_oracle_checks.append(ANSWER_IDS[composed_relation(correct)] == answer)
        corrupted_evidence_gold_checks.append(ANSWER_IDS[composed_relation(corrupted)] == answer)
        index_answer_checks.append(mod4_to_answer[index % 4] == answer)
        index_position_checks.append(index % 4 == question["correct_option_position"])
        candidate_semantic_checks.append(
            all(re.fullmatch(r"ANS_REL_(NE|NW|SE|SW)", candidate) for candidate in candidates)
        )
        entity_index_checks.append(
            all(
                f"{index:04d}" in entity_id
                for entity_id in (question["source_entity_id"], question["target_entity_id"])
            )
        )
        answer_counts[answer] += 1
        answer_relation_counts[question["answer_relation"]] += 1
        positions[f"{scene['split']}:{question['correct_option_position']}"] += 1

    uptake_task_counts: Counter[str] = Counter()
    uptake_answers: dict[str, Counter[str]] = defaultdict(Counter)
    uptake_positions: dict[str, Counter[int]] = defaultdict(Counter)
    uptake_index_position: list[bool] = []
    uptake_semantic_candidates: list[bool] = []
    for scene in uptake:
        probe = scene["uptake_probe"]
        task = probe["task"]
        index = int(re.search(r"_(\d+)$", scene["scene_id"]).group(1))
        answer = probe["answer_id"]
        position = probe["candidate_ids"].index(answer)
        uptake_task_counts[task] += 1
        uptake_answers[task][answer] += 1
        uptake_positions[task][position] += 1
        uptake_index_position.append(position == index % 4)
        uptake_semantic_candidates.append(
            all(candidate.startswith("ANS_") for candidate in probe["candidate_ids"])
        )

    prereg_text = "\n".join(
        path.read_text(encoding="utf-8", errors="ignore").lower()
        for base in (ROOT / "research/preregistration", ROOT / "reports", ROOT / "docs")
        for path in base.rglob("*")
        if path.is_file()
        and "independent_audit" not in path.parts
        and path.suffix in {".md", ".yaml", ".yml"}
    )
    leakage_acknowledgment_terms = {
        "question_only_leakage": "question-only" in prereg_text or "question only" in prereg_text,
        "template_index_leakage": "template-index leakage" in prereg_text
        or "template index leakage" in prereg_text,
        "entity_id_leakage": "entity-id leakage" in prereg_text
        or "entity id leakage" in prereg_text,
        "option_position_leakage": "option-position leakage" in prereg_text
        or "option position leakage" in prereg_text,
    }

    uptake_task_summary = {}
    for task in sorted(uptake_task_counts):
        counts = uptake_answers[task]
        position_counts = uptake_positions[task]
        uptake_task_summary[task] = {
            "scene_count": uptake_task_counts[task],
            "answer_counts": dict(sorted(counts.items())),
            "majority_answer_rate": max(counts.values()) / uptake_task_counts[task],
            "correct_option_position_counts": {
                str(k): v for k, v in sorted(position_counts.items())
            },
            "task_label_to_option_position_accuracy": max(position_counts.values())
            / uptake_task_counts[task],
        }

    leakage = {
        "question_only_answer_leakage": {
            "scene_index_visible_in_question_entity_ids_rate": rate(entity_index_checks),
            "scene_index_mod4_to_answer_id_accuracy": rate(index_answer_checks),
            "finding": "FATAL_UNRECORDED_LEAKAGE",
        },
        "candidate_id_semantic_leakage": {
            "primary_candidate_sets_directly_encode_NE_NW_SE_SW_rate": rate(
                candidate_semantic_checks
            ),
            "classification": "predeclared_in_generator_but_not_justified_as_nonleaking_measurement_label",
        },
        "option_position_leakage": {
            "scene_index_mod4_to_correct_position_accuracy": rate(index_position_checks),
            "uptake_task_or_index_to_correct_position_accuracy": rate(uptake_index_position),
        },
        "template_index_leakage": {
            "template_index_mod4_to_answer_accuracy": rate(index_answer_checks),
        },
        "answer_frequency": {
            "primary_answer_counts": dict(sorted(answer_counts.items())),
            "primary_majority_rate": max(answer_counts.values()) / len(scenes),
            "uptake_by_task": uptake_task_summary,
        },
        "relation_frequency": {
            "primary_answer_relation_counts": dict(sorted(answer_relation_counts.items())),
            "primary_balanced": len(set(answer_relation_counts.values())) == 1,
            "entity_to_direct_relation_all_same_answer": len(
                uptake_answers["entity_to_direct_relation"]
            )
            == 1,
            "relation_direction_all_same_answer": len(uptake_answers["relation_direction"]) == 1,
        },
        "image_coordinate_only_solvability": rate(image_oracle_checks),
        "correct_evidence_only_solvability": rate(evidence_oracle_checks),
        "corrupted_evidence_only_gold_accuracy": rate(corrupted_evidence_gold_checks),
        "preregistration_leakage_acknowledgments": leakage_acknowledgment_terms,
        "unrecorded_answer_leakage_present": not all(leakage_acknowledgment_terms.values())
        and rate(index_answer_checks) == 1.0,
    }

    checks = {
        "scene_count_960": len(scenes) == 960,
        "split_counts_192_768": len(uptake) == 192 and len(reasoning) == 768,
        "split_disjointness": not (uptake_ids & reasoning_ids),
        "split_union_equals_scenes": uptake_ids | reasoning_ids == set(scene_ids),
        "engineering_ids_disjoint": not (smoke_ids & set(scene_ids)),
        "unique_scene_ids": len(scene_ids) == len(set(scene_ids)) == 960,
        "unique_formal_seed_values": len(formal_seeds) == len(set(formal_seeds)) == 4800,
        "formal_engineering_seed_disjoint": not (set(formal_seeds) & set(smoke_seeds)),
        "unique_correct_answer": all(unique_answer_checks),
        "two_hop_path_correct": all(path_checks),
        "alternative_path_count_zero": all(alternative_path_checks),
        "relation_direction_matches_coordinates": all(relation_direction_checks),
        "corruption_changed_fact_count_one": all(corruption_count_checks),
        "corruption_is_directional_inverse_only": all(corruption_equivalence_checks),
        "corrupted_implied_answer_correct_and_changed": all(corrupted_answer_checks),
        "option_position_balance": dict(sorted(positions.items()))
        == {
            "reasoning_test:0": 192,
            "reasoning_test:1": 192,
            "reasoning_test:2": 192,
            "reasoning_test:3": 192,
            "uptake_validation:0": 48,
            "uptake_validation:1": 48,
            "uptake_validation:2": 48,
            "uptake_validation:3": 48,
        },
        "entity_answer_namespace_separation": all(namespace_checks),
        "natural_language_canonical_equality": all(nl_checks),
        "triples_canonical_equality": all(triple_checks),
        "correct_corrupted_whitespace_token_balance": all(
            max(values) == 0 for values in whitespace_differences.values()
        ),
        "uptake_task_counts_48_each": set(uptake_task_counts.values()) == {48}
        and len(uptake_task_counts) == 4,
    }
    output = {
        "schema_version": 1,
        "audited_scene_count": len(scenes),
        "audited_uptake_scene_count": len(uptake),
        "audited_reasoning_scene_count": len(reasoning),
        "audited_engineering_scene_count": len(smoke),
        "checks": checks,
        "option_position_counts": dict(sorted(positions.items())),
        "whitespace_token_difference": {
            key: {"max": max(values), "mean": sum(values) / len(values)}
            for key, values in sorted(whitespace_differences.items())
        },
        "character_length_difference": {
            key: {"max": max(values), "mean": sum(values) / len(values)}
            for key, values in sorted(character_differences.items())
        },
        "leakage": leakage,
        "construct_validity_status": "FAIL_UNRECORDED_ANSWER_LEAKAGE",
        "structural_checks_status": "PASS" if all(checks.values()) else "FAIL",
        "status": "FAIL",
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(output, indent=2, sort_keys=True) + "\n")
    with LEAKAGE_OUTPUT.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(leakage, indent=2, sort_keys=True) + "\n")
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
