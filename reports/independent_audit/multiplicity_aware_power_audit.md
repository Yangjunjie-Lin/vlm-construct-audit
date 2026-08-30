# Multiplicity-Aware Stable-Path Power Audit

## Result

The repository's marginal cell power is not the Mini-Pilot's overall power. Stable Certification
requires Holm support across six cells and both serializations in at least two families. N=768 does
not provide 80% Stable-Path power throughout even the frozen 0.15–0.25 discordance region.

The independent simulation used 50,000 draws per scenario from the joint asymptotic distribution
of the six paired estimators. It crossed within-family cross-serialization correlation
0.00/0.25/0.50/0.75/0.90 with between-model correlation 0.00/0.25/0.50. Uptake was assumed to pass
in all cells, so the results are optimistic with respect to the full gate.

At a representative dependence setting (within=0.50, between=0.25):

| Marginal effects | d | Mean unadjusted cell power | Mean Holm cell power | Family pass probabilities | Stable Path |
|---|---:|---:|---:|---|---:|
| all six 0.15 | 0.15 | 0.9728 | 0.9586 | 0.934 / 0.933 / 0.935 | 0.9525 |
| all six 0.15 | 0.25 | 0.8272 | 0.7159 | 0.612 / 0.611 / 0.611 | 0.6091 |
| all six 0.15 | 0.35 | 0.6773 | 0.4995 | 0.371 / 0.372 / 0.367 | 0.3388 |
| all six 0.15 | 0.50 | 0.5178 | 0.3175 | 0.198 / 0.199 / 0.197 | 0.1563 |
| two families 0.15, third 0 | 0.15 | 0.6489 | 0.6167 | 0.877 / 0.877 / 0 | 0.7930 |
| two families 0.15, third 0 | 0.25 | 0.5517 | 0.4352 | 0.516 / 0.517 / 0 | 0.3433 |
| two families 0.18, third 0 | 0.35 | 0.6501 | 0.6210 | 0.886 / 0.887 / 0 | 0.8077 |
| heterogeneous 0.15 / 0.18 / 0.25 | 0.50 | 0.8077 | 0.7496 | 0.319 / 0.727 / 1.000 | 0.7448 |

For all-six=0.15 at d=0.25, Stable-Path power ranged from 0.5479 to 0.7074 over the requested
dependence grid. For two active families at 0.15 and a null third family, d=0.25 power ranged from
0.2284 to 0.4736. Even at the lowest feasible discordance d=0.15, the latter scenario ranged from
0.7531 to 0.8427. The 0.18 scenario is mathematically infeasible at d=0.15, as is the heterogeneous
scenario containing 0.25 effects.

The leave-one-family-out pooling weight is not frozen. The artifact reports equal-cell and
inverse-paired-variance sensitivity; this ambiguity did not materially drive the positive-effect
scenarios, but it prevents unique future code from implementing the registered condition.

Decision on this dimension: `AUDIT_CONDITIONAL_PREINFERENCE_AMENDMENT`. A v2 would have to state
explicitly that the existing table is cell-level only, add this multiplicity/replication-aware
analysis, freeze the pooling rule, and avoid claiming 80% overall power. Because the current data
construct fails, those amendments alone cannot authorize the frozen experiment.
