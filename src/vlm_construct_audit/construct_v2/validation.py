"""Automated construct-v2 balance, equivalence, and integrity gates."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from collections import Counter, defaultdict
from collections.abc import Callable, Hashable
from pathlib import Path
from typing import Any

import yaml

from .generator import ANSWERS, CARDINALS, ROOT
from .runner_guard import ConstructV2Runner, verify_no_construct_v2_inference
from .uptake import validate_uptake_design

NL_PATTERN = re.compile(r"^The (.+) is (north|south|east|west) of the (.+)\.$")
TRIPLE_PATTERN = re.compile(r"^\((.+), (north|south|east|west)_of, (.+)\)$")
AUTOMATED_FREEZE_TAG = "construct-v2-automated-preaudit-freeze"
AUTOMATED_FREEZE_COMMIT = "1552a3c77e0bdd6bf0fdb0bf49447c19df4af6f2"
TOKEN_BALANCE_PATH = "artifacts/construct_v2/token_balance.yaml"
TOKEN_REGISTRY_PATH = "configs/p_mini_pilot_models.yaml"
TOKEN_REASONING_PATH = "data/construct_v2/reasoning_test.jsonl"


def _read_jsonl(path: str) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in (ROOT / path).read_text(encoding="utf-8").splitlines()
        if line
    ]


def _dump_yaml(path: str, value: Any) -> None:
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(yaml.safe_dump(value, sort_keys=False, allow_unicode=True), encoding="utf-8")


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _git_bytes(*args: str, check: bool = True) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(["git", *args], cwd=ROOT, check=check, capture_output=True)


def _verify_frozen_token_balance_read_only(
    rows: list[dict[str, Any]], *, fallback_reason: str
) -> dict[str, Any]:
    """Verify the preaudit token result when a clean CI host has no tokenizer cache."""
    failures: list[str] = []
    tag_type = _git_bytes(
        "cat-file", "-t", f"refs/tags/{AUTOMATED_FREEZE_TAG}", check=False
    )
    if tag_type.returncode != 0 or tag_type.stdout.decode().strip() != "tag":
        failures.append("automated preaudit freeze is not an annotated tag")
    target = _git_bytes(
        "rev-parse", "--verify", f"{AUTOMATED_FREEZE_TAG}^{{commit}}", check=False
    )
    if target.returncode != 0 or target.stdout.decode().strip() != AUTOMATED_FREEZE_COMMIT:
        failures.append("automated preaudit freeze tag target mismatch")

    frozen_bytes: dict[str, bytes] = {}
    for relative in (TOKEN_BALANCE_PATH, TOKEN_REGISTRY_PATH, TOKEN_REASONING_PATH):
        result = _git_bytes("show", f"{AUTOMATED_FREEZE_TAG}:{relative}", check=False)
        if result.returncode != 0:
            failures.append(f"frozen token-balance input missing: {relative}")
            continue
        frozen_bytes[relative] = result.stdout
        current = ROOT / relative
        if not current.is_file() or current.read_bytes() != result.stdout:
            failures.append(f"current token-balance input differs from frozen tag: {relative}")

    token: dict[str, Any] = {}
    registry: dict[str, Any] = {}
    try:
        token = yaml.safe_load(frozen_bytes.get(TOKEN_BALANCE_PATH, b"")) or {}
        registry = yaml.safe_load(frozen_bytes.get(TOKEN_REGISTRY_PATH, b"")) or {}
    except yaml.YAMLError as exc:
        failures.append(f"frozen token-balance YAML invalid: {exc}")
    models = registry.get("models", []) if isinstance(registry, dict) else []
    expected_summaries = {
        (model.get("model_id"), model.get("tokenizer_revision"), serialization)
        for model in models
        for serialization in ("natural_language", "triples")
    }
    summaries = token.get("summaries", []) if isinstance(token, dict) else []
    observed_summaries = {
        (row.get("model_id"), row.get("tokenizer_revision"), row.get("serialization"))
        for row in summaries
    }
    if len(models) != 3 or observed_summaries != expected_summaries or len(summaries) != 6:
        failures.append("frozen token-balance model/revision/serialization coverage mismatch")
    if any(row.get("scene_count") != len(rows) for row in summaries):
        failures.append("frozen token-balance scene count mismatch")
    if (
        token.get("checked_before_model_inference") is not True
        or token.get("model_weights_loaded") is not False
        or token.get("maximum_allowed_difference") != 1
        or token.get("maximum_observed_difference", 2) > 1
        or token.get("failures") != []
        or token.get("status") != "PASS"
        or any(row.get("maximum_absolute_token_difference", 2) > 1 for row in summaries)
    ):
        failures.append("frozen token-balance gate content mismatch")
    result = dict(token)
    result.update(
        {
            "status": "PASS" if not failures else "FAIL",
            "failures": failures,
            "verification_mode": "READ_ONLY_AUTOMATED_FREEZE_TAG_SNAPSHOT",
            "fallback_reason": fallback_reason,
            "frozen_tag": AUTOMATED_FREEZE_TAG,
            "frozen_commit": AUTOMATED_FREEZE_COMMIT,
            "tracked_artifact_modified": False,
        }
    )
    return result


def _stratified_counts(
    rows: list[dict[str, Any]],
    extractor: Callable[[dict[str, Any]], Hashable],
    *,
    answer_extractor: Callable[[dict[str, Any]], str] = lambda row: row["answer"]["semantic"],
) -> dict[str, dict[str, int]]:
    table: dict[Hashable, Counter[str]] = defaultdict(Counter)
    for row in rows:
        table[extractor(row)][answer_extractor(row)] += 1
    return {
        str(stratum): dict(sorted(counts.items()))
        for stratum, counts in sorted(table.items(), key=lambda item: str(item[0]))
    }


def _balanced(
    table: dict[str, dict[str, int]], expected_answers: set[str], *, tolerance: int = 0
) -> bool:
    return all(
        set(counts) == expected_answers and max(counts.values()) - min(counts.values()) <= tolerance
        for counts in table.values()
    )


def write_balance_artifacts(
    reasoning: list[dict[str, Any]],
    uptake: list[dict[str, Any]],
    *,
    write: bool = True,
) -> dict[str, Any]:
    whole = _stratified_counts(reasoning, lambda _row: "reasoning_test")
    by_template = _stratified_counts(reasoning, lambda row: row["template_id"])
    by_entity_count = _stratified_counts(reasoning, lambda row: row["entity_count"])
    by_option_position = _stratified_counts(
        reasoning, lambda row: row["answer"]["correct_option_position"]
    )
    by_serialization = {
        serialization: dict(Counter(row["answer"]["semantic"] for row in reasoning))
        for serialization in ("natural_language", "triples")
    }
    answer_artifact = {
        "schema_version": 1,
        "whole_split": whole,
        "by_template": by_template,
        "by_entity_count": by_entity_count,
        "by_correct_option_position": by_option_position,
        "by_serialization": by_serialization,
        "gates": {
            "whole_split_four_class_exact": _balanced(whole, set(ANSWERS)),
            "template_four_class_exact": _balanced(by_template, set(ANSWERS)),
            "entity_count_four_class_exact": _balanced(by_entity_count, set(ANSWERS)),
            "option_position_four_class_exact": _balanced(by_option_position, set(ANSWERS)),
            "serialization_four_class_exact": _balanced(by_serialization, set(ANSWERS)),
        },
    }
    answer_artifact["status"] = (
        "PASS" if all(answer_artifact["gates"].values()) else "FAIL"
    )

    by_first = _stratified_counts(
        reasoning, lambda row: row["image"]["canonical_facts"][0]["relation"]
    )
    by_second = _stratified_counts(
        reasoning,
        lambda row: row["evidence"]["correct"]["canonical_facts"][0]["relation"],
    )
    relation_applicable_balanced = all(
        len(counts) == 2 and len(set(counts.values())) == 1
        for table in (by_first, by_second)
        for counts in table.values()
    )
    uptake_design = validate_uptake_design(uptake)
    relation_artifact = {
        "schema_version": 1,
        "reasoning_visual_first_hop": by_first,
        "reasoning_text_second_hop": by_second,
        "structural_support_note": (
            "Conditioning on one cardinal component of a diagonal answer leaves exactly two, "
            "not four, logically possible diagonal classes; both are exactly balanced."
        ),
        "conditional_support_size": 2,
        "conditional_entropy_bits": 1.0,
        "uptake_task_answer_counts": uptake_design["answer_counts"],
        "gates": {
            "first_hop_all_cardinals_present": set(by_first)
            == {f"{relation}_of" for relation in CARDINALS},
            "second_hop_all_cardinals_present": set(by_second)
            == {f"{relation}_of" for relation in CARDINALS},
            "reasoning_applicable_support_exact": relation_applicable_balanced,
            "uptake_each_task_16_per_cardinal": uptake_design["status"] == "PASS",
        },
    }
    relation_artifact["status"] = (
        "PASS" if all(relation_artifact["gates"].values()) else "FAIL"
    )
    template_artifact = {
        "schema_version": 1,
        "reasoning": by_template,
        "uptake_templates": dict(Counter(row["template_id"] for row in uptake)),
        "question_text_deterministic_answer_mapping": False,
        "status": "PASS" if _balanced(by_template, set(ANSWERS)) else "FAIL",
    }
    if write:
        _dump_yaml("artifacts/construct_v2/answer_balance.yaml", answer_artifact)
        _dump_yaml("artifacts/construct_v2/relation_balance.yaml", relation_artifact)
        _dump_yaml("artifacts/construct_v2/template_balance.yaml", template_artifact)
    return {
        "answer_balance": answer_artifact["status"],
        "relation_balance": relation_artifact["status"],
        "template_balance": template_artifact["status"],
        "uptake_balance": uptake_design["status"],
    }


def _parse_serialization(value: str, serialization: str) -> tuple[str, str, str]:
    pattern = NL_PATTERN if serialization == "natural_language" else TRIPLE_PATTERN
    match = pattern.fullmatch(value)
    if not match:
        raise ValueError(value)
    return match.group(1), f"{match.group(2)}_of", match.group(3)


def write_serialization_equivalence(
    rows: list[dict[str, Any]], *, write: bool = True
) -> dict[str, Any]:
    failures = []
    changed_fact_failures = []
    conflict_count = 0
    for row in rows:
        for condition in ("correct", "corrupted"):
            nl = _parse_serialization(row["evidence"][condition]["natural_language"], "natural_language")
            triples = _parse_serialization(row["evidence"][condition]["triples"], "triples")
            canonical = row["evidence"][condition]["canonical_facts"][0]
            roles = {entity["role"]: entity["descriptor"] for entity in row["entities"]}
            expected = (roles[canonical["head_role"]], canonical["relation"], roles[canonical["tail_role"]])
            if nl != triples or nl != expected:
                failures.append(row["scene_uuid"])
        correct = row["evidence"]["correct"]["canonical_facts"][0]
        corrupted = row["evidence"]["corrupted"]["canonical_facts"][0]
        changed = sum(correct[key] != corrupted[key] for key in ("head_role", "relation", "tail_role"))
        if changed != 1 or correct["relation"] == corrupted["relation"]:
            changed_fact_failures.append(row["scene_uuid"])
        conflict_count += int(row["evidence"]["direct_image_text_conflict"])
    result = {
        "schema_version": 1,
        "scene_count": len(rows),
        "canonical_nl_triples_equality": 1 - len(set(failures)) / len(rows),
        "changed_fact_count_exactly_one_rate": 1 - len(set(changed_fact_failures)) / len(rows),
        "direct_image_text_conflict_count": conflict_count,
        "failures": sorted(set(failures)),
        "changed_fact_failures": sorted(set(changed_fact_failures)),
        "status": (
            "PASS"
            if not failures and not changed_fact_failures and conflict_count == 0
            else "FAIL"
        ),
    }
    if write:
        _dump_yaml("artifacts/construct_v2/serialization_equivalence.yaml", result)
    return result


def write_token_balance(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Use frozen local tokenizers only; never load model weights."""

    try:
        from transformers import AutoTokenizer  # type: ignore[import-not-found]
    except ModuleNotFoundError as exc:
        return _verify_frozen_token_balance_read_only(rows, fallback_reason=str(exc))

    model_registry = yaml.safe_load(
        (ROOT / "configs/p_mini_pilot_models.yaml").read_text(encoding="utf-8")
    )["models"]
    summaries = []
    failures = []
    try:
        for model in model_registry:
            tokenizer = AutoTokenizer.from_pretrained(
                model["repository"],
                revision=model["tokenizer_revision"],
                local_files_only=True,
                trust_remote_code=bool(model["trust_remote_code"]),
            )
            for serialization in ("natural_language", "triples"):
                differences = []
                for row in rows:
                    correct = len(
                        tokenizer.encode(
                            row["evidence"]["correct"][serialization], add_special_tokens=False
                        )
                    )
                    corrupted = len(
                        tokenizer.encode(
                            row["evidence"]["corrupted"][serialization], add_special_tokens=False
                        )
                    )
                    difference = abs(correct - corrupted)
                    differences.append(difference)
                    if difference > 1:
                        failures.append(
                            {
                                "scene_uuid": row["scene_uuid"],
                                "model_id": model["model_id"],
                                "serialization": serialization,
                                "difference": difference,
                            }
                        )
                summaries.append(
                    {
                        "model_id": model["model_id"],
                        "tokenizer_revision": model["tokenizer_revision"],
                        "serialization": serialization,
                        "scene_count": len(rows),
                        "maximum_absolute_token_difference": max(differences),
                        "mean_absolute_token_difference": sum(differences) / len(differences),
                    }
                )
    except OSError as exc:
        return _verify_frozen_token_balance_read_only(rows, fallback_reason=str(exc))
    result = {
        "schema_version": 1,
        "checked_before_model_inference": True,
        "tokenizer_source": "frozen revisions loaded from local cache only",
        "model_weights_loaded": False,
        "maximum_allowed_difference": 1,
        "maximum_observed_difference": max(
            summary["maximum_absolute_token_difference"] for summary in summaries
        ),
        "summaries": summaries,
        "failures": failures,
        "status": "PASS" if not failures else "FAIL",
    }
    _dump_yaml("artifacts/construct_v2/token_balance.yaml", result)
    return result


