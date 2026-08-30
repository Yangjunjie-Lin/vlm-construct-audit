"""Build a blinded external human construct-review packet."""

from __future__ import annotations

import copy
import csv
import hashlib
import json
import random
from collections import Counter
from pathlib import Path
from typing import Any

import yaml

from .generator import INVERSE, ROOT, VECTORS, _serialize
from .renderer import render_scene

JUDGMENTS = (
    "visual_first_hop_correct",
    "bridge_entity_uniquely_identifiable",
    "text_second_hop_correct",
    "text_second_hop_not_visually_represented",
    "conditions_differ_in_exactly_one_target_relation",
    "no_direct_image_text_conflict",
    "joint_answer_unique",
    "image_alone_not_uniquely_sufficient",
    "evidence_alone_not_uniquely_sufficient",
    "nl_triples_fact_equivalent",
    "critical_error",
)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _descriptor(row: dict[str, Any], role: str) -> str:
    return next(entity["descriptor"] for entity in row["entities"] if entity["role"] == role)


def _relation(row: dict[str, Any], modality: str, condition: str = "correct") -> str:
    if modality == "image":
        fact = row["image"]["canonical_facts"][0]
    else:
        fact = row["evidence"][condition]["canonical_facts"][0]
    return fact["relation"].removesuffix("_of")


def _packet_record(row: dict[str, Any], review_id: str) -> dict[str, str]:
    first = _relation(row, "image")
    return {
        "review_id": review_id,
        "image_path": row["image"]["path"],
        "visual_first_hop_claim": (
            f"The {_descriptor(row, 'A')} is {first} of the {_descriptor(row, 'B')}."
        ),
        "correct_evidence_natural_language": row["evidence"]["correct"]["natural_language"],
        "correct_evidence_triples": row["evidence"]["correct"]["triples"],
        "corrupted_evidence_natural_language": row["evidence"]["corrupted"]["natural_language"],
        "corrupted_evidence_triples": row["evidence"]["corrupted"]["triples"],
        "question": row["question"]["text"],
        "semantic_candidates": " | ".join(row["answer"]["semantic_candidates"]),
        "proposed_joint_answer": row["answer"]["semantic"],
        "proposed_corrupted_answer": row["answer"]["corrupted_semantic"],
    }


def _genuine_key(review_id: str, row: dict[str, Any]) -> dict[str, Any]:
    return {
        "review_id": review_id,
        "source_scene_uuid": row["scene_uuid"],
        "status": "genuine",
        "decoy_type": None,
        "expected": {**{judgment: "yes" for judgment in JUDGMENTS[:-1]}, "critical_error": "no"},
    }


def _decoy(
    source: dict[str, Any], decoy_type: str, review_id: str
) -> tuple[dict[str, str], dict[str, Any]]:
    row = copy.deepcopy(source)
    row["image"]["path"] = f"data/construct_v2_review/images/{review_id}.png"
    packet = _packet_record(row, review_id)
    expected = {**{judgment: "yes" for judgment in JUDGMENTS[:-1]}, "critical_error": "yes"}
    if decoy_type == "visual_first_hop_mismatch":
        claimed = INVERSE[_relation(row, "image")]
        packet["visual_first_hop_claim"] = (
            f"The {_descriptor(row, 'A')} is {claimed} of the {_descriptor(row, 'B')}."
        )
        expected["visual_first_hop_correct"] = "no"
    elif decoy_type == "ambiguous_bridge_entity":
        second = _relation(row, "evidence")
        packet["correct_evidence_natural_language"] = (
            f"The {_descriptor(row, 'B')} or the {_descriptor(row, 'D')} is {second} of "
            f"the {_descriptor(row, 'C')}."
        )
        expected["bridge_entity_uniquely_identifiable"] = "no"
        expected["text_second_hop_correct"] = "no"
        expected["joint_answer_unique"] = "no"
        expected["nl_triples_fact_equivalent"] = "no"
    elif decoy_type == "second_hop_visually_represented":
        second = _relation(row, "evidence")
        dx, dy = VECTORS[second]
        c = next(entity for entity in row["entities"] if entity["role"] == "C")
        row["image"]["render_entities"].append(
            {
                "role": "C",
                "descriptor": c["descriptor"],
                "color": c["color"],
                "shape": c["shape"],
                "x": 128 - 64 * dx,
                "y": 128 - 64 * dy,
            }
        )
        expected["text_second_hop_not_visually_represented"] = "no"
    elif decoy_type == "multi_fact_corruption":
        corrupted_relation = _relation(row, "evidence", "corrupted")
        head = _descriptor(row, "D")
        tail = _descriptor(row, "C")
        packet["corrupted_evidence_natural_language"] = _serialize(
            head, corrupted_relation, tail, "natural_language"
        )
        packet["corrupted_evidence_triples"] = _serialize(
            head, corrupted_relation, tail, "triples"
        )
        expected["conditions_differ_in_exactly_one_target_relation"] = "no"
    else:
        raise ValueError(decoy_type)
    render_scene(row)
    key = {
        "review_id": review_id,
        "source_scene_uuid": source["scene_uuid"],
        "status": "decoy",
        "decoy_type": decoy_type,
        "expected": expected,
    }
    return packet, key


def _select_genuine(rows: list[dict[str, Any]], seed: int) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    by_answer: dict[str, list[dict[str, Any]]] = {}
    for answer in ("northeast", "northwest", "southeast", "southwest"):
        candidates = [row for row in rows if row["answer"]["semantic"] == answer]
        rng.shuffle(candidates)
        by_answer[answer] = candidates[:16]
    return [row for answer in sorted(by_answer) for row in by_answer[answer]]


