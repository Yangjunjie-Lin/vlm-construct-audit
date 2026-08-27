# Loop B: measurement robustness

Decision: **LOOP_B_AUTOMATED_GO_HUMAN_PENDING**.

The new holdout contained 600 probes crossed over
200 scenes and 200 finite templates. The
probe-level one-sided lower bound was 0.9950; the
scene-complete lower bound was 0.9851; and the
Bonferroni two-way scene × template lower bound was 0.9817. Degenerate all-success
cluster bootstraps were disclosed and were not used as the boundary-safe gate.

Independent scorer candidate-ranking agreement, semantic-answer agreement, parser valid recall,
parser invalid rejection, canonical NL/triples fact equality, and mutation-control detection were
all 1.0000. The scorer maximum token log-probability difference was
6.245e-16. There were 240
adversarial parser cases and 1200 serialization comparisons.

The automated portion passed. The 54-row blinded packet contains 42 genuine pairs and 12 mismatch
decoys, but zero human reviewers have completed it. Its status remains
`HUMAN_EQUIVALENCE_REVIEW_PENDING`; an agent or model was not used as an independent reviewer.

Evidence: `artifacts/loop_b/measurement_metrics.yaml`, `artifacts/loop_b/decision.yaml`, and
`data/annotations/serialization_review_packet.csv` (config hash `e7ccfd385b83b97b26567462996f9a0e8dcbbfa2bb0a44087b8ac6cb0e96b3c4`).
