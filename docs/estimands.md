# Estimands

All expectations are over the explicitly named eligible scene/model/task/format population.

## E1 — Behavioral ITT

For fixed `(F,E,M)` and intervention version `K`, the scene-paired contrast is
`E[S_Y(A=correct,K=identity) - S_Y(A=corrupted,K=k)]`. The primary standardized E1 uses
equal weights over `relation_flip`, `entity_swap`, and `attribute_swap`; operator-specific
effects are always retained. Matched irrelevant and plausible contradictory are named secondary
contrasts. No sample is removed according to `U_tilde`.

## E2 — Measurement Contract Effect

For a fixed scene and frozen response/logit record `O`, E2 is the difference in the conclusion
induced by two legal scoring operators `M`. Conditional likelihood versus constrained generation
changes `E` and produces different `O`; its kappa is response-contract robustness, not pure E2.

## E3 — Format Effect

At equal programmatic fact multisets, the primary downstream E3 is the interaction
`[S_Y(correct,NL)-S_Y(corrupted,NL)] - [S_Y(correct,triples)-S_Y(corrupted,triples)]`.
The uptake interaction is defined analogously with `U_tilde`. Raw format score differences are
descriptive. Failed equivalence makes E3 ineligible and forces `INCONCLUSIVE`; it cannot produce
`FORMAT_DEPENDENT`. Format stability is tested with TOST on the interaction.

## E4 — Validated-Cell Effect

E4 is E1 within predeclared candidate `model × task × format` cells selected by a frozen
lower-confidence-bound evidence-tracking gate on `uptake_validation` before `reasoning_test` is
read. It is an effect conditional on the gate procedure's selected random set, not a
principal-stratum effect or population ATE. E1 for every cell is still reported, and E4 must not
be extrapolated to failed or untested cells.

## E5 — Latent Uptake-Capable Effect

For binary latent evidence tracking, define the always-uptake stratum
`G=(U*(1),U*(0))=(1,1)` and `E5=E[S_Y(1)-S_Y(0) | G=(1,1)]`, fixing format and uptake
elicitation/measurement. Other strata are `(0,0)`, `(1,0)`, and `(0,1)`. E5 is never estimated
by filtering on `U_tilde`. With binary outcomes and no stratum-membership assumptions, the
outcome-support bounds are `[-1,1]`. Proxy sensitivity/specificity grids can narrow compatible
sets in sensitivity analysis; no monotonicity direction is scientifically asserted because
correctness need not determine whether evidence is read. The result remains
`PARTIALLY_IDENTIFIED` unless additional assumptions are separately defended.
