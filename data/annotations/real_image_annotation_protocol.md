# Real-Image Transport Annotation Protocol

Status: protocol complete; images and licenses not acquired.

Each candidate sample requires two independent annotators. They record entity identities,
directed relation correctness, entity–attribute bindings, answer uniqueness, distractor validity,
and uncertainty without seeing model predictions. Disagreements receive blinded adjudication by
a third reviewer. Inclusion requires agreement or documented adjudication on every field.

The provenance ledger must record source URL, dataset/version, image identifier, copyright owner
when available, license text and version, redistribution permission, derivative/annotation terms,
attribution, access date, and reviewer. “Research use” without redistribution permission is not
sufficient for an artifact release. No image enters Git until the license reviewer signs the row.

Synthetic and real-image effects are analysed separately. Failure to establish a legal 120-sample
set yields `BLOCKED_BY_DATA_LICENSE`; more synthetic scenes cannot replace it.

