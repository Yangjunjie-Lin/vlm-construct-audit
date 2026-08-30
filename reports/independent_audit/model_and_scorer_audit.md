# Model and Scorer Engineering Audit

## Official checkpoint identity

The official Hugging Face model API resolved all three exact revisions on 2026-08-30. Each
resolved SHA equals the frozen revision, and the official LFS SHA-256 records equal the frozen
weight hashes. Official card metadata reports Apache-2.0 for SmolVLM, MIT for InternVL2.5, and
Apache-2.0 for Qwen2-VL. Processor and tokenizer revisions equal the model revision in all three
registry entries. Dtype, int8/no-quantization choices, Transformers 4.49.0, device placement, and
`trust_remote_code` are frozen.

## Existing scorer source

The historical engineering worker passes images to both standard processor paths and InternVL's
`pixel_values` path. It checks that the base token IDs are an exact prefix of the candidate-
extended IDs, scores every candidate token with the correct one-token shift, sums raw log
likelihood, and length-normalizes over the full multi-token candidate span. A NumPy log-softmax
recomputation agrees with Torch rankings in the historical artifacts for all three exact
checkpoints, and the historical deterministic rerun agreement is 1.00.

That evidence is useful but not sufficient for Mini-Pilot execution readiness:

- The checkout has no Mini-Pilot renderer, prompt builder, candidate mapper, artifact writer, or
  runner. `run-p-mini-pilot` correctly returns
  `AUTHORIZED_AUDIT_VALID_BUT_SCIENTIFIC_RUNNER_NOT_BUNDLED` after a valid authorization.
- The historical worker breaks exact score ties by candidate input order. The frozen Mini-Pilot
  policy requires stable lexical `candidate_id` order.
- The so-called independent scorer performs an independently coded log-softmax on the same
  forward logits and token boundaries. It is not an independent model-input/forward path and
  cannot detect omission of the image or a shared prompt-boundary error.
- The runtime prefix assertion is fail-closed, but no Mini-Pilot-specific prompt has yet shown that
  `ANS_REL_*` and other multi-token candidate strings preserve the required prefix on all three
  tokenizers.
- No images for the 12 Mini-Pilot engineering-smoke records are frozen, and the named
  `p_mini_flat_shapes_v1` renderer is not implemented. An audit-only implementation would make
  this preregistration auditor the runner implementer, which the audit charter forbids.

Therefore checkpoint availability and generic CLL feasibility pass, but the Mini-Pilot scorer
execution gate is `CONDITIONAL_PREINFERENCE_AMENDMENT_REQUIRED`. A separate runner branch must
implement the frozen design, lexical tie-break, truly independent cross-check, image rendering,
and the 12-scene engineering smoke, followed by a second execution-readiness audit. Neither formal
split was sent to a model in this audit.
