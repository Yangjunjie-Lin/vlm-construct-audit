# Post-STOP Three-Direction Report

# 1. Final Decision

`PREREGISTER_POWER_CALIBRATED_MINI_PILOT`

# 2. Frozen Historical State

AuditV2 remains failed; the old holdout was not rerun; old reports are unchanged; ReCoAlign is unchanged.

# 3. Direction P

δ0=0.10 remained fixed. δ1=0.15 was selected analytically before simulation from the target-power, alpha, feasible-N, variance, and false-claim constraints; analytic certification power was 0.9337 at N=768. The indifference interval (0.10, 0.15) is neither success nor failure.

The single sealed holdout returned FMCR 0, specificity 1.00, sensitivity 1.00, gray-zone overclaim 0, coverage 1.00, Type-S 0, Type-M ratio 1.0023, abstention 0, and explicit gray-zone output on 14.57% of datasets. Across all preregistered risk/coverage thresholds, FMCR, sensitivity, and gray-zone overclaim were stable and the decision remained inside the registered operating region. Four non-strong families each had sensitivity 1.00. Relative to the frozen AuditV2 adapter, paired sensitivity improved by 0.296 (95% CI 0.256–0.336) without worse FMCR. Decision: `DIRECTION_P_GO`.

# 4. Direction M

Prompt-only JSON syntactic compliance was 0.00 for SmolVLM and 0.25 for Qwen2-VL; true token-level constrained compliance was 1.00 in both completed families. Independent scorer agreement and deterministic rerun agreement were 1.00, and canonicalizer valid-form recall and ambiguous/invalid rejection were both 1.00. These are syntactic and engineering results, not capability claims.

CLL versus constrained semantic κ was 0.211 (95% CI 0.121–0.302) for SmolVLM and 0.928 (95% CI 0.853–0.982) for Qwen2-VL. Constrained-minus-CLL task correctness changed by -0.233 (95% CI -0.383 to -0.067) and +0.033 (95% CI -0.033 to 0.100), respectively. SmolVLM answer changes spanned tasks and serializations and were not parser-rejection artifacts, but the effect was not cross-family. InternVL failed after the only development revision, so the three-family engineering gate failed and no sealed holdout was authorized. Decision: `DIRECTION_M_NO_GO`; it is neither scientific GO nor engineering-only GO.

# 5. Direction U

No admissible bias, RMSE, coverage, FMCR, principal-stratum recovery, IV-strength, bound-width, assumption-violation, or naive-filtering comparison was emitted. Both 7,200-dataset development attempts failed during Type-S aggregation, and the sole revision budget was exhausted. Consequently there is no identification decision beyond development failure, no sealed holdout, and no real-model smoke. Decision: `DIRECTION_U_NO_GO`. No numerical operating characteristic from an incomplete in-memory run is treated as evidence.

# 6. Human Review

Reviewer count 2; agreement 1.0000; κ 1.0000; critical mismatches 0; minimum decoy detection 1.0000; status `HUMAN_REVIEW_GO`.

# 7. Novelty Audit

P (`NOVELTY_PASS_WITH_CAUTION`) is nearest to Xu et al. (2026), Yu, Niu & He (2026), and Kotte (2026). Its remaining possible difference is known-DGP certification of scene-level effect claims against fixed δ0 and precomputed δ1 with false-mechanistic-claim control and explicit invalid states.

M (`NOVELTY_PASS_WITH_CAUTION`) is nearest to Parikh (2026), Chen, Qu & Wang (2026), Usman (2026), and Song et al. (2026). Only fixed-truth VLM cross-contract measurement equivalence remains potentially different; syntax/semantics decomposition and schema constraints are not novel.

U (`NOVELTY_PASS`) is nearest to established principal-stratification/IV work plus Bronder (2026) and Li & Liu (2026). Only known-potential-state calibration of encouragement-based multimodal uptake with correct point/partial/non-identification decisions remains potentially different. No generic SESOI, conformal, JSON-schema, principal-stratification, IV, or bounds ingredient is claimed as novel.

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
| Human | independent reviewer count | 2 | 2 | PASS |
| Human | fact-equivalence agreement | ≥0.95 | 1.00 | PASS |
| Human | Cohen's κ | ≥0.80 | 1.00 | PASS |
| Human | critical semantic mismatch | 0 | 0 | PASS |
| Human | minimum decoy detection | ≥0.90 | 1.00 | PASS |
| Human | model/agent used as reviewer | false | false | PASS |

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

Selected: `P`. M was not selected because it is NO-GO; U was not selected because it is NO-GO. At most one direction is selected.

# 11. Claim Boundary

P is known-DGP methodology. M is development measurement/engineering. There is no post-STOP real-VLM scientific evidence and no internal-mechanism evidence.

# 12. Exact Next Action

`PREREGISTER_POWER_CALIBRATED_MINI_PILOT`
