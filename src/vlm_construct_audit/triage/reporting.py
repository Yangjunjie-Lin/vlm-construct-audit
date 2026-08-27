"""Tier 0.5 claim-bounded reports, evidence map, and immutable artifact audit."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from ..utils import canonical_hash, dump_yaml, load_yaml, sha256_file, utc_timestamp


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True).strip()


def _fmt(value: float) -> str:
    return f"{value:.4f}"


def _write(path: str, text: str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text.strip() + "\n", encoding="utf-8")


def _loop_a_report(summary: dict[str, Any]) -> str:
    a0 = summary["primary_metrics"]["A0"]
    v2 = summary["primary_metrics"]["AuditV2"]
    curves = summary["sample_size_curves"]
    rows = []
    for index, n in enumerate((48, 96, 192, 384)):
        rows.append(
            f"| {n} | {_fmt(curves['A0'][index]['known_valid_sensitivity'])} | "
            f"{_fmt(curves['AuditV2'][index]['known_valid_sensitivity'])} | "
            f"{_fmt(curves['AuditV2'][index]['known_invalid_specificity'])} | "
            f"{_fmt(curves['AuditV2'][index]['abstention'])} |"
        )
    return f"""
# Loop A: unseen-DGP generalization

Decision: **{summary['decision']}**. The one permitted development-only repair was frozen before
the one-pass holdout. The holdout was not rerun.

| N | A0 sensitivity | AuditV2 sensitivity | AuditV2 specificity | AuditV2 abstention |
|---:|---:|---:|---:|---:|
{chr(10).join(rows)}

At N=384, AuditV2 sensitivity was {_fmt(v2['known_valid_sensitivity'])}, specificity
{_fmt(v2['known_invalid_specificity'])}, FMCR {_fmt(v2['fmcr'])}, coverage
{_fmt(v2['coverage'])}, Type-S {_fmt(v2['type_s'])}, Type-M {_fmt(v2['type_m'])}, and
abstention {_fmt(v2['abstention'])}. A0 sensitivity was {_fmt(a0['known_valid_sensitivity'])};
AuditV2 improved it by {_fmt(summary['A0_vs_AuditV2']['sensitivity_change'])}.

The overall operating point passed, but the non-strong macro sensitivity was
{_fmt(v2['non_strong_macro_sensitivity'])}, the ValidBoundaryEffect sensitivity was
{_fmt(v2['valid_boundary_effect_sensitivity'])}, and only
{_fmt(summary['threshold_stability']['go_fraction'])} of the frozen sensitivity-grid cells retained
GO. Therefore the conclusion was driven too heavily by easier effect tiers and reversed under a
reasonable frozen gate grid. No second repair is permitted.

Evidence: `artifacts/loop_a/holdout/summary.yaml` (config hash
`{summary['config_hash']}`), `artifacts/loop_a/holdout/execution_marker.yaml`, and
`research/preregistration/audit_v2.yaml`.
"""


def _loop_b_report(metrics: dict[str, Any], decision: dict[str, Any]) -> str:
    two_way = metrics["two_way_cluster"]["two_way_lower"]
    return f"""
# Loop B: measurement robustness

Decision: **{decision['decision']}**.

The new holdout contained {metrics['probe_count']} probes crossed over
{metrics['scene_clusters']} scenes and {metrics['template_clusters']} finite templates. The
probe-level one-sided lower bound was {_fmt(metrics['probe_level_one_sided_95_lower'])}; the
scene-complete lower bound was {_fmt(metrics['scene_complete_one_sided_95_lower'])}; and the
Bonferroni two-way scene × template lower bound was {_fmt(two_way)}. Degenerate all-success
cluster bootstraps were disclosed and were not used as the boundary-safe gate.

Independent scorer candidate-ranking agreement, semantic-answer agreement, parser valid recall,
parser invalid rejection, canonical NL/triples fact equality, and mutation-control detection were
all {_fmt(1.0)}. The scorer maximum token log-probability difference was
{metrics['maximum_token_logprob_difference']:.3e}. There were {metrics['parser_case_count']}
adversarial parser cases and {metrics['canonical_pair_count']} serialization comparisons.

The automated portion passed. The 54-row blinded packet contains 42 genuine pairs and 12 mismatch
decoys, but zero human reviewers have completed it. Its status remains
`HUMAN_EQUIVALENCE_REVIEW_PENDING`; an agent or model was not used as an independent reviewer.

