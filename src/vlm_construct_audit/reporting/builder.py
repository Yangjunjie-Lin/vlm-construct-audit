"""Build claim-bounded Tier-0 reports and hash-verifiable manifests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..utils import canonical_hash, dump_yaml, load_yaml, read_jsonl, sha256_file, utc_timestamp
from .claims import lint_claim_language


def _config_hash() -> str:
    return canonical_hash(
        {
            "pilot": load_yaml("configs/pilot.yaml"),
            "policy": load_yaml("configs/audit_policy.yaml"),
            "preregistration": load_yaml("research/preregistration/minimum_pilot.yaml"),
        }
    )


def build_evidence_map() -> dict[str, Any]:
    audit = load_yaml("artifacts/metrics/audit_decisions.yaml")
    stats = load_yaml("artifacts/metrics/statistical_calibration.yaml")
    equivalence = load_yaml("artifacts/metrics/equivalence_report.yaml")
    config_hash = _config_hash()
    evidence = {
        "schema_version": 1,
        "config_hash": config_hash,
        "project_decision": "TIER0_INCONCLUSIVE_TIER1_NOT_AUTHORIZED",
        "claims": [
            {
                "id": "T0C001",
                "claim": "The two serializers round-trip to identical proposition multisets.",
                "status": "verified_programmatically_human_review_pending" if equivalence["programmatic_fact_equivalence"] else "failed",
                "artifacts": ["artifacts/metrics/equivalence_report.yaml", "data/annotations/serialization_manual_review.csv"],
                "boundary": "Programmatic equivalence is not an independent human audit or semantic validity proof.",
            },
            {
                "id": "T0C002",
                "claim": "The audit recovers the preregistered claim class of all six known-state systems.",
                "status": "verified" if audit["expected_class_matches"] == 6 else "falsified",
                "artifacts": ["artifacts/metrics/audit_decisions.yaml", "artifacts/predictions/calibration_predictions.jsonl"],
                "boundary": "Trusted stage diagnostics exist only for calibration systems.",
            },
            {
                "id": "T0C003",
                "claim": "B5 reduces known-DGP false mechanistic claims relative to B1.",
                "status": "verified_in_simulation",
                "estimate": stats["B5_vs_B1_absolute_reduction"],
                "artifacts": ["artifacts/metrics/statistical_calibration.yaml"],
                "boundary": "Repeated known-DGP calibration, not a real-VLM scientific result.",
            },
            {
                "id": "T0C004",
                "claim": "Sensitivity to known valid effects meets the 80 percent GO gate.",
                "status": "inconclusive",
                "estimate": stats["sensitivity_to_known_valid_effects"],
                "artifacts": ["artifacts/metrics/statistical_calibration.yaml"],
                "boundary": "73.5 percent lies in the preregistered 70–80 percent inconclusive band.",
            },
            {
                "id": "T0C005",
                "claim": "A three-family real-VLM result exists.",
                "status": "not_executed",
                "artifacts": ["configs/models.yaml", "artifacts/metrics/smoke_report.yaml"],
                "boundary": "The tiny random BLIP forward is engineering smoke only.",
            },
        ],
    }
    dump_yaml("reports/evidence_map.yaml", evidence)
    return evidence


def _gate_table(stats: dict[str, Any], _audit: dict[str, Any], sensitivity: dict[str, Any]) -> list[dict[str, Any]]:
    analysis = load_yaml("artifacts/metrics/analysis_results.yaml")
    oracle_measurement = analysis["systems"]["OracleEvidenceReasoner"]["measurement"]
    kappa = oracle_measurement["contract_agreement"]
    return [
        {"gate": "FMCR absolute reduction >= 0.10", "value": stats["B5_vs_B1_absolute_reduction"], "status": "PASS" if stats["B5_vs_B1_absolute_reduction"] >= 0.10 else "FAIL"},
        {"gate": "FMCR relative reduction >= 0.40", "value": stats["B5_vs_B1_relative_reduction"], "status": "PASS" if stats["B5_vs_B1_relative_reduction"] >= 0.40 else "FAIL"},
        {"gate": "FMCR improvement CI excludes zero", "value": stats["B5_vs_B1_improvement_ci95"], "status": "PASS" if stats["B5_vs_B1_improvement_ci95"][0] > 0 else "FAIL"},
        {"gate": "Known valid sensitivity >= 0.80", "value": stats["sensitivity_to_known_valid_effects"], "status": "INCONCLUSIVE" if 0.70 <= stats["sensitivity_to_known_valid_effects"] < 0.80 else ("PASS" if stats["sensitivity_to_known_valid_effects"] >= 0.80 else "FAIL")},
        {"gate": "Empirical CI coverage >= 0.90", "value": stats["empirical_ci_coverage"], "status": "PASS" if stats["empirical_ci_coverage"] >= 0.90 else "FAIL"},
        {"gate": "Abstention <= 0.40", "value": stats["abstention_rate"], "status": "PASS" if stats["abstention_rate"] <= 0.40 else "FAIL"},
        {"gate": "Measurement lower bound >= 0.98", "value": oracle_measurement["one_sided_95_lower"], "status": "PASS" if oracle_measurement["one_sided_95_lower"] >= 0.98 else "FAIL"},
        {"gate": "Response-contract kappa >= .90 and lower >= .85", "value": {"kappa": kappa["kappa"], "lower": kappa["ci95"][0]}, "status": "PASS" if kappa["kappa"] >= .9 and kappa["ci95"][0] >= .85 else "FAIL"},
        {"gate": "B5 outperforms B2/B3/B4", "value": stats["baseline_false_mechanistic_claim_rate"], "status": "PASS" if stats["baseline_false_mechanistic_claim_rate"]["B5"] < min(stats["baseline_false_mechanistic_claim_rate"][key] for key in ("B2", "B3", "B4")) else "FAIL"},
        {"gate": "Real VLM material audit-change case", "value": "NOT_EXECUTED", "status": "NOT_EVALUABLE"},
        {"gate": "Threshold advantage does not reverse", "value": sensitivity["min_advantage_over_B1"], "status": "PASS" if sensitivity["advantage_never_reverses"] else "FAIL"},
        {"gate": "Not driven by one real model/family/template/operator", "value": "NO_REAL_MODELS", "status": "NOT_EVALUABLE"},
    ]


def _md_table(rows: list[dict[str, Any]]) -> str:
    lines = ["| Gate | Value | Status |", "| --- | --- | --- |"]
    for row in rows:
        value = json.dumps(row["value"], sort_keys=True) if not isinstance(row["value"], str) else row["value"]
        lines.append(f"| {row['gate']} | `{value}` | {row['status']} |")
    return "\n".join(lines)


def build_report() -> dict[str, Any]:
    audit = load_yaml("artifacts/metrics/audit_decisions.yaml")
    stats = load_yaml("artifacts/metrics/statistical_calibration.yaml")
    sensitivity = load_yaml("artifacts/metrics/threshold_sensitivity_table.yaml")
    equivalence = load_yaml("artifacts/metrics/equivalence_report.yaml")
    prediction_manifest = load_yaml("artifacts/manifests/prediction_manifest.yaml")
    smoke = load_yaml("artifacts/metrics/smoke_report.yaml")
    gates = _gate_table(stats, audit, sensitivity)
    decision = {
        "schema_version": 1,
        "tier0_decision": "INCONCLUSIVE",
        "scientific_pilot_status": "NOT_AUTHORIZED",
        "next_action": "REPAIR_ENGINEERING_ONLY",
        "reason": "Known-effect sensitivity is 0.735, inside the preregistered inconclusive band; human serialization review, model freeze, real-image licensing, and real VLM execution are incomplete.",
        "config_hash": _config_hash(),
        "go_gate_table": gates,
        "real_vlm_result": "NOT_EXECUTED",
    }
    dump_yaml("reports/pilot_decision.yaml", decision)

    confusion = json.dumps(audit["calibration_confusion_matrix"], indent=2, sort_keys=True)
    report = f"""# Minimum Closed-Loop Report

