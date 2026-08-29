# P Mini-Pilot Intervention Balance

Status: **PASS**. This is an inference-free tokenizer and evidence-form check.

Correct and target-specific corrupted evidence contain the same entities, relation count,
sentence/triple count, lexical template, punctuation pattern, entity repetitions, evidence
position, and candidate overlap. Exactly one target-path relation is replaced by its
grammatical directional antonym. Random nonsense, empty evidence, and malformed strings are
not controls.

| Model | Serialization | Scenes | Max | Mean | <=1 |
|---|---|---:|---:|---:|---:|
| smolvlm_256m_instruct | natural_language | 960 | 0 | 0.0000 | 1.0000 |
| smolvlm_256m_instruct | triples | 960 | 0 | 0.0000 | 1.0000 |
| internvl2_5_2b | natural_language | 960 | 0 | 0.0000 | 1.0000 |
| internvl2_5_2b | triples | 960 | 0 | 0.0000 | 1.0000 |
| qwen2_vl_2b_instruct | natural_language | 960 | 0 | 0.0000 | 1.0000 |
| qwen2_vl_2b_instruct | triples | 960 | 0 | 0.0000 | 1.0000 |

Pre-inference exclusions: 0. No scene may be excluded after scientific outcomes.
The eligible-scene manifest is frozen in `data/p_mini_pilot/data_manifest.yaml`.
All tokenizer results are marked `scientific_outcome_use_forbidden: true`.
