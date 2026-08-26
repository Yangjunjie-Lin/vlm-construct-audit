# Claim Taxonomy

The audit emits only scope-bounded claim classes.

| Level | Meaning | Eligible evidence |
| --- | --- | --- |
| Behavioral effect | Supplied evidence changes an observed score under frozen conditions | ITT with valid measurement and intervention gates |
| Measurement effect | Conclusions differ across legal scoring operators or contracts | Frozen-response rescoring and contract comparison |
| Intervention uptake | An independent task detects whether supplied propositions affect behavior | Uptake-validation split only |
| Format dependence | Proposition-equivalent serializations change uptake or downstream behavior | Equivalence-validated NL/triples contrasts |
| Internal mechanism | A latent computation or representation implements a claimed process | Not identified by this input-output design |

`VALID_BEHAVIORAL_EFFECT` never means a valid internal mechanism. Elicitation changes that
alter model generation, including constrained generation, are treatments (`E`), whereas a
scoring rule over a fixed response is a measurement operator (`M`).

Forbidden statements include graph superiority, semantic sufficiency, internal scene graphs,
universal VLM mechanisms, and any generalization from a calibration system to a real VLM.
