# P Mini-Pilot Paired Power Analysis

Status: **FEASIBLE; retain N=768**. This analysis uses paired base-scene outcomes, not
two independent Bernoulli samples. For paired difference D in {-1,0,1},
`E[D]=p10-p01` and `Var(D)=p10+p01-(p10-p01)^2`.

The preregistered plausible discordance region is 0.15-0.25. It contains the frozen
known-DGP variance assumption (variance 0.16 corresponds to discordance 0.1825 at
effect 0.15). Discordances 0.35, 0.50, and 1.00 are reported as stress cases, not used
to redefine delta1 or the plausible region after results.

## N=768 at the certification alternative

| Discordance | p10 | p01 | Analytic power | MC power | Gray | CI coverage |
|---:|---:|---:|---:|---:|---:|---:|
| 0.15 | 0.150 | 0.000 | 0.9726 | 0.9843 | 0.0157 | 0.9452 |
| 0.25 | 0.200 | 0.050 | 0.8277 | 0.8332 | 0.1668 | 0.9494 |
| 0.35 | 0.250 | 0.100 | 0.6777 | 0.6791 | 0.3209 | 0.9499 |
| 0.50 | 0.325 | 0.175 | 0.5181 | 0.5207 | 0.4791 | 0.9500 |
| 1.00 | 0.575 | 0.425 | 0.2883 | 0.2803 | 0.7184 | 0.9513 |

Minimum analytic power within the plausible region: **0.8277**.
The certification false-positive probability at the boundary effect delta0 is
0.025 analytically. Monte Carlo false-positive estimates, gray-zone probabilities,
95% Wald-CI coverage, and ordinary one-sided minimum-effect rejection probabilities
are frozen for every feasible effect x discordance x N cell in the YAML artifact.

Stress cases show why the paired discordance assumption matters: high discordance can
make N=768 underpowered even when the mean effect is 0.15. They do not trigger an N
increase because they are outside the prospectively declared plausible region.
Neither delta0 nor delta1 is changed.

## Resource decision

The design requires at most 46,080 candidate scores with sequential checkpoint loading.
The conservative local budget is 18 GPU-hours on the preflighted RTX 3060 Laptop GPU.
No sample-size increase is required, so N=768 remains within the frozen engineering
envelope. This resource estimate does not authorize model execution.
