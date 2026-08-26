# Estimands

All expectations are over the explicitly named eligible scene/model/task/format population.

## E1 — Behavioral ITT

`E[S(A=correct) - S(A=corrupted)]`, estimated by scene-paired risk difference. No sample is
removed according to its observed uptake answer. The primary corruption contrast pools only
the preregistered target-specific operators; matched irrelevant and plausible contradictory
remain named secondary contrasts.

## E2 — Measurement Contract Effect

For a fixed scene and, when possible, a frozen response `O`, E2 is the difference in the
conclusion induced by two legal measurement operators. A comparison that changes decoding is
reported as an elicitation-plus-measurement effect, not a pure measurement effect.

## E3 — Format Effect

At equal programmatic fact sets, E3 is the paired difference in uptake and downstream score
between natural-language and triple serialization. It is conditional on the equivalence audit;
failed equivalence makes E3 ineligible.

## E4 — Validated-Cell Effect

E4 is E1 within a predeclared `model × task × format` cell whose measurement and uptake gates
pass on the independent `uptake_validation` split before the `reasoning_test` split is read.
E4 is not a population ATE and must not be extrapolated to failed or untested cells.

## E5 — Latent Uptake-Capable Effect

E5 is a principal-stratum effect defined by joint potential uptake states, never by filtering
on observed uptake. With imperfect uptake proxies and no exclusion/monotonicity guarantees it
is not point identified. Tier 0 reports conservative outcome-support bounds; sensitivity rows
may tighten them under preregistered proxy sensitivity/specificity and monotonicity ranges.
The result is labelled `PARTIALLY_IDENTIFIED` unless the identifying assumptions are defended.

