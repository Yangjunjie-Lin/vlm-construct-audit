"""Deterministic conditional-likelihood and constrained-generation contracts."""

from __future__ import annotations

import json
import re
from typing import Any

TOKEN_RE = re.compile(r"[A-Za-z0-9_]+|[^\w\s]")


def tokenize_candidate(candidate: str) -> list[str]:
    """Tokenize the exact semantic candidate; option IDs are never scored."""
    tokens = TOKEN_RE.findall(candidate)
    if not tokens:
        raise ValueError("Candidate answer must contain at least one token")
    return tokens


def score_conditional_likelihood(selected_answer: str, candidates: list[str]) -> dict[str, Any]:
    if selected_answer not in candidates:
        raise ValueError("Selected semantic answer is not in the allowed candidate set")
    candidate_scores: dict[str, dict[str, Any]] = {}
    for candidate in candidates:
        tokens = tokenize_candidate(candidate)
        per_token = -0.1 if candidate == selected_answer else -2.0
        logprobs = [per_token for _ in tokens]
        raw = sum(logprobs)
        candidate_scores[candidate] = {
            "semantic_answer": candidate,
            "tokens": tokens,
            "token_logprobs": logprobs,
            "raw_log_likelihood": raw,
            "length_normalized_score": raw / len(tokens),
        }
    ranking = sorted(
        candidate_scores,
        key=lambda answer: (-candidate_scores[answer]["length_normalized_score"], candidates.index(answer)),
    )
    margin = (
        candidate_scores[ranking[0]]["length_normalized_score"]
        - candidate_scores[ranking[1]]["length_normalized_score"]
    )
    return {
        "parsed_response": ranking[0],
        "candidate_scores": candidate_scores,
        "candidate_margin": margin,
        "tokenization_policy": "exact_semantic_answer_regex_tokens_no_option_ids",
        "tie_rule": "candidate_list_order",
        "parser_status": "not_applicable_likelihood",
    }


def recompute_candidate_scores(candidate_scores: dict[str, dict[str, Any]]) -> dict[str, float]:
    """Independent recomputation from the frozen per-token record."""
    return {
        answer: sum(record["token_logprobs"]) / len(record["tokens"])
        for answer, record in candidate_scores.items()
    }


def generate_constrained_raw(selected_answer: str, schema_valid: bool = True) -> str:
    if schema_valid:
        return json.dumps({"answer": selected_answer}, separators=(",", ":"), sort_keys=True)
    return json.dumps({"option_id": "A"}, separators=(",", ":"), sort_keys=True)


def parse_constrained(raw: str, allowed_answers: list[str]) -> dict[str, Any]:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return {"parsed_response": None, "parser_status": "failed_invalid_json"}
    if not isinstance(value, dict) or set(value) != {"answer"}:
        return {"parsed_response": None, "parser_status": "failed_schema"}
    answer = value["answer"]
    if not isinstance(answer, str) or answer not in allowed_answers:
        return {"parsed_response": None, "parser_status": "failed_disallowed_answer"}
    return {"parsed_response": answer, "parser_status": "ok"}


def option_map(candidates: list[str]) -> dict[str, str]:
    return {chr(ord("A") + i): candidate for i, candidate in enumerate(candidates)}

