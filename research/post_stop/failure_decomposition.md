# Frozen Failure Decomposition

The decomposition records why three independent hypotheses are admissible without repairing the
failed method.

## Historical facts

- AuditV2: `LOOP_A_NO_GO`. At N=384, overall sensitivity was 0.8233, non-strong macro sensitivity
  was 0.7900, ValidBoundaryEffect sensitivity was 0.1000, and only 0.5000 of the frozen threshold
  grid retained GO. Its single repair was consumed and its holdout was run once.
- Loop B: automated `GO`; human review `PENDING`. Automated measurement checks do not substitute
  for two independent human reviewers.
- Loop C: `LOOP_C_NO_GO`. All three pinned checkpoints loaded and performed visual forwards, but the
  prompt-only exact-JSON condition had parser-valid rates 0.00, 0.00, and 0.15. In post-STOP
  provenance this historical condition is named `historical_prompt_only_exact_json`; it was not
  token-level constrained decoding.
- Formal three-model scientific Pilot: `NOT_AUTHORIZED` and not executed.
- Exact Tier 0.5 action: `STOP_FOR_METHOD_FAILURE`.

## Independent questions

Direction P tests whether an effect-certification design with the unchanged scientific SESOI
δ0=0.10 can have realistic power at a precomputed certification alternative δ1 while controlling
false claims. It does not alter AuditV2 or reinterpret its result.

Direction M tests whether conditional likelihood, true token-level constrained JSON, prompt-only
JSON, and deterministic canonicalization measure the same semantic response on new scenes. It does
not relabel historical prompt-only generation as constrained decoding.

Direction U tests known-DGP identification of uptake as a post-treatment or latent compliance
variable. It does not infer principal strata or real-VLM causal effects from historical cells.

The directions may fail independently. Their most favorable pieces may not be combined after
seeing results, and failure of all three terminates the successor program rather than creating a
fourth diagnostic direction.