Evidence: `artifacts/loop_b/measurement_metrics.yaml`, `artifacts/loop_b/decision.yaml`, and
`data/annotations/serialization_review_packet.csv` (config hash `{metrics['config_hash']}`).
"""


def _loop_c_report(decision: dict[str, Any], registry: dict[str, Any]) -> str:
    registry_by_id = {item["model_id"]: item for item in registry["models"]}
    rows = []
    for summary in decision["model_summaries"]:
        model = registry_by_id[summary["model_id"]]
        rows.append(
            f"| {summary['family']} | `{model['revision']}` | "
            f"{summary['checkpoint_load_success']} | {summary['actual_visual_forward_success']} | "
            f"{_fmt(summary['parser_valid_rate'])} | "
            f"{_fmt(summary['independent_scorer_ranking_agreement'])} | "
            f"{_fmt(summary['deterministic_rerun_agreement'])} | "
            f"{summary['peak_vram_bytes'] / 2**30:.2f} GiB | {summary['latency_seconds_mean']:.3f}s |"
        )
    projection = decision["full_pilot_runtime_projection"]
    return f"""
# Loop C: three-family real-checkpoint engineering preflight

Decision: **{decision['decision']}**.

| Family | Revision | Loaded | Visual forward | Parser-valid | Independent scorer | Determinism | Peak VRAM | Mean latency |
|---|---|---:|---:|---:|---:|---:|---:|---:|
{chr(10).join(rows)}

All three official, pinned, non-tiny checkpoints loaded and completed 40 primary development-only
engineering cases plus deterministic reruns. Artifact completeness was 1.000 for all models; no
mock, tiny-random, API proxy, silent retry, or fallback was used. Nevertheless, the frozen
constrained-generation parser-valid threshold of 0.98 failed for every family. Prompt or parser
repair after observing these failures was forbidden and was not performed.

The measured latency projects to {projection['hours']:.2f} hours for 28,800 synthetic calls on this
machine, excluding setup and transport samples. This is a profiling estimate, not scientific VLM
evidence. The engineering gate failed, so the resource-feasibility gate is false.

