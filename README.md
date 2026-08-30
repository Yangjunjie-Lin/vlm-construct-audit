# VLM Construct Audit

Frozen negative-evidence and research-governance resource for validity-aware auditing of
behavioral claims in vision-language models.

This repository is independent from the archived ReCoAlign repository. Tier 0 is a
known-state engineering and calibration exercise; it is not evidence about real VLMs.

## Final status

`TERMINATE_SUCCESSOR_PROGRAM`. Directions M and U are NO-GO. Direction P v1 failed
independent construct-validity audit. Direction P v2 did not obtain a human review capable of
authorizing scientific execution; its final integrity classification is
`REVIEW_INTEGRITY_INCONCLUSIVE`. Formal Direction P v2 VLM inference count is zero.

The P known-DGP result remains controlled methodological calibration only. It does not validate a
real-VLM effect or internal mechanism. This repository is not a successful method, a benchmark
leaderboard, or authority for further experiments or claim-bearing paper writing.

## Closeout verification

```bash
python -m pip install -e ".[dev]"
pytest
ruff check .
python -m vlm_construct_audit verify-final-closeout
```

The canonical resource is `release/vlm-construct-audit-negative-evidence-v1`. Its checksums and
artifact manifest are verified by the final closeout command. CI success establishes software and
record consistency only; it is not scientific validation.
