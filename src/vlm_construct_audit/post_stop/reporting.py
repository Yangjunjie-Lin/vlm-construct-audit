"""Post-STOP verification and final priority adjudication."""

from __future__ import annotations

from typing import Any

from .common import ROOT, assert_historical_freeze, dump_yaml, load_yaml, utc_now


def seal_direction(direction: str) -> dict[str, Any]:
    direction = direction.lower()
    freeze = load_yaml(f"research/post_stop/direction_{direction}/method_freeze.yaml")
    return {
        "direction": direction.upper(),
        "status": freeze["status"],
        "holdout_authorized": bool(freeze.get("holdout_authorized", (ROOT / f"research/post_stop/direction_{direction}/holdout_authorization.yaml").exists())),
        "holdout_execution_count": freeze.get("holdout_execution_count", 1 if (ROOT / f"artifacts/post_stop/direction_{direction}/holdout/execution_marker.yaml").exists() else 0),
    }


def _select_final(p: str, u: str, m: str, human: str) -> str:
    if human != "HUMAN_REVIEW_GO":
        return "MEASUREMENT_FOUNDATION_NO_GO"
    if p == "DIRECTION_P_GO":
        return "PREREGISTER_POWER_CALIBRATED_MINI_PILOT"
    if u == "DIRECTION_U_GO":
        return "PREREGISTER_UPTAKE_IDENTIFICATION_MINI_PILOT"
    if m == "DIRECTION_M_SCIENTIFIC_GO":
        return "PREREGISTER_ANSWER_CONTRACT_SCIENTIFIC_PILOT"
    return "TERMINATE_SUCCESSOR_PROGRAM"


def verify_post_stop_artifacts() -> dict[str, Any]:
    historical = assert_historical_freeze()
    p = load_yaml("reports/post_stop_direction_p_decision.yaml")
    m = load_yaml("reports/post_stop_direction_m_decision.yaml")
    u = load_yaml("reports/post_stop_direction_u_decision.yaml")
    human_path = ROOT / "data/annotations/human_review_metrics.yaml"
    human = load_yaml("data/annotations/human_review_metrics.yaml") if human_path.exists() else None
    checks = {
        "historical_freeze": historical["status"] == "PASS",
        "P_holdout_once": p["holdout_execution_count"] == 1 and load_yaml("artifacts/post_stop/direction_p/holdout/execution_marker.yaml")["execution_count"] == 1,
        "M_holdout_zero": m["sealed_holdout"]["execution_count"] == 0 and not (ROOT / "artifacts/post_stop/direction_m/holdout/execution_marker.yaml").exists(),
        "U_holdout_zero": u["sealed_holdout"]["execution_count"] == 0 and not (ROOT / "artifacts/post_stop/direction_u/holdout/execution_marker.yaml").exists(),
        "direction_decisions_present": all(value in {"DIRECTION_P_GO", "DIRECTION_M_NO_GO", "DIRECTION_U_NO_GO"} for value in [p["decision"], m["decision"], u["decision"]]),
        "human_review_complete": (
            human is not None
            and human.get("reviewer_count") == 2
            and human.get("status") == "HUMAN_REVIEW_GO"
            and all(human.get("gates", {}).values())
        ),
        "model_as_human_forbidden": human is None or human.get("agent_or_model_review_used") is False,
    }
    status = "PASS" if all(checks.values()) else ("PENDING_EXTERNAL_HUMAN_REVIEW" if not checks["human_review_complete"] and all(value for key, value in checks.items() if key != "human_review_complete") else "FAIL")
    result = {"schema_version": 1, "verified_at": utc_now(), "status": status, "checks": checks, "directions": {"P": p["decision"], "M": m["decision"], "U": u["decision"]}, "human_review": human["status"] if human else "PENDING", "final_reports_present": all((ROOT / path).exists() for path in ["reports/post_stop_three_direction_report.md", "reports/post_stop_final_decision.yaml", "reports/post_stop_evidence_map.yaml", "reports/post_stop_claim_boundary.md"])}
    dump_yaml("artifacts/post_stop/verification_report.yaml", result)
    return result