## 1. Repository Boundary

The archived ReCoAlign repository remained read-only and clean at successor bootstrap. The
successor has an independent Git root. No ReCoAlign code, predictions, metrics, gates, or
claim-bearing evidence were copied. The read-only source was inspected at `e200921...`; its
scientific freeze is `a808820...` under Apache-2.0.

## 2. Novelty Status

**PASS WITH CAUTION** for Tier-0 implementation. No audited primary work combined all five
required axes. SugarCrepe, Sutter et al., and MMIB are the closest benchmark, false-success,
and VLM-mechanistic neighbours. The remaining contribution is only the joint known-state audit
and its error calibration; ordinary manipulation checking or prompt sensitivity is not novel.

## 3. Theory Status

E1 is identified for the frozen complete paired scene-generator population. Pure E2 requires a
fixed response/logit record; CL-versus-constrained generation is labelled elicitation-plus-
measurement robustness. E3 is an interaction conditional on programmatic fact equivalence.
E4 is conditional on the independent split-level gate procedure and is not an ATE. E5 remains
partially identified with primary bounds `[-1,1]`. Internal mechanisms are not identified.

## 4. Engineering Closure

`make minimum-loop` executes generation, six interventions, two serializations, six systems,
two contracts, scoring, uptake, downstream analysis, audit, statistics, evidence mapping,
reporting, and verification. It uses {prediction_manifest['prediction_count']} predictions from
48 scenes and 1,800 measurement probes. No intermediate hand edit is required.

