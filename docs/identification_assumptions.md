# Identification Assumptions

## E1

Scene-paired intervention assignment is deterministic from a recorded seed; all conditions are
generated for every scene. Consistency requires that each serialized evidence package matches
its recorded condition. No interference is assumed across independent inference calls. The
estimand remains conditional on the frozen models, prompts, contracts, and scene generator.

## E2

A pure measurement-contract effect requires the same frozen `O`. If contracts change `E` or
decoding, the contrast is not identified as measurement alone and is explicitly relabelled.
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

Observed uptake is post-treatment. Direct conditioning creates selection bias. Point
identification would require strong assumptions about proxy error, monotonicity, exclusion, and
principal-stratum membership that Tier 0 does not assert. Bounds and sensitivity analyses keep
the uncertainty visible.

General internal-mechanism claims additionally require interventions on internal variables,
faithful localization, alternative-mechanism controls, and cross-setting invariance. Those
requirements are outside this behavioral input-output design.

