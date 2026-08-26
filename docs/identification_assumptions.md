# Identification Assumptions

## E1

Scene-paired intervention assignment is deterministic from a recorded seed; all conditions are
generated for every scene. The multi-version treatment is indexed by `K`; the standardized
corrupted contrast uses frozen equal operator weights. Consistency requires that each serialized
package matches `(A,K)`. No interference is assumed across calls. The estimand remains conditional
on frozen models, prompts, contracts, and generator.

## E2

A pure measurement effect requires the same frozen `O`. Conditional likelihood versus constrained
generation changes `E`/decoding and is explicitly labelled response-contract robustness.
Candidate tokenization, option-to-semantic mapping, parser failures, and raw scores must be kept.

## E3

The two serializers must round-trip to an identical proposition multiset. Entity positions,
length, and lexical overlap are measured rather than assumed balanced. Residual familiarity or
tokenization differences are part of the format treatment, not controlled internal mechanisms.

## E4

Cell eligibility is frozen using only `uptake_validation`. No `reasoning_test` result may alter
the gate, prompt, corruption, SESOI, or threshold. Selection changes the target population and
does not license an overall ATE.

## E5

`U_tilde` is an imperfect post-treatment proxy for `U*`. Direct conditioning creates selection bias. Point
identification would require strong assumptions about proxy error, monotonicity, exclusion, and
principal-stratum membership that Tier 0 does not assert. Bounds and sensitivity analyses keep
the uncertainty visible.

General internal-mechanism claims additionally require interventions on internal variables,
faithful localization, alternative-mechanism controls, and cross-setting invariance. Those
requirements are outside this behavioral input-output design.
