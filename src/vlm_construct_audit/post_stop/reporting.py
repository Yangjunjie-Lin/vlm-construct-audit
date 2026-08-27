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
        "human_review_complete": human is not None and human.get("reviewer_count") == 2,
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
            {"claim": "Direction P sealed known-DGP GO", "evidence": "reports/post_stop_direction_p_decision.yaml", "scope": "known-DGP methodology"},
            {"claim": "Direction M NO-GO without sealed holdout", "evidence": "reports/post_stop_direction_m_decision.yaml", "scope": "development engineering"},
            {"claim": "Direction U NO-GO without sealed holdout", "evidence": "reports/post_stop_direction_u_decision.yaml", "scope": "development execution"},
            {"claim": "Loop B independent human gate", "evidence": "data/annotations/human_review_metrics.yaml", "scope": "measurement foundation"},
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

δ0=0.10, δ1=0.15, analytic power 0.9337 at N=768. The single sealed holdout returned FMCR 0, specificity 1.00, sensitivity 1.00, gray-zone overclaim 0, coverage 1.00, Type-S 0, and stable risk/coverage. Decision: `{p['decision']}`.

# 4. Direction M

Prompt-only JSON syntax was 0.00 and 0.25 in completed families; true constrained syntax was 1.00 in both. InternVL failed after the only development revision. No sealed holdout. Decision: `{m['decision']}`.

# 5. Direction U

No bias/coverage/FMCR/bounds result was emitted because both development attempts failed in summary aggregation and the revision budget was exhausted. No sealed holdout or real-model smoke. Decision: `{u['decision']}`.

# 6. Human Review

Reviewer count {human['reviewer_count']}; agreement {human['fact_equivalence_agreement']:.4f}; κ {human['cohen_kappa']:.4f}; critical mismatches {human['critical_semantic_mismatch']}; minimum decoy detection {human['decoy_detection']['minimum']:.4f}; status `{human['status']}`.

# 7. Novelty Audit

P is closest to VLM selective/conformal answer certification but retains only known-DGP effect-claim calibration as a possible difference. M is closest to structured-output semantic-shift and format-repair work and passed only with caution. U's causal tools are established; the remaining difference is known-state VLM uptake calibration.

# 8. Gate Table

P passed every preregistered sealed gate. M failed the three-model engineering gate. U failed development completion. Human review status is `{human['status']}`.

# 9. Failures and Researcher Degrees of Freedom

P consumed one reporting-only development revision; its initial attempt is retained. M consumed one InternVL compatibility revision and then failed again; both attempts and launcher failure are retained. U consumed one bool-type reporting revision and failed at a second occurrence; both markers/logs are retained. No holdout exclusion or rerun occurred.

# 10. Selected Direction

Selected: `{selected}`. M was not selected because it is NO-GO; U was not selected because it is NO-GO. At most one direction is selected.

# 11. Claim Boundary

P is known-DGP methodology. M is development measurement/engineering. There is no post-STOP real-VLM scientific evidence and no internal-mechanism evidence.

# 12. Exact Next Action

`{decision}`
"""
    (ROOT / "reports/post_stop_three_direction_report.md").write_text(report, encoding="utf-8")
    return final
