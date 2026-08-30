"""Terminal, non-rescue audit and release governance for the successor program."""

from __future__ import annotations

import csv
import hashlib
import json
import re
import subprocess
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
RELEASE_ROOT = Path("release/vlm-construct-audit-negative-evidence-v1")
FINAL_TAG = "vlm-construct-audit-final-closeout-2026-08-30"
RELEASE_NAME = "vlm-construct-audit-negative-evidence-v1"
HISTORICAL_TAGS = {
    "construct-v2-automated-preaudit-freeze": (
        "1552a3c77e0bdd6bf0fdb0bf49447c19df4af6f2"
    ),
    "construct-v2-human-gate-policy-freeze": (
        "1f4e85b8d474a882c40f39d3fd0aa26b70e254a1"
    ),
    "p-mini-pilot-preregistered": "9de60b87ec54bc852a7bb2e9cff87d9c23638042",
    "p-mini-pilot-preregistration-audit-no-pass": (
        "97c64947a0e6b30b0c9a0654519bbd93ae37d846"
    ),
    "vlm-construct-audit-post-stop-final": (
        "f993282e0a27b8da0ba1c239fb96715c9fc5b79a"
    ),
    "vlm-construct-audit-tier0-5-stop": (
        "ce0e797a4926ab5d2309915c2eef14fd9c5be44d"
    ),
}


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


def _final_adjudication_payload() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "program": "vlm-construct-audit",
        "decision": "TERMINATE_SUCCESSOR_PROGRAM",
        "review_integrity_classification": "REVIEW_INTEGRITY_INCONCLUSIVE",
        "scientific_pilot_authorized": False,
        "scientific_inference_executed": False,
        "paper_writing_authorized": False,
        "benchmark_expansion_authorized": False,
        "directions": {
            "M": "NO_GO",
            "U": "NO_GO",
            "P_v1": "AUDIT_FAIL_CONSTRUCT_VALIDITY",
            "P_v2": "REVIEW_INTEGRITY_INCONCLUSIVE",
            "further_direction_creation": "forbidden",
        },
        "scientific_execution": {
            "formal_vlm_inference": 0,
            "scientific_prediction_files": 0,
            "uptake_outputs": 0,
            "reasoning_outputs": 0,
            "scientific_metrics": 0,
            "runner_authorization": False,
            "paper_writing_authorization": False,
        },
        "interpretation": {
            "p_known_dgp_role": "CONTROLLED_METHODOLOGICAL_CALIBRATION",
            "p_known_dgp_supports_real_vlm_claim": False,
            "v2_automated_pass_overrides_human_or_integrity_gate": False,
            "ci_pass_meaning": "SOFTWARE_AND_RECORD_CONSISTENCY_ONLY",
            "real_vlm_scientific_result_produced": False,
            "sci_q1_claim_bearing_paper_available": False,
        },
        "exact_next_action": "PUBLISH_NEGATIVE_EVIDENCE_AND_ARCHIVE",
    }


def _release_readme() -> str:
    return f"""# VLM Construct Audit negative evidence v1

This is a negative-evidence and research-governance resource. It is not a successful method,
not a model benchmark leaderboard, and not evidence for an internal VLM mechanism. It does not
authorize continued experimentation, a new direction, benchmark expansion, or claim-bearing
paper writing.

The terminal decision is `TERMINATE_SUCCESSOR_PROGRAM`; the review classification is
`REVIEW_INTEGRITY_INCONCLUSIVE`. Direction P v2 executed zero formal VLM scientific inferences.
The P3 known-DGP result remains controlled methodological calibration only.

The package preserves the lineage from archived ReCoAlign negative evidence through final
successor-program termination. Reviewer identity data are limited to necessary anonymous codes.
No unnecessary personal information, private mapping state, hidden-key material, or unneeded
source returns are included.

Canonical tag: `{FINAL_TAG}`. Release name: `{RELEASE_NAME}`.
Run the commands in `REPRODUCIBILITY.md` and verify `checksums.sha256` before use.
"""


