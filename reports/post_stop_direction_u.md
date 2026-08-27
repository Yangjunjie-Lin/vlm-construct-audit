# Post-STOP Direction U

Decision: **DIRECTION_U_NO_GO**. Development did not produce a complete numeric summary after the
one permitted revision, so the sealed holdout was not authorized or executed.

## Frozen identification design

The preregistration defined 12 known-potential-state DGPs, including AlwaysUptake, NeverUptake,
FormatComplier, InstructionComplier, Defier, PartialUptake, MeasurementMisclassifiedUptake,
HeterogeneousTreatmentEffect, exclusion-restriction violation, monotonicity violation, weak
encouragement, and a large defier population. Each DGP fixed Z, A, U0, U1, Y0, Y1, principal
stratum proportions, exclusion, monotonicity, measurement error, true ITT, target-stratum effect,
and identification status.

The six frozen methods were naive observed-uptake filtering (U0), full-population ITT (U1),
regression adjustment using observed uptake (U2), a principal-mixture estimator (U3), Wald IV
(U4), and registered assumption-sensitivity bounds (U5). The policy never used observed uptake to
select individual samples for a causal claim. Point estimates were allowed only in registered
point-identified, strong-first-stage settings; registered violation budgets led to
`PARTIALLY_IDENTIFIED`, and weak or unsupported settings led to `NOT_IDENTIFIED`.

## Development failure

Each attempt generated the registered 12×3×200 = 7,200 datasets in memory using new seeds. The
first attempt then failed when `statistics.mean` received a `numpy.bool_` in policy Type-S
aggregation; it emitted neither dataset results nor a summary. The one permitted development
revision converted that comparison to a built-in Boolean without changing any DGP, estimator,
seed, bound, threshold, or gate. The full rerun reached a second occurrence of the same type
compatibility problem in per-method Type-S aggregation.

Fixing the second occurrence would be another development repair. The protocol permits only one.
Consequently, no development bias, RMSE, coverage, FMCR, bound-width, or assumption-sensitivity
number is treated as evidence. Both traceback logs and execution markers are preserved. The
estimators and failure are frozen rather than repeatedly patched.

## Holdout and real-model boundary

The sealed holdout execution count is zero. Because known-DGP GO was not obtained, the optional
three-model, 20-scene feasibility smoke was also not authorized. There is no real-VLM uptake
probability result, causal effect, principal-stratum estimate, or internal-mechanism evidence.
