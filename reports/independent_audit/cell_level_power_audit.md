# Independent Cell-Level Power Audit

## Result

`PASS` for the frozen marginal cell-level implementation. This does not establish power for the
six-cell Stable Certification Path.

The independent implementation used the paired ternary outcome
`D ∈ {-1,0,1}`, with `theta = p10 - p01`, `d = p10 + p01`, and
`Var(D) = d - theta²`. It recomputed all 175 requested effect × discordance × N combinations using
an analytic normal approximation and 100,000 independent multinomial repetitions per feasible
cell. It also exactly summed the finite-sample multinomial law for the frozen plug-in-Wald rule at
N=768 for effects 0.10 and 0.15, and evaluated a paired percentile-bootstrap rule.

## N=768 at `delta1=0.15`

| Discordance | Analytic | Monte Carlo | Exact frozen-Wald | Bootstrap behavior | MC gray | Wald CI coverage |
|---:|---:|---:|---:|---:|---:|---:|
| 0.15 | 0.9726 | 0.9832 | 0.9836 | 0.9933 | 0.0168 | 0.9424 |
| 0.25 | 0.8277 | 0.8321 | 0.8312 | 0.8567 | 0.1679 | 0.9505 |
| 0.35 | 0.6777 | 0.6801 | 0.6785 | 0.7167 | 0.3199 | 0.9493 |
| 0.50 | 0.5181 | 0.5164 | 0.5183 | 0.5733 | 0.4835 | 0.9490 |
| 1.00 | 0.2883 | 0.2831 | 0.2825 | 0.3100 | 0.7158 | 0.9519 |

Bootstrap entries are descriptive Monte Carlo behavior from 300 datasets with 999 paired
resamples each, not the frozen decision rule.

At the boundary `theta=delta0=0.10`, the analytic Type-I error is 0.025. Independent Monte Carlo
values across discordance 0.15, 0.25, 0.35, 0.50, and 1.00 were respectively 0.0224, 0.0252,
0.0262, 0.0257, and 0.0245. Exact finite-sample values were 0.0218, 0.0245, 0.0254, 0.0256, and
0.0244. The repository and independent grids agree within the prespecified numerical tolerance.

## Discordance plausibility

The range 0.15–0.25 is not independently established for real VLM paired outcomes. It is imported
from a known-DGP variance chosen inside a different synthetic generator. Real VLMs can plausibly
have `d=0.35–0.50`, where N=768 marginal power falls to 0.68–0.52. No formal outcome may be used
to defend the narrower range after the fact.

If this direction is restarted, a blinded internal discordance re-estimation may be valid only if
the procedure is frozen in advance, uses the condition-swap-invariant indicator that the two paired
binary outcomes differ, reports only `p10+p01`, and never exposes `p10-p01`, condition-labelled
marginals, or directional intermediate results. Such a procedure estimates variance without
directly revealing the treatment-effect direction, but it still requires a new preregistration.

Full results are in `artifacts/independent_audit/power_recalculation.yaml`.