## 5. Calibration Performance

Expected claim classes recovered: **{audit['expected_class_matches']}/6**.

```json
{confusion}
```

Fixed-inventory B1 false claim rate was {audit['baseline_metrics']['B1_standard_single_contract_accuracy']['false_mechanistic_claim_rate']:.3f}; B5 was {audit['baseline_metrics']['B5_full_validity_aware_audit']['false_mechanistic_claim_rate']:.3f}. Repeated known-DGP B1/B5 rates were {stats['baseline_false_mechanistic_claim_rate']['B1']:.3f}/{stats['baseline_false_mechanistic_claim_rate']['B5']:.3f}. Repeated-DGP sensitivity was {stats['sensitivity_to_known_valid_effects']:.3f}, coverage {stats['empirical_ci_coverage']:.3f}, Type-S error {stats['type_s_error']:.3f}, Type-M ratio {stats['type_m_error_ratio']:.3f}, and abstention {stats['abstention_rate']:.3f}.

## 6. Benchmark Status

All interventions match fact, entity, relation, sentence, token-tolerance, and answer-option-
overlap constraints. NL/triples programmatic fact equivalence is `{equivalence['programmatic_fact_equivalence']}` across {equivalence['pair_count']} pairs. Independent human review remains `{equivalence['manual_sample_review']['status']}`. Splits have disjoint scene and template IDs. A real-image license has not been established.

## 7. Statistical Status

The primary estimand is a scene-paired marginal risk difference standardized equally over three
target corruptions. Scene-cluster bootstrap is primary in Tier 0; the formal Tier-1 design freezes
model/family fixed effects and a scene random intercept, with an evidence random slope only if
identifiable. Threshold sensitivity covers {sensitivity['grid_rows']} frozen combinations and
does not reverse the B5 advantage. E5 uses support bounds, not sample-level uptake filtering.
Holm and TOST procedures are implemented/frozen; no equivalence is inferred from non-significance.

## 8. Scientific Pilot Status

**NOT_AUTHORIZED.** No open-weight checkpoint was run. The seeded 33,104-parameter random BLIP
forward ({smoke['offline_tiny_random_vlm_forward']['status']}) tests engineering only. Three model
revisions, a human serialization audit, and real-image license provenance are unresolved.

## 9. Q1 Contribution Status

- Theory: promising separation of latent uptake, proxy, elicitation, scoring, and behavior; E5 remains weakly bounded.
- Methodology: known-state class recovery succeeded, but valid-effect sensitivity missed GO.
- Benchmark: synthetic Tier 0 is closed; no licensed real transport set.
- Empirical evidence: calibration only; no real-VLM evidence.
- Reproducibility: deterministic data, full predictions, hashes, tests, and CI are present.

Code volume does not change these ratings.

## 10. Next Action

**REPAIR_ENGINEERING_ONLY.** Do not proceed to the three-model pilot. Permitted repairs are limited
to independent human serialization review, real checkpoint smoke plumbing, legal transport-data
feasibility, and improving calibrated sensitivity without changing the frozen scientific gates.

## GO / NO-GO Gate Table

{_md_table(gates)}
"""
    for target in ("reports/minimum_closed_loop_report.md", "reports/tier0_closed_loop_report.md"):
        path = Path(target)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(report, encoding="utf-8")

    calibration_report = f"""# Calibration Report

- Expected class recovery: {audit['expected_class_matches']}/6.
- Fixed inventory B1 FMCR: {audit['baseline_metrics']['B1_standard_single_contract_accuracy']['false_mechanistic_claim_rate']:.3f}.
- Fixed inventory B5 FMCR: {audit['baseline_metrics']['B5_full_validity_aware_audit']['false_mechanistic_claim_rate']:.3f}.
- Repeated-DGP sensitivity: {stats['sensitivity_to_known_valid_effects']:.3f} (INCONCLUSIVE against 0.80 GO / 0.70 NO-GO bounds).
- Empirical coverage: {stats['empirical_ci_coverage']:.3f}.
- Abstention: {stats['abstention_rate']:.3f}.
- Claim boundary: known-state calibration only.
"""
    Path("reports/calibration_report.md").write_text(calibration_report, encoding="utf-8")
    Path("reports/claim_boundary.md").write_text(
        "# Claim Boundary\n\nAllowed: known-system audit performance and frozen behavioral effects.\n\nForbidden: real-VLM findings, internal mechanisms, semantic sufficiency, graph superiority, or generalization from Tier 0.\n",
        encoding="utf-8",
    )
    _write_resource_report(smoke)
    return decision


def _write_resource_report(smoke: dict[str, Any]) -> None:
    text = f"""# Resource Requirements

