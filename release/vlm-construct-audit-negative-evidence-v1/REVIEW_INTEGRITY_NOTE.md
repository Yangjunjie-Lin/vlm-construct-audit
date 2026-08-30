# Review integrity note

The two returns agree on all 880 classification judgments and all 80 reviewer-note rows. Both
reviews started at the same recorded time, both missed the same four
`second_hop_visually_represented` decoys, and their explanations for the other 12 decoys are
verbatim identical. Reviewer 1's machine code is `R1-HUMAN-A7K3`, while the original signed
statement contains `R1-HUMAN-A7K2`; the importer checked only that the statement was non-empty.

Static audit classified all four missed decoys `DECOY_VALID`. All 64 genuine items passed, while
the unchanged 0.90 decoy gate failed at 0.75 for each reviewer. These artifacts do not establish
reviewer independence credibly, but they also do not prove fraud, collusion, fabrication,
dishonesty, or any other personnel conduct. No replacement signature, reviewer, third reviewer,
or rerun is authorized. See `reports/final_closeout/review_integrity_audit.*` in the tagged source.
