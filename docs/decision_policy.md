# Decision Policy

The audit uses preregistered intersection–union gates. `VALID_BEHAVIORAL_EFFECT` requires all
of measurement validity, independent uptake, effect above SESOI, contract replication, format
stability, and identification-boundary gates. One significant check is never sufficient.

The required scalar `decision` uses the following precedence for calibration scoring:

1. `INVALID_MEASUREMENT` for failed parser/mapping/contract-validity gates.
2. `FORMAT_DEPENDENT` for a material or sign-changing format interaction after exact
   programmatic fact equivalence passes. Failed equivalence forces `INCONCLUSIVE`.
3. `INVALID_INTERVENTION` for failed independent uptake.
4. `MODEL_SPECIFIC` for failed preregistered family replication.
5. `VALID_BEHAVIORAL_EFFECT` only after every mandatory gate passes.
6. `PARTIALLY_IDENTIFIED` when the target is E5 and only bounds are supported.
7. `INCONCLUSIVE` otherwise, including uptake success without downstream effect.

This scalar never suppresses parallel `scope_flags`, `identification_status`, or the full gate
vector. A result may be format-dependent and partially identified even when its primary validity
decision is invalid or inconclusive.

For calibration systems the decision additionally reports a trusted diagnostic subtype. This
distinguishes parser/option mapping from final-output corruption without claiming that the same
stage is observable in real VLMs.

Reported changes distinguish sign reversal, magnitude reversal, significance downgrade, scope
downgrade, and inconclusive conversion. A loss of `p<.05` alone is a significance downgrade.
