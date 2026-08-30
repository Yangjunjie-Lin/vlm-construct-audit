# Final external-review integrity audit

Classification: `REVIEW_INTEGRITY_INCONCLUSIVE`.

Scientific action: `TERMINATE_DIRECTION_P`. This audit has no rescue authority and does not
alter `CONSTRUCT_V2_HUMAN_NO_GO`, the review answers, the 0.90 decoy threshold, or any frozen
review artifact.

## Attestations

Reviewer 1's machine field is `R1-HUMAN-A7K3`, while the
signed statement says `R1-HUMAN-A7K2`.
`attestation_internal_identity_consistency: FAIL`. The frozen importer passed this record because
it required only a non-empty `signed_statement`; it did not compare the code within the statement
with the machine field. This is an attestation-validation implementation gap.

A pre-deblinding filing/provenance clarification was inspected under hash
`87af9067427a3be835e8ffb7b4f156f4bb497e2a6de85d6e8293e22e50bb4e45`. It cannot repair or supersede the
internal inconsistency in the original signed statement, and no new signature is accepted.
Reviewer 2's corresponding internal check is `PASS`.

## Reviewer-independence evidence

- All 880 classification judgments are identical;
  overall agreement is 1.0 and three-category Cohen kappa is
  1.0. Every field has agreement 1.0.
- Notes match verbatim on 80/80 rows. Both reviewers
  wrote `none` on all 64 genuine rows. The 12 detected-decoy explanations match verbatim.
- Both reviews started at
  `2026-08-30T10:00:00+01:00`. Completion times were
  `2026-08-30T12:30:00+01:00` and
  `2026-08-30T12:15:00+01:00`.
- Both reviewers missed exactly CVR-073, CVR-074, CVR-075, CVR-076; all four are
  `second_hop_visually_represented` decoys.

These artifact patterns do not prove fraud, collusion, fabrication, dishonesty, or any other
personnel conduct. They do mean independence is not credibly established from the preserved
artifacts. The integrity classification is therefore inconclusive, not an accusation.

## Decoy construction

Static inspection of generation code, packet text, instructions, and all four images found each
C descriptor visibly rendered at the text-specified second hop, 64 pixels from B and without
overlap. The instructions explicitly require checking whether C/the second hop is absent.
Classification: `DECOY_VALID`. No ambiguity, replacement review, or scientific continuation is
authorized.

## Preserved outcome

All 64 genuine items passed the required construct fields and had no critical error. The frozen
human gate nevertheless failed because each reviewer detected 12/16 decoys (0.75), below the
unchanged 0.90 threshold. Regardless of integrity classification, Direction P terminates.
