"""Production analytical scorer for frozen raw-logit measurement fixtures."""

from __future__ import annotations

import math
from typing import Any

import numpy as np


def tokenize_candidate_a(text: str, vocabulary: dict[str, int]) -> list[int]:
    pieces = [piece for piece in text.strip().split(" ") if piece]
    if not pieces:
        raise ValueError("Empty candidate")
    try:
        return [int(vocabulary[piece]) for piece in pieces]
    except KeyError as exc:
        raise ValueError(f"Out-of-vocabulary candidate piece: {exc.args[0]}") from exc


def _log_softmax(row: np.ndarray) -> np.ndarray:
    maximum = float(np.max(row))
    shifted = row.astype(np.float64) - maximum
    return shifted - math.log(float(np.exp(shifted).sum()))


def score_logit_fixture_a(fixture: dict[str, Any]) -> dict[str, Any]:
    candidates = fixture["candidates"]
    scored = {}
    for candidate in candidates:
        token_ids = tokenize_candidate_a(candidate["text"], fixture["vocabulary"])
        stored_ids = [int(value) for value in candidate["candidate_token_ids"]]
        if token_ids != stored_ids:
            raise ValueError("Candidate tokenization differs from frozen fixture")
        logits = np.asarray(candidate["step_logits"], dtype=np.float64)
        if logits.shape[0] != len(token_ids):
            raise ValueError("One next-token logit row is required per candidate token")
        token_logprobs = [float(_log_softmax(logits[index])[token_id]) for index, token_id in enumerate(token_ids)]
        raw = sum(token_logprobs)
        scored[candidate["text"]] = {
            "candidate_token_ids": token_ids,
            "token_logprobs": token_logprobs,
            "raw_log_likelihood": raw,
            "length_normalized_score": raw / len(token_ids),
        }
    ranking = sorted(
        scored,
        key=lambda text: (-scored[text]["length_normalized_score"], fixture["candidate_order"].index(text)),
    )
    return {
        "scores": scored,
        "ranking": ranking,
        "predicted_semantic_answer": ranking[0],
        "option_id_mapping": fixture["option_id_mapping"],
    }