def build_construct_v2_review_packet() -> dict[str, Any]:
    registry = yaml.safe_load(
        (ROOT / "research/construct_restart/v2_review_decoys.yaml").read_text(encoding="utf-8")
    )
    rows = _read_jsonl(ROOT / "data/construct_v2/reasoning_test.jsonl")
    genuine = _select_genuine(rows, int(registry["selection_seed"]))
    used = {row["scene_uuid"] for row in genuine}
    decoy_sources = [
        row
        for row in rows
        if row["scene_uuid"] not in used and row["entity_count"] >= 4
    ][:16]
    packet_rows = []
    keys = []
    for index, row in enumerate(genuine):
        review_id = f"CVR-{index + 1:03d}"
        packet_rows.append(_packet_record(row, review_id))
        keys.append(_genuine_key(review_id, row))
    decoy_types = [
        decoy_type
        for decoy_type, spec in registry["decoy_types"].items()
        for _ in range(int(spec["count"]))
    ]
    for offset, (row, decoy_type) in enumerate(zip(decoy_sources, decoy_types, strict=True), 65):
        review_id = f"CVR-{offset:03d}"
        packet, key = _decoy(row, decoy_type, review_id)
        packet_rows.append(packet)
        keys.append(key)
    random.Random(int(registry["packet_shuffle_seed"])).shuffle(packet_rows)
    packet_path = ROOT / "data/construct_v2_review/review_packet.csv"
    packet_path.parent.mkdir(parents=True, exist_ok=True)
    with packet_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(packet_rows[0]))
        writer.writeheader()
        writer.writerows(packet_rows)
    template_path = ROOT / "data/construct_v2_review/review_template.csv"
    with template_path.open("w", encoding="utf-8-sig", newline="") as handle:
        fields = ["review_id", *JUDGMENTS, "reviewer_notes"]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in packet_rows:
            writer.writerow({"review_id": row["review_id"]})
    instructions_path = ROOT / "data/construct_v2_review/review_instructions.md"
    instructions_path.write_text(
        """# Independent Direction P v2 construct review

Review all 80 rows independently. Do not consult another reviewer, the author,
the hidden key, generator code, or another reviewer's answers. The packet mixes
genuine scenes with preregistered decoys; their identities are blinded.

Open each `image_path` from the repository root and answer every column with
exactly `yes`, `no`, or `uncertain`. Judge the displayed image and supplied text,
not what you believe the generator intended. Mark `critical_error=yes` whenever
any flaw would invalidate cross-modal bridge composition or its paired contrast.

Definitions:

- `visual_first_hop_correct`: the claim about A relative to B matches the image.
- `bridge_entity_uniquely_identifiable`: the text identifies exactly one image B.
- `text_second_hop_correct`: one definite B-to-C cardinal relation is stated.
- `text_second_hop_not_visually_represented`: C/that second hop is absent spatially.
- `conditions_differ_in_exactly_one_target_relation`: only R2 changes.
- `no_direct_image_text_conflict`: neither condition contradicts a visible fact.
- `joint_answer_unique`: image first hop plus correct evidence yield one candidate.
- unimodal insufficiency columns: that modality alone cannot select one candidate.
- `nl_triples_fact_equivalent`: both serializations state exactly the same fact.

Reviewer eligibility: a real person independent of dataset authorship and this
agentic build. Two eligible reviewers are required. Agreement is computed across
all binary construct judgments, with overall agreement >=0.95 and Cohen's kappa
>=0.80. Genuine scenes require zero critical errors. At least 90% of decoys must
be marked `critical_error=yes`. Do not edit `review_packet.csv`.
""",
        encoding="utf-8",
    )
    hidden_path = ROOT / "artifacts/construct_v2_review/hidden_key.yaml"
    hidden_path.parent.mkdir(parents=True, exist_ok=True)
    hidden = {
        "schema_version": 1,
        "blinded": True,
        "genuine_count": 64,
        "decoy_count": 16,
        "rows": keys,
    }
    hidden_path.write_text(yaml.safe_dump(hidden, sort_keys=False), encoding="utf-8")
    manifest_path = ROOT / "artifacts/construct_v2_review/packet_manifest.yaml"
    files = [packet_path, instructions_path, template_path, hidden_path]
    manifest = {
        "schema_version": 1,
        "packet_id": "direction_p_construct_v2_blinded_review_v1",
        "row_count": len(packet_rows),
        "genuine_count": 64,
        "decoy_count": 16,
        "answer_balance_genuine": dict(
            Counter(row["answer"]["semantic"] for row in genuine)
        ),
        "decoy_type_counts": dict(Counter(decoy_types)),
        "reviewer_count_required": 2,
        "reviewer_count_completed": 0,
        "review_status": "PENDING_EXTERNAL_CONSTRUCT_REVIEW",
        "files": {str(path.relative_to(ROOT)).replace("\\", "/"): _sha256(path) for path in files},
        "agent_or_author_may_serve_as_reviewer": False,
    }
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    return {
        "status": "PENDING_EXTERNAL_CONSTRUCT_REVIEW",
        "packet_rows": len(packet_rows),
        "genuine": 64,
        "decoys": 16,
        "packet_sha256": manifest["files"]["data/construct_v2_review/review_packet.csv"],
        "reviewer_count_completed": 0,
    }
