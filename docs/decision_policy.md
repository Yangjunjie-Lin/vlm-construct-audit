# Decision Policy

The audit uses preregistered intersection–union gates. `VALID_BEHAVIORAL_EFFECT` requires all
of measurement validity, independent uptake, effect above SESOI, contract replication, format
stability, and identification-boundary gates. One significant check is never sufficient.

Decision precedence is:

1. `INVALID_MEASUREMENT` for failed parser/mapping/contract-validity gates.
2. `FORMAT_DEPENDENT` for a material, non-equivalent or sign-changing format interaction.
3. `INVALID_INTERVENTION` for failed independent uptake.
4. `MODEL_SPECIFIC` for failed preregistered family replication.
5. `VALID_BEHAVIORAL_EFFECT` only after every mandatory gate passes.
6. `PARTIALLY_IDENTIFIED` when the target is E5 and only bounds are supported.
7. `INCONCLUSIVE` otherwise, including uptake success without downstream effect.

Reported changes distinguish sign reversal, magnitude reversal, significance downgrade, scope
downgrade, and inconclusive conversion. A loss of `p<.05` alone is a significance downgrade.

