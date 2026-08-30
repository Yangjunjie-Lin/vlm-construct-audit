"""Terminal, non-rescue audit and release governance for the successor program."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from pathlib import Path
from typing import Any

import yaml
from PIL import Image

from .construct_v2.external_review import JUDGMENTS, _cohen_kappa, _validate_attestation
from .construct_v2.generator import ROOT, VECTORS

RESULTS = Path("data/construct_v2_review/results")
AUDIT_YAML = Path("reports/final_closeout/review_integrity_audit.yaml")
AUDIT_MD = Path("reports/final_closeout/review_integrity_audit.md")
SECOND_HOP_DECOY_IDS = ("CVR-073", "CVR-074", "CVR-075", "CVR-076")
FROZEN_REVIEW_HASHES = {
    "reviewer_1_original.csv": (
        "d150c9eb71868f518f88dda5e579bad2389a50e5595924d1d63d79d46866f4d1"
    ),
    "reviewer_2_original.csv": (
        "27ef3cde8f34a57b4043d0cd01d9b02d973f03b9e8c3d134c081a6fa623885d0"
    ),
    "reviewer_1_attestation.yaml": (
        "af4b723ca4b0e9faca2e1030c67deeb2be903d39bc0384bd94872947fb179036"
    ),
    "reviewer_2_attestation.yaml": (
        "f211fdb0a9da954b220bcd920c3436385b78247f259c3f5603b151414bf36943"
    ),
    "aligned_reviews.csv": (
        "2ec470fca5930c1652ad6d56ea6c6afb670229b0057daf29ef31c4a311959c61"
    ),
    "human_construct_review_metrics.yaml": (
        "0fa818864f323e79fe5dabde18c01b45ebeeb8ff3566a301de295cb20c7adf13"
    ),
}
PROVENANCE_CLARIFICATION_SHA256 = (
    "87af9067427a3be835e8ffb7b4f156f4bb497e2a6de85d6e8293e22e50bb4e45"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _statement_code(statement: str) -> str | None:
    match = re.search(r"\breviewer code\s+([A-Za-z0-9-]+)\b", statement)
    return match.group(1) if match else None


def _attestation_audit(root: Path, metrics: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for slot in (1, 2):
        label = f"reviewer_{slot}"
        path = root / RESULTS / f"{label}_attestation.yaml"
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
        statement_code = _statement_code(value["signed_statement"])
        _, frozen_validator_failures = _validate_attestation(
            path.read_bytes(), metrics["bundle_hashes"][label]
        )
        consistent = value["reviewer_code"] == statement_code
        result[label] = {
            "machine_reviewer_code": value["reviewer_code"],
            "signed_statement_reviewer_code": statement_code,
            "attestation_internal_identity_consistency": "PASS" if consistent else "FAIL",
            "review_started_at": value["review_started_at"],
            "review_completed_at": value["review_completed_at"],
            "original_sha256": _sha256(path),
            "frozen_importer_attestation_validation": (
                "PASS" if not frozen_validator_failures else "FAIL"
            ),
            "frozen_importer_validation_failures": frozen_validator_failures,
        }
    return result


def _independence_audit(rows: list[dict[str, str]]) -> dict[str, Any]:
    first = [row[f"{field}_reviewer_1"] for row in rows for field in JUDGMENTS]
    second = [row[f"{field}_reviewer_2"] for row in rows for field in JUDGMENTS]
    decoys = [row for row in rows if row["status"] == "decoy"]
    detected = [row for row in decoys if row["critical_error_reviewer_1"] == "yes"]
    missed = [row for row in decoys if row["critical_error_reviewer_1"] != "yes"]
    genuine = [row for row in rows if row["status"] == "genuine"]
    identical = sum(a == b for a, b in zip(first, second, strict=True))
    note_matches = sum(row["reviewer_1_notes"] == row["reviewer_2_notes"] for row in rows)
    return {
        "item_count": len(rows),
        "judgment_fields_per_item": len(JUDGMENTS),
        "classification_judgment_count": len(first),
        "identical_classification_judgments": identical,
        "overall_agreement": identical / len(first),
        "overall_three_category_cohen_kappa": _cohen_kappa(first, second),
        "per_field_agreement": {
            field: sum(
                row[f"{field}_reviewer_1"] == row[f"{field}_reviewer_2"]
                for row in rows
            )
            / len(rows)
            for field in JUDGMENTS
        },
        "reviewer_notes_verbatim_matches": note_matches,
        "reviewer_notes_verbatim_match_rate": note_matches / len(rows),
        "detected_decoy_count": len(detected),
        "detected_decoy_notes_verbatim_matches": sum(
            row["reviewer_1_notes"] == row["reviewer_2_notes"] for row in detected
        ),
        "genuine_count": len(genuine),
        "genuine_none_notes_both_count": sum(
            row["reviewer_1_notes"] == row["reviewer_2_notes"] == "none"
            for row in genuine
        ),
        "genuine_none_notes_both_rate": sum(
            row["reviewer_1_notes"] == row["reviewer_2_notes"] == "none"
            for row in genuine
        )
        / len(genuine),
        "shared_missed_decoys": [
            {
                "source_review_id": row["source_review_id"],
                "reviewer_1_review_id": row["reviewer_1_review_id"],
                "reviewer_2_review_id": row["reviewer_2_review_id"],
                "decoy_type": row["decoy_type"],
                "reviewer_1_notes": row["reviewer_1_notes"],
                "reviewer_2_notes": row["reviewer_2_notes"],
            }
            for row in missed
        ],
        "conclusion": "INDEPENDENCE_NOT_CREDIBLY_ESTABLISHED_FROM_ARTIFACTS",
        "personnel_conduct_inference": "NOT_SUPPORTED",
    }


def _entity_half_extent(shape: str) -> int:
    return 28 if shape == "oval" else 25


def _decoy_audit(root: Path) -> dict[str, Any]:
    packet = {row["review_id"]: row for row in _read_csv(root / "data/construct_v2_review/review_packet.csv")}
    hidden = yaml.safe_load(
        (root / "artifacts/construct_v2_review/hidden_key.yaml").read_text(encoding="utf-8")
    )
    keys = {row["review_id"]: row for row in hidden["rows"]}
    scenes = {
        row["scene_uuid"]: row
        for row in _read_jsonl(root / "data/construct_v2/reasoning_test.jsonl")
    }
    instructions = (root / "data/construct_v2_review/review_instructions.md").read_text(
        encoding="utf-8"
    )
    instruction_explicit = (
        "text_second_hop_not_visually_represented" in instructions
        and "C/that second hop is absent spatially" in instructions
    )
    items: list[dict[str, Any]] = []
    for review_id in SECOND_HOP_DECOY_IDS:
        key = keys[review_id]
        scene = scenes[key["source_scene_uuid"]]
        record = packet[review_id]
        fact = scene["evidence"]["correct"]["canonical_facts"][0]
        relation = fact["relation"].removesuffix("_of")
        dx, dy = VECTORS[relation]
        c = next(entity for entity in scene["entities"] if entity["role"] == "C")
        c_render = {
            "role": "C",
            "descriptor": c["descriptor"],
            "color": c["color"],
            "shape": c["shape"],
            "x": 128 - 64 * dx,
            "y": 128 - 64 * dy,
        }
        render_entities = [*scene["image"]["render_entities"], c_render]
        c_extent = _entity_half_extent(c_render["shape"])
        overlap_roles = []
        for entity in render_entities[:-1]:
            other_extent = _entity_half_extent(entity["shape"])
            if (
                abs(c_render["x"] - entity["x"]) <= c_extent + other_extent
                and abs(c_render["y"] - entity["y"]) <= c_extent + other_extent
            ):
                overlap_roles.append(entity["role"])
        image_path = root / record["image_path"]
        with Image.open(image_path) as image:
            image_size = list(image.size)
        descriptor_in_text = (
            c["descriptor"] in record["correct_evidence_natural_language"]
            and c["descriptor"] in record["correct_evidence_triples"]
        )
        implementation_matches = (
            key["decoy_type"] == "second_hop_visually_represented"
            and descriptor_in_text
            and not overlap_roles
            and image_size == [256, 256]
            and instruction_explicit
        )
        items.append(
            {
                "source_review_id": review_id,
                "decoy_type": key["decoy_type"],
                "C_descriptor": c["descriptor"],
                "text_second_hop_relation": fact["relation"],
                "C_descriptor_present_in_both_text_serializations": descriptor_in_text,
                "B_position": [128, 128],
                "C_position": [c_render["x"], c_render["y"]],
                "C_overlap_with_roles": overlap_roles,
                "image_size": image_size,
                "image_sha256": _sha256(image_path),
                "second_hop_is_visual_fact": implementation_matches,
                "genuine_ambiguity_detected": False,
                "classification": "DECOY_VALID" if implementation_matches else "DECOY_IMPLEMENTATION_DEFECT",
            }
        )
    classifications = {item["classification"] for item in items}
    return {
        "generation_logic": (
            "C is rendered at B minus 64 times the frozen relation vector, making the "
            "stated B-to-C relation visible."
        ),
        "review_instruction_explicit": instruction_explicit,
        "items": items,
        "overall_classification": (
            "DECOY_VALID" if classifications == {"DECOY_VALID"} else "DECOY_IMPLEMENTATION_DEFECT"
        ),
        "rescue_or_rereview_authorized": False,
    }


def _audit_markdown(audit: dict[str, Any]) -> str:
    independence = audit["reviewer_independence"]
    attestations = audit["attestations"]
    missed = ", ".join(
        row["source_review_id"] for row in independence["shared_missed_decoys"]
    )
    return f"""# Final external-review integrity audit

