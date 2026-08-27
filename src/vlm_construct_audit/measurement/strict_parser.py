"""Declared-schema parser with duplicate-key rejection and no implicit repair."""

from __future__ import annotations

import json
from typing import Any


class DuplicateKeyError(ValueError):
    """Raised when JSON repeats a key."""


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateKeyError(key)
        result[key] = value
    return result


def parse_declared_contract(
    raw: str,
    *,
    schema: str,
    allowed_answers: list[str],
    option_id_mapping: dict[str, str],
    registered_aliases: dict[str, str] | None = None,
) -> dict[str, Any]:
    aliases = registered_aliases or {}
    try:
        value = json.loads(raw, object_pairs_hook=_unique_object)
    except DuplicateKeyError:
        return {"parsed_response": None, "parser_status": "failed_duplicate_key"}
    except json.JSONDecodeError:
        return {"parsed_response": None, "parser_status": "failed_invalid_json"}
    if not isinstance(value, dict):
        return {"parsed_response": None, "parser_status": "failed_schema"}
    if schema == "semantic_answer":
        if set(value) != {"answer"} or not isinstance(value["answer"], str):
            return {"parsed_response": None, "parser_status": "failed_schema"}
        answer = aliases.get(value["answer"], value["answer"])
        if answer not in allowed_answers:
            return {"parsed_response": None, "parser_status": "failed_disallowed_answer"}
        return {"parsed_response": answer, "parser_status": "ok"}
    if schema == "option_id":
        if set(value) != {"option_id"} or not isinstance(value["option_id"], str):
            return {"parsed_response": None, "parser_status": "failed_schema"}
        if value["option_id"] not in option_id_mapping:
            return {"parsed_response": None, "parser_status": "failed_disallowed_option_id"}
        return {"parsed_response": option_id_mapping[value["option_id"]], "parser_status": "ok"}
    raise ValueError(f"Unknown declared parser schema: {schema}")

