# Loop A: unseen-DGP generalization

Decision: **LOOP_A_NO_GO**. The one permitted development-only repair was frozen before
the one-pass holdout. The holdout was not rerun.

| N | A0 sensitivity | AuditV2 sensitivity | AuditV2 specificity | AuditV2 abstention |
|---:|---:|---:|---:|---:|
| 48 | 0.3250 | 0.3533 | 1.0000 | 0.3717 |
| 96 | 0.5317 | 0.6150 | 1.0000 | 0.2992 |
| 192 | 0.7117 | 0.7667 | 1.0000 | 0.2442 |
| 384 | 0.8033 | 0.8233 | 1.0000 | 0.2283 |

At N=384, AuditV2 sensitivity was 0.8233, specificity
1.0000, FMCR 0.0000, coverage
0.9617, Type-S 0.0000, Type-M 0.9921, and
abstention 0.2283. A0 sensitivity was 0.8033;
AuditV2 improved it by 0.0200.

The overall operating point passed, but the non-strong macro sensitivity was
0.7900, the ValidBoundaryEffect sensitivity was
0.1000, and only
0.5000 of the frozen sensitivity-grid cells retained
GO. Therefore the conclusion was driven too heavily by easier effect tiers and reversed under a
reasonable frozen gate grid. No second repair is permitted.

Evidence: `artifacts/loop_a/holdout/summary.yaml` (config hash
`b7b6f4fbf68a099282ce0ffb037540c8f59b29e2ae6243fa2850fe0301669e64`), `artifacts/loop_a/holdout/execution_marker.yaml`, and
`research/preregistration/audit_v2.yaml`.
