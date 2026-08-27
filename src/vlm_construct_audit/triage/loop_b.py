"""New clustered measurement holdout and blinded serialization review packet."""

from __future__ import annotations

import csv
import hashlib
import random
import subprocess
from collections import defaultdict
from copy import deepcopy
from pathlib import Path
from statistics import mean
from typing import Any

import numpy as np

from ..data.generator import INVERSE
from ..interventions.operators import intervene
from ..measurement.logit_scorer import score_logit_fixture_a
from ..measurement.strict_parser import parse_declared_contract
from ..serialization.formats import parse_facts, serialize_facts
from ..statistics.core import clopper_pearson_lower
from ..utils import canonical_hash, dump_yaml, load_yaml, write_jsonl
from .cluster_bounds import (
    beta_binomial_profile_lower,
    icc_design_effect_lower,
    simultaneous_scene_template_lower,
)
from .independent_scorer import score_logit_fixture_b

CONDITIONS = (
    "correct_evidence",
    "relation_flip",
    "entity_swap",
    "attribute_swap",
    "matched_irrelevant",
    "plausible_contradictory",
)


def _git_head() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()


def _template_inventory() -> list[dict[str, str]]:
    prereg = load_yaml("research/preregistration/loop_b_measurement.yaml")
    frame = prereg["template_frame"]
    templates = []
    index = 0
    for opener in frame["openers"]:
        for action in frame["actions"]:
            for closer in frame["closers"]:
                text = f"{opener}, {action} {closer}"
                templates.append(
                    {
                        "template_id": f"loop_b_template_{index:03d}",
                        "text": text,
                        "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                    }
                )
                index += 1
    if len(templates) != 200:
        raise AssertionError("Frozen template frame must contain 200 strings")
    return templates


def _make_scene(index: int) -> dict[str, Any]:
    rng = random.Random(62000 + index)
    n_entities = 3 + index % 3
    shapes = ["circle", "square", "triangle", "star"]
    colors = ["red", "blue", "green", "yellow", "purple", "orange"]
    entity_ids = [f"lb_{index:03d}_{chr(107 + ((j * 7 + index) % 16))}{j}" for j in range(n_entities)]
    sampled_colors = rng.sample(colors, n_entities)
    entities = [
        {
            "entity_id": entity_id,
            "shape": shapes[(index + j) % len(shapes)],
            "color": sampled_colors[j],
        }
        for j, entity_id in enumerate(entity_ids)
    ]
    predicate = list(INVERSE)[index % len(INVERSE)]
    depth = 1 + index % 2
    target = entity_ids[0]
    if depth == 1:
        anchor = entity_ids[1]
        required = [
            {"kind": "relation", "subject": target, "predicate": predicate, "object": anchor},
            {"kind": "attribute", "subject": target, "predicate": "color", "object": sampled_colors[0]},
        ]
    else:
        middle, anchor = entity_ids[1], entity_ids[2]
        required = [
            {"kind": "relation", "subject": target, "predicate": predicate, "object": middle},
            {"kind": "relation", "subject": middle, "predicate": predicate, "object": anchor},
            {"kind": "attribute", "subject": target, "predicate": "color", "object": sampled_colors[0]},
        ]
    relations = [fact for fact in required if fact["kind"] == "relation"]
    relations += [
        {"kind": "relation", "subject": fact["object"], "predicate": INVERSE[fact["predicate"]], "object": fact["subject"]}
        for fact in required
        if fact["kind"] == "relation"
    ]
    return {
        "scene_id": f"loop_b_{index:04d}",
        "split": "tier0_5_measurement_holdout",
        "template_namespace": "loop_b_crossed_finite_inventory",
        "entities": entities,
        "relations": relations,
        "question": {
            "question_type": "relational_attribute_binding",
            "text": f"What color is the entity {predicate} {'twice from ' if depth == 2 else ''}{anchor}?",
            "target_entity": target,
            "anchor_entity": anchor,
            "predicate": predicate,
            "options": colors,
            "answer": sampled_colors[0],
            "reasoning_depth": depth,
            "required_facts": required,
        },
        "answer": sampled_colors[0],
        "reasoning_depth": depth,
        "required_facts": required,
    }


def _canonical(facts: list[dict[str, str]]) -> dict[str, Any]:
    attributes = sorted(
        (fact["subject"], fact["predicate"], fact["object"])
        for fact in facts
        if fact["kind"] == "attribute"
    )
    relations = sorted(
        (fact["subject"], fact["predicate"], fact["object"])
        for fact in facts
        if fact["kind"] == "relation"
    )
    entities = sorted(
        {fact["subject"] for fact in facts}
        | {fact["object"] for fact in facts if fact["kind"] == "relation"}
    )
    multiset = sorted(
        (fact["kind"], fact["subject"], fact["predicate"], fact["object"]) for fact in facts
    )
    return {
        "evidence_mentioned_entity_set": entities,
        "attribute_multiset": attributes,
        "directed_relation_multiset": relations,
        "fact_multiset": multiset,
    }


def _mutate(facts: list[dict[str, str]], mutation: str) -> list[dict[str, str]]:
    result = deepcopy(facts)
    if mutation == "omission":
        return result[:-1]
    if mutation == "duplicate_fact":
        return result + [deepcopy(result[0])]
    if mutation == "attribute_change":
        fact = next(fact for fact in result if fact["kind"] == "attribute")
        fact["object"] = "__mutated_attribute__"
        return result
    relation = next(fact for fact in result if fact["kind"] == "relation")
    if mutation == "subject_object_swap":
        relation["subject"], relation["object"] = relation["object"], relation["subject"]
    elif mutation == "inverse_relation":
        relation["predicate"] = INVERSE[relation["predicate"]]
    else:
        raise KeyError(mutation)
    return result


def _build_serialization_source() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    scenes = [_make_scene(index) for index in range(200)]
    rows = []
    for scene in scenes:
        for condition in CONDITIONS:
            facts = intervene(scene, condition)
            required_count = len(scene["required_facts"])
            rows.append(
                {
                    "scene_id": scene["scene_id"],
                    "depth": scene["reasoning_depth"],
                    "condition": condition,
                    "question": scene["question"]["text"],
                    "options": scene["question"]["options"],
                    "gold_answer": scene["answer"],
                    "facts": facts,
                    "required_fact_set_external": facts[:required_count],
                    "natural_language": serialize_facts(facts, "natural_language"),
                    "triples": serialize_facts(facts, "triples"),
                }
            )
    return scenes, rows


def prepare_loop_b_review_packet() -> dict[str, Any]:
    packet_path = Path("data/annotations/serialization_review_packet.csv")
    if packet_path.exists():
        raise RuntimeError("Loop B review packet already exists and is immutable")
    scenes, rows = _build_serialization_source()
    config = load_yaml("research/preregistration/loop_b_measurement.yaml")
    config_hash = canonical_hash(config)
    write_jsonl("artifacts/loop_b/serialization_source.jsonl", rows)
    write_jsonl("artifacts/loop_b/measurement_scenes.jsonl", scenes)

    rng = random.Random(62041)
    genuine = []
    for condition in CONDITIONS:
        candidates = [row for row in rows if row["condition"] == condition]
        depth_one = [row for row in candidates if row["depth"] == 1]
        depth_two = [row for row in candidates if row["depth"] == 2]
        genuine.extend(rng.sample(depth_one, 3) + rng.sample(depth_two, 3))
    remaining = [row for row in rows if row not in genuine]
    genuine.extend(rng.sample(remaining, 6))
    if len(genuine) != 42:
        raise AssertionError("Review packet must have 42 genuine pairs")

    packet_rows = []
    key_rows = []
    for index, row in enumerate(genuine):
        pair_id = f"pair_{index:03d}"
        swapped = bool(rng.getrandbits(1))
        evidence_a, evidence_b = (
            (row["triples"], row["natural_language"])
            if swapped
            else (row["natural_language"], row["triples"])
        )
        packet_rows.append(_blank_review_row(pair_id, row, evidence_a, evidence_b))
        key_rows.append(
            {
                "pair_id": pair_id,
                "scene_id": row["scene_id"],
                "condition": row["condition"],
                "depth": row["depth"],
                "decoy": False,
                "evidence_a_format": "triples" if swapped else "natural_language",
                "expected_fact_equivalent": True,
            }
        )

    decoy_mutations = ["omission", "subject_object_swap", "inverse_relation", "attribute_change", "duplicate_fact"]
    for offset, row in enumerate(rng.sample(rows, 12)):
        mutation = decoy_mutations[offset % len(decoy_mutations)]
        mutated = serialize_facts(_mutate(row["facts"], mutation), "triples")
        pair_id = f"pair_{42 + offset:03d}"
        swapped = bool(rng.getrandbits(1))
        evidence_a, evidence_b = (mutated, row["natural_language"]) if swapped else (row["natural_language"], mutated)
        packet_rows.append(_blank_review_row(pair_id, row, evidence_a, evidence_b))
        key_rows.append(
            {
                "pair_id": pair_id,
                "scene_id": row["scene_id"],
                "condition": row["condition"],
                "depth": row["depth"],
                "decoy": True,
                "mutation": mutation,
                "expected_fact_equivalent": False,
            }
        )

    packet_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(packet_rows[0])
    with packet_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(packet_rows)
    template_path = Path("data/annotations/serialization_review_template.csv")
    with template_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in packet_rows:
            writer.writerow({key: row[key] if key == "pair_id" else "" for key in fieldnames})
    dump_yaml(
        "artifacts/loop_b/serialization_review_key.yaml",
        {
            "schema_version": 1,
            "config_hash": config_hash,
            "packet_seed": 62041,
            "genuine_pairs": 42,
            "decoy_pairs": 12,
            "rows": key_rows,
        },
    )
    result = {
        "schema_version": 1,
        "status": "HUMAN_EQUIVALENCE_REVIEW_PENDING",
        "genuine_pairs": 42,
        "decoy_pairs": 12,
        "packet_rows": 54,
        "reviewers_completed": 0,
        "agent_or_model_review_used": False,
        "config_hash": config_hash,
    }
    dump_yaml("artifacts/loop_b/review_packet_manifest.yaml", result)
    return result


def _blank_review_row(pair_id: str, row: dict[str, Any], evidence_a: str, evidence_b: str) -> dict[str, str]:
    return {
        "pair_id": pair_id,
        "question": row["question"],
        "options": " | ".join(row["options"]),
        "evidence_a": evidence_a,
        "evidence_b": evidence_b,
        "fact_equivalent": "",
        "same_entities": "",
        "same_attributes": "",
        "same_relations": "",
        "same_answer": "",
        "naturalness_issue": "",
        "ambiguity_issue": "",
        "critical_error": "",
        "reviewer_id": "",
    }


def _candidate_fixture(scene_index: int, probe_index: int, category: str) -> dict[str, Any]:
    candidate_sets = {
        "single_token_answer": ["red", "blue", "green"],
        "multi_token_answer": ["deep blue", "bright red", "soft green"],
        "entity_id": [f"entity_{scene_index}_a", f"entity_{scene_index}_b", f"entity_{scene_index}_c"],
        "option_id": ["choice alpha", "choice beta", "choice gamma"],
        "relation_direction": ["left of", "right of", "above"],
        "attribute_binding": ["red circle", "blue square", "green triangle"],
        "answer_alias": ["scarlet", "azure blue", "verdant"],
    }
    candidates = candidate_sets[category]
    shift = (scene_index + probe_index) % len(candidates)
    order = candidates[shift:] + candidates[:shift]
    answer = candidates[(scene_index * 3 + probe_index) % len(candidates)]
    tokens = sorted({token for candidate in candidates for token in candidate.split(" ")})
    vocabulary = {token: index + 3 for index, token in enumerate(tokens)}
    vocab_size = max(vocabulary.values()) + 4
    records = []
    for candidate in order:
        ids = [vocabulary[token] for token in candidate.split(" ")]
        rows = []
        for token_id in ids:
            logits = [0.0] * vocab_size
            logits[token_id] = 5.0 if candidate == answer else 2.0
            rows.append(logits)
        records.append(
            {"text": candidate, "candidate_token_ids": ids, "step_logits": rows}
        )
    return {
        "fixture_id": f"lb_{scene_index:03d}_{probe_index}",
        "prompt_token_ids": [1, 17 + probe_index, 29 + scene_index % 11],
        "attention_mask": [1, 1, 1],
        "BOS_policy": "context_contains_BOS_candidate_does_not",
        "EOS_policy": "not_scored",
        "candidate_boundary": 3,
        "dtype": "float64",
        "category": category,
        "vocabulary": vocabulary,
        "candidates": records,
        "candidate_order": order,
        "semantic_answer": answer,
        "option_id_mapping": {chr(65 + index): candidate for index, candidate in enumerate(order)},
    }


def _compare_scorers(fixture: dict[str, Any]) -> dict[str, Any]:
    left = score_logit_fixture_a(fixture)
    right = score_logit_fixture_b(fixture)
    token_differences = []
    raw_differences = []
    normalized_differences = []
    for candidate in fixture["candidate_order"]:
        l_record, r_record = left["scores"][candidate], right["scores"][candidate]
        token_differences.extend(
            abs(a - b) for a, b in zip(l_record["token_logprobs"], r_record["token_logprobs"], strict=True)
        )
        raw_differences.append(abs(l_record["raw_log_likelihood"] - r_record["raw_log_likelihood"]))
        normalized_differences.append(
            abs(l_record["length_normalized_score"] - r_record["length_normalized_score"])
        )
    tolerance = 1e-10

    def tie_aware_pairs(result: dict[str, Any]) -> dict[tuple[str, str], int]:
        candidates = fixture["candidate_order"]
        relations = {}
        for left_index, left_candidate in enumerate(candidates):
            for right_candidate in candidates[left_index + 1 :]:
                difference = (
                    result["scores"][left_candidate]["length_normalized_score"]
                    - result["scores"][right_candidate]["length_normalized_score"]
                )
                relations[(left_candidate, right_candidate)] = (
                    0 if abs(difference) <= tolerance else (1 if difference > 0 else -1)
                )
        return relations

    return {
        "implementation_a": left,
        "implementation_b": right,
        "max_token_logprob_difference": max(token_differences, default=0.0),
        "max_raw_difference": max(raw_differences, default=0.0),
        "max_normalized_difference": max(normalized_differences, default=0.0),
        "ranking_exact_order_agreement": left["ranking"] == right["ranking"],
        "ranking_agreement": tie_aware_pairs(left) == tie_aware_pairs(right),
        "ranking_tolerance": tolerance,
        "semantic_answer_agreement": left["predicted_semantic_answer"] == right["predicted_semantic_answer"],
        "option_mapping_agreement": left["option_id_mapping"] == right["option_id_mapping"],
    }


def _parser_cases() -> list[dict[str, Any]]:
    cases = []
    option_map = {"A": "red", "B": "blue", "C": "green"}
    aliases = {"azure": "blue"}
    valid_specs = [
        ("semantic_json", 30, '{"answer":"red"}', "semantic_answer", ["red", "blue", "green"], {}, "red"),
        ("option_id_json", 30, '{"option_id":"B"}', "option_id", ["red", "blue", "green"], {}, "blue"),
        ("whitespace_json", 20, ' \n { "answer" : "green" } \t', "semantic_answer", ["red", "blue", "green"], {}, "green"),
        ("registered_alias_json", 20, '{"answer":"azure"}', "semantic_answer", ["red", "blue", "green"], aliases, "blue"),
        ("legal_unicode_string_json", 20, '{"answer":"蓝色"}', "semantic_answer", ["红色", "蓝色", "绿色"], {}, "蓝色"),
    ]
    for category, count, raw, schema, allowed, registered, expected in valid_specs:
        for index in range(count):
            cases.append(
                {
                    "case_id": f"valid_{category}_{index:03d}",
                    "category": category,
                    "expected_valid": True,
                    "raw_response": raw,
                    "schema": schema,
                    "allowed_answers": allowed,
                    "option_id_mapping": option_map,
                    "registered_aliases": registered,
                    "expected_parsed_response": expected,
                }
            )
    invalid_specs = {
        "entity_id_as_option": ('{"option_id":"entity_1"}', "option_id"),
        "multiple_answers": ('{"answer":["red","blue"]}', "semantic_answer"),
        "duplicate_json_key": ('{"answer":"red","answer":"blue"}', "semantic_answer"),
        "prefix_suffix": ('Answer: {"answer":"red"}.', "semantic_answer"),
        "malformed_json": ('{"answer":"red"', "semantic_answer"),
        "unicode_curly_punctuation": ('{“answer”:“red”}', "semantic_answer"),
        "out_of_vocabulary": ('{"answer":"magenta"}', "semantic_answer"),
        "empty": ("", "semantic_answer"),
        "contradictory_dual_answer": ('{"answer":"red","option_id":"B"}', "semantic_answer"),
        "cross_schema": ('{"answer":"red"}', "option_id"),
    }
    for category, (raw, schema) in invalid_specs.items():
        for index in range(12):
            cases.append(
                {
                    "case_id": f"invalid_{category}_{index:03d}",
                    "category": category,
                    "expected_valid": False,
                    "raw_response": raw,
                    "schema": schema,
                    "allowed_answers": ["red", "blue", "green"],
                    "option_id_mapping": option_map,
                    "registered_aliases": aliases,
                    "expected_parsed_response": None,
                }
            )
    if len(cases) != 240:
        raise AssertionError("Adversarial parser suite must contain 240 cases")
    return cases


def _bootstrap_cluster_means(rows: list[dict[str, Any]], cluster_field: str, seed: int) -> dict[str, Any]:
    groups: dict[str, list[int]] = defaultdict(list)
    for row in rows:
        groups[str(row[cluster_field])].append(int(row["probe_pass"]))
    cluster_means = [mean(values) for values in groups.values()]
    rng = np.random.default_rng(seed)
    replicates = rng.choice(cluster_means, size=(20000, len(cluster_means)), replace=True).mean(axis=1)
    degenerate = bool(np.all(replicates == replicates[0]))
    return {
        "cluster_field": cluster_field,
        "cluster_count": len(cluster_means),
        "equal_cluster_mean": mean(cluster_means),
        "percentile_one_sided_lower": float(np.quantile(replicates, 0.05)),
        "degenerate_all_success": degenerate,
        "used_as_boundary_safe_gate": False,
    }


def run_loop_b() -> dict[str, Any]:
    if Path("artifacts/loop_b/decision.yaml").exists():
        return load_yaml("artifacts/loop_b/decision.yaml")
    if not Path("data/annotations/serialization_review_packet.csv").exists():
        raise RuntimeError("Prepare and freeze the human review packet before Loop B execution")
    prereg = load_yaml("research/preregistration/loop_b_measurement.yaml")
    templates = _template_inventory()
    config_hash = canonical_hash(prereg)
    probe_categories = [
        "single_token_answer",
        "multi_token_answer",
        "entity_id",
        "option_id",
        "relation_direction",
        "attribute_binding",
        "answer_alias",
    ]
    probe_rows = []
    for scene_index in range(200):
        for probe_index in range(3):
            template = templates[(scene_index + probe_index * 67) % 200]
            category = probe_categories[(scene_index * 3 + probe_index) % len(probe_categories)]
            fixture = _candidate_fixture(scene_index, probe_index, category)
            comparison = _compare_scorers(fixture)
            probe_pass = (
                comparison["max_token_logprob_difference"] <= 1e-10
                and comparison["max_raw_difference"] <= 1e-10
                and comparison["max_normalized_difference"] <= 1e-10
                and comparison["ranking_agreement"]
                and comparison["semantic_answer_agreement"]
                and comparison["option_mapping_agreement"]
            )
            probe_rows.append(
                {
                    "probe_id": fixture["fixture_id"],
                    "scene_id": f"loop_b_{scene_index:04d}",
                    "template_id": template["template_id"],
                    "template_sha256": template["sha256"],
                    "probe_category": category,
                    "probe_pass": probe_pass,
                    "fixture": fixture,
                    "scorer_comparison": comparison,
                    "config_hash": config_hash,
                }
            )
    write_jsonl("artifacts/loop_b/measurement_probe_results.jsonl", probe_rows)

    parser_rows = []
    for case in _parser_cases():
        parsed = parse_declared_contract(
            case["raw_response"],
            schema=case["schema"],
            allowed_answers=case["allowed_answers"],
            option_id_mapping=case["option_id_mapping"],
            registered_aliases=case["registered_aliases"],
        )
        observed_valid = parsed["parser_status"] == "ok"
        case_pass = (
            observed_valid == case["expected_valid"]
            and parsed["parsed_response"] == case["expected_parsed_response"]
        )
        parser_rows.append({**case, **parsed, "case_pass": case_pass, "config_hash": config_hash})
    write_jsonl("artifacts/loop_b/parser_adversarial_results.jsonl", parser_rows)

    _scenes, serializations = _build_serialization_source()
    equality_rows = []
    mutation_rows = []
    for row in serializations:
        source = _canonical(row["facts"])
        nl = _canonical(parse_facts(row["natural_language"], "natural_language"))
        triples = _canonical(parse_facts(row["triples"], "triples"))
        equality_rows.append(
            {
                "scene_id": row["scene_id"],
                "condition": row["condition"],
                "depth": row["depth"],
                "source_equals_nl": source == nl,
                "source_equals_triples": source == triples,
                "nl_equals_triples": nl == triples,
                "required_fact_set_external_equal": row["required_fact_set_external"] == row["facts"][: len(row["required_fact_set_external"])],
            }
        )
        for mutation in ("omission", "subject_object_swap", "inverse_relation", "attribute_change", "duplicate_fact"):
            detected = _canonical(_mutate(row["facts"], mutation)) != source
            mutation_rows.append(
                {"scene_id": row["scene_id"], "condition": row["condition"], "mutation": mutation, "detected": detected}
            )
    write_jsonl("artifacts/loop_b/serialization_equality_results.jsonl", equality_rows)
    write_jsonl("artifacts/loop_b/serialization_mutation_controls.jsonl", mutation_rows)

    successes = sum(row["probe_pass"] for row in probe_rows)
    scene_groups: dict[str, list[bool]] = defaultdict(list)
    template_groups: dict[str, list[bool]] = defaultdict(list)
    for row in probe_rows:
        scene_groups[row["scene_id"]].append(row["probe_pass"])
        template_groups[row["template_id"]].append(row["probe_pass"])
    scene_complete = sum(all(values) for values in scene_groups.values())
    template_complete = sum(all(values) for values in template_groups.values())
    simultaneous = simultaneous_scene_template_lower(
        scene_complete, len(scene_groups), template_complete, len(template_groups)
    )
    cluster_sensitivity = {}
    for dimension, groups in (("scene", scene_groups), ("template", template_groups)):
        success_vector = [sum(values) for values in groups.values()]
        trial_vector = [len(values) for values in groups.values()]
        cluster_sensitivity[dimension] = {
            "beta_binomial_profile_lower": {
                str(rho): beta_binomial_profile_lower(success_vector, trial_vector, rho)
                for rho in (0.0, 0.05, 0.10, 0.20)
            },
            "icc_design_effect": [
                icc_design_effect_lower(successes, len(probe_rows), trial_vector, rho)
                for rho in (0.0, 0.05, 0.10, 0.20)
            ],
        }
    valid_parser = [row for row in parser_rows if row["expected_valid"]]
    invalid_parser = [row for row in parser_rows if not row["expected_valid"]]
    metrics = {
        "schema_version": 1,
        "execution_head": _git_head(),
        "config_hash": config_hash,
        "probe_count": len(probe_rows),
        "scene_clusters": len(scene_groups),
        "template_clusters": len(template_groups),
        "probe_level_rate": successes / len(probe_rows),
        "probe_level_one_sided_95_lower": clopper_pearson_lower(successes, len(probe_rows)),
        "scene_level_rate": mean(mean(values) for values in scene_groups.values()),
        "scene_complete_successes": scene_complete,
        "scene_complete_one_sided_95_lower": clopper_pearson_lower(scene_complete, len(scene_groups)),
        "template_level_rate": mean(mean(values) for values in template_groups.values()),
        "template_complete_successes": template_complete,
        "template_complete_one_sided_95_lower": clopper_pearson_lower(template_complete, len(template_groups)),
        "two_way_cluster": simultaneous,
        "scene_cluster_bootstrap": _bootstrap_cluster_means(probe_rows, "scene_id", 62031),
        "template_cluster_bootstrap": _bootstrap_cluster_means(probe_rows, "template_id", 62037),
        "cluster_dependence_sensitivity": cluster_sensitivity,
        "cross_scorer_ranking_agreement": sum(row["scorer_comparison"]["ranking_agreement"] for row in probe_rows) / len(probe_rows),
        "cross_scorer_semantic_answer_agreement": sum(row["scorer_comparison"]["semantic_answer_agreement"] for row in probe_rows) / len(probe_rows),
        "cross_scorer_option_mapping_agreement": sum(row["scorer_comparison"]["option_mapping_agreement"] for row in probe_rows) / len(probe_rows),
        "maximum_token_logprob_difference": max(row["scorer_comparison"]["max_token_logprob_difference"] for row in probe_rows),
        "valid_parser_recall": sum(row["case_pass"] for row in valid_parser) / len(valid_parser),
        "invalid_parser_rejection": sum(row["case_pass"] for row in invalid_parser) / len(invalid_parser),
        "parser_case_count": len(parser_rows),
        "canonical_serialization_fact_equality": sum(row["source_equals_nl"] and row["source_equals_triples"] and row["nl_equals_triples"] for row in equality_rows) / len(equality_rows),
        "canonical_pair_count": len(equality_rows),
        "mutation_control_detection": sum(row["detected"] for row in mutation_rows) / len(mutation_rows),
        "mutation_control_count": len(mutation_rows),
        "full_scene_entity_set_recoverable_from_evidence": False,
        "required_fact_role_recovered_from_text": False,
        "human_review_status": "HUMAN_EQUIVALENCE_REVIEW_PENDING",
        "human_reviewers_completed": 0,
        "agent_or_model_review_used": False,
    }
    gates = {
        "scene_cluster_lower": metrics["scene_complete_one_sided_95_lower"] >= 0.98,
        "two_way_cluster_lower": simultaneous["two_way_lower"] >= 0.98,
        "cross_scorer_ranking": metrics["cross_scorer_ranking_agreement"] == 1.0,
        "cross_scorer_semantic_answer": metrics["cross_scorer_semantic_answer_agreement"] == 1.0,
        "parser_recall": metrics["valid_parser_recall"] >= 0.99,
        "parser_rejection": metrics["invalid_parser_rejection"] >= 0.99,
        "serialization_equality": metrics["canonical_serialization_fact_equality"] == 1.0,
        "mutation_controls": metrics["mutation_control_detection"] == 1.0,
    }
    decision = {
        "schema_version": 1,
        "loop_b_automated": "GO" if all(gates.values()) else "NO_GO",
        "loop_b_human": "PENDING",
        "decision": (
            "LOOP_B_AUTOMATED_GO_HUMAN_PENDING"
            if all(gates.values())
            else "LOOP_B_NO_GO"
        ),
        "gates": gates,
        "config_hash": config_hash,
        "scientific_vlm_result": "NOT_EXECUTED",
    }
    dump_yaml("artifacts/loop_b/measurement_metrics.yaml", metrics)
    dump_yaml("artifacts/loop_b/decision.yaml", decision)
    return decision