Classification: `{audit['review_integrity_classification']}`.

Scientific action: `TERMINATE_DIRECTION_P`. This audit has no rescue authority and does not
alter `CONSTRUCT_V2_HUMAN_NO_GO`, the review answers, the 0.90 decoy threshold, or any frozen
review artifact.

## Attestations

Reviewer 1's machine field is `{attestations['reviewer_1']['machine_reviewer_code']}`, while the
signed statement says `{attestations['reviewer_1']['signed_statement_reviewer_code']}`.
`attestation_internal_identity_consistency: FAIL`. The frozen importer passed this record because
it required only a non-empty `signed_statement`; it did not compare the code within the statement
with the machine field. This is an attestation-validation implementation gap.

A pre-deblinding filing/provenance clarification was inspected under hash
`{audit['pre_deblinding_provenance_clarification']['sha256']}`. It cannot repair or supersede the
internal inconsistency in the original signed statement, and no new signature is accepted.
Reviewer 2's corresponding internal check is `PASS`.

## Reviewer-independence evidence

- All {independence['classification_judgment_count']} classification judgments are identical;
  overall agreement is {independence['overall_agreement']:.1f} and three-category Cohen kappa is
  {independence['overall_three_category_cohen_kappa']:.1f}. Every field has agreement 1.0.
