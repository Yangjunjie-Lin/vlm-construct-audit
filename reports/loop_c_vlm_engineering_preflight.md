# Loop C: three-family real-checkpoint engineering preflight

Decision: **LOOP_C_NO_GO**.

| Family | Revision | Loaded | Visual forward | Parser-valid | Independent scorer | Determinism | Peak VRAM | Mean latency |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| SmolVLM-Idefics3 | `7e3e67edbbed1bf9888184d9df282b700a323964` | True | True | 0.0000 | 1.0000 | 1.0000 | 2.47 GiB | 2.230s |
| InternVL2.5-InternLM2 | `573169ee54df216786bb9a189e9a32a060a008cf` | True | True | 0.0000 | 1.0000 | 1.0000 | 3.13 GiB | 0.878s |
| Qwen2-VL | `895c3a49bc3fa70a340399125c650a463535e71c` | True | True | 0.1500 | 1.0000 | 1.0000 | 2.66 GiB | 1.025s |

All three official, pinned, non-tiny checkpoints loaded and completed 40 primary development-only
engineering cases plus deterministic reruns. Artifact completeness was 1.000 for all models; no
mock, tiny-random, API proxy, silent retry, or fallback was used. Nevertheless, the frozen
constrained-generation parser-valid threshold of 0.98 failed for every family. Prompt or parser
repair after observing these failures was forbidden and was not performed.

The measured latency projects to 11.02 hours for 28,800 synthetic calls on this
machine, excluding setup and transport samples. This is a profiling estimate, not scientific VLM
evidence. The engineering gate failed, so the resource-feasibility gate is false.

Evidence: `configs/model_smoke_registry.yaml` (config hash `b4c04afa8e7664c5f02ffded6309aa3f3c72703082b3f23666176e6af777ed5e`),
`artifacts/loop_c/decision.yaml`, and per-model predictions and summaries under
`artifacts/loop_c/`.
