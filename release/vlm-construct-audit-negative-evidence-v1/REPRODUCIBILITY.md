# Reproducibility

Use Python 3.10 or later. No model weights are needed or permitted for this closeout.

```bash
git clone https://github.com/Yangjunjie-Lin/vlm-construct-audit.git
cd vlm-construct-audit
git checkout vlm-construct-audit-final-closeout-2026-08-30
python -m pip install -e ".[dev]"
pytest
ruff check .
python -m vlm_construct_audit verify-artifacts
python -m vlm_construct_audit verify-post-stop-artifacts
python -m vlm_construct_audit verify-frozen-p-mini-pilot-preregistration-read-only
python -m vlm_construct_audit validate-construct-v2
python -m vlm_construct_audit verify-no-construct-v2-inference
python -m vlm_construct_audit audit-final-review-integrity
python -m vlm_construct_audit build-final-successor-adjudication
python -m vlm_construct_audit build-final-negative-evidence-release
python -m vlm_construct_audit verify-final-closeout
```

`verify-final-closeout` verifies this package's SHA-256 file list, all historical tags, preserved
review returns and attestations, the absent candidate and authorization artifacts, the blocked
runner, and zero formal Direction P v2 outputs. Re-running deterministic builders must leave the
tagged working tree clean. CI success means software and record consistency, not scientific
validation.
