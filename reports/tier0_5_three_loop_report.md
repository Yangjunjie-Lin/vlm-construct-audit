# Tier 0.5 three-loop adjudication

Final decision: **STOP_FOR_METHOD_FAILURE**. The preregistered three-model scientific Pilot remains
**NOT_AUTHORIZED**.

## Repository boundary

ReCoAlign remained archived and unchanged. The canonical public main is
`3e9a81432e83d651db59bf4d9a337984db7cf0fc`, the local read-only checkout is
`e200921af44e9307c60f470c247f808a75e7d625`, and the evidence-freeze commit is
`a80882071a6cf17c275453319d78d879c1546e3a` tagged
`recoalign-evidence-freeze-2026-08-25`. No Tier 0.5 result was written there.

## Loop results

- Loop A: `LOOP_A_NO_GO`. Overall sensitivity reached 0.8233, but non-strong macro sensitivity was 0.7900 and frozen-grid GO fraction was 0.5000.
- Loop B: `LOOP_B_AUTOMATED_GO_HUMAN_PENDING`. Automated clustered measurement gates passed; two independent human reviewers are still required.
- Loop C: `LOOP_C_NO_GO`. Three real checkpoints loaded and ran visual forwards, but parser-valid rates were [0.0, 0.0, 0.15] against 0.98.

## Gate table

| Gate | Value | Status |
|---|---|---|
| Loop A known-valid sensitivity >= 0.80 | `0.8233333333333334` | PASS |
| Loop A known-invalid specificity >= 0.95 | `1.0` | PASS |
| Loop A FMCR <= 0.05 | `0.0` | PASS |
| Loop A coverage >= 0.90 | `0.9616666666666667` | PASS |
| Loop A Type-S <= 0.05 | `0.0` | PASS |
| Loop A abstention <= 0.40 | `0.22833333333333333` | PASS |
| Loop A not driven by strong tier | `0.79` | FAIL |
| Loop A stable across frozen grid | `0.5` | FAIL |
| Loop B scene-cluster lower >= 0.98 | `0.9851329607687279` | PASS |
| Loop B two-way lower >= 0.98 | `0.9817246596448638` | PASS |
| Loop B cross-scorer ranking = 1 | `1.0` | PASS |
| Loop B parser recall/rejection >= 0.99 | `[1.0, 1.0]` | PASS |
| Loop B canonical fact equality = 1 | `1.0` | PASS |
| Loop B two independent human reviewers | `0` | PENDING |
| Loop C three checkpoint loads | `3` | PASS |
| Loop C three visual forwards | `3` | PASS |
| Loop C artifact completeness = 1 | `[1.0, 1.0, 1.0]` | PASS |
| Loop C parser-valid >= 0.98 | `[0.0, 0.0, 0.15]` | FAIL |
| Loop C independent scorer = 1 | `[1.0, 1.0, 1.0]` | PASS |
| Loop C determinism >= 0.99 | `[1.0, 1.0, 1.0]` | PASS |
| Remote successor available | `git@github.com:Yangjunjie-Lin/vlm-construct-audit.git` | PASS |
| All three loops GO | `['LOOP_A_NO_GO', 'LOOP_B_AUTOMATED_GO_HUMAN_PENDING', 'LOOP_C_NO_GO']` | FAIL |

## Claim boundary

Allowed: known-DGP methodological operating characteristics; automated measurement-engineering
results; and pinned-checkpoint load, visual-forward, scorer, parser, determinism, VRAM, RAM, latency,
and artifact-integrity results. Prohibited: real-VLM evidence uptake, compositional reasoning,
correct-versus-corrupted effects, cross-family scientific replication, claim reversal, semantic
sufficiency, or any internal mechanism. The real-VLM scientific result is `NOT_EXECUTED`.

## Failed and pending work

Loop A failed after the one permitted repair; another repair or holdout run is forbidden. Loop B
human review is pending. Loop C parser integrity failed for every family. Real-image transport was
not executed. The successor remote is public, but no formal Pilot preregistration is authorized.

## Exact next action

`STOP_FOR_METHOD_FAILURE`
