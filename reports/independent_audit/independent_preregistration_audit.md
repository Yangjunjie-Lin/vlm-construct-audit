# 1. Audit Verdict

`AUDIT_FAIL_CONSTRUCT_VALIDITY`

The frozen preregistration must not proceed to scientific-runner implementation or formal VLM
inference. Every one of the 960 formal questions exposes a scene index in its entity IDs, and that
index deterministically reveals both the gold answer and its option position. The frozen
preregistration does not disclose this shortcut. The audit charter explicitly makes unrecorded
answer leakage a construct-validity failure, so the less severe conditional findings cannot rescue
the package.

# 2. Independence Declaration

The auditor is `independent_ai_audit_instance_direction_p_2026_08_30`, an independent AI audit
instance with no prior project role. It authored neither the preregistration files nor the Direction
P method, did not access scientific VLM results, and is not a human expert reviewer. This report is
an independent computational and methodological audit, not formal human peer review.

# 3. Frozen State Verification

- Audited tag: annotated tag `p-mini-pilot-preregistered`
- Tag object: `a58898f7b1cbd50f61296cd12476ef599c1ba546`
- Peeled target: `9de60b87ec54bc852a7bb2e9cff87d9c23638042`
- Manifest: 45 files; independently recomputed aggregate SHA-256
  `20906cff6cbddcc18a491c562dea83bcc201bd76f5905d27c2e58bc8db32f9d2`
- Method-lock SHA-256:
  `c252336a8e14e37f0fce14329a845c042a5ff0037aa5692544f6aab14f62f978`
- Model-registry SHA-256:
  `738bef0cce88957e81b670665289d830c7d451d6774f75d9164327d88585c2d6`
- Data-manifest SHA-256:
  `1eef8c25123326549c345b91dcec861941b45001edd19414884339bce0c1d534`
- Historical state: AuditV2 `LOOP_A_NO_GO`; P/M/U holdout counts `1/0/0`; human review
  `HUMAN_REVIEW_GO`
- Scientific output counts: formal predictions 0, reasoning-test model outputs 0,
  uptake-validation model outputs 0, scientific metrics 0
- ReCoAlign: unchanged and clean at `e200921af44e9307c60f470c247f808a75e7d625`

The repository verifier and the independent Python-standard-library verifier agree. No protected
manifest file differs from the frozen tag.

# 4. Most Serious Findings

1. **Fatal question-only leakage.** The printed entity IDs contain the scene index. `index mod 4`
   identifies the gold answer in 960/960 scenes and the correct option position in 960/960 scenes.
   The frozen preregistration records none of the question-only, entity-ID, template-index, or
   option-position leakage.
2. **Degenerate uptake probes.** Both relation tasks use `ANS_DIR_S` in every one of their 48 rows,
   and every uptake task has one fixed task-specific correct option position.
3. **Confounded treatment interpretation.** Correct evidence repeats the complete image geometry;
   corrupted evidence conflicts with the image and implies a different complete answer. The
   treatment jointly changes correctness, image-text consistency, conflict presence, and implied
   answer.
4. **Undercharacterized final-gate power.** At `N=768`, effect 0.15, and discordance 0.25, marginal
   cell power is about 0.83, but representative Stable-Path power is about 0.61 after Holm and the
   two-format/two-family gate. It falls further under higher discordance or only two active
   families.
5. **Nonmechanical Path B and incomplete runner.** Several success predicates have no deterministic
   code definition. The frozen checkout also lacks the Mini-Pilot renderer, prompt builder, runner,
   lexical tie-break implementation, and independent forward-path cross-check.

Novelty is `NOVELTY_PASS_WITH_CAUTION`: no reviewed work fully duplicates the proposed joint design,
but the frozen construct failure prevents this dataset from realizing the remaining contribution.

# 5. Construct Validity

All structural scene checks pass: split and seed disjointness, unique IDs, unique correct answers,
two-hop paths, recorded corruptions, global option balance, namespace separation, canonical
natural-language/triple equivalence, and correct/corrupted length balance.

The measurement nevertheless fails. The image-coordinate oracle solves 960/960 scenes, and the
correct-evidence-only oracle also solves 960/960. Correct evidence duplicates the two relations in
the image. Corrupted evidence directionally inverts one relation, directly conflicts with the
image, and implies a different complete answer in 960/960 scenes. A text-only symbolic reasoner can
solve the evidence path; an image-coordinate oracle can solve the image path.

Absent the fatal identifiers, the narrow comparison would be a **supplied-evidence behavioral ITT
under redundant-consistent versus conflicting evidence**. It is not an effect on an internal VLM
compositional-reasoning mechanism. As frozen, even that bounded behavioral construct is not cleanly
measured because a question-only rule is perfect. Candidate IDs such as `ANS_REL_NE` also directly
encode direction semantics and were not justified as necessary nonleaking measurement labels.

# 6. Uptake Gate

The one-sided 95% Clopper-Pearson aggregate gate needs 164/192 successes for a lower bound of at
least 0.80. The equivalent task-specific rule needs 44/48. If three tasks score 48/48, the aggregate
gate still passes when `relation_direction` scores only 20/48 (accuracy 0.4167; lower bound 0.2959).
Thus the aggregate can mask failure of a prerequisite relation skill.

The four probes are distinct formative prerequisites, not interchangeable reflective indicators.
The frozen aggregate-only gate does not impose noncompensatory minima on
`entity_to_direct_relation` and `relation_direction`.

The negative-control cutoff is also permissive: 103/192 correct responses can still pass its upper
bound rule, despite four-choice chance being 0.25. The two relation tasks alone permit 96/192 from a
constant answer prior. A valid control would need absolute accuracy, correct-versus-irrelevant
contrast, answer-prior, and option-position checks. The frozen separation between failed-cell ITT
reporting and claim eligibility is adequate but does not repair these defects.

