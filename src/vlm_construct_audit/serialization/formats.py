"""Natural-language and triple fact serialization with exact round trips."""

from __future__ import annotations

import csv
import re
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean
from typing import Any

from ..utils import dump_yaml, read_jsonl, sha256_file, write_jsonl


TOKEN_RE = re.compile(r"[A-Za-z0-9_]+|[^\w\s]")


def serialize_facts(facts: list[dict[str, str]], fmt: str) -> str:
    if fmt == "natural_language":
        lines = []
        for fact in facts:
            if fact["kind"] == "relation":
                lines.append(
                    f"Entity {fact['subject']} is {fact['predicate']} entity {fact['object']}."
                )
            else:
                lines.append(
                    f"Entity {fact['subject']} has {fact['predicate']} {fact['object']}."
                )
        return "\n".join(lines)
    if fmt == "triples":
        return "\n".join(
            f"({fact['subject']}, {fact['predicate']}, {fact['object']})" for fact in facts
        )
    raise KeyError(fmt)


def parse_facts(text: str, fmt: str) -> list[dict[str, str]]:
    facts: list[dict[str, str]] = []
    for line in text.splitlines():
        if fmt == "natural_language":
            relation = re.fullmatch(r"Entity (\S+) is (\S+) entity (\S+)\.", line)
            attribute = re.fullmatch(r"Entity (\S+) has (\S+) (\S+)\.", line)
            if relation:
                facts.append(
                    {"kind": "relation", "subject": relation[1], "predicate": relation[2], "object": relation[3]}
                )
            elif attribute:
                facts.append(
                    {"kind": "attribute", "subject": attribute[1], "predicate": attribute[2], "object": attribute[3]}
                )
            else:
                raise ValueError(f"Invalid natural-language fact: {line!r}")
        elif fmt == "triples":
            match = re.fullmatch(r"\(([^,]+), ([^,]+), ([^)]+)\)", line)
            if not match:
                raise ValueError(f"Invalid triple fact: {line!r}")
            predicate = match[2]
            facts.append(
                {
                    "kind": "attribute" if predicate in {"color", "shape"} else "relation",
                    "subject": match[1],
                    "predicate": predicate,
                    "object": match[3],
                }
            )
        else:
            raise KeyError(fmt)
    return facts


def _tokens(text: str) -> list[str]:
    return TOKEN_RE.findall(text.lower())


def _entity_positions(text: str, facts: list[dict[str, str]]) -> list[int]:
    tokens = _tokens(text)
    entities = {fact["subject"].lower() for fact in facts}
    entities |= {fact["object"].lower() for fact in facts if fact["kind"] == "relation"}
    return [i for i, token in enumerate(tokens) if token in entities]


def build_serializations(
    interventions_path: str | Path = "data/generated/interventions.jsonl",
) -> dict[str, Any]:
    rows = []
    for record in read_jsonl(interventions_path):
        for fmt in ("natural_language", "triples"):
            text = serialize_facts(record["facts"], fmt)
            tokens = _tokens(text)
            rows.append(
                {
                    **record,
                    "serialization": fmt,
                    "serialized_evidence": text,
                    "token_length": len(tokens),
                    "sentence_count": len(record["facts"]),
                    "entity_positions": _entity_positions(text, record["facts"]),
                    "lexical_items": sorted(set(tokens)),
                    "lexical_frequency": dict(Counter(tokens)),
                    "answer_option_overlap": sum(token in set(record["question"]["options"]) for token in tokens),
                }
            )
    output = Path("data/generated/serialized.jsonl")
    write_jsonl(output, rows)
    dump_yaml(
        "data/manifests/serialization_manifest.yaml",
        {"schema_version": 1, "row_count": len(rows), "sha256": sha256_file(output)},
    )
    return {"row_count": len(rows), "sha256": sha256_file(output)}


