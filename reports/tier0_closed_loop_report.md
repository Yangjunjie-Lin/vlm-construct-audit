# Minimum Closed-Loop Report

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
reporting, and verification. It uses 6912 predictions from
48 scenes and 1,800 measurement probes. No intermediate hand edit is required.

## 5. Calibration Performance

Expected claim classes recovered: **6/6**.

```json
{
  "FORMAT_DEPENDENT": {
    "FORMAT_DEPENDENT": 1
  },
  "INCONCLUSIVE": {
    "INCONCLUSIVE": 1
  },
  "INVALID_INTERVENTION": {
    "INVALID_INTERVENTION": 1
  },
  "INVALID_MEASUREMENT": {
    "INVALID_MEASUREMENT": 2
  },
  "VALID_BEHAVIORAL_EFFECT": {
    "VALID_BEHAVIORAL_EFFECT": 1
  }
}
```

Fixed-inventory B1 false claim rate was 0.200; B5 was 0.000. Repeated known-DGP B1/B5 rates were 0.600/0.000. Repeated-DGP sensitivity was 0.735, coverage 0.964, Type-S error 0.000, Type-M ratio 1.009, and abstention 0.229.

## 6. Benchmark Status

All interventions match fact, entity, relation, sentence, token-tolerance, and answer-option-
overlap constraints. NL/triples programmatic fact equivalence is `True` across 288 pairs. Independent human review remains `PENDING_INDEPENDENT_HUMAN_REVIEW`. Splits have disjoint scene and template IDs. A real-image license has not been established.

## 7. Statistical Status

The primary estimand is a scene-paired marginal risk difference standardized equally over three
target corruptions. Scene-cluster bootstrap is primary in Tier 0; the formal Tier-1 design freezes
model/family fixed effects and a scene random intercept, with an evidence random slope only if
identifiable. Threshold sensitivity covers 405 frozen combinations and
does not reverse the B5 advantage. E5 uses support bounds, not sample-level uptake filtering.
Holm and TOST procedures are implemented/frozen; no equivalence is inferred from non-significance.

## 8. Scientific Pilot Status

**NOT_AUTHORIZED.** No open-weight checkpoint was run. The seeded 33,104-parameter random BLIP
forward (PASS) tests engineering only. Three model
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

| Gate | Value | Status |
| --- | --- | --- |
| FMCR absolute reduction >= 0.10 | `0.6` | PASS |
| FMCR relative reduction >= 0.40 | `1.0` | PASS |
| FMCR improvement CI excludes zero | `[0.6, 0.6]` | PASS |
| Known valid sensitivity >= 0.80 | `0.735` | INCONCLUSIVE |
| Empirical CI coverage >= 0.90 | `0.96375` | PASS |
| Abstention <= 0.40 | `0.2288888888888889` | PASS |
| Measurement lower bound >= 0.98 | `0.9900639180555423` | PASS |
| Response-contract kappa >= .90 and lower >= .85 | `{"kappa": 1.0, "lower": 1.0}` | PASS |
| B5 outperforms B2/B3/B4 | `{"B1": 0.6, "B2": 0.6, "B3": 0.6, "B4": 0.4, "B5": 0.0}` | PASS |
| Real VLM material audit-change case | `NOT_EXECUTED` | NOT_EVALUABLE |
| Threshold advantage does not reverse | `0.2` | PASS |
| Not driven by one real model/family/template/operator | `NO_REAL_MODELS` | NOT_EVALUABLE |