def _research_lineage() -> str:
    return """# Research lineage

The frozen governance chain is:

1. ReCoAlign archived negative evidence (`TERMINATE_CURRENT_PROGRAM`).
2. Tier 0 known-state calibration and executable audit plumbing.
3. AuditV2 method failure (`LOOP_A_NO_GO`; no reinterpretation).
4. Post-STOP M/U/P screen under frozen priority and revision limits.
5. Direction P controlled known-DGP GO; Directions M and U NO-GO.
6. Direction P v1 construct-validity failure under independent preregistration audit.
7. Direction P v2 redesign and automated construct-gate PASS.
8. External human gate NO-GO, followed by a non-rescue integrity audit classified
   `REVIEW_INTEGRITY_INCONCLUSIVE`.
9. Successor-program termination with zero formal Direction P v2 VLM inference.

No link in this chain authorizes a mechanism claim. Later calibration evidence does not repair an
earlier failed method, and an automated gate does not override the human or integrity outcome.
"""


def _review_integrity_note() -> str:
    return """# Review integrity note

The two returns agree on all 880 classification judgments and all 80 reviewer-note rows. Both
reviews started at the same recorded time, both missed the same four
`second_hop_visually_represented` decoys, and their explanations for the other 12 decoys are
verbatim identical. Reviewer 1's machine code is `R1-HUMAN-A7K3`, while the original signed
statement contains `R1-HUMAN-A7K2`; the importer checked only that the statement was non-empty.

Static audit classified all four missed decoys `DECOY_VALID`. All 64 genuine items passed, while
the unchanged 0.90 decoy gate failed at 0.75 for each reviewer. These artifacts do not establish
reviewer independence credibly, but they also do not prove fraud, collusion, fabrication,
dishonesty, or any other personnel conduct. No replacement signature, reviewer, third reviewer,
or rerun is authorized. See `reports/final_closeout/review_integrity_audit.*` in the tagged source.
"""


def _reproducibility_note() -> str:
    return f"""# Reproducibility

Use Python 3.10 or later. No model weights are needed or permitted for this closeout.

```bash
git clone https://github.com/Yangjunjie-Lin/vlm-construct-audit.git
cd vlm-construct-audit
git checkout {FINAL_TAG}
python -m pip install -e ".[dev]"
pytest
ruff check .
python -m vlm_construct_audit verify-artifacts
python -m vlm_construct_audit verify-post-stop-artifacts
python -m vlm_construct_audit verify-frozen-p-mini-pilot-preregistration-read-only
python -m vlm_construct_audit validate-construct-v2
python -m vlm_construct_audit verify-no-construct-v2-inference
python -m vlm_construct_audit audit-final-review-integrity
python -m vlm_construct_audit build-final-successor-adjudication
python -m vlm_construct_audit build-final-negative-evidence-release
python -m vlm_construct_audit verify-final-closeout
```

`verify-final-closeout` verifies this package's SHA-256 file list, all historical tags, preserved
review returns and attestations, the absent candidate and authorization artifacts, the blocked
runner, and zero formal Direction P v2 outputs. Re-running deterministic builders must leave the
tagged working tree clean. CI success means software and record consistency, not scientific
validation.
"""


def _licenses_note() -> str:
    return """# Licenses and privacy

The `vlm-construct-audit` source and closeout documentation are released under the repository's
MIT License; see the root `LICENSE` file in the tagged source. ReCoAlign is referenced only as an
archived provenance source under Apache-2.0. No ReCoAlign code, data, predictions, or scientific
artifacts are redistributed in this package.

Generated construct images and governance text are included as repository artifacts under the
repository license. External-review identities are represented only by anonymous reviewer codes.
Private mapping state, unnecessary personal information, and the private provenance filing are
not distributed in this release package.
"""