def validate_equivalence(
    serialized_path: str | Path = "data/generated/serialized.jsonl",
) -> dict[str, Any]:
    rows = read_jsonl(serialized_path)
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[(row["scene_id"], row["condition"])].append(row)

    failures = []
    lexical_overlaps = []
    length_by_format: dict[str, list[int]] = defaultdict(list)
    positions_by_format: dict[str, list[float]] = defaultdict(list)
    match_failures = []
    for key, pair in groups.items():
        if len(pair) != 2:
            failures.append({"key": list(key), "reason": "missing_format"})
            continue
        parsed = [parse_facts(row["serialized_evidence"], row["serialization"]) for row in pair]
        canonical = [sorted(facts, key=lambda fact: tuple(sorted(fact.items()))) for facts in parsed]
        if canonical[0] != canonical[1] or canonical[0] != sorted(pair[0]["facts"], key=lambda fact: tuple(sorted(fact.items()))):
            failures.append({"key": list(key), "reason": "round_trip_mismatch"})
        token_sets = [set(row["lexical_items"]) for row in pair]
        lexical_overlaps.append(len(token_sets[0] & token_sets[1]) / max(1, len(token_sets[0] | token_sets[1])))
        for row in pair:
            length_by_format[row["serialization"]].append(row["token_length"])
            if row["entity_positions"]:
                positions_by_format[row["serialization"]].append(mean(row["entity_positions"]))

    by_scene_format: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_scene_format[(row["scene_id"], row["serialization"])].append(row)
    for key, condition_rows in by_scene_format.items():
        correct = next(row for row in condition_rows if row["condition"] == "correct_evidence")
        for row in condition_rows:
            checks = {
                "token_length_delta": abs(row["token_length"] - correct["token_length"]) <= 2,
                "entity_count_delta": row["entity_count"] == correct["entity_count"],
                "relation_count_delta": row["relation_count"] == correct["relation_count"],
                "sentence_count_delta": row["sentence_count"] == correct["sentence_count"],
                "answer_option_overlap_delta": row["answer_option_overlap"] == correct["answer_option_overlap"],
            }
            if not all(checks.values()):
                match_failures.append({"scene_id": key[0], "serialization": key[1], "condition": row["condition"], "checks": checks})

    manual_path = Path("data/annotations/serialization_manual_review.csv")
    manual_path.parent.mkdir(parents=True, exist_ok=True)
    sample_keys = sorted(groups)[:12]
    with manual_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["scene_id", "condition", "nl", "triples", "review_status", "reviewer"])
        for key in sample_keys:
            pair = {row["serialization"]: row for row in groups[key]}
            writer.writerow(
                [key[0], key[1], pair["natural_language"]["serialized_evidence"], pair["triples"]["serialized_evidence"], "PENDING_INDEPENDENT_HUMAN_REVIEW", ""]
            )

    report = {
        "schema_version": 1,
        "programmatic_fact_equivalence": not failures,
        "equivalence_failures": failures,
        "pair_count": len(groups),
        "token_length": {fmt: {"mean": mean(values), "min": min(values), "max": max(values)} for fmt, values in length_by_format.items()},
        "entity_position": {fmt: {"mean": mean(values)} for fmt, values in positions_by_format.items()},
        "lexical_overlap_mean": mean(lexical_overlaps),
        "matching_tolerances": {
            "within_format_token_delta": 2,
            "entity_count_delta": 0,
            "relation_count_delta": 0,
            "sentence_count_delta": 0,
            "answer_option_overlap_delta": 0,
        },
        "matched_intervention_validation": not match_failures,
        "matching_failures": match_failures,
        "lexical_frequency_recorded_per_prediction": True,
        "manual_sample_review": {
            "sample_size": len(sample_keys),
            "status": "PENDING_INDEPENDENT_HUMAN_REVIEW",
            "path": str(manual_path).replace("\\", "/"),
        },
    }
    dump_yaml("artifacts/metrics/equivalence_report.yaml", report)
    return report