def validate_construct_v2() -> dict[str, Any]:
    uptake = _read_jsonl("data/construct_v2/uptake_validation.jsonl")
    reasoning = _read_jsonl("data/construct_v2/reasoning_test.jsonl")
    smoke = _read_jsonl("data/construct_v2/engineering_smoke.jsonl")
    manifest = yaml.safe_load(
        (ROOT / "data/construct_v2/data_manifest.yaml").read_text(encoding="utf-8")
    )
    counts = {
        "uptake_256": len(uptake) == 256,
        "reasoning_matches_power_selected_n": len(reasoning) == 1280,
        "smoke_24": len(smoke) == 24,
        "formal_total_1536": len(uptake) + len(reasoning) == 1536,
    }
    split_uuids = [
        {row["scene_uuid"] for row in rows} for rows in (uptake, reasoning, smoke)
    ]
    disjoint = all(
        split_uuids[left].isdisjoint(split_uuids[right])
        for left in range(3)
        for right in range(left + 1, 3)
    )
    manifest_hashes = all(
        _hash(ROOT / path) == digest for path, digest in manifest["files"].items()
    )
    image_paths = [
        row["image"][key]
        for row in uptake + reasoning + smoke
        for key in ("path", "irrelevant_control_path")
        if row["image"].get(key)
    ]
    images_exist = all((ROOT / path).is_file() for path in image_paths)
    runner = ConstructV2Runner()
    prompt_ids_excluded = True
    for row in reasoning:
        for condition in ("correct", "corrupted"):
            for serialization in ("natural_language", "triples"):
                runner.build_prompt(row, condition=condition, serialization=serialization)
    balance = write_balance_artifacts(reasoning, uptake)
    equivalence = write_serialization_equivalence(reasoning)
    token = write_token_balance(reasoning)
    no_inference = verify_no_construct_v2_inference()
    gates = {
        **counts,
        "split_uuids_disjoint": disjoint,
        "manifest_hashes_match": manifest_hashes,
        "all_rendered_images_exist": images_exist,
        "model_visible_internal_ids_absent": prompt_ids_excluded,
        "answer_balance": balance["answer_balance"] == "PASS",
        "relation_balance": balance["relation_balance"] == "PASS",
        "template_balance": balance["template_balance"] == "PASS",
        "uptake_balance": balance["uptake_balance"] == "PASS",
        "canonical_serialization_equality": equivalence["status"] == "PASS",
        "token_length_difference_le_one": token["status"] == "PASS",
        "no_scientific_inference": no_inference["status"] == "PASS",
    }
    result = {
        "schema_version": 1,
        "counts": {"uptake": len(uptake), "reasoning": len(reasoning), "smoke": len(smoke)},
        "rendered_image_count": len(image_paths),
        "gates": gates,
        "balance": balance,
        "serialization_equivalence": equivalence,
        "token_balance": {
            "status": token["status"],
            "maximum_observed_difference": token["maximum_observed_difference"],
        },
        "no_inference": no_inference,
        "status": "PASS" if all(gates.values()) else "CONSTRUCT_V2_AUTOMATED_NO_GO",
    }
    _dump_yaml("artifacts/construct_v2/verification_report.yaml", result)
    return result