def _release_source_paths() -> tuple[Path, ...]:
    return (
        Path("docs/recoalign_provenance_boundary.md"),
        Path("reports/tier0_5_final_decision.yaml"),
        Path("reports/post_stop_direction_p_decision.yaml"),
        Path("reports/post_stop_direction_m_decision.yaml"),
        Path("reports/post_stop_direction_u_decision.yaml"),
        Path("reports/independent_audit/final_audit_decision.yaml"),
        Path("reports/construct_v2_automated_gate.yaml"),
        Path("reports/construct_v2_human_review_decision.yaml"),
        Path("reports/final_closeout/review_integrity_audit.yaml"),
        Path("reports/final_closeout/final_claim_boundary.yaml"),
        Path("reports/final_closeout/final_evidence_map.yaml"),
        Path("research/final_closeout/hypothesis_closeout.yaml"),
    )


def build_final_negative_evidence_release(root: Path = ROOT) -> dict[str, Any]:
    """Build the deterministic, non-claim-bearing negative-evidence package."""

    root = root.resolve()
    release = root / RELEASE_ROOT
    release.mkdir(parents=True, exist_ok=True)
    text_payloads = {
        "README.md": _release_readme(),
        "RESEARCH_LINEAGE.md": _research_lineage(),
        "REVIEW_INTEGRITY_NOTE.md": _review_integrity_note(),
        "REPRODUCIBILITY.md": _reproducibility_note(),
        "LICENSES.md": _licenses_note(),
    }
    for name, content in text_payloads.items():
        (release / name).write_bytes(content.encode("utf-8"))
    copies = {
        "CLAIM_BOUNDARY.md": Path("reports/final_closeout/final_claim_boundary.md"),
        "HYPOTHESIS_CLOSEOUT.yaml": Path("research/final_closeout/hypothesis_closeout.yaml"),
        "EVIDENCE_MAP.yaml": Path("reports/final_closeout/final_evidence_map.yaml"),
    }
    for name, source in copies.items():
        (release / name).write_bytes((root / source).read_bytes())
    (release / "FINAL_ADJUDICATION.yaml").write_bytes(
        yaml.safe_dump(_final_adjudication_payload(), sort_keys=False).encode("utf-8")
    )
    package_names = sorted([*text_payloads, *copies, "FINAL_ADJUDICATION.yaml"])
    source_artifacts = {
        path.as_posix(): _sha256(root / path) for path in _release_source_paths()
    }
    manifest = {
        "schema_version": 1,
        "release": RELEASE_NAME,
        "canonical_tag": FINAL_TAG,
        "source_closeout_base": "8b3769724b53fe014bbbca8d501b1fd8cc5ea5ba",
        "decision": "TERMINATE_SUCCESSOR_PROGRAM",
        "review_integrity_classification": "REVIEW_INTEGRITY_INCONCLUSIVE",
        "formal_vlm_inference": 0,
        "privacy": {
            "anonymous_reviewer_codes_only": True,
            "unnecessary_personal_information_included": False,
            "private_mapping_or_hidden_key_included": False,
        },
        "package_files": {name: _sha256(release / name) for name in package_names},
        "source_artifacts": source_artifacts,
        "frozen_review_inputs": FROZEN_REVIEW_HASHES,
    }
    manifest_path = release / "ARTIFACT_MANIFEST.yaml"
    manifest_path.write_bytes(yaml.safe_dump(manifest, sort_keys=False).encode("utf-8"))
    checksum_names = sorted([*package_names, "ARTIFACT_MANIFEST.yaml"])
    checksums = "".join(f"{_sha256(release / name)}  {name}\n" for name in checksum_names)
    checksum_path = release / "checksums.sha256"
    checksum_path.write_bytes(checksums.encode("utf-8"))
    return {
        "status": "NEGATIVE_EVIDENCE_RELEASE_BUILT",
        "release": RELEASE_NAME,
        "canonical_tag": FINAL_TAG,
        "decision": "TERMINATE_SUCCESSOR_PROGRAM",
        "file_count": len(checksum_names) + 1,
        "manifest_sha256": _sha256(manifest_path),
        "checksums_sha256": _sha256(checksum_path),
    }


