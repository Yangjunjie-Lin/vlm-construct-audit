from __future__ import annotations

import csv
import hashlib
from collections import Counter
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def test_review_packet_contains_blinded_balanced_genuine_and_registered_decoys() -> None:
    commitment = yaml.safe_load(
        (ROOT / "external_review_packages/public_commitment.yaml").read_text(encoding="utf-8")
    )
    manifest = yaml.safe_load(
        (ROOT / "artifacts/construct_v2_review/packet_manifest.yaml").read_text(
            encoding="utf-8"
        )
    )
    with (ROOT / "data/construct_v2_review/review_packet.csv").open(
        encoding="utf-8-sig", newline=""
    ) as handle:
        packet = list(csv.DictReader(handle))
    key = yaml.safe_load(
        (ROOT / "artifacts/construct_v2_review/hidden_key.yaml").read_text(encoding="utf-8")
    )
    assert len(packet) == 80
    assert manifest["row_count"] == 80
    assert manifest["genuine_count"] == 64
    assert manifest["decoy_count"] == 16
    assert "status" not in packet[0]
    assert "decoy_type" not in packet[0]
    assert Counter(row["status"] for row in key["rows"]) == Counter(
        {"genuine": 64, "decoy": 16}
    )
    assert all(row["expected"]["critical_error"] == "yes" for row in key["rows"] if row["status"] == "decoy")
    assert hashlib.sha256(
        (ROOT / "data/construct_v2_review/review_packet.csv").read_bytes()
    ).hexdigest() == commitment["original_packet"]["sha256"]
    assert hashlib.sha256(
        (ROOT / "artifacts/construct_v2_review/hidden_key.yaml").read_bytes()
    ).hexdigest() == commitment["frozen_hidden_key_sha256"]
    assert hashlib.sha256(
        (ROOT / "artifacts/construct_v2_review/packet_manifest.yaml").read_bytes()
    ).hexdigest() == commitment["frozen_packet_manifest_sha256"]
