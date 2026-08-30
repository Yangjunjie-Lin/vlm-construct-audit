# Independent Uptake-Gate Audit

## Exact thresholds

For the one-sided 95% Clopper-Pearson lower bound to be at least 0.80, the aggregate 192-scene gate
requires 164 successes (observed accuracy 0.8542; lower bound 0.8056). Applied separately to a
48-scene task, the same rule requires 44 successes (observed accuracy 0.9167; lower bound 0.8194).

## Worst-case masking

If three tasks score 48/48, the aggregate gate passes with only 20/48 successes on
`relation_direction`: observed accuracy 0.4167 and one-sided lower bound 0.2959. Thus object,
attribute, or ID-mapping performance can mask failure of a prerequisite for the registered
two-hop directed-relation construct.

The four probes are not defensibly interchangeable reflective indicators. They are distinct
formative prerequisites. Before any inference, `entity_to_direct_relation` and
`relation_direction` need their own noncompensatory minimum gates. The frozen aggregate-only rule
does not provide that protection.

## Negative control

At the frozen upper-bound cutoff of 0.60, as many as 103/192 negative-control responses can be
correct and still pass (accuracy 0.5365; upper bound 0.5975). For a single 48-scene task, 22/48 can
pass (accuracy 0.4583; upper bound 0.5863). This is permissive for four-choice chance accuracy
0.25. More importantly, the two relation tasks have the same answer in all 96 rows, so an
answer-prior strategy can score 96/192 overall and remain compatible with the aggregate negative
control.

A valid negative-control analysis must jointly check absolute accuracy, the paired
correct-versus-irrelevant contrast, answer priors, and option-position dependence. The frozen rule
checks only aggregate absolute accuracy.

## Reporting boundary

The preregistration correctly requires complete ITT reporting for failed cells while forbidding a
validated supplied-evidence interpretation. That reporting/eligibility separation is adequate;
it does not fix the compensatory gate or the frozen-data leakage.

Decision: `AUDIT_CONDITIONAL_PREINFERENCE_AMENDMENT` on this audit dimension. The overall audit is
more severe because the data construct independently fails.