def _git(root: Path, *args: str, check: bool = True) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=root,
        check=check,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _verify_release_hashes(root: Path) -> tuple[bool, list[str]]:
    release = root / RELEASE_ROOT
    failures: list[str] = []
    checksum_path = release / "checksums.sha256"
    if not checksum_path.is_file():
        return False, ["release checksums.sha256 missing"]
    listed: set[str] = set()
    for line in checksum_path.read_text(encoding="utf-8").splitlines():
        parts = line.split("  ", 1)
        if len(parts) != 2:
            failures.append(f"malformed checksum line: {line}")
            continue
        expected, name = parts
        path = release / name
        try:
            path.resolve().relative_to(release.resolve())
        except ValueError:
            failures.append(f"checksum path escapes release: {name}")
            continue
        listed.add(name)
        if not path.is_file():
            failures.append(f"release file missing: {name}")
        elif _sha256(path) != expected:
            failures.append(f"release checksum mismatch: {name}")
    expected_files = {
        path.name for path in release.iterdir() if path.is_file() and path != checksum_path
    }
    if listed != expected_files:
        failures.append("release checksum inventory mismatch")
    manifest_path = release / "ARTIFACT_MANIFEST.yaml"
    if manifest_path.is_file():
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        for name, expected in manifest.get("package_files", {}).items():
            if not (release / name).is_file() or _sha256(release / name) != expected:
                failures.append(f"release manifest package mismatch: {name}")
        for relative, expected in manifest.get("source_artifacts", {}).items():
            source = root / relative
            if not source.is_file() or _sha256(source) != expected:
                failures.append(f"release manifest source mismatch: {relative}")
    return not failures, failures


def _formal_construct_v2_state(root: Path) -> dict[str, Any]:
    roots = (
        Path("artifacts/construct_v2/predictions"),
        Path("artifacts/construct_v2/model_outputs"),
        Path("artifacts/construct_v2/uptake_model_outputs"),
        Path("artifacts/construct_v2/reasoning_model_outputs"),
    )
    counts = {
        path.as_posix(): (
            sum(item.is_file() for item in (root / path).rglob("*"))
            if (root / path).exists()
            else 0
        )
        for path in roots
    }
    authorization_paths = (
        Path("research/authorization/construct_v2_independent_audit.yaml"),
        Path("research/authorization/construct_v2_execution_readiness.yaml"),
    )
    authorization_files = [
        path.as_posix() for path in authorization_paths if (root / path).is_file()
    ]
    return {
        "formal_prediction_files": sum(counts.values()),
        "uptake_outputs": counts["artifacts/construct_v2/uptake_model_outputs"],
        "reasoning_outputs": counts["artifacts/construct_v2/reasoning_model_outputs"],
        "scientific_metrics": int(
            (root / "artifacts/construct_v2/scientific_metrics.yaml").is_file()
        ),
        "authorization_files": authorization_files,
        "runner_blocked": not authorization_files,
        "counts_by_root": counts,
    }


