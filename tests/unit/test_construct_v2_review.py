from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

import yaml

from vlm_construct_audit.construct_v2.review import build_construct_v2_review_packet

ROOT = Path(__file__).resolve().parents[2]


def test_review_packet_contains_blinded_balanced_genuine_and_registered_decoys() -> None:
    result = build_construct_v2_review_packet()
    assert result["status"] == "PENDING_EXTERNAL_CONSTRUCT_REVIEW"
    assert result["packet_rows"] == 80
    with (ROOT / "data/construct_v2_review/review_packet.csv").open(
        encoding="utf-8-sig", newline=""
    ) as handle:
        packet = list(csv.DictReader(handle))
    key = yaml.safe_load(
        (ROOT / "artifacts/construct_v2_review/hidden_key.yaml").read_text(encoding="utf-8")
    )
    assert len(packet) == 80
    assert "status" not in packet[0]
    assert "decoy_type" not in packet[0]
    assert Counter(row["status"] for row in key["rows"]) == Counter(
        {"genuine": 64, "decoy": 16}
    )
    assert all(row["expected"]["critical_error"] == "yes" for row in key["rows"] if row["status"] == "decoy")