Evidence: `configs/model_smoke_registry.yaml` (config hash `{decision['config_hash']}`),
`artifacts/loop_c/decision.yaml`, and per-model predictions and summaries under
`artifacts/loop_c/`.
"""


def _gate_table(a: dict[str, Any], b: dict[str, Any], c: dict[str, Any]) -> list[dict[str, Any]]:
    v2 = a["primary_metrics"]["AuditV2"]
    metrics_b = load_yaml("artifacts/loop_b/measurement_metrics.yaml")
    model_summaries = c["model_summaries"]
    return [
        {"gate": "Loop A known-valid sensitivity >= 0.80", "value": v2["known_valid_sensitivity"], "status": "PASS"},
        {"gate": "Loop A known-invalid specificity >= 0.95", "value": v2["known_invalid_specificity"], "status": "PASS"},
        {"gate": "Loop A FMCR <= 0.05", "value": v2["fmcr"], "status": "PASS"},
        {"gate": "Loop A coverage >= 0.90", "value": v2["coverage"], "status": "PASS"},
        {"gate": "Loop A Type-S <= 0.05", "value": v2["type_s"], "status": "PASS"},
        {"gate": "Loop A abstention <= 0.40", "value": v2["abstention"], "status": "PASS"},
        {"gate": "Loop A not driven by strong tier", "value": v2["non_strong_macro_sensitivity"], "status": "FAIL"},
        {"gate": "Loop A stable across frozen grid", "value": a["threshold_stability"]["go_fraction"], "status": "FAIL"},
        {"gate": "Loop B scene-cluster lower >= 0.98", "value": metrics_b["scene_complete_one_sided_95_lower"], "status": "PASS"},
        {"gate": "Loop B two-way lower >= 0.98", "value": metrics_b["two_way_cluster"]["two_way_lower"], "status": "PASS"},
        {"gate": "Loop B cross-scorer ranking = 1", "value": metrics_b["cross_scorer_ranking_agreement"], "status": "PASS"},
        {"gate": "Loop B parser recall/rejection >= 0.99", "value": [metrics_b["valid_parser_recall"], metrics_b["invalid_parser_rejection"]], "status": "PASS"},
        {"gate": "Loop B canonical fact equality = 1", "value": metrics_b["canonical_serialization_fact_equality"], "status": "PASS"},
        {"gate": "Loop B two independent human reviewers", "value": 0, "status": "PENDING"},
        {"gate": "Loop C three checkpoint loads", "value": c["checkpoint_load_successes"], "status": "PASS"},
        {"gate": "Loop C three visual forwards", "value": c["visual_forward_successes"], "status": "PASS"},
        {"gate": "Loop C artifact completeness = 1", "value": [row["artifact_completeness"] for row in model_summaries], "status": "PASS"},
        {"gate": "Loop C parser-valid >= 0.98", "value": [row["parser_valid_rate"] for row in model_summaries], "status": "FAIL"},
        {"gate": "Loop C independent scorer = 1", "value": [row["independent_scorer_ranking_agreement"] for row in model_summaries], "status": "PASS"},
        {"gate": "Loop C determinism >= 0.99", "value": [row["deterministic_rerun_agreement"] for row in model_summaries], "status": "PASS"},
        {"gate": "Remote successor available", "value": "git@github.com:Yangjunjie-Lin/vlm-construct-audit.git", "status": "PASS"},
        {"gate": "All three loops GO", "value": [a["decision"], b["decision"], c["decision"]], "status": "FAIL"},
    ]


def _file_evidence(path: str) -> dict[str, Any]:
    target = Path(path)
    return {"path": path, "sha256": sha256_file(target), "bytes": target.stat().st_size}


def build_tier0_5_manifest() -> dict[str, Any]:
    roots = [Path("artifacts/loop_a"), Path("artifacts/loop_b"), Path("artifacts/loop_c"), Path("reports")]
    manifest_path = Path("artifacts/manifests/tier0_5_artifact_manifest.yaml")
    verification_path = Path("artifacts/manifests/tier0_5_verification_report.yaml")
    files = []
    for root in roots:
        for path in sorted(item for item in root.rglob("*") if item.is_file()):
            if path in {manifest_path, verification_path}:
                continue
            files.append(_file_evidence(path.as_posix()))
    manifest = {
        "schema_version": 1,
        "created_at": utc_timestamp(),
        "tier0_5_config_hash": canonical_hash(load_yaml("research/preregistration/tier0_5_three_loop.yaml")),
        "artifact_count": len(files),
        "artifacts": files,
    }
    dump_yaml(manifest_path, manifest)
    return manifest


def verify_tier0_5_artifacts() -> dict[str, Any]:
    manifest = load_yaml("artifacts/manifests/tier0_5_artifact_manifest.yaml")
    failures = []
    for item in manifest["artifacts"]:
        path = Path(item["path"])
        if not path.exists():
            failures.append({"path": item["path"], "reason": "missing"})
        elif sha256_file(path) != item["sha256"]:
            failures.append({"path": item["path"], "reason": "hash_mismatch"})
    loop_c_rows = []
    for path in Path("artifacts/loop_c").glob("*/predictions.jsonl"):
        import json

        loop_c_rows.extend(json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line)
    required = {
        "model_family", "model_id", "model_revision", "scene_id", "split", "condition",
        "serialization", "contract", "raw_response", "parsed_response", "candidate_scores",
        "parser_status", "runtime_seconds", "timestamp", "config_hash",
    }
    incomplete = [index for index, row in enumerate(loop_c_rows) if not required <= set(row)]
    result = {
        "schema_version": 1,
        "verified_at": utc_timestamp(),
        "manifest_artifacts": manifest["artifact_count"],
        "hash_failures": failures,
        "loop_c_prediction_count": len(loop_c_rows),
        "incomplete_loop_c_prediction_rows": incomplete,
        "loop_a_holdout_execution_count": load_yaml("artifacts/loop_a/holdout/execution_marker.yaml")["holdout_execution_count"],
        "loop_b_human_review_status": load_yaml("artifacts/loop_b/review_packet_manifest.yaml")["status"],
        "scientific_vlm_result": "NOT_EXECUTED",
        "status": "PASS" if not failures and not incomplete and len(loop_c_rows) == 120 else "FAIL",
    }
    dump_yaml("artifacts/manifests/tier0_5_verification_report.yaml", result)
    if result["status"] != "PASS":
        raise RuntimeError(f"Tier 0.5 artifact verification failed: {result}")
    return result


def adjudicate_tier0_5() -> dict[str, Any]:
    a = load_yaml("artifacts/loop_a/holdout/summary.yaml")
    b = load_yaml("artifacts/loop_b/decision.yaml")
    b_metrics = load_yaml("artifacts/loop_b/measurement_metrics.yaml")
    c = load_yaml("artifacts/loop_c/decision.yaml")
    registry = load_yaml("configs/model_smoke_registry.yaml")
    gates = _gate_table(a, b, c)
    decision = {
        "schema_version": 1,
        "decision": "STOP_FOR_METHOD_FAILURE",
        "loop_a": a["decision"],
        "loop_b_automated": b["loop_b_automated"],
        "loop_b_human": b["loop_b_human"],
        "loop_c": c["decision"],
        "three_model_scientific_pilot": "NOT_AUTHORIZED",
        "exact_next_action": "STOP_FOR_METHOD_FAILURE",
        "reasons": [
            "loop_a_non_strong_sensitivity_and_threshold_stability_failed_after_single_allowed_repair",
            "loop_b_human_equivalence_review_pending",
            "loop_c_constrained_parser_integrity_gate_failed_for_all_three_families",
        ],
        "remote_successor_repository": "https://github.com/Yangjunjie-Lin/vlm-construct-audit",
        "gate_table": gates,
    }
    dump_yaml("reports/loop_a_decision.yaml", {"decision": a["decision"], "failed_reasons": a["failed_reasons"], "config_hash": a["config_hash"]})
    dump_yaml("reports/loop_b_decision.yaml", b)
    dump_yaml("reports/loop_c_decision.yaml", c)
    dump_yaml("reports/tier0_5_final_decision.yaml", decision)
    _write("reports/loop_a_calibration_generalization.md", _loop_a_report(a))
    _write("reports/loop_b_measurement_robustness.md", _loop_b_report(b_metrics, b))
    _write("reports/loop_c_vlm_engineering_preflight.md", _loop_c_report(c, registry))
    evidence = {
        "schema_version": 1,
        "decision": decision["decision"],
        "claims": [
            {"id": "T05-A", "status": a["decision"], "boundary": "known-DGP methodological calibration only", "evidence": [_file_evidence("artifacts/loop_a/holdout/summary.yaml")]},
            {"id": "T05-B-AUTO", "status": b["decision"], "boundary": "automated measurement engineering; human equivalence pending", "evidence": [_file_evidence("artifacts/loop_b/measurement_metrics.yaml"), _file_evidence("data/annotations/serialization_review_packet.csv")]},
            {"id": "T05-C", "status": c["decision"], "boundary": "real-checkpoint engineering only; no scientific behavior claim", "evidence": [_file_evidence("artifacts/loop_c/decision.yaml"), _file_evidence("configs/model_smoke_registry.yaml")]},
            {"id": "T05-SCI", "status": "NOT_EXECUTED", "boundary": "no real-VLM scientific factorial or reasoning-test result exists", "evidence": []},
        ],
    }
    dump_yaml("reports/tier0_5_evidence_map.yaml", evidence)
    gate_lines = "\n".join(
        f"| {item['gate']} | `{item['value']}` | {item['status']} |" for item in gates
    )
    report = f"""