def verify_final_closeout(
    root: Path = ROOT, *, require_clean_worktree: bool = True
) -> dict[str, Any]:
    """Fail closed on any mutable claim, authorization, output, tag, or hash drift."""

    root = root.resolve()
    failures: list[str] = []
    evidence = yaml.safe_load(
        (root / "reports/final_closeout/final_evidence_map.yaml").read_text(encoding="utf-8")
    )
    hypotheses = yaml.safe_load(
        (root / "research/final_closeout/hypothesis_closeout.yaml").read_text(
            encoding="utf-8"
        )
    )
    claim_statuses = {claim["status"] for claim in evidence["claims"]}
    hypothesis_statuses = {item["status"] for item in hypotheses["hypotheses"]}
    forbidden_states = {"PENDING", "ACTIVE", "AUTHORIZED"}
    if evidence.get("pending_claim_count") != 0 or claim_statuses & forbidden_states:
        failures.append("pending claim detected")
    if (
        hypotheses.get("active_hypothesis_count") != 0
        or hypothesis_statuses & forbidden_states
    ):
        failures.append("active hypothesis detected")

    formal = _formal_construct_v2_state(root)
    if formal["formal_prediction_files"] != 0:
        failures.append("formal construct-v2 prediction or model output detected")
    if formal["uptake_outputs"] != 0:
        failures.append("formal construct-v2 uptake output detected")
    if formal["reasoning_outputs"] != 0:
        failures.append("formal construct-v2 reasoning output detected")
    if formal["scientific_metrics"] != 0:
        failures.append("formal construct-v2 scientific metrics detected")
    if formal["authorization_files"] or not formal["runner_blocked"]:
        failures.append("construct-v2 authorization or open runner detected")

    candidate_paths = (
        Path("research/preregistration/construct_v2"),
        Path("artifacts/construct_v2_preregistration_candidate"),
        Path("reports/construct_v2_preregistration_candidate_readiness.md"),
        Path("reports/construct_v2_preregistration_candidate_decision.yaml"),
        Path("reports/construct_v2_candidate_evidence_map.yaml"),
        Path("reports/construct_v2_open_audit_issues.yaml"),
    )
    candidate_artifacts = [
        path.as_posix() for path in candidate_paths if (root / path).exists()
    ]
    candidate_tags = [
        tag for tag in _git(root, "tag", "--list", "*candidate*").splitlines() if tag
    ]
    if candidate_artifacts or candidate_tags:
        failures.append("construct-v2 preregistration candidate detected")

    tag_targets: dict[str, str | None] = {}
    for tag, expected in HISTORICAL_TAGS.items():
        completed = subprocess.run(
            ["git", "rev-parse", "--verify", f"{tag}^{{commit}}"],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
        )
        observed = completed.stdout.strip() if completed.returncode == 0 else None
        tag_targets[tag] = observed
        if observed != expected:
            failures.append(f"historical tag mismatch: {tag}")

    review_preservation: dict[str, dict[str, Any]] = {}
    for name, expected in FROZEN_REVIEW_HASHES.items():
        path = root / RESULTS / name
        observed = _sha256(path) if path.is_file() else None
        review_preservation[name] = {
            "expected": expected,
            "observed": observed,
            "preserved": observed == expected,
        }
        if observed != expected:
            failures.append(f"frozen review artifact mismatch: {name}")

    release_valid, release_failures = _verify_release_hashes(root)
    failures.extend(release_failures)
    release_adjudication_path = root / RELEASE_ROOT / "FINAL_ADJUDICATION.yaml"
    if not release_adjudication_path.is_file() or yaml.safe_load(
        release_adjudication_path.read_text(encoding="utf-8")
    ) != _final_adjudication_payload():
        failures.append("release final adjudication mismatch")

    clean = not _git(root, "status", "--porcelain=v1")
    if require_clean_worktree and not clean:
        failures.append("working tree is not clean")
    result = {
        "status": "PASS" if not failures else "FAIL",
        "decision": "TERMINATE_SUCCESSOR_PROGRAM",
        "failures": failures,
        "no_pending_claims": evidence.get("pending_claim_count") == 0,
        "no_active_hypotheses": hypotheses.get("active_hypothesis_count") == 0,
        "scientific_execution": formal,
        "candidate_tag_absent": not candidate_tags,
        "candidate_artifacts_absent": not candidate_artifacts,
        "historical_tags": tag_targets,
        "review_returns_and_attestations": review_preservation,
        "release_hashes_match": release_valid,
        "working_tree_clean": clean,
        "head": _git(root, "rev-parse", "HEAD"),
    }
    return result
