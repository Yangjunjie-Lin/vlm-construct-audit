"""Symbolic construct-validity oracles for Direction P v2."""

from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from collections.abc import Callable, Hashable
from pathlib import Path
from typing import Any

import yaml

from .generator import ANSWERS, COMPOSE, INVERSE, ROOT


def _cardinal(fact: dict[str, str]) -> str:
    relation = fact["relation"]
    if not relation.endswith("_of"):
        raise ValueError(relation)
    value = relation.removesuffix("_of")
    if value not in INVERSE:
        raise ValueError(value)
    return value


class QuestionOnlyOracle:
    """Question wording identifies entities but contains no relational fact."""

    @staticmethod
    def support(_row: dict[str, Any]) -> set[str]:
        return set(ANSWERS)


class ImageOnlyOracle:
    """One visual cardinal hop leaves the orthogonal sign unresolved."""

    @staticmethod
    def support(row: dict[str, Any]) -> set[str]:
        first = _cardinal(row["image"]["canonical_facts"][0])
        possible_seconds = ("east", "west") if first in {"north", "south"} else ("north", "south")
        return {COMPOSE[(first, second)] for second in possible_seconds}


class EvidenceOnlyOracle:
    """One textual cardinal hop leaves the orthogonal first hop unresolved."""

    @staticmethod
    def support(row: dict[str, Any], condition: str = "correct") -> set[str]:
        second = _cardinal(row["evidence"][condition]["canonical_facts"][0])
        possible_firsts = ("east", "west") if second in {"north", "south"} else ("north", "south")
        return {COMPOSE[(first, second)] for first in possible_firsts}


class JointMultimodalOracle:
    """The visual and textual hops jointly identify one composed answer."""

    @staticmethod
    def solve(row: dict[str, Any], condition: str = "correct") -> str:
        first = _cardinal(row["image"]["canonical_facts"][0])
        second = _cardinal(row["evidence"][condition]["canonical_facts"][0])
        return COMPOSE[(first, second)]

    @classmethod
    def support(cls, row: dict[str, Any], condition: str = "correct") -> set[str]:
        return {cls.solve(row, condition)}


def _signature_question(row: dict[str, Any]) -> Hashable:
    return row["question"]["text"]


def _signature_image(row: dict[str, Any]) -> Hashable:
    visible = tuple(
        (entity["descriptor"], entity["x"], entity["y"])
        for entity in row["image"]["render_entities"]
    )
    fact = row["image"]["canonical_facts"][0]
    return visible, tuple(sorted(fact.items()))


def _signature_evidence(row: dict[str, Any]) -> Hashable:
    return row["evidence"]["correct"]["natural_language"]


def _empirical_bayes_metrics(
    rows: list[dict[str, Any]], signature: Callable[[dict[str, Any]], Hashable]
) -> dict[str, float]:
    groups: dict[Hashable, Counter[str]] = defaultdict(Counter)
    for row in rows:
        groups[signature(row)][row["answer"]["semantic"]] += 1
    correct = 0
    entropy_sum = 0.0
    unique_rows = 0
    for counts in groups.values():
        total = sum(counts.values())
        correct += max(counts.values())
        entropy = -sum((count / total) * math.log2(count / total) for count in counts.values())
        entropy_sum += total * entropy
        if len(counts) == 1:
            unique_rows += total
    n = len(rows)
    return {
        "bayes_optimal_accuracy": correct / n,
        "conditional_answer_entropy_bits": entropy_sum / n,
        "unique_solution_rate": unique_rows / n,
        "signature_count": len(groups),
    }


def evaluate_oracles(rows: list[dict[str, Any]]) -> dict[str, Any]:
    question = _empirical_bayes_metrics(rows, _signature_question)
    image = _empirical_bayes_metrics(rows, _signature_image)
    evidence = _empirical_bayes_metrics(rows, _signature_evidence)
    expected_support = {
        "question_only": all(QuestionOnlyOracle.support(row) == set(ANSWERS) for row in rows),
        "image_only": all(len(ImageOnlyOracle.support(row)) == 2 for row in rows),
        "evidence_only": all(len(EvidenceOnlyOracle.support(row)) == 2 for row in rows),
    }
    joint_correct = sum(
        JointMultimodalOracle.solve(row) == row["answer"]["semantic"] for row in rows
    )
    corrupted_correct = sum(
        JointMultimodalOracle.solve(row, "corrupted") == row["answer"]["corrupted_semantic"]
        for row in rows
    )
    n = len(rows)
    joint = {
        "accuracy": joint_correct / n,
        "unique_solution_rate": sum(
            len(JointMultimodalOracle.support(row)) == 1 for row in rows
        ) / n,
        "corrupted_expected_answer_accuracy": corrupted_correct / n,
    }
    gates = {
        "question_only_unique_solution_rate_zero": question["unique_solution_rate"] == 0,
        "question_only_bayes_accuracy_le_0_30": question["bayes_optimal_accuracy"] <= 0.30,
        "image_only_unique_solution_rate_zero": image["unique_solution_rate"] == 0,
        "image_only_entropy_ge_1_bit": image["conditional_answer_entropy_bits"] >= 1.0,
        "image_only_bayes_accuracy_le_0_50": image["bayes_optimal_accuracy"] <= 0.50,
        "evidence_only_unique_solution_rate_zero": evidence["unique_solution_rate"] == 0,
        "evidence_only_entropy_ge_1_bit": evidence["conditional_answer_entropy_bits"] >= 1.0,
        "evidence_only_bayes_accuracy_le_0_50": evidence["bayes_optimal_accuracy"] <= 0.50,
        "joint_accuracy_one": joint["accuracy"] == 1.0,
        "joint_unique_solution_rate_one": joint["unique_solution_rate"] == 1.0,
        "corrupted_joint_expected_accuracy_one": joint["corrupted_expected_answer_accuracy"] == 1.0,
        "symbolic_support_sizes": all(expected_support.values()),
    }
    return {
        "schema_version": 1,
        "protocol_id": rows[0]["protocol_id"] if rows else None,
        "scene_count": n,
        "question_only": question,
        "image_only": image,
        "evidence_only": evidence,
        "joint_multimodal": joint,
        "support_checks": expected_support,
        "gates": gates,
        "status": "PASS" if all(gates.values()) else "CONSTRUCT_V2_NO_GO",
    }


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def run_construct_v2_oracles() -> dict[str, Any]:
    rows = _read_jsonl(ROOT / "data/construct_v2/reasoning_test.jsonl")
    result = evaluate_oracles(rows)
    target = ROOT / "artifacts/construct_v2/oracle_metrics.yaml"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(yaml.safe_dump(result, sort_keys=False), encoding="utf-8")
    return result