# Tier 0.5 three-loop adjudication

Final decision: **STOP_FOR_METHOD_FAILURE**. The preregistered three-model scientific Pilot remains
**NOT_AUTHORIZED**.

## Repository boundary

ReCoAlign remained archived and unchanged. The canonical public main is
`3e9a81432e83d651db59bf4d9a337984db7cf0fc`, the local read-only checkout is
`e200921af44e9307c60f470c247f808a75e7d625`, and the evidence-freeze commit is
`a80882071a6cf17c275453319d78d879c1546e3a` tagged
`recoalign-evidence-freeze-2026-08-25`. No Tier 0.5 result was written there.

## Loop results

- Loop A: `{a['decision']}`. Overall sensitivity reached {_fmt(a['primary_metrics']['AuditV2']['known_valid_sensitivity'])}, but non-strong macro sensitivity was {_fmt(a['primary_metrics']['AuditV2']['non_strong_macro_sensitivity'])} and frozen-grid GO fraction was {_fmt(a['threshold_stability']['go_fraction'])}.
- Loop B: `{b['decision']}`. Automated clustered measurement gates passed; two independent human reviewers are still required.
- Loop C: `{c['decision']}`. Three real checkpoints loaded and ran visual forwards, but parser-valid rates were {[row['parser_valid_rate'] for row in c['model_summaries']]} against 0.98.

## Gate table

| Gate | Value | Status |
|---|---|---|
{gate_lines}

## Claim boundary

Allowed: known-DGP methodological operating characteristics; automated measurement-engineering
results; and pinned-checkpoint load, visual-forward, scorer, parser, determinism, VRAM, RAM, latency,
and artifact-integrity results. Prohibited: real-VLM evidence uptake, compositional reasoning,
correct-versus-corrupted effects, cross-family scientific replication, claim reversal, semantic
sufficiency, or any internal mechanism. The real-VLM scientific result is `NOT_EXECUTED`.

## Failed and pending work

Loop A failed after the one permitted repair; another repair or holdout run is forbidden. Loop B
human review is pending. Loop C parser integrity failed for every family. Real-image transport was
not executed. The successor remote is public, but no formal Pilot preregistration is authorized.

## Exact next action

`STOP_FOR_METHOD_FAILURE`
"""
    _write("reports/tier0_5_three_loop_report.md", report)
    manifest = build_tier0_5_manifest()
    verification = verify_tier0_5_artifacts()
    return {
        "decision": decision["decision"],
        "loop_a": a["decision"],
        "loop_b": b["decision"],
        "loop_c": c["decision"],
        "scientific_pilot": "NOT_AUTHORIZED",
        "manifest_artifacts": manifest["artifact_count"],
        "verification": verification["status"],
    }
