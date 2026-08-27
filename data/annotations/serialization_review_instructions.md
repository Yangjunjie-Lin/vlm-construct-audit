# Blinded Serialization Review Instructions

Review each pair independently without consulting another reviewer or model. The packet hides
format, condition, scene ID, gold answer, and source facts. Judge whether the two evidence blocks
express the same fact multiset for the displayed question.

Complete every boolean field and provide a stable reviewer ID. `critical_error` means a changed,
missing, reversed, or duplicated fact that can change the evidential content. Do not repair text,
infer hidden source facts, or use an LLM. Some pairs are preregistered mismatch controls.

Two human reviewers must return independent append-only files. Agent-generated labels do not count.

