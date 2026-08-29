# P Mini-Pilot Measurement Contract

The primary endpoint is length-normalized candidate conditional likelihood (CLL). For every
candidate the future execution must retain candidate token IDs, raw log likelihood, token count,
length-normalized score, independently recomputed score, ranking, margin, and maximum scorer
difference. Independent ranking agreement must equal `1.00`.

Candidate answers use an answer-ID namespace distinct from entity IDs. Candidate count and option
position policy are frozen in the data configuration. Ties are resolved only by the preregistered
deterministic candidate-ID rule and are reported; semantic repair or a judge model is forbidden.

Natural-language and triple evidence are two serializations of the same canonical entity,
attribute, directed-relation, required-fact, and answer record. Programmatic canonical equality
must be `1.00`. The earlier two-human semantic-equivalence result licenses the generation
principle; it is not a new model-generated review.

Tokenizer balance is an engineering eligibility check performed before scientific inference for
all three frozen tokenizer revisions. Correct and corrupted evidence preferentially differ by at
most one token in every model-by-serialization cell. A failure is repaired only by a pre-inference
operator/relation replacement and is recorded; post-outcome sample deletion is forbidden.

All engineering scorer and tokenizer artifacts carry
`scientific_outcome_use_forbidden: true` and cannot be used to select a checkpoint by task
correctness.
