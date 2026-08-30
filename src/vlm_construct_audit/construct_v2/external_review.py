"""Fail-closed reblinding and import for the Direction P v2 human review."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import secrets
import stat
import subprocess
import zipfile
from collections import Counter
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from .generator import ROOT
from .review import JUDGMENTS
from .runner_guard import verify_no_construct_v2_inference

PROTOCOL_ID = "direction_p_construct_valid_mini_pilot_v2"
PENDING_STATUS = "PENDING_EXTERNAL_CONSTRUCT_REVIEW"
INFRASTRUCTURE_FAILURE = "REVIEW_REBLINDING_INFRASTRUCTURE_FAILURE"
RETURN_VALIDATION_FAILURE = "EXTERNAL_REVIEW_RETURN_VALIDATION_FAILURE"

PACKET = Path("data/construct_v2_review/review_packet.csv")
HIDDEN_KEY = Path("artifacts/construct_v2_review/hidden_key.yaml")
PACKET_MANIFEST = Path("artifacts/construct_v2_review/packet_manifest.yaml")
AMENDMENT = Path("research/construct_restart/v2_review_blinding_amendment_001.yaml")
POLICY = Path("research/construct_restart/v2_external_review_policy.yaml")
PACKAGE_DIR = Path("external_review_packages")
PRIVATE_STATE_DIR = Path("private_review_state")
PRIVATE_RETURN_DIR = Path("private_review_returns")
RESULTS_DIR = Path("data/construct_v2_review/results")
PUBLIC_COMMITMENT = PACKAGE_DIR / "public_commitment.yaml"

ALLOWED_JUDGMENTS = ("yes", "no", "uncertain")
REQUIRED_CONSTRUCT_FIELDS = JUDGMENTS[:-1]
RESPONSE_FIELDS = ("review_id", *JUDGMENTS, "reviewer_notes")
PACKET_FIELDS = (
    "review_id",
    "image_path",
    "visual_first_hop_claim",
    "correct_evidence_natural_language",
    "correct_evidence_triples",
    "corrupted_evidence_natural_language",
    "corrupted_evidence_triples",
    "question",
    "semantic_candidates",
    "proposed_joint_answer",
    "proposed_corrupted_answer",
)
ATTESTATION_FIELDS = (
    "reviewer_code",
    "is_real_human",
    "independent_of_dataset_authorship",
    "independent_of_generator_implementation",
    "did_not_consult_other_reviewer",
    "did_not_use_ai_or_automated_model",
    "did_not_access_repository",
    "did_not_access_hidden_key",
    "did_not_access_generator_code",
    "review_started_at",
    "review_completed_at",
    "bundle_sha256",
    "signed_statement",
)
ATTESTATION_TRUE_FIELDS = ATTESTATION_FIELDS[1:9]
OPAQUE_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"


class ReviewInfrastructureError(RuntimeError):
    """Raised before a safe reviewer-specific blind can be established."""


class ReviewReturnValidationError(RuntimeError):
    """Raised without deblinding when either reviewer return is invalid."""


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _relative(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def _yaml_bytes(value: Any) -> bytes:
    return yaml.safe_dump(value, sort_keys=False, allow_unicode=True).encode("utf-8")


def _csv_bytes(rows: Iterable[dict[str, Any]], fieldnames: Iterable[str]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(fieldnames), lineterminator="\r\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8-sig")


def _read_csv_bytes(content: bytes) -> tuple[list[str], list[dict[str, str]]]:
    stream = io.StringIO(content.decode("utf-8-sig"), newline="")
    reader = csv.DictReader(stream)
    return list(reader.fieldnames or []), list(reader)


def _write_atomic(path: Path, content: bytes, *, private: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{secrets.token_hex(8)}.tmp")
    try:
        temporary.write_bytes(content)
        if private:
            temporary.chmod(stat.S_IRUSR | stat.S_IWUSR)
        os.replace(temporary, path)
        if private:
            path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    finally:
        if temporary.exists():
            temporary.unlink()


def _git_ignores(root: Path, relative_path: Path) -> bool:
    result = subprocess.run(
        ["git", "check-ignore", "--quiet", "--no-index", relative_path.as_posix()],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def _assert_private_storage(root: Path) -> None:
    paths = [
        PRIVATE_STATE_DIR / "reviewer_1_mapping.json",
        PRIVATE_STATE_DIR / "reviewer_2_mapping.json",
        PRIVATE_RETURN_DIR / "reviewer_1_responses.csv",
        PRIVATE_RETURN_DIR / "reviewer_1_attestation.yaml",
        PRIVATE_RETURN_DIR / "reviewer_2_responses.csv",
        PRIVATE_RETURN_DIR / "reviewer_2_attestation.yaml",
    ]
    failures = [path.as_posix() for path in paths if not _git_ignores(root, path)]
    if failures:
        raise ReviewInfrastructureError(f"{INFRASTRUCTURE_FAILURE}: not gitignored: {failures}")


def _assert_frozen_source(root: Path) -> dict[str, Any]:
    manifest = yaml.safe_load((root / PACKET_MANIFEST).read_text(encoding="utf-8"))
    packet_hash = _sha256(root / PACKET)
    hidden_hash = _sha256(root / HIDDEN_KEY)
    failures: list[str] = []
    if manifest.get("review_status") != PENDING_STATUS:
        failures.append("review status is not pending")
    if manifest.get("reviewer_count_completed") != 0:
        failures.append("reviewer_count_completed is not zero")
    if manifest.get("row_count") != 80:
        failures.append("packet row count is not 80")
    frozen_files = manifest.get("files", {})
    if frozen_files.get(PACKET.as_posix()) != packet_hash:
        failures.append("original packet hash changed")
    if frozen_files.get(HIDDEN_KEY.as_posix()) != hidden_hash:
        failures.append("hidden key hash changed")
    no_inference = verify_no_construct_v2_inference()
    if no_inference.get("status") != "PASS":
        failures.append("formal inference or open runner detected")
    if failures:
        raise ReviewInfrastructureError(f"{INFRASTRUCTURE_FAILURE}: {failures}")
    return {
        "manifest_hash": _sha256(root / PACKET_MANIFEST),
        "packet_hash": packet_hash,
        "hidden_key_hash": hidden_hash,
        "no_inference": no_inference,
    }


def _opaque_ids(slot: int, count: int) -> list[str]:
    prefix = f"R{slot}-"
    values: set[str] = set()
    while len(values) < count:
        token = "".join(secrets.choice(OPAQUE_ALPHABET) for _ in range(6))
        values.add(prefix + token)
    result = list(values)
    secrets.SystemRandom().shuffle(result)
    return result


def _attestation_template() -> bytes:
    return _yaml_bytes(
        {
            "reviewer_code": "",
            "is_real_human": None,
            "independent_of_dataset_authorship": None,
            "independent_of_generator_implementation": None,
            "did_not_consult_other_reviewer": None,
            "did_not_use_ai_or_automated_model": None,
            "did_not_access_repository": None,
            "did_not_access_hidden_key": None,
            "did_not_access_generator_code": None,
            "review_started_at": "",
            "review_completed_at": "",
            "bundle_sha256": "",
            "signed_statement": "",
        }
    )


def _review_instructions(slot: int) -> bytes:
    return f"""# Independent Direction P v2 construct review — reviewer {slot}

