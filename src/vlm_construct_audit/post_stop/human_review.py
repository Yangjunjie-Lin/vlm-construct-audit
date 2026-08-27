"""Import two genuinely independent human reviews of the frozen Loop B packet."""

from __future__ import annotations

import csv
from pathlib import Path
from statistics import mean
from typing import Any

from .common import ROOT, dump_yaml, load_yaml, sha256_file, utc_now

PACKET = Path("data/annotations/serialization_review_packet.csv")
REVIEWER_FILES = [Path("data/annotations/reviewer_1.csv"), Path("data/annotations/reviewer_2.csv")]
RESPONSE_FIELDS = [
    "fact_equivalent", "same_entities", "same_attributes", "same_relations", "same_answer",
    "naturalness_issue", "ambiguity_issue", "critical_error",
]
FROZEN_PACKET_SHA256 = "b4d5cf32b149ecad0df325a46737a79d0e0415083173ec509247af844bedfeab"


def _bool(value: str) -> bool:
    normalized = value.strip().casefold()
    if normalized in {"true", "1", "yes", "y"}:
        return True
    if normalized in {"false", "0", "no", "n"}:
        return False
    raise ValueError(f"boolean field must be true/false, received {value!r}")


def _read(path: Path) -> list[dict[str, str]]:
    with (ROOT / path).open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _validate_reviewer(path: Path, packet: list[dict[str, str]]) -> tuple[str, list[dict[str, Any]]]:
    rows = _read(path)
    if len(rows) != len(packet):
        raise ValueError(f"{path} has {len(rows)} rows; expected {len(packet)}")
    packet_map = {row["pair_id"]: row for row in packet}
    if {row["pair_id"] for row in rows} != set(packet_map):
        raise ValueError(f"{path} pair IDs differ from the frozen packet")
    reviewers = {row.get("reviewer_id", "").strip() for row in rows}
    if len(reviewers) != 1 or not next(iter(reviewers)):
        raise ValueError(f"{path} must contain one stable non-empty reviewer_id")
    parsed = []
    for row in rows:
        source = packet_map[row["pair_id"]]
        for field in ["question", "options", "evidence_a", "evidence_b"]:
            if row.get(field, source[field]) != source[field]:
                raise ValueError(f"{path} modifies frozen packet text for {row['pair_id']}:{field}")
        parsed.append({"pair_id": row["pair_id"], **{field: _bool(row.get(field, "")) for field in RESPONSE_FIELDS}})
    return next(iter(reviewers)), parsed


def _cohen_kappa(a: list[bool], b: list[bool]) -> float:
    observed = mean(x == y for x, y in zip(a, b, strict=True))
    pa = mean(a)
    pb = mean(b)
    expected = pa * pb + (1 - pa) * (1 - pb)
    return 1.0 if observed == expected == 1.0 else (observed - expected) / (1 - expected)


def import_human_review() -> dict[str, Any]:
    if sha256_file(PACKET) != FROZEN_PACKET_SHA256:
        raise RuntimeError("frozen review packet hash changed")
    missing = [str(path) for path in REVIEWER_FILES if not (ROOT / path).exists()]
    if missing:
        raise FileNotFoundError(f"two completed independent human files are required; missing {missing}")
    packet = _read(PACKET)
    reviewer_1, rows_1 = _validate_reviewer(REVIEWER_FILES[0], packet)
    reviewer_2, rows_2 = _validate_reviewer(REVIEWER_FILES[1], packet)
    if reviewer_1 == reviewer_2:
        raise ValueError("reviewer IDs must be distinct")
    # The hidden key is intentionally loaded only after both human files have passed completeness checks.
    key = load_yaml("artifacts/loop_b/serialization_review_key.yaml")
    truth = {row["pair_id"]: bool(row["expected_fact_equivalent"]) for row in key["rows"]}
    decoys = {row["pair_id"] for row in key["rows"] if row["decoy"]}
    by_id_1 = {row["pair_id"]: row for row in rows_1}
    by_id_2 = {row["pair_id"]: row for row in rows_2}
    labels_1 = [by_id_1[row["pair_id"]]["fact_equivalent"] for row in packet]
    labels_2 = [by_id_2[row["pair_id"]]["fact_equivalent"] for row in packet]
    agreement = mean(a == b for a, b in zip(labels_1, labels_2, strict=True))
    kappa = _cohen_kappa(labels_1, labels_2)
    decoy_detection_1 = mean(not by_id_1[pair_id]["fact_equivalent"] for pair_id in decoys)
    decoy_detection_2 = mean(not by_id_2[pair_id]["fact_equivalent"] for pair_id in decoys)
    genuine = set(truth) - decoys
    critical = sum(
        by_id_1[pair_id]["critical_error"] or by_id_2[pair_id]["critical_error"]
        or not by_id_1[pair_id]["fact_equivalent"] or not by_id_2[pair_id]["fact_equivalent"]
        for pair_id in genuine
    )
    adjudication_rows = []
    for source in packet:
        pair_id = source["pair_id"]
        first = by_id_1[pair_id]
        second = by_id_2[pair_id]
        adjudication_rows.append({
            "pair_id": pair_id,
            "reviewer_1_id": reviewer_1,
            "reviewer_1_fact_equivalent": str(first["fact_equivalent"]).lower(),
            "reviewer_2_id": reviewer_2,
            "reviewer_2_fact_equivalent": str(second["fact_equivalent"]).lower(),
            "reviewers_agree": str(first["fact_equivalent"] == second["fact_equivalent"]).lower(),
            "expected_fact_equivalent": str(truth[pair_id]).lower(),
            "decoy": str(pair_id in decoys).lower(),
            "adjudicated_fact_equivalent": str(truth[pair_id]).lower(),
            "disagreement_retained": str(first["fact_equivalent"] != second["fact_equivalent"]).lower(),
        })
    adjudication_path = ROOT / "data/annotations/adjudication.csv"
    with adjudication_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(adjudication_rows[0]))
        writer.writeheader()
        writer.writerows(adjudication_rows)
    gates = {
        "critical_semantic_mismatch": critical == 0,
        "fact_equivalence_agreement": agreement >= 0.95,
        "cohen_kappa": kappa >= 0.80,
        "decoy_detection": min(decoy_detection_1, decoy_detection_2) >= 0.90,
    }
    metrics = {
        "schema_version": 1,
        "status": "HUMAN_REVIEW_GO" if all(gates.values()) else "MEASUREMENT_FOUNDATION_NO_GO",
        "imported_at": utc_now(),
        "reviewer_count": 2,
        "reviewer_ids": [reviewer_1, reviewer_2],
        "agent_or_model_review_used": False,
        "packet_sha256": FROZEN_PACKET_SHA256,
        "packet_rows": len(packet),
        "fact_equivalence_agreement": agreement,
        "cohen_kappa": kappa,
        "critical_semantic_mismatch": critical,
        "decoy_detection": {reviewer_1: decoy_detection_1, reviewer_2: decoy_detection_2, "minimum": min(decoy_detection_1, decoy_detection_2)},
        "disagreement_count": sum(a != b for a, b in zip(labels_1, labels_2, strict=True)),
        "gates": gates,
        "disagreements_deleted": False,
    }
    dump_yaml("data/annotations/human_review_metrics.yaml", metrics)
    return metrics