Current Python runtime: Torch CUDA availability is `{smoke['offline_tiny_random_vlm_forward'].get('cuda_available_to_torch', False)}`.
The host exposes an RTX 3060 Laptop GPU with 6 GiB through `nvidia-smi`, but the active Torch
build is CPU-only. The offline tiny-random BLIP forward passed; it is not a checkpoint smoke.

A three-family pilot needs model-specific frozen revisions, one-model-at-a-time VRAM feasibility,
checkpoint storage, image preprocessing caches, and approximately 28,800 synthetic evaluations
plus 120 separately analysed transport samples. No resource estimate is treated as execution.
"""
    Path("reports/resource_requirements.md").write_text(text, encoding="utf-8")


def build_artifact_manifest() -> dict[str, Any]:
    roots = [Path("data/generated"), Path("data/manifests"), Path("data/annotations"), Path("artifacts"), Path("reports")]
    manifest_path = Path("artifacts/manifests/artifact_manifest.yaml")
    verification_path = Path("artifacts/manifests/verification_report.yaml")
    tier0_5_manifest_path = Path("artifacts/manifests/tier0_5_artifact_manifest.yaml")
    tier0_5_verification_path = Path("artifacts/manifests/tier0_5_verification_report.yaml")
    excluded_manifests = {
        manifest_path,
        verification_path,
        tier0_5_manifest_path,
        tier0_5_verification_path,
    }
    tier0_5_report_names = {
        "loop_a_calibration_generalization.md",
        "loop_a_decision.yaml",
        "loop_b_decision.yaml",
        "loop_b_measurement_robustness.md",
        "loop_c_decision.yaml",
        "loop_c_vlm_engineering_preflight.md",
        "tier0_5_evidence_map.yaml",
        "tier0_5_final_decision.yaml",
        "tier0_5_three_loop_report.md",
    }
    files = []
    for root in roots:
        if not root.exists():
            continue
        for path in sorted(p for p in root.rglob("*") if p.is_file()):
            if path in excluded_manifests or (path.parent == Path("reports") and path.name in tier0_5_report_names):
                continue
            files.append({"path": path.as_posix(), "sha256": sha256_file(path), "bytes": path.stat().st_size})
    manifest = {
        "schema_version": 1,
        "created_at": utc_timestamp(),
        "config_hash": _config_hash(),
        "artifact_count": len(files),
        "artifacts": files,
    }
    dump_yaml(manifest_path, manifest)
    return manifest


def verify_artifacts() -> dict[str, Any]:
    manifest_path = Path("artifacts/manifests/artifact_manifest.yaml")
    if not manifest_path.exists():
        raise FileNotFoundError("Build the artifact manifest before verification")
    manifest = load_yaml(manifest_path)
    failures = []
    for item in manifest["artifacts"]:
        path = Path(item["path"])
        if not path.exists():
            failures.append({"path": item["path"], "reason": "missing"})
        elif sha256_file(path) != item["sha256"]:
            failures.append({"path": item["path"], "reason": "hash_mismatch"})
    predictions = read_jsonl("artifacts/predictions/calibration_predictions.jsonl")
    required = {
        "scene_id", "split", "model_id", "model_revision", "condition", "serialization",
        "contract", "raw_response", "parsed_response", "candidate_scores", "parser_status",
        "timestamp", "config_hash",
    }
    incomplete = [index for index, row in enumerate(predictions) if not required <= set(row)]
    config_hash_matches = all(row["config_hash"] == _config_hash() for row in predictions)
    claim_violations = {
        path.as_posix(): lint_claim_language(path.read_text(encoding="utf-8"))
        for path in Path("reports").glob("*.md")
    }
    claim_violations = {path: violations for path, violations in claim_violations.items() if violations}
    result = {
        "schema_version": 1,
        "verified_at": utc_timestamp(),
        "manifest_artifacts": manifest["artifact_count"],
        "hash_failures": failures,
        "prediction_count": len(predictions),
        "incomplete_prediction_rows": incomplete,
        "config_hash_recomputed": _config_hash(),
        "config_hash_matches_all_predictions": config_hash_matches,
        "claim_language_violations": claim_violations,
        "status": "PASS" if not failures and not incomplete and config_hash_matches and not claim_violations else "FAIL",
    }
    dump_yaml("artifacts/manifests/verification_report.yaml", result)
    if result["status"] != "PASS":
        raise RuntimeError(f"Artifact verification failed: {result}")
    return result