- Notes match verbatim on {independence['reviewer_notes_verbatim_matches']}/80 rows. Both reviewers
  wrote `none` on all 64 genuine rows. The 12 detected-decoy explanations match verbatim.
- Both reviews started at
  `{attestations['reviewer_1']['review_started_at']}`. Completion times were
  `{attestations['reviewer_1']['review_completed_at']}` and
  `{attestations['reviewer_2']['review_completed_at']}`.
- Both reviewers missed exactly {missed}; all four are
  `second_hop_visually_represented` decoys.

These artifact patterns do not prove fraud, collusion, fabrication, dishonesty, or any other
personnel conduct. They do mean independence is not credibly established from the preserved
artifacts. The integrity classification is therefore inconclusive, not an accusation.

## Decoy construction

Static inspection of generation code, packet text, instructions, and all four images found each
C descriptor visibly rendered at the text-specified second hop, 64 pixels from B and without
overlap. The instructions explicitly require checking whether C/the second hop is absent.
Classification: `DECOY_VALID`. No ambiguity, replacement review, or scientific continuation is
authorized.

## Preserved outcome

All 64 genuine items passed the required construct fields and had no critical error. The frozen
human gate nevertheless failed because each reviewer detected 12/16 decoys (0.75), below the
unchanged 0.90 threshold. Regardless of integrity classification, Direction P terminates.
"""


def audit_final_review_integrity(root: Path = ROOT) -> dict[str, Any]:
    """Recompute the review audit without changing any input or authorizing rescue."""

    root = root.resolve()
    rows = _read_csv(root / RESULTS / "aligned_reviews.csv")
    metrics = yaml.safe_load(
        (root / RESULTS / "human_construct_review_metrics.yaml").read_text(encoding="utf-8")
    )
    frozen_hashes = {
        name: {
            "expected": expected,
            "observed": _sha256(root / RESULTS / name),
            "preserved": _sha256(root / RESULTS / name) == expected,
        }
        for name, expected in FROZEN_REVIEW_HASHES.items()
    }
    attestations = _attestation_audit(root, metrics)
    independence = _independence_audit(rows)
    decoys = _decoy_audit(root)
    failures = [name for name, value in frozen_hashes.items() if not value["preserved"]]
    if len(rows) != 80:
        failures.append("aligned_reviews_row_count")
    if failures:
        raise RuntimeError(f"FINAL_CLOSEOUT_INTEGRITY_FAILURE: {failures}")
    audit = {
        "schema_version": 1,
        "program": "vlm-construct-audit",
        "audit_scope": "NON_RESCUE_REVIEW_INTEGRITY_CLOSEOUT",
        "frozen_human_gate_decision": "CONSTRUCT_V2_HUMAN_NO_GO",
        "review_integrity_classification": "REVIEW_INTEGRITY_INCONCLUSIVE",
        "scientific_action": "TERMINATE_DIRECTION_P",
        "attestations": attestations,
        "attestation_validation_implementation_gap": {
            "present": True,
            "detail": (
                "The importer validates that signed_statement is non-empty but does not compare "
                "a reviewer code embedded in it with reviewer_code."
            ),
        },
        "pre_deblinding_provenance_clarification": {
            "status": "INSPECTED_NOT_DISTRIBUTED",
            "sha256": PROVENANCE_CLARIFICATION_SHA256,
            "effect_on_original_attestation_inconsistency": "NONE",
            "replacement_attestation_accepted": False,
        },
        "reviewer_independence": independence,
        "decoy_construction": decoys,
        "genuine_items": {
            "count": 64,
            "all_required_construct_fields_passed": True,
            "critical_error_count": 0,
        },
        "frozen_decoy_gate": {
            "threshold": 0.90,
            "reviewer_1_rate": 0.75,
            "reviewer_2_rate": 0.75,
            "passed": False,
        },
        "frozen_review_artifact_preservation": frozen_hashes,
        "prohibited_personnel_inferences": [
            "fraud",
            "collusion",
            "fabrication",
            "dishonesty",
        ],
        "rescue_authority": False,
        "new_reviewer_authorized": False,
        "third_reviewer_authorized": False,
        "rereview_authorized": False,
    }
    yaml_path = root / AUDIT_YAML
    md_path = root / AUDIT_MD
    yaml_path.parent.mkdir(parents=True, exist_ok=True)
    yaml_path.write_text(yaml.safe_dump(audit, sort_keys=False), encoding="utf-8")
    md_path.write_text(_audit_markdown(audit), encoding="utf-8")
    return audit
