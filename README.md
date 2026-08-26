# VLM Construct Audit

Independent successor project for validity-aware auditing of behavioral claims in
vision-language models.

Working title: *Intervene Before You Infer: Validity-Aware Auditing for Behavioral
Claims in Vision-Language Models*.

This repository is independent from the archived ReCoAlign repository. Tier 0 is a
known-state engineering and calibration exercise; it is not evidence about real VLMs.

## Status

Tier 0 completed its executable loop with 48 scenes, six known-state systems, two
serializations, two response contracts, 6,912 predictions, and 1,800 measurement probes.
All six expected claim classes were recovered. The preregistered known-effect sensitivity
was 0.735, so Tier 0 is `INCONCLUSIVE` and the three-family scientific pilot is
`NOT_AUTHORIZED`. No real VLM result is claimed.

## Quick start

```bash
python -m pip install -e ".[dev]"
make minimum-loop
```

The total command builds and verifies data, predictions, metrics, reports, and SHA-256
manifests. Individual commands are available through `python -m vlm_construct_audit --help`.

`make scientific-pilot` intentionally fails closed until the Tier-0, model-freeze,
human-review, compute, and real-image license gates are satisfied.

Primary result: `reports/minimum_closed_loop_report.md`.
