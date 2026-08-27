# Post-STOP Direction M

Decision: **DIRECTION_M_NO_GO**. The three-family engineering measurement gate failed after the
only permitted development revision, so the sealed holdout was not authorized or executed.

## Contract identity

- M-C1 used length-normalized candidate conditional likelihood with an independent float64 scorer.
- M-C2 used a finite-language token-prefix automaton. At every generation step it admitted only
  prefixes of `{"answer":"<allowed-value>"}`. This was true token-level constrained decoding.
- M-C3 was ordinary greedy generation with a prompt-only exact-JSON instruction and strict parsing.
- M-C4 was ordinary greedy generation followed by a preregistered deterministic canonicalizer.

The historical Loop C condition is referenced only as `historical_prompt_only_exact_json`. It is
not true constrained decoding, and no historical artifact was changed.

## Development engineering result

| Family | status | prompt-only JSON syntax | true constrained syntax | scorer agreement | rerun agreement |
|---|---|---:|---:|---:|---:|
| SmolVLM-Idefics3 | complete | 0.00 | 1.00 | 1.00 | 1.00 |
| InternVL2.5-InternLM2 | failed | not measured | not complete | not complete | not complete |
| Qwen2-VL | complete | 0.25 | 1.00 | 1.00 | 1.00 |

The canonicalizer valid-form recall and invalid/ambiguous rejection were both 1.00. Completed-model
artifact completeness was 1.00. Nevertheless, the mandatory gate was across all three families.
InternVL's pinned remote generation wrapper rejected `image_flags` after the one allowed
development compatibility revision had already been consumed. A second repair was forbidden.

## Development-only semantic observations

For SmolVLM, CLL versus true constrained semantic agreement was 0.25, κ=0.211 (bootstrap 95% CI
0.121–0.302), and M-C2 minus M-C1 correctness was -0.233 (CI -0.383 to -0.067). Answer changes
spanned six tasks and both serializations and were not caused by parser rejection. For Qwen2-VL,
agreement was 0.933, κ=0.928 (CI 0.853–0.982), and correctness difference was +0.033 (CI -0.033
to 0.100). These opposite patterns do not meet a two-of-three same-direction material-effect path;
the strict equivalence path also did not reach two families. SmolVLM alone cannot establish a
cross-family scientific contract effect.

Prompt-only syntactic compliance was not interpreted as capability. M-C2 syntax was perfect in the
two completed families, yet its semantic relationship with CLL differed greatly by family. This
is development evidence only because the engineering gate blocked the sealed holdout.

## Failures and revisions

The first launcher failed before import because the isolated environment lacked an editable
installation; it produced no model/data outcome and is retained in
`artifacts/post_stop/direction_m_development_console.log`. The first real development attempt
failed at InternVL because `use_cache` was passed twice. That attempt, including completed SmolVLM
and Qwen2-VL rows, is preserved under `development_initial_attempt/`. The only permitted revision
removed only that duplicated compatibility kwarg and caused a full three-family rerun. The rerun
then failed at the next pinned-wrapper incompatibility (`image_flags`). No prompt, scene, candidate,
parser, automaton, threshold, revision, or completed-model outcome was used to make another repair.

## Claim boundary

This screen supports only development-stage real-checkpoint engineering and measurement-contract
observations. It supplies no sealed scientific VLM result, no evidence-uptake result, and no
internal-mechanism evidence. Direction M cannot continue as either a scientific direction or an
engineering-only holdout under this protocol.