Use only this offline ZIP. Do not access the repository, source code, generator,
hidden key, audit reports, another reviewer's files, ChatGPT, an LLM, a vision
model, or any automated answer tool. Do not discuss the review with the other
reviewer. The author and build agent cannot answer review items for you.

Review every row in `review_packet.csv`, opening its bundle-local `image_path`.
Enter every answer in `response_template.csv`; do not edit `review_packet.csv`.
Each judgment must be exactly `yes`, `no`, or `uncertain`. `uncertain` is a third
nominal category: it is not converted to yes and is retained in agreement and
Cohen's kappa. `reviewer_notes` is required on every row; enter `none` when you
have no additional note. Judge what is displayed and stated, not generator intent.

Definitions:

- `visual_first_hop_correct`: the claim about A relative to B matches the image.
- `bridge_entity_uniquely_identifiable`: text identifies exactly one image B.
- `text_second_hop_correct`: one definite B-to-C cardinal relation is stated.
- `text_second_hop_not_visually_represented`: C and the second hop are not spatially shown.
- `conditions_differ_in_exactly_one_target_relation`: only target relation R2 changes.
- `no_direct_image_text_conflict`: neither condition contradicts a visible fact.
- `joint_answer_unique`: image first hop plus correct evidence yield one candidate.
- the two unimodal-insufficiency fields: that modality alone cannot select one candidate.
- `nl_triples_fact_equivalent`: both serializations state exactly the same fact.
- `critical_error`: yes when any flaw invalidates bridge composition or its paired contrast.

