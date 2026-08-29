# P Mini-Pilot Execution Boundary

Preregistration validation, deterministic data generation, canonical serialization checks,
tokenizer-length balance, source hashing, and scorer engineering checks are allowed. They must not
produce reasoning-test model responses, correct-versus-corrupted scientific outcomes, real-model
effect estimates, or P3 real-model certification decisions.

The command `python -m vlm_construct_audit run-p-mini-pilot` is fail-closed. It remains blocked
unless `research/authorization/p_mini_pilot_independent_audit.yaml` exists and validates all of:

- `status: PASS`;
- audited preregistration tag and commit;
- auditor identity and audit date;
- preregistration, method-lock, model-registry, and data-manifest hashes;
- explicit authorization scope.

This preregistration task cannot create that file or name itself as the independent auditor. CI
must validate artifacts without downloading model weights or executing a visual forward pass.

Formal prediction, output, result, and scientific-metric directories are forbidden before the
audit authorization. The no-inference verifier scans both forbidden paths and textual markers in
JSONL, YAML, CSV, and log files. Any detected scientific outcome invalidates preregistration
readiness.
