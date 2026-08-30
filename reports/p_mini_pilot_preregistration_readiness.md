# P Mini-Pilot Preregistration Readiness

## Decision

`PREREGISTRATION_COMPLETE_NO_INFERENCE`

The package is ready to be frozen and submitted to an independent preregistration auditor. It
does not authorize, start, or implement scientific VLM inference.

## Historical integrity

The source branch and remote both resolved to
`f993282e0a27b8da0ba1c239fb96715c9fc5b79a` before work began. AuditV2 remains
`LOOP_A_NO_GO`; the old Loop A holdout was not rerun; the Direction P known-DGP holdout remains a
single execution; Directions M and U remain NO-GO; human adjudication is unchanged; ReCoAlign is
unchanged. The Tier 0.5 tag still resolves to `ce0e797a4926ab5d2309915c2eef14fd9c5be44d`,
and the Post-STOP final tag freezes the source commit.

## Novelty

Cutoff is 2026-08-30. The nearest works are Answer-Level Trust Selection, Budgeted Conformal
Evidence Acquisition, structured-generation conformal risk-control feasibility, and EviSafe.
No located work meets the complete registered collision conjunction. The decision remains
`NOVELTY_PASS_WITH_CAUTION`; the only candidate contribution is the prospective, known-DGP-
calibrated application of power-calibrated behavioral claim certification across multiple
open-weight VLM families.

## Frozen design

- Models: SmolVLM-256M-Instruct at `7e3e67e…`, InternVL2_5-2B at `573169e…`, and
  Qwen2-VL-2B-Instruct at `895c3a4…`.
- Scenes: 960 formal base scenes, split into 192 uptake-validation and 768 reasoning-test scenes;
  12 separate engineering-smoke scenes.
- Primary construct: two-hop directed relation composition.
- Intervention: correct relational evidence versus target-specific grammatical corruption.
- Serializations: natural language and triples only.
- Endpoint: length-normalized candidate conditional likelihood with independent ranking agreement
  required to equal 1.00.
- Estimand: scene-paired behavioral ITT within each model-by-serialization cell.
- Thresholds: `delta0=0.10`, `delta1=0.15`; the open interval is an indifference zone.

All four uptake tasks contain 48 scenes. The gate is a scene-level one-sided 95% exact lower
bound of at least 0.80 at the model-by-serialization level. Individual-scene uptake filtering is
forbidden. Failed cells remain in the complete ITT report but cannot receive a validated supplied-
evidence interpretation.

## Balance and power

Canonical serialization equality is 1.00. Across the three frozen tokenizers and two
serializations, the maximum correct/corrupted token-length difference is 0; no scene was excluded.

Power uses the paired joint outcomes p10 and p01. In the preregistered plausible discordance
region 0.15-0.25, N=768 has minimum analytic power 0.8277 at effect 0.15. Boundary false-positive
probability is 0.025 analytically. Higher discordances are retained as transparent stress tests
and do not change delta1 or the sample size decision.

## Decision policy

Stable Certification requires at least two families to pass uptake and obtain Holm-supported P3
certification in both serializations, without a certified reverse effect or single-format driver.
Audit-Value Certification is evaluated only if Stable Certification fails and requires at least
two independent, artifact-free claim-scope downgrades consistent with the known-DGP P3 logic.
Neither path identifies an internal mechanism. Any registered NO-GO condition ends the successor
program without model, prompt, threshold, serialization, or dataset rescue.

## Verification status

- Full pytest: PASS.
- Full `ruff check .`: PASS.
- Historical artifact verification: PASS.
- Post-STOP artifact verification: PASS.
- Preregistration validation: PASS.
- Preregistration hash verification: PASS against the pre-tag 45-file aggregate manifest.
- No-inference verification: PASS; predictions 0, reasoning outputs 0, scientific metrics 0,
  run command blocked.
- CI: configured to install normal/dev dependencies, run all three preregistration checks, and
  never download or execute formal model weights.
- Fresh clone: PASS at `fa68091684504e780857da640d7027c745d416a3` using a new remote clone
  and external Python 3.12 venv. Installation, 68 passed tests with 2 optional model-stack skips,
  ruff, historical artifact verification, read-only Post-STOP verification, preregistration
  validation and hashes, no-inference validation, and the blocked run-command check all passed;
  the clone remained Git-clean.

## Researcher degrees of freedom

Current preregistration amendments: none. Model replacements: none. Pre-inference scene
exclusions: none. Scientific deviations: none. Failed scientific runs: none. Six failed pre-tag
validation attempts are recorded in the deviation policy. They concerned new-code hygiene,
timestamp-preserving read-only verification, an optional-dependency import, test isolation, and
cross-checkout LF normalization. None involved scientific model output or changed any numerical
or scientific design element.

## Exact next action

`AWAIT_INDEPENDENT_PREREGISTRATION_AUDIT`