After all rows are complete, fill `reviewer_attestation.yaml`. Use a reviewer code,
not unnecessary personal identity information. Copy the SHA-256 of the received
ZIP from the accompanying `reviewer_{slot}_bundle_sha256.txt`, record timezone-aware
start and completion timestamps, and provide a signed statement under your code.
Return only the completed response CSV and attestation YAML to the designated
private return destination.
""".encode()


def _build_zip(payload: dict[str, bytes]) -> bytes:
    checksums = "".join(
        f"{_sha256_bytes(content)}  {name}\n" for name, content in sorted(payload.items())
    ).encode("utf-8")
    complete = {**payload, "SHA256SUMS.txt": checksums}
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as bundle:
        for name, content in sorted(complete.items()):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            bundle.writestr(info, content)
    return stream.getvalue()


def _mapping_bytes(slot: int, rows: list[dict[str, str]]) -> bytes:
    mapping = {
        "schema_version": 1,
        "protocol_id": PROTOCOL_ID,
        "reviewer_slot": f"reviewer_{slot}",
        "mapping_release_condition": "after_both_complete_returns_validate",
        "rows": rows,
    }
    return (json.dumps(mapping, indent=2, sort_keys=True) + "\n").encode("utf-8")


def build_external_review_packages(root: Path = ROOT) -> dict[str, Any]:
    """Create two independently permuted offline bundles and private mappings once."""

    root = root.resolve()
    _assert_private_storage(root)
    frozen = _assert_frozen_source(root)
    fields, source_rows = _read_csv_bytes((root / PACKET).read_bytes())
    if tuple(fields) != PACKET_FIELDS or len(source_rows) != 80:
        raise ReviewInfrastructureError(f"{INFRASTRUCTURE_FAILURE}: invalid frozen packet schema")
    source_ids = [row["review_id"] for row in source_rows]
    if len(set(source_ids)) != 80:
        raise ReviewInfrastructureError(f"{INFRASTRUCTURE_FAILURE}: duplicate source review IDs")

    outputs = [
        root / PUBLIC_COMMITMENT,
        *(root / PACKAGE_DIR / f"reviewer_{slot}_bundle.zip" for slot in (1, 2)),
        *(root / PACKAGE_DIR / f"reviewer_{slot}_bundle_sha256.txt" for slot in (1, 2)),
        *(root / PRIVATE_STATE_DIR / f"reviewer_{slot}_mapping.json" for slot in (1, 2)),
    ]
    existing = [_relative(root, path) for path in outputs if path.exists()]
    if existing:
        raise ReviewInfrastructureError(f"{INFRASTRUCTURE_FAILURE}: refusing overwrite: {existing}")

    permutations: dict[int, list[dict[str, str]]] = {}
    mappings: dict[int, bytes] = {}
    bundles: dict[int, bytes] = {}
    for slot in (1, 2):
        ordered = list(source_rows)
        secrets.SystemRandom().shuffle(ordered)
        opaque = _opaque_ids(slot, len(ordered))
        packet_rows: list[dict[str, str]] = []
        response_rows: list[dict[str, str]] = []
        mapping_rows: list[dict[str, str]] = []
        images: dict[str, bytes] = {}
        for position, (source, review_id) in enumerate(zip(ordered, opaque, strict=True), 1):
            packet = dict(source)
            packet["review_id"] = review_id
            packet["image_path"] = f"images/{review_id}.png"
            packet_rows.append(packet)
            response_rows.append({field: review_id if field == "review_id" else "" for field in RESPONSE_FIELDS})
            mapping_rows.append(
                {
                    "opaque_review_id": review_id,
                    "source_review_id": source["review_id"],
                    "bundle_row_position": str(position),
                }
            )
            source_image = root / source["image_path"]
            if not source_image.is_file():
                raise ReviewInfrastructureError(
                    f"{INFRASTRUCTURE_FAILURE}: missing source image {source['image_path']}"
                )
            images[packet["image_path"]] = source_image.read_bytes()
        permutations[slot] = mapping_rows
        mappings[slot] = _mapping_bytes(slot, mapping_rows)
        payload = {
            "review_packet.csv": _csv_bytes(packet_rows, PACKET_FIELDS),
            "response_template.csv": _csv_bytes(response_rows, RESPONSE_FIELDS),
            "review_instructions.md": _review_instructions(slot),
            "reviewer_attestation.yaml": _attestation_template(),
            **images,
        }
        bundles[slot] = _build_zip(payload)

    order_1 = [row["source_review_id"] for row in permutations[1]]
    order_2 = [row["source_review_id"] for row in permutations[2]]
    if order_1 == order_2:
        raise ReviewInfrastructureError(f"{INFRASTRUCTURE_FAILURE}: reviewer permutations identical")

    for slot in (1, 2):
        mapping_path = root / PRIVATE_STATE_DIR / f"reviewer_{slot}_mapping.json"
        _write_atomic(mapping_path, mappings[slot], private=True)
        bundle_path = root / PACKAGE_DIR / f"reviewer_{slot}_bundle.zip"
        _write_atomic(bundle_path, bundles[slot])
        bundle_hash = _sha256_bytes(bundles[slot])
        hash_text = f"{bundle_hash}  reviewer_{slot}_bundle.zip\n".encode("ascii")
        _write_atomic(root / PACKAGE_DIR / f"reviewer_{slot}_bundle_sha256.txt", hash_text)

    commitment = {
        "schema_version": 1,
        "protocol_id": PROTOCOL_ID,
        "status": PENDING_STATUS,
        "source_freeze": {
            "branch": "codex/construct-valid-direction-p-v2",
            "commit": "1552a3c77e0bdd6bf0fdb0bf49447c19df4af6f2",
            "annotated_tag": "construct-v2-automated-preaudit-freeze",
        },
        "packet_row_count": 80,
        "original_packet": {"path": PACKET.as_posix(), "sha256": frozen["packet_hash"]},
        "frozen_hidden_key_sha256": frozen["hidden_key_hash"],
        "frozen_packet_manifest_sha256": frozen["manifest_hash"],
        "amendment": {"path": AMENDMENT.as_posix(), "sha256": _sha256(root / AMENDMENT)},
        "review_policy": {"path": POLICY.as_posix(), "sha256": _sha256(root / POLICY)},
        "reviewer_count_required": 2,
        "bundles": {
            f"reviewer_{slot}": {
                "path": (PACKAGE_DIR / f"reviewer_{slot}_bundle.zip").as_posix(),
                "sha256": _sha256(root / PACKAGE_DIR / f"reviewer_{slot}_bundle.zip"),
                "sha256_file": (PACKAGE_DIR / f"reviewer_{slot}_bundle_sha256.txt").as_posix(),
                "mapping_sha256_commitment": _sha256(
                    root / PRIVATE_STATE_DIR / f"reviewer_{slot}_mapping.json"
                ),
            }
            for slot in (1, 2)
        },
        "private_mapping_controls": {
            "gitignored": True,
            "included_in_bundle": False,
            "publish_before_both_returns_validate": False,
        },
        "original_packet_unchanged": True,
        "formal_vlm_inference_count": frozen["no_inference"]["formal_prediction_files"],
        "uptake_output_count": frozen["no_inference"]["uptake_model_outputs"],
        "reasoning_output_count": frozen["no_inference"]["reasoning_model_outputs"],
        "scientific_metrics_count": frozen["no_inference"]["scientific_metrics"],
        "runner_blocked": frozen["no_inference"]["runner_blocked"],
        "model_or_agent_review_used": False,
    }
    _write_atomic(root / PUBLIC_COMMITMENT, _yaml_bytes(commitment))
    return verify_external_review_packages(root)


def _bundle_members(bundle_bytes: bytes) -> tuple[list[str], dict[str, bytes]]:
    with zipfile.ZipFile(io.BytesIO(bundle_bytes)) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ReviewInfrastructureError(f"{INFRASTRUCTURE_FAILURE}: duplicate ZIP members")
        return names, {name: archive.read(name) for name in names}


def _verify_internal_sums(files: dict[str, bytes]) -> bool:
    lines = files["SHA256SUMS.txt"].decode("utf-8").splitlines()
    expected = {}
    for line in lines:
        digest, name = line.split("  ", 1)
        expected[name] = digest
    payload_names = set(files) - {"SHA256SUMS.txt"}
    return set(expected) == payload_names and all(
        _sha256_bytes(files[name]) == digest for name, digest in expected.items()
    )


def verify_external_review_packages(root: Path = ROOT) -> dict[str, Any]:
    """Audit public bundles and commitments without loading either private mapping."""

    root = root.resolve()
    _assert_private_storage(root)
    frozen = _assert_frozen_source(root)
    commitment = yaml.safe_load((root / PUBLIC_COMMITMENT).read_text(encoding="utf-8"))
    failures: list[str] = []
    if commitment.get("original_packet", {}).get("sha256") != frozen["packet_hash"]:
        failures.append("packet commitment mismatch")
    if commitment.get("frozen_hidden_key_sha256") != frozen["hidden_key_hash"]:
        failures.append("hidden key commitment mismatch")
    orders: list[list[str]] = []
    ids_by_slot: dict[str, set[str]] = {}
    for slot in (1, 2):
        label = f"reviewer_{slot}"
        spec = commitment.get("bundles", {}).get(label, {})
        bundle_path = root / PACKAGE_DIR / f"{label}_bundle.zip"
        if not bundle_path.is_file() or _sha256(bundle_path) != spec.get("sha256"):
            failures.append(f"{label} bundle hash mismatch")
            continue
        names, files = _bundle_members(bundle_path.read_bytes())
        base = {
            "review_packet.csv",
            "response_template.csv",
            "review_instructions.md",
            "reviewer_attestation.yaml",
            "SHA256SUMS.txt",
        }
        images = {name for name in names if name.startswith("images/") and name.endswith(".png")}
        if set(names) != base | images or len(images) != 80:
            failures.append(f"{label} member whitelist or image count failed")
        if not _verify_internal_sums(files):
            failures.append(f"{label} internal SHA256SUMS failed")
        packet_fields, packet_rows = _read_csv_bytes(files["review_packet.csv"])
        response_fields, response_rows = _read_csv_bytes(files["response_template.csv"])
        ids = [row["review_id"] for row in packet_rows]
        ids_by_slot[label] = set(ids)
        orders.append(ids)
        if tuple(packet_fields) != PACKET_FIELDS or len(packet_rows) != 80 or len(set(ids)) != 80:
            failures.append(f"{label} packet schema, count, or ID uniqueness failed")
        if tuple(response_fields) != RESPONSE_FIELDS or [row["review_id"] for row in response_rows] != ids:
            failures.append(f"{label} response template does not match packet")
        prefix = f"R{slot}-"
        if any(len(value) != 9 or not value.startswith(prefix) for value in ids):
            failures.append(f"{label} opaque ID format failed")
        expected_paths = {f"images/{value}.png" for value in ids}
        if {row["image_path"] for row in packet_rows} != expected_paths or images != expected_paths:
            failures.append(f"{label} image path uniformity failed")
        serialized = "\n".join(names) + files["review_packet.csv"].decode("utf-8-sig")
        forbidden = (
            "CVR-",
            "source_scene_uuid",
            "internal_scene_id",
            "hidden_key",
            "packet_manifest",
            "generator seed",
            "genuine_count",
            "decoy_count",
            ".py",
        )
        if any(value in serialized for value in forbidden):
            failures.append(f"{label} contains a forbidden identifier or path")
        mapping_path = root / PRIVATE_STATE_DIR / f"{label}_mapping.json"
        if mapping_path.is_file() and _sha256(mapping_path) != spec.get(
            "mapping_sha256_commitment"
        ):
            failures.append(f"{label} private mapping commitment mismatch")
    if ids_by_slot.get("reviewer_1", set()) & ids_by_slot.get("reviewer_2", set()):
        failures.append("reviewer opaque ID sets overlap")
    if len(orders) == 2 and orders[0] == orders[1]:
        failures.append("reviewer row permutations are identical")
    if failures:
        raise ReviewInfrastructureError(f"{INFRASTRUCTURE_FAILURE}: {failures}")
    return pending_external_review_status(root)


def pending_external_review_status(root: Path = ROOT) -> dict[str, Any]:
    root = root.resolve()
    commitment = yaml.safe_load((root / PUBLIC_COMMITMENT).read_text(encoding="utf-8"))
    no_inference = verify_no_construct_v2_inference()
    return {
        "status": PENDING_STATUS,
        "reviewer_bundle_paths": {
            slot: str((root / spec["path"]).resolve())
            for slot, spec in commitment["bundles"].items()
        },
        "bundle_sha256": {
            slot: spec["sha256"] for slot, spec in commitment["bundles"].items()
        },
        "response_destination_paths": {
            f"reviewer_{slot}": str(
                (root / PRIVATE_RETURN_DIR / f"reviewer_{slot}_responses.csv").resolve()
            )
            for slot in (1, 2)
        },
        "attestation_destination_paths": {
            f"reviewer_{slot}": str(
                (root / PRIVATE_RETURN_DIR / f"reviewer_{slot}_attestation.yaml").resolve()
            )
            for slot in (1, 2)
        },
        "original_packet_unchanged": _sha256(root / PACKET)
        == commitment["original_packet"]["sha256"],
        "formal_vlm_inference_count": no_inference["formal_prediction_files"],
        "uptake_output_count": no_inference["uptake_model_outputs"],
        "reasoning_output_count": no_inference["reasoning_model_outputs"],
        "scientific_metrics_count": no_inference["scientific_metrics"],
        "runner_blocked": no_inference["runner_blocked"],
        "mapping_revealed": False,
        "candidate_tag_created": False,
    }


def _parse_time(value: Any, field: str, failures: list[str]) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        failures.append(f"{field} missing")
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        failures.append(f"{field} is not ISO-8601")
        return None
    if parsed.utcoffset() is None:
        failures.append(f"{field} lacks timezone")
        return None
    return parsed


def _validate_attestation(content: bytes, expected_bundle_hash: str) -> tuple[dict[str, Any], list[str]]:
    value = yaml.safe_load(content.decode("utf-8"))
    failures: list[str] = []
    if not isinstance(value, dict):
        return {}, ["attestation is not a mapping"]
    if set(value) != set(ATTESTATION_FIELDS):
        failures.append("attestation fields do not exactly match frozen schema")
    code = value.get("reviewer_code")
    if not isinstance(code, str) or not code.strip() or "\n" in code or len(code) > 64:
        failures.append("reviewer_code invalid")
    for field in ATTESTATION_TRUE_FIELDS:
        if value.get(field) is not True:
            failures.append(f"{field} is not true")
    started = _parse_time(value.get("review_started_at"), "review_started_at", failures)
    completed = _parse_time(value.get("review_completed_at"), "review_completed_at", failures)
    if started and completed and completed < started:
        failures.append("review_completed_at precedes review_started_at")
    if value.get("bundle_sha256") != expected_bundle_hash:
        failures.append("bundle_sha256 mismatch")
    statement = value.get("signed_statement")
    if not isinstance(statement, str) or not statement.strip():
        failures.append("signed_statement missing")
    return value, failures


def _validate_responses(content: bytes, expected_ids: set[str]) -> tuple[list[dict[str, str]], list[str]]:
    fields, rows = _read_csv_bytes(content)
    failures: list[str] = []
    if tuple(fields) != RESPONSE_FIELDS:
        failures.append("response fields do not exactly match frozen schema")
    ids = [row.get("review_id", "") for row in rows]
    counts = Counter(ids)
    if len(rows) != 80:
        failures.append(f"response row count is {len(rows)}, expected 80")
    if any(count > 1 for count in counts.values()):
        failures.append("duplicate opaque review ID")
    if set(ids) - expected_ids:
        failures.append("unknown opaque review ID")
    if expected_ids - set(ids):
        failures.append("missing opaque review ID")
    for index, row in enumerate(rows, 2):
        if None in row:
            failures.append(f"row {index} has surplus CSV cells")
            continue
        for field in JUDGMENTS:
            if row.get(field) not in ALLOWED_JUDGMENTS:
                failures.append(f"row {index} field {field} is not yes/no/uncertain")
        if not row.get("reviewer_notes", "").strip():
            failures.append(f"row {index} reviewer_notes is empty")
    return rows, failures


def _cohen_kappa(first: list[str], second: list[str]) -> float | None:
    if len(first) != len(second) or not first:
        raise ValueError("paired nonempty ratings required")
    observed = sum(a == b for a, b in zip(first, second, strict=True)) / len(first)
    expected = sum(
        (first.count(category) / len(first)) * (second.count(category) / len(second))
        for category in ALLOWED_JUDGMENTS
    )
    if expected == 1.0:
        return None
    return (observed - expected) / (1.0 - expected)


def _agreement(first: list[str], second: list[str]) -> float:
    return sum(a == b for a, b in zip(first, second, strict=True)) / len(first)


def _bundle_packet_ids(bundle_path: Path) -> set[str]:
    _, files = _bundle_members(bundle_path.read_bytes())
    _, rows = _read_csv_bytes(files["review_packet.csv"])
    return {row["review_id"] for row in rows}


def import_external_review_returns(root: Path = ROOT) -> dict[str, Any]:
    """Validate both complete returns before deblinding, then compute the raw gate."""

    root = root.resolve()
    verify_external_review_packages(root)
    return_paths = {
        slot: {
            "responses": root / PRIVATE_RETURN_DIR / f"reviewer_{slot}_responses.csv",
            "attestation": root / PRIVATE_RETURN_DIR / f"reviewer_{slot}_attestation.yaml",
        }
        for slot in (1, 2)
    }
    missing = [
        _relative(root, path)
        for paths in return_paths.values()
        for path in paths.values()
        if not path.is_file()
    ]
    if missing:
        pending = pending_external_review_status(root)
        pending["missing_return_files"] = missing
        return pending

    commitment = yaml.safe_load((root / PUBLIC_COMMITMENT).read_text(encoding="utf-8"))
    responses: dict[int, list[dict[str, str]]] = {}
    attestations: dict[int, dict[str, Any]] = {}
    failures: list[str] = []
    for slot in (1, 2):
        spec = commitment["bundles"][f"reviewer_{slot}"]
        ids = _bundle_packet_ids(root / spec["path"])
        response_content = return_paths[slot]["responses"].read_bytes()
        attestation_content = return_paths[slot]["attestation"].read_bytes()
        responses[slot], response_failures = _validate_responses(response_content, ids)
        attestations[slot], attestation_failures = _validate_attestation(
            attestation_content, spec["sha256"]
        )
        failures.extend(f"reviewer_{slot}: {failure}" for failure in response_failures)
        failures.extend(f"reviewer_{slot}: {failure}" for failure in attestation_failures)
    codes = [attestations[slot].get("reviewer_code") for slot in (1, 2)]
    if len(set(codes)) != 2:
        failures.append("reviewer codes are not distinct")
    if _sha256(root / PACKET) != commitment["original_packet"]["sha256"]:
        failures.append("original packet hash changed")
    if _sha256(root / HIDDEN_KEY) != commitment["frozen_hidden_key_sha256"]:
        failures.append("frozen hidden key hash changed")
    for slot in (1, 2):
        mapping_path = root / PRIVATE_STATE_DIR / f"reviewer_{slot}_mapping.json"
        if not mapping_path.is_file():
            failures.append(f"reviewer_{slot}: private mapping missing")
        elif _sha256(mapping_path) != commitment["bundles"][f"reviewer_{slot}"][
            "mapping_sha256_commitment"
        ]:
            failures.append(f"reviewer_{slot}: mapping commitment changed")
    if failures:
        raise ReviewReturnValidationError(f"{RETURN_VALIDATION_FAILURE}: {failures}")

    # Deblinding begins only after both response/attestation sets and all byte hashes pass.
    mappings = {
        slot: json.loads(
            (root / PRIVATE_STATE_DIR / f"reviewer_{slot}_mapping.json").read_text(
                encoding="utf-8"
            )
        )
        for slot in (1, 2)
    }
    hidden = yaml.safe_load((root / HIDDEN_KEY).read_text(encoding="utf-8"))
    hidden_by_source = {row["review_id"]: row for row in hidden["rows"]}
    response_by_id = {
        slot: {row["review_id"]: row for row in responses[slot]} for slot in (1, 2)
    }
    source_to_opaque = {
        slot: {row["source_review_id"]: row["opaque_review_id"] for row in mappings[slot]["rows"]}
        for slot in (1, 2)
    }
    if any(set(source_to_opaque[slot]) != set(hidden_by_source) for slot in (1, 2)):
        raise ReviewReturnValidationError(
            f"{RETURN_VALIDATION_FAILURE}: revealed mapping source IDs do not match hidden key"
        )

    aligned: list[dict[str, Any]] = []
    disagreements: list[dict[str, Any]] = []
    first_all: list[str] = []
    second_all: list[str] = []
    first_by_field = {field: [] for field in JUDGMENTS}
    second_by_field = {field: [] for field in JUDGMENTS}
    for source_id in sorted(hidden_by_source):
        key = hidden_by_source[source_id]
        opaque_1 = source_to_opaque[1][source_id]
        opaque_2 = source_to_opaque[2][source_id]
        row_1 = response_by_id[1][opaque_1]
        row_2 = response_by_id[2][opaque_2]
        record: dict[str, Any] = {
            "source_review_id": source_id,
            "reviewer_1_review_id": opaque_1,
            "reviewer_2_review_id": opaque_2,
            "status": key["status"],
            "decoy_type": key.get("decoy_type") or "",
        }
        for field in JUDGMENTS:
            value_1, value_2 = row_1[field], row_2[field]
            record[f"{field}_reviewer_1"] = value_1
            record[f"{field}_reviewer_2"] = value_2
            record[f"{field}_agreement"] = value_1 == value_2
            first_all.append(value_1)
            second_all.append(value_2)
            first_by_field[field].append(value_1)
            second_by_field[field].append(value_2)
            if value_1 != value_2:
                disagreements.append(
                    {
                        "source_review_id": source_id,
                        "reviewer_1_review_id": opaque_1,
                        "reviewer_2_review_id": opaque_2,
                        "status": key["status"],
                        "decoy_type": key.get("decoy_type") or "",
                        "field": field,
                        "reviewer_1_value": value_1,
                        "reviewer_2_value": value_2,
                        "reviewer_1_notes": row_1["reviewer_notes"],
                        "reviewer_2_notes": row_2["reviewer_notes"],
                    }
                )
        record["reviewer_1_notes"] = row_1["reviewer_notes"]
        record["reviewer_2_notes"] = row_2["reviewer_notes"]
        aligned.append(record)

    overall_agreement = _agreement(first_all, second_all)
    overall_kappa = _cohen_kappa(first_all, second_all)
    per_field_agreement = {
        field: _agreement(first_by_field[field], second_by_field[field]) for field in JUDGMENTS
    }
    per_field_kappa = {
        field: _cohen_kappa(first_by_field[field], second_by_field[field]) for field in JUDGMENTS
    }
    uncertain_by_reviewer = {
        f"reviewer_{slot}": sum(
            row[field] == "uncertain" for row in responses[slot] for field in JUDGMENTS
        )
        for slot in (1, 2)
    }
    uncertain_by_field = {
        field: sum(value == "uncertain" for value in first_by_field[field])
        + sum(value == "uncertain" for value in second_by_field[field])
        for field in JUDGMENTS
    }
    genuine_rows = [row for row in aligned if row["status"] == "genuine"]
    genuine_no = sum(
        row[f"{field}_reviewer_{slot}"] == "no"
        for row in genuine_rows
        for slot in (1, 2)
        for field in REQUIRED_CONSTRUCT_FIELDS
    )
    genuine_uncertain = sum(
        row[f"{field}_reviewer_{slot}"] == "uncertain"
        for row in genuine_rows
        for slot in (1, 2)
        for field in REQUIRED_CONSTRUCT_FIELDS
    )
    genuine_critical_yes = sum(
        row[f"critical_error_reviewer_{slot}"] == "yes"
        for row in genuine_rows
        for slot in (1, 2)
    )
    genuine_critical_uncertain = sum(
        row[f"critical_error_reviewer_{slot}"] == "uncertain"
        for row in genuine_rows
        for slot in (1, 2)
    )
    decoy_rows = [row for row in aligned if row["status"] == "decoy"]
    decoy_detection = {}
    for slot in (1, 2):
        detected = sum(row[f"critical_error_reviewer_{slot}"] == "yes" for row in decoy_rows)
        decoy_detection[f"reviewer_{slot}"] = {
            "reviewer_code": attestations[slot]["reviewer_code"],
            "detected": detected,
            "total": len(decoy_rows),
            "rate": detected / len(decoy_rows),
        }
    minimum_detection = min(value["rate"] for value in decoy_detection.values())
    gates = {
        "reviewer_count_2": True,
        "response_completeness_1_00": True,
        "attestation_validation_pass": True,
        "overall_agreement_ge_0_95": overall_agreement >= 0.95,
        "overall_nominal_cohen_kappa_ge_0_80": overall_kappa is not None
        and overall_kappa >= 0.80,
        "genuine_required_field_no_count_0": genuine_no == 0,
        "genuine_required_field_uncertain_count_0": genuine_uncertain == 0,
        "genuine_critical_error_yes_or_uncertain_count_0": (
            genuine_critical_yes + genuine_critical_uncertain == 0
        ),
        "minimum_reviewer_decoy_detection_ge_0_90": minimum_detection >= 0.90,
        "deleted_disagreements_0": True,
        "model_or_agent_review_used_false": True,
    }
    status = "HUMAN_CONSTRUCT_REVIEW_PASS" if all(gates.values()) else "HUMAN_CONSTRUCT_REVIEW_FAIL"
    affected_required = sum(
        any(
            row[f"{field}_reviewer_{slot}"] != "yes"
            for slot in (1, 2)
            for field in REQUIRED_CONSTRUCT_FIELDS
        )
        for row in genuine_rows
    )
    affected_critical = sum(
        any(row[f"critical_error_reviewer_{slot}"] != "no" for slot in (1, 2))
        for row in genuine_rows
    )
    metrics = {
        "status": status,
        "reviewer_count": 2,
        "bundle_hashes": {
            slot: spec["sha256"] for slot, spec in commitment["bundles"].items()
        },
        "mapping_commitment_verified": True,
        "packet_hash_verified": True,
        "overall_agreement": overall_agreement,
        "overall_cohen_kappa": overall_kappa,
        "per_field_agreement": per_field_agreement,
        "per_field_kappa": per_field_kappa,
        "uncertain_count": {
            **uncertain_by_reviewer,
            "total": sum(uncertain_by_reviewer.values()),
            "per_field": uncertain_by_field,
        },
        "genuine_required_field_failures": {
            "no_count": genuine_no,
            "uncertain_count": genuine_uncertain,
            "total": genuine_no + genuine_uncertain,
            "affected_item_count": affected_required,
        },
        "genuine_critical_errors": {
            "yes_count": genuine_critical_yes,
            "uncertain_count": genuine_critical_uncertain,
            "total": genuine_critical_yes + genuine_critical_uncertain,
            "affected_item_count": affected_critical,
        },
        "reviewer_decoy_detection": decoy_detection,
        "minimum_decoy_detection": minimum_detection,
        "disagreement_count": len(disagreements),
        "deleted_disagreements": 0,
        "agent_or_model_review_used": False,
        "reviewer_independence_attested": True,
        "gates": gates,
    }
    field_metrics = {
        "schema_version": 1,
        "nominal_categories": list(ALLOWED_JUDGMENTS),
        "uncertain_retained": True,
        "fields": {
            field: {
                "n": len(first_by_field[field]),
                "agreement": per_field_agreement[field],
                "cohen_kappa": per_field_kappa[field],
                "uncertain_count": uncertain_by_field[field],
            }
            for field in JUDGMENTS
        },
    }

    results = root / RESULTS_DIR
    if results.exists() and any(results.iterdir()):
        raise ReviewReturnValidationError(
            f"{RETURN_VALIDATION_FAILURE}: refusing to overwrite existing results"
        )
    results.mkdir(parents=True, exist_ok=True)
    for slot in (1, 2):
        _write_atomic(
            results / f"reviewer_{slot}_original.csv", return_paths[slot]["responses"].read_bytes()
        )
        _write_atomic(
            results / f"reviewer_{slot}_attestation.yaml",
            return_paths[slot]["attestation"].read_bytes(),
        )
        _write_atomic(
            results / f"revealed_mapping_reviewer_{slot}.json",
            (root / PRIVATE_STATE_DIR / f"reviewer_{slot}_mapping.json").read_bytes(),
        )
    aligned_fields = list(aligned[0])
    disagreement_fields = [
        "source_review_id",
        "reviewer_1_review_id",
        "reviewer_2_review_id",
        "status",
        "decoy_type",
        "field",
        "reviewer_1_value",
        "reviewer_2_value",
        "reviewer_1_notes",
        "reviewer_2_notes",
    ]
    _write_atomic(results / "aligned_reviews.csv", _csv_bytes(aligned, aligned_fields))
    _write_atomic(
        results / "disagreements.csv", _csv_bytes(disagreements, disagreement_fields)
    )
    _write_atomic(results / "field_metrics.yaml", _yaml_bytes(field_metrics))
    _write_atomic(results / "human_construct_review_metrics.yaml", _yaml_bytes(metrics))

    if status == "HUMAN_CONSTRUCT_REVIEW_PASS":
        no_inference = verify_no_construct_v2_inference()
        candidate_files = sorted(path for path in results.iterdir() if path.is_file())
        candidate = {
            "schema_version": 1,
            "protocol_id": PROTOCOL_ID,
            "status": "PENDING_INDEPENDENT_PREREGISTRATION_AUDIT",
            "human_construct_review_gate": status,
            "human_metrics_sha256": _sha256(results / "human_construct_review_metrics.yaml"),
            "files": {_relative(root, path): _sha256(path) for path in candidate_files},
            "formal_vlm_inference_count": no_inference["formal_prediction_files"],
            "runner_blocked": no_inference["runner_blocked"],
            "execution_authorization_created": False,
            "candidate_tag_created": False,
        }
        _write_atomic(
            root / "artifacts/construct_v2_preregistration_candidate/manifest.yaml",
            _yaml_bytes(candidate),
        )
    return metrics