def adjudicate_post_stop() -> dict[str, Any]:
    human_path = ROOT / "data/annotations/human_review_metrics.yaml"
    if not human_path.exists():
        raise RuntimeError("final adjudication requires two completed independent human reviews")
    human = load_yaml("data/annotations/human_review_metrics.yaml")
    p = load_yaml("reports/post_stop_direction_p_decision.yaml")
    m = load_yaml("reports/post_stop_direction_m_decision.yaml")
    u = load_yaml("reports/post_stop_direction_u_decision.yaml")
    decision = _select_final(p["decision"], u["decision"], m["decision"], human["status"])
    selected = "P" if decision == "PREREGISTER_POWER_CALIBRATED_MINI_PILOT" else ("U" if decision == "PREREGISTER_UPTAKE_IDENTIFICATION_MINI_PILOT" else ("M" if decision == "PREREGISTER_ANSWER_CONTRACT_SCIENTIFIC_PILOT" else None))
    final = {
        "schema_version": 1,
        "decision": decision,
        "selected_direction": selected,
        "priority_order": ["P", "U", "M"],
        "direction_decisions": {"P": p["decision"], "U": u["decision"], "M": m["decision"]},
        "novelty": {"P": p["novelty"], "U": u["novelty"], "M": m["novelty"]},
        "loop_b_human": human["status"],
        "audit_v2": "LOOP_A_NO_GO",
        "old_holdout_rerun": False,
        "recoalign_modified": False,
        "exact_next_action": decision,
    }
    dump_yaml("reports/post_stop_final_decision.yaml", final)
    evidence = {
        "schema_version": 1,
        "final_decision": decision,
        "claims": [
            {"claim": "Tier 0.5 STOP state and historical artifacts remain frozen", "evidence": "artifacts/post_stop/verification_report.yaml", "scope": "historical provenance"},
            {"claim": "Post-STOP novelty audit completed before new results", "evidence": "research/post_stop/literature_matrix.yaml", "scope": "novelty screening"},
            {"claim": "Direction P sealed known-DGP GO", "evidence": "reports/post_stop_direction_p_decision.yaml", "scope": "known-DGP methodology"},
            {"claim": "Direction M NO-GO without sealed holdout", "evidence": "reports/post_stop_direction_m_decision.yaml", "scope": "development engineering"},
            {"claim": "Direction U NO-GO without sealed holdout", "evidence": "reports/post_stop_direction_u_decision.yaml", "scope": "development execution"},
            {"claim": "Loop B independent human gate", "evidence": "data/annotations/human_review_metrics.yaml", "scope": "measurement foundation"},
            {"claim": "Exactly one direction selected under frozen priority P > U > M", "evidence": "reports/post_stop_final_decision.yaml", "scope": "final adjudication"},
        ],
    }
    dump_yaml("reports/post_stop_evidence_map.yaml", evidence)
    claim_boundary = """# Post-STOP Claim Boundary\n\nKnown-DGP methodological evidence: Direction P GO only. Direction U emitted no numeric operating-characteristic result.\n\nMeasurement-contract evidence: Direction M development only; no M sealed holdout.\n\nReal-checkpoint engineering evidence: M completed SmolVLM and Qwen2-VL development batches; InternVL failed.\n\nReal-VLM scientific evidence: none. No post-STOP real-VLM scientific Pilot was executed.\n\nInternal-mechanism evidence: none. No direction identifies an internal VLM mechanism.\n"""
    (ROOT / "reports/post_stop_claim_boundary.md").write_text(claim_boundary, encoding="utf-8")
    report = f"""# Post-STOP Three-Direction Report

# 1. Final Decision

`{decision}`

# 2. Frozen Historical State

AuditV2 remains failed; the old holdout was not rerun; old reports are unchanged; ReCoAlign is unchanged.

# 3. Direction P

δ0=0.10 remained fixed. δ1=0.15 was selected analytically before simulation from the target-power, alpha, feasible-N, variance, and false-claim constraints; analytic certification power was 0.9337 at N=768. The indifference interval (0.10, 0.15) is neither success nor failure.

The single sealed holdout returned FMCR 0, specificity 1.00, sensitivity 1.00, gray-zone overclaim 0, coverage 1.00, Type-S 0, Type-M ratio 1.0023, abstention 0, and explicit gray-zone output on 14.57% of datasets. Across all preregistered risk/coverage thresholds, FMCR, sensitivity, and gray-zone overclaim were stable and the decision remained inside the registered operating region. Four non-strong families each had sensitivity 1.00. Relative to the frozen AuditV2 adapter, paired sensitivity improved by 0.296 (95% CI 0.256–0.336) without worse FMCR. Decision: `{p['decision']}`.

# 4. Direction M

Prompt-only JSON syntactic compliance was 0.00 for SmolVLM and 0.25 for Qwen2-VL; true token-level constrained compliance was 1.00 in both completed families. Independent scorer agreement and deterministic rerun agreement were 1.00, and canonicalizer valid-form recall and ambiguous/invalid rejection were both 1.00. These are syntactic and engineering results, not capability claims.

CLL versus constrained semantic κ was 0.211 (95% CI 0.121–0.302) for SmolVLM and 0.928 (95% CI 0.853–0.982) for Qwen2-VL. Constrained-minus-CLL task correctness changed by -0.233 (95% CI -0.383 to -0.067) and +0.033 (95% CI -0.033 to 0.100), respectively. SmolVLM answer changes spanned tasks and serializations and were not parser-rejection artifacts, but the effect was not cross-family. InternVL failed after the only development revision, so the three-family engineering gate failed and no sealed holdout was authorized. Decision: `{m['decision']}`; it is neither scientific GO nor engineering-only GO.

# 5. Direction U

No admissible bias, RMSE, coverage, FMCR, principal-stratum recovery, IV-strength, bound-width, assumption-violation, or naive-filtering comparison was emitted. Both 7,200-dataset development attempts failed during Type-S aggregation, and the sole revision budget was exhausted. Consequently there is no identification decision beyond development failure, no sealed holdout, and no real-model smoke. Decision: `{u['decision']}`. No numerical operating characteristic from an incomplete in-memory run is treated as evidence.

# 6. Human Review

Reviewer count {human['reviewer_count']}; agreement {human['fact_equivalence_agreement']:.4f}; κ {human['cohen_kappa']:.4f}; critical mismatches {human['critical_semantic_mismatch']}; minimum decoy detection {human['decoy_detection']['minimum']:.4f}; status `{human['status']}`.

# 7. Novelty Audit

P (`{p['novelty']}`) is nearest to Xu et al. (2026), Yu, Niu & He (2026), and Kotte (2026). Its remaining possible difference is known-DGP certification of scene-level effect claims against fixed δ0 and precomputed δ1 with false-mechanistic-claim control and explicit invalid states.

M (`{m['novelty']}`) is nearest to Parikh (2026), Chen, Qu & Wang (2026), Usman (2026), and Song et al. (2026). Only fixed-truth VLM cross-contract measurement equivalence remains potentially different; syntax/semantics decomposition and schema constraints are not novel.

U (`{u['novelty']}`) is nearest to established principal-stratification/IV work plus Bronder (2026) and Li & Liu (2026). Only known-potential-state calibration of encouragement-based multimodal uptake with correct point/partial/non-identification decisions remains potentially different. No generic SESOI, conformal, JSON-schema, principal-stratification, IV, or bounds ingredient is claimed as novel.

# 8. Gate Table

| Direction / foundation | Gate | Required | Observed | Result |
|---|---|---:|---:|---|
| P | FMCR | ≤0.05 | 0.00 | PASS |
| P | specificity, effect ≤δ0 | ≥0.95 | 1.00 | PASS |
| P | sensitivity, effect ≥δ1 | ≥0.80 | 1.00 | PASS |
| P | gray-zone overclaim | ≤0.05 | 0.00 | PASS |
| P | coverage | ≥0.90 | 1.00 | PASS |
| P | Type-S | ≤0.05 | 0.00 | PASS |
| P | abstention | ≤0.40 | 0.00 | PASS |
| P | non-strong families at sensitivity ≥0.80 | ≥2 | 4 | PASS |
| P | threshold stability | stable in registered range | PASS | PASS |
| P | paired sensitivity gain vs frozen AuditV2 adapter | >0 with FMCR non-worse | +0.296; FMCR non-worse | PASS |
| M | true-constrained syntax, all 3 families | 1.00 | 2 complete; InternVL failed | FAIL |
| M | scorer ranking agreement, all 3 families | 1.00 | 2 complete at 1.00 | FAIL |
| M | deterministic rerun, all 3 families | ≥0.99 | 2 complete at 1.00 | FAIL |
| M | canonicalizer valid recall / invalid rejection | ≥0.99 / ≥0.99 | 1.00 / 1.00 | PASS |
| M | scientific equivalence or material-effect path | ≥2/3 families | 0/3 equivalence; 1/3 material | FAIL |
| U | complete numeric development summary | required before holdout | not emitted | FAIL |
| U | known-DGP GO | required | false | FAIL |
| Human | independent reviewer count | 2 | {human['reviewer_count']} | PASS |
| Human | fact-equivalence agreement | ≥0.95 | {human['fact_equivalence_agreement']:.2f} | PASS |
| Human | Cohen's κ | ≥0.80 | {human['cohen_kappa']:.2f} | PASS |
| Human | critical semantic mismatch | 0 | {human['critical_semantic_mismatch']} | PASS |
| Human | minimum decoy detection | ≥0.90 | {human['decoy_detection']['minimum']:.2f} | PASS |
| Human | model/agent used as reviewer | false | {str(human['agent_or_model_review_used']).lower()} | PASS |

# 9. Failures and Researcher Degrees of Freedom

| Direction | Attempt / event | Revision, failure, exclusion, blocker, or deviation | Disposition |
|---|---|---|---|
| P | initial development summary | reporting-only control-flow revision; development was incorrectly allowed to emit GO | original attempt retained; no numeric design element changed |
| P | sealed holdout | no failure, exclusion, deviation, or rerun | executed exactly once |
| M | launcher preflight | isolated environment lacked editable install | console log retained; no model/data outcome |
| M | development attempt 1 | pinned InternVL wrapper received duplicate `use_cache` | full attempt retained; sole revision consumed |
| M | development attempt 2 | pinned InternVL wrapper rejected `image_flags` | failure retained; second repair forbidden; holdout blocked |
| U | development attempt 1 | `numpy.bool_` rejected in policy Type-S aggregation | marker/traceback retained; sole revision consumed |
| U | development attempt 2 | second `numpy.bool_` incompatibility in per-method Type-S aggregation | marker/traceback retained; further repair forbidden; holdout blocked |
| Human | review import | no packet edit, deleted disagreement, exclusion, or model reviewer | packet hash verified; both append-only files retained |

No direction used another direction's holdout, selected a method from holdout results, excluded an inconvenient run, or combined favorable pieces post hoc. M and U holdout execution counts remain zero.

# 10. Selected Direction

Selected: `{selected}`. M was not selected because it is NO-GO; U was not selected because it is NO-GO. At most one direction is selected.

# 11. Claim Boundary

P is known-DGP methodology. M is development measurement/engineering. There is no post-STOP real-VLM scientific evidence and no internal-mechanism evidence.

# 12. Exact Next Action

`{decision}`
"""
    (ROOT / "reports/post_stop_three_direction_report.md").write_text(report, encoding="utf-8")
    return final
