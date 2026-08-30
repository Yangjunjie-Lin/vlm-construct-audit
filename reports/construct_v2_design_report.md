# Direction P v2 construct-valid design report

Decision: `PENDING_EXTERNAL_CONSTRUCT_REVIEW`.

The image supplies A and B plus the visual first hop A R1 B. Text supplies only
the bridge fact B R2 C. C is not spatially rendered. The question asks for A relative
to C, so image-only and evidence-only inputs each retain one bit of answer uncertainty.
Correct and corrupted conditions share image, question, entities, semantic candidates,
and option order; only R2 changes. Neither condition contradicts a visible fact.

The power policy selected N=1280 before data generation.
Natural language is the sole confirmatory serialization; triples is robustness only.
The estimand is a paired behavioral ITT, not an internal mechanism effect.

All automated construct, leakage, balance, serialization, token, power, P3-hash, and
no-inference gates pass. Two real independent human reviews remain outstanding.
