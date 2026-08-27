"""Independent scorer B; intentionally does not import production scorer A."""

from __future__ import annotations

import math
from typing import Any

import numpy as np


def _tokenize_b(candidate: str, vocabulary: dict[str, int]) -> list[int]:
    tokens = candidate.split(" ")
    tokens = [token for token in tokens if token != ""]
    if len(tokens) == 0:
        raise ValueError("Candidate contains no scored tokens")
    ids = []
    for token in tokens:
        if token not in vocabulary:
            raise ValueError(f"Unknown token {token!r}")
        ids.append(int(vocabulary[token]))
    return ids


def _independent_log_probability(logits: list[float], target: int) -> float:
    values = np.asarray(logits, dtype=np.float64)
    normalizer = float(np.logaddexp.reduce(values))
    return float(values[target] - normalizer)


def score_logit_fixture_b(fixture: dict[str, Any]) -> dict[str, Any]:
    records: dict[str, Any] = {}
    for candidate in fixture["candidates"]:
        token_ids = _tokenize_b(candidate["text"], fixture["vocabulary"])
        if token_ids != [int(value) for value in candidate["candidate_token_ids"]]:
            raise ValueError("Independent tokenizer disagrees with frozen IDs")
        rows = candidate["step_logits"]
        if len(rows) != len(token_ids):
            raise ValueError("Shifted logit trace length mismatch")
        log_probabilities = [
            _independent_log_probability(row, token_ids[index]) for index, row in enumerate(rows)
        ]
        total = math.fsum(log_probabilities)
        records[candidate["text"]] = {
            "candidate_token_ids": token_ids,
            "token_logprobs": log_probabilities,
            "raw_log_likelihood": total,
            "length_normalized_score": total / len(token_ids),
        }
    ordered = sorted(
        records,
        key=lambda text: (-records[text]["length_normalized_score"], fixture["candidate_order"].index(text)),
    )
    return {
        "scores": records,
        "ranking": ordered,
        "predicted_semantic_answer": ordered[0],
        "option_id_mapping": dict(fixture["option_id_mapping"]),
    }

