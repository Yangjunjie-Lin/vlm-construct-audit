# Independent Direction P v2 construct review

Review all 80 rows independently. Do not consult another reviewer, the author,
the hidden key, generator code, or another reviewer's answers. The packet mixes
genuine scenes with preregistered decoys; their identities are blinded.

Open each `image_path` from the repository root and answer every column with
exactly `yes`, `no`, or `uncertain`. Judge the displayed image and supplied text,
not what you believe the generator intended. Mark `critical_error=yes` whenever
any flaw would invalidate cross-modal bridge composition or its paired contrast.

Definitions:

- `visual_first_hop_correct`: the claim about A relative to B matches the image.
- `bridge_entity_uniquely_identifiable`: the text identifies exactly one image B.
- `text_second_hop_correct`: one definite B-to-C cardinal relation is stated.
- `text_second_hop_not_visually_represented`: C/that second hop is absent spatially.
- `conditions_differ_in_exactly_one_target_relation`: only R2 changes.
- `no_direct_image_text_conflict`: neither condition contradicts a visible fact.
- `joint_answer_unique`: image first hop plus correct evidence yield one candidate.
- unimodal insufficiency columns: that modality alone cannot select one candidate.
- `nl_triples_fact_equivalent`: both serializations state exactly the same fact.

Reviewer eligibility: a real person independent of dataset authorship and this
agentic build. Two eligible reviewers are required. Agreement is computed across
all binary construct judgments, with overall agreement >=0.95 and Cohen's kappa
>=0.80. Genuine scenes require zero critical errors. At least 90% of decoys must
be marked `critical_error=yes`. Do not edit `review_packet.csv`.