# 7. Power Audit

The independent paired-binary implementation confirms `theta=p10-p01`, `d=p10+p01`, and
`Var(D)=d-theta^2`, with `delta0=0.10`, `delta1=0.15`, one-sided `alpha=0.025`, and `N=768`.
Analytic, 100,000-repetition Monte Carlo, and exact finite-sample calculations agree. Boundary
Type-I behavior is approximately 0.025.

At effect 0.15, marginal cell power (analytic / Monte Carlo / exact) is:

| Discordance | Analytic | Monte Carlo | Exact |
|---:|---:|---:|---:|
| 0.15 | 0.9726 | 0.9832 | 0.9836 |
| 0.25 | 0.8277 | 0.8321 | 0.8312 |
| 0.35 | 0.6777 | 0.6801 | 0.6785 |
| 0.50 | 0.5181 | 0.5164 | 0.5183 |
| 1.00 | 0.2883 | 0.2831 | 0.2825 |

At representative within-model correlation 0.50 and between-model correlation 0.25, all six
effects equal to 0.15 with discordance 0.25 yield mean Holm-supported cell power 0.716, family pass
probabilities near 0.611, and Stable-Path power 0.609. With only two active 0.15 families, Stable
Path falls to 0.343. Across the requested dependence grid those two scenarios range 0.548-0.707
and 0.228-0.474, respectively. With all six effects 0.15, Stable-Path power is about 0.339 at
discordance 0.35 and 0.156 at 0.50.

The 0.15-0.25 discordance range is not independently supported for real VLM outcomes. A future
program could preregister a blinded, condition-swap-invariant estimate of `p10+p01`, but no such
procedure may be added to this frozen package. Cell-level power must not be described as overall
Mini-Pilot power.

# 8. Multiplicity and Path B

Holm mechanically controls the six confirmatory minimum-effect claims as frozen. Stable Path is
not adequately powered across the registered plausible region and does not freeze its
leave-one-family-out pooling weights.

Under six independent global-null cells, the exact probability of at least two naïve-positive
cells is 0.008767. Across the requested correlations it is approximately 0.00875-0.04464. At high
within-model correlation, most of that event consists of two serializations from one model and is
not independent replication.

Path B does not mechanically define “independent cells,” a different-family requirement,
template/model/serialization attribution, abstention-driven advantage, the `INCONCLUSIVE`
denominator/tie rule, or pooling weights. These omissions permit post-result discretion. Path B
therefore lacks a uniquely executable success rule and adequate scope-change error-control
interpretation.

# 9. P3 Method Lock

`PASS_WITH_LIMITATIONS`

Source hashes and commits match; `delta0`, `delta1`, critical values, gray-zone rules, fail-first
measurement/intervention precedence, abstention policy, namespace separation, and the single
sealed holdout are intact. The historical power-table hash difference is a CRLF-versus-LF byte
difference with unchanged parsed values, not a numerical method change. The sealed holdout was not
rerun or reselected.

P3 is a normal-approximation, known-DGP three-way rule, not a distribution-free guarantee for real
VLM outcomes. Valid rows ordinarily emit positive, below-SESOI, or gray rather than
`INCONCLUSIVE`, creating a limitation in later GO/NO-GO prose. These are retained limitations but
do not constitute the substantive P3 failure required for `AUDIT_FAIL_P3_METHOD_LOCK`.

# 10. Model and Scorer Feasibility

Official Hugging Face records resolve the exact frozen revisions and weight hashes for
SmolVLM-256M-Instruct, InternVL2_5-2B, and Qwen2-VL-2B-Instruct. Licenses, processor/tokenizer
revisions, quantization/dtype, Transformers version, device policy, and remote-code settings are
recorded. Historical generic CLL checks passed actual visual forwards, multi-token span scoring,
length normalization, prefix assertions, ranking recomputation, and deterministic reruns.

Mini-Pilot execution readiness does not pass. The checkout has no renderer, prompt/candidate
builder, artifact writer, or scientific runner. Historical ties follow input order instead of the
frozen lexical `candidate_id` rule. The “independent scorer” reuses the same forward logits and
therefore cannot detect a shared prompt/image/forward-path error. The 12 registered smoke scenes
were not run because implementing their missing image and runner path inside this audit would
violate the required auditor/implementer separation. Neither formal split was sent to a model.

# 11. Required Amendment

Not applicable. This is a construct-validity failure, not a conditional-amendment verdict. A
transparent v2 amendment cannot cure the already frozen data while preserving the audited
experiment. Direction P must stop or restart from the required scientific gate with newly designed
construct-valid data and a new preregistration.

# 12. Authorization Status

`NO_AUTHORIZATION_CREATED`

No `research/authorization/p_mini_pilot_independent_audit.yaml` exists, and no scientific inference
is authorized.

# 13. Repository State

- Branch: `codex/independent-p-mini-pilot-preregistration-audit`
- Audited source: `9de60b87ec54bc852a7bb2e9cff87d9c23638042`
- Audit publication tag: `p-mini-pilot-preregistration-audit-no-pass`
- Required publication state: clean working tree after the final audit commit
- Original tag: annotated `p-mini-pilot-preregistered`, unchanged at
  `9de60b87ec54bc852a7bb2e9cff87d9c23638042`

Final command-level results and publication checks are recorded in
`artifacts/independent_audit/verification_report.yaml`.

# 14. Exact Next Action

`STOP_DIRECTION_P_OR_RESTART_FROM_REQUIRED_SCIENTIFIC_GATE`
