from __future__ import annotations

import csv
import hashlib
import io
import re
import subprocess
import zipfile
from pathlib import Path

import pytest
import yaml

from vlm_construct_audit.construct_v2.external_review import (
    ATTESTATION_FIELDS,
    PACKET_FIELDS,
    RESPONSE_FIELDS,
    _cohen_kappa,
    import_external_review_returns,
    verify_external_review_packages,
)

ROOT = Path(__file__).resolve().parents[2]
PACKAGES = ROOT / "external_review_packages"
UUID_PATTERN = re.compile(
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
    re.IGNORECASE,
)


def _rows(content: bytes) -> tuple[list[str], list[dict[str, str]]]:
    reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig"), newline=""))
    return list(reader.fieldnames or []), list(reader)


@pytest.mark.parametrize("slot", [1, 2])
def test_reviewer_bundle_is_strictly_isolated(slot: int) -> None:
    commitment = yaml.safe_load((PACKAGES / "public_commitment.yaml").read_text())
    bundle_path = PACKAGES / f"reviewer_{slot}_bundle.zip"
    assert hashlib.sha256(bundle_path.read_bytes()).hexdigest() == commitment["bundles"][
        f"reviewer_{slot}"
    ]["sha256"]
    with zipfile.ZipFile(bundle_path) as bundle:
        names = bundle.namelist()
        files = {name: bundle.read(name) for name in names}
    base = {
        "review_packet.csv",
        "response_template.csv",
        "review_instructions.md",
        "reviewer_attestation.yaml",
        "SHA256SUMS.txt",
    }
    images = {name for name in names if name.startswith("images/")}
    assert set(names) == base | images
    assert len(names) == len(set(names))
    assert len(images) == 80
    assert all(name.endswith(".png") for name in images)

    packet_fields, packet_rows = _rows(files["review_packet.csv"])
    response_fields, response_rows = _rows(files["response_template.csv"])
    assert tuple(packet_fields) == PACKET_FIELDS
    assert tuple(response_fields) == RESPONSE_FIELDS
    assert len(packet_rows) == len(response_rows) == 80
    review_ids = [row["review_id"] for row in packet_rows]
    assert len(review_ids) == len(set(review_ids)) == 80
    assert all(re.fullmatch(rf"R{slot}-[23456789A-HJ-NP-Z]{{6}}", value) for value in review_ids)
    assert [row["review_id"] for row in response_rows] == review_ids
    assert {row["image_path"] for row in packet_rows} == {
        f"images/{review_id}.png" for review_id in review_ids
    }
    assert images == {row["image_path"] for row in packet_rows}
    assert all(files[name].startswith(b"\x89PNG\r\n\x1a\n") for name in images)

    visible_text = "\n".join(names) + files["review_packet.csv"].decode("utf-8-sig")
    assert "CVR-" not in visible_text
    assert not UUID_PATTERN.search(visible_text)
    for forbidden in (
        "source_scene_uuid",
        "internal_scene_id",
        "hidden_key.yaml",
        "packet_manifest.yaml",
        "genuine_count",
        "decoy_count",
        "generator seed",
    ):
        assert forbidden not in visible_text
    assert not any(name.endswith(".py") or name.startswith(".git/") for name in names)

    expected_sums = {}
    for line in files["SHA256SUMS.txt"].decode().splitlines():
        digest, name = line.split("  ", 1)
        expected_sums[name] = digest
    assert set(expected_sums) == set(names) - {"SHA256SUMS.txt"}
    assert all(hashlib.sha256(files[name]).hexdigest() == digest for name, digest in expected_sums.items())
    attestation = yaml.safe_load(files["reviewer_attestation.yaml"])
    assert tuple(attestation) == ATTESTATION_FIELDS


def test_reviewer_id_sets_and_packet_orders_are_independent() -> None:
    packets = []
    for slot in (1, 2):
        with zipfile.ZipFile(PACKAGES / f"reviewer_{slot}_bundle.zip") as bundle:
            _, rows = _rows(bundle.read("review_packet.csv"))
        packets.append([row["review_id"] for row in rows])
    assert set(packets[0]).isdisjoint(packets[1])
    assert packets[0] != packets[1]


def test_public_commitment_preserves_frozen_source_hashes() -> None:
    commitment = yaml.safe_load((PACKAGES / "public_commitment.yaml").read_text())
    packet = ROOT / commitment["original_packet"]["path"]
    hidden_key = ROOT / "artifacts/construct_v2_review/hidden_key.yaml"
    assert hashlib.sha256(packet.read_bytes()).hexdigest() == commitment["original_packet"][
        "sha256"
    ]
    assert hashlib.sha256(hidden_key.read_bytes()).hexdigest() == commitment[
        "frozen_hidden_key_sha256"
    ]
    assert commitment["packet_row_count"] == 80
    assert commitment["formal_vlm_inference_count"] == 0
    assert commitment["uptake_output_count"] == 0
    assert commitment["reasoning_output_count"] == 0
    assert commitment["scientific_metrics_count"] == 0
    assert commitment["runner_blocked"] is True
    assert commitment["model_or_agent_review_used"] is False


def test_private_mappings_and_returns_are_not_tracked() -> None:
    tracked = subprocess.run(
        ["git", "ls-files", "private_review_state", "private_review_returns"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert tracked == ""


def test_import_remains_pending_without_all_four_returns() -> None:
    result = import_external_review_returns()
    assert result["status"] == "PENDING_EXTERNAL_CONSTRUCT_REVIEW"
    assert len(result["missing_return_files"]) == 4
    assert result["original_packet_unchanged"] is True
    assert result["formal_vlm_inference_count"] == 0
    assert result["runner_blocked"] is True
    assert result["mapping_revealed"] is False
    assert result["candidate_tag_created"] is False


def test_three_category_kappa_keeps_uncertain() -> None:
    first = ["yes", "no", "uncertain", "yes", "uncertain", "no"]
    second = ["yes", "uncertain", "uncertain", "no", "yes", "no"]
    assert _cohen_kappa(first, second) == pytest.approx(0.25)
    assert _cohen_kappa(["yes", "yes"], ["yes", "yes"]) is None


def test_public_bundle_verifier_passes() -> None:
    result = verify_external_review_packages()
    assert result["status"] == "PENDING_EXTERNAL_CONSTRUCT_REVIEW"
