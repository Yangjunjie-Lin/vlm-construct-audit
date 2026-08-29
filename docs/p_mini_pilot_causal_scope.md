# P Mini-Pilot Causal Scope

The randomized unit is the synthetic base scene, and both evidence conditions are evaluated for
the same scene. The intervention contrast is correct supplied relational evidence minus a
target-specific corruption that preserves the evidence form while changing the target fact.

For model `m` and serialization `f`, the estimand is:

`theta[m,f] = E[Y(correct evidence) - Y(corrupted evidence)]`,

where `Y` equals one when the length-normalized conditional-likelihood scorer ranks the correct
semantic answer first. This is an intention-to-treat behavioral effect under the frozen protocol.
It is not an effect of a measured latent uptake state and does not identify an internal reasoning
mechanism.

Independent uptake validation is a construct-validity gate. It determines whether a complete
model-by-serialization cell is eligible for a supplied-evidence interpretation; it never filters
individual reasoning scenes. A failed cell remains in the ITT report and receives
`UPTAKE_NOT_ESTABLISHED` or `INVALID_INTERVENTION` rather than being deleted.

The target population is exactly the three frozen checkpoints, two frozen serializations, frozen
synthetic generator, candidate set, image renderer, evidence operators, and conditional-
likelihood contract. No inference is licensed for all VLMs, other model sizes, API models, other
serializations, free-generation contracts, real images, or distribution shifts.
