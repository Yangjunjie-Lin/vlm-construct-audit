# Post-STOP Direction P

Decision: **DIRECTION_P_GO** on the single sealed known-DGP holdout. This is methodological
evidence only; it does not authorize a real-VLM Pilot or identify an internal mechanism.

## Analytic power and frozen design

The scientific SESOI remained δ0=0.10. Before any Direction P simulated outcome, the paired
scene-level variance was fixed at 0.16, one-sided certification α at 0.025, and feasible maximum N
at 768. The smallest two-decimal alternative meeting 80% analytic power was δ1=0.15; its analytic
certification probability was 0.9337. The predeclared indifference interval (0.10, 0.15) is neither
success nor failure: it means the design does not certify a positive effect claim at the target
error rate.

## Sealed holdout

The holdout used 14 new families × four sample sizes × 100 repetitions, new seed and template
namespaces, new corruption patterns, and new entity mappings. The primary N was 768. No historical
Loop A outcome was used for method or threshold selection, and the old holdout was not rerun.

| Method | FMCR | specificity ≤δ0 | sensitivity ≥δ1 | gray overclaim | coverage | Type-S | abstention |
|---|---:|---:|---:|---:|---:|---:|---:|
| P0 frozen AuditV2 adapter | 0.000 | 1.000 | 0.704 | 0.000 | 1.000 | 0.000 | 0.463 |
| P1 ordinary minimum-effect | 0.000 | 1.000 | 1.000 | 0.000 | 1.000 | 0.000 | 0.286 |
| P2 three-way certification | 0.000 | 1.000 | 1.000 | 0.000 | 1.000 | 0.000 | 0.000 |
| P3 selective risk/coverage | 0.000 | 1.000 | 1.000 | 0.000 | 1.000 | 0.000 | 0.000 |

P3 emitted an explicit indifference-zone result for 14.57% of all datasets; those outputs were
not counted as ordinary false negatives or as positive claims. Its Type-M ratio was 1.0023.

All four registered non-strong families—CertificationBoundaryEffect, ModerateEffect,
HeterogeneousEffect, and StochasticUptakeITT—had sensitivity 1.00. Thus the result did not depend
on the StrongEffect family. Across the preregistered critical-z values 1.81, 1.96, 2.05, and 2.17,
FMCR remained 0, sensitivity remained 1, gray-zone overclaim remained 0, and the decision stayed
within the registered operating region.

Against the frozen AuditV2 adapter on the same new holdout datasets, P3's paired sensitivity gain
was 0.296 (95% CI 0.256–0.336) while FMCR did not worsen. This is a frozen-baseline comparison, not
a repair or reinterpretation of AuditV2.

## Researcher degrees of freedom

One development-only revision was consumed. The initial development summary incorrectly allowed a
development split to emit `DIRECTION_P_GO`; the numeric results, seeds, families, δ0, δ1, methods,
and gates were unchanged. The initial attempt is preserved under
`artifacts/post_stop/direction_p/development_initial_attempt/`. The revised control flow restricted
GO/NO-GO to the holdout split, after which the method was frozen. There were no holdout revisions,
exclusions, failures, or reruns.

## Guarantee boundary

P3's analytic/selective control assumes exchangeability only within each registered family,
sample size, split, and frozen generator. Development and holdout have disjoint seed namespaces.
No finite-sample guarantee is claimed across family mixtures, generator changes, threshold tuning,
distribution shift, or real VLMs. The result does not establish evidence uptake or an internal VLM
mechanism.
