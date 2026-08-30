# Independent Data and Construct Audit

## Decision

`AUDIT_FAIL_CONSTRUCT_VALIDITY`

All 960 formal scenes pass the structural checks: the 192/768 splits and all seed namespaces are
disjoint; scene IDs and all 4,800 formal seed values are unique; every two-hop path is correct and
unique; exactly one target-path fact is directionally inverted; the corrupted implied answer is
correctly recorded and differs from the gold answer; option positions are globally balanced;
entity and answer namespaces are disjoint; and the natural-language and triple serializations
parse back to the same canonical facts. Correct/corrupted strings have equal whitespace-token and
character lengths in both serializations.

Those structural successes do not rescue the construct because the frozen identifiers expose a
perfect answer shortcut.

## Fatal leakage

Every question prints entity IDs containing the zero-padded scene index. The generator makes both
the gold relation and the correct option position deterministic functions of that same index:

| `index mod 4` | Gold answer | Correct option position |
|---:|---|---:|
| 0 | `ANS_REL_NE` | 0 |
| 1 | `ANS_REL_SE` | 1 |
| 2 | `ANS_REL_NW` | 2 |
| 3 | `ANS_REL_SW` | 3 |

The independent decoder therefore achieves 960/960 question-only answer accuracy and 960/960
option-position accuracy. This leakage is not disclosed in the frozen preregistration. It is not
ordinary class balance: the four answers are globally balanced at 240 each, while the sample ID
still deterministically reveals the answer.

The answer IDs themselves also expose semantic direction (`NE`, `NW`, `SE`, `SW`) in all 960
scenes. These are generator-declared semantic labels, but the preregistration never justifies why
they are necessary or analyzes their tokenizer/semantic shortcut effects. They therefore cannot
be automatically treated as harmless opaque IDs.

## Uptake-set leakage

The two relation probes are degenerate:

| Task | Scenes | Answer distribution | Correct option position |
|---|---:|---|---|
| `entity_to_direct_relation` | 48 | `ANS_DIR_S`: 48 | position 1: 48 |
| `relation_direction` | 48 | `ANS_DIR_S`: 48 | position 2: 48 |

The task name alone predicts the correct option position perfectly, and the two primary relation
tasks require no answer discrimination. Attribute and entity-ID tasks each use only three answer
values and also have a fixed task-specific option position.

## What the frozen intervention identifies

The image coordinates contain the complete correct answer in 960/960 scenes. The correct evidence
duplicates the two image relations and is independently sufficient for 960/960 answers. The
corrupted evidence changes one horizontal relation, conflicts directly with the image, and implies
a different complete answer in 960/960 scenes. Thus the treatment simultaneously changes evidence
correctness, image-text consistency, conflict presence, and the evidence-implied answer.

With the leakage removed, the narrow estimand could be described as a supplied-evidence behavioral
ITT under a redundant-consistent versus conflicting-evidence intervention. It cannot be called an
effect on an internal VLM compositional-reasoning mechanism. In the frozen dataset as shipped,
however, a question-only rule already solves the primary endpoint perfectly, so even the intended
behavioral construct is not cleanly measured.

Programmatic evidence is in
`artifacts/independent_audit/data_construct_metrics.yaml` and
`artifacts/independent_audit/data_leakage_checks.yaml`.
